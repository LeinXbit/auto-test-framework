# -*- coding: utf-8 -*-
"""
HTTP 请求基类：所有 API 接口的通信出口
    - 统一封装 GET/POST/PUT/DELETE
    - 自动记录请求/响应日志 + 自动归档到 Allure
    - 统一异常处理
    - 支持 GVA 的 x-token 鉴权注入
    - 提供 GVA 业务码断言(code=0 成功 / 非 0 失败)
    - [TOCTOU 修复] 当请求被 GVA 以 code=7/HTTP 401 判为 token 失效时,
        若外部注入了 on_token_expired 回调, 会调用它刷新 token 并重放原请求一次
"""
import json

import allure
import requests

from utils.exceptions import APIException
from utils.logger import get_logger

logger = get_logger(__name__)

# GVA 典型 token 失效特征: HTTP 401 且 code=7, 常见 msg 关键词
_TOKEN_INVALID_MESSAGES = (
    "异地登陆",
    "令牌失效",
    "未登录",
    "非法访问",
    "请登录",
)


def _is_token_invalid(response):
    """识别 GVA 返回「异地登陆或令牌失效 / 未登录」类响应(模块级函数,避开 @staticmethod 绑定问题)"""
    if response.status_code == 401:
        return True
    try:
        data = response.json()
    except Exception:
        return False
    if data.get("code") == 7:
        msg = data.get("msg", "") or ""
        return any(kw in msg for kw in _TOKEN_INVALID_MESSAGES)
    return False


class BaseApi(object):
    """
    业务 API 基类：所有 API 模块继承此类
    """

    # 类级默认值, 保证 hasattr/getattr 在类对象上也能找到; 实例 __init__ 会覆盖
    on_token_expired = None

    def __init__(self, base_url, timeout=10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        # 可选回调: 当请求遭遇 GVA code=7/HTTP 401(异地登陆/令牌失效)时触发,
        #   返回一个新的有效 token 字符串, 随后 request 会换 token 重放原请求一次。
        # 签名: () -> str
        # 典型场景: session 级 admin_token 被单点登出作废后自动重登。
        self.on_token_expired = None

    # 鉴权

    def set_token(self, token):
        """GVA 使用 x-token 头部鉴权"""
        if not token:
            raise APIException("Token 不能为空")
        self.session.headers["x-token"] = token
        logger.info("x-token 已注入请求头")

    # ---------- 内部 ----------

    def _try_auto_refresh_token(self, method, url, kwargs):
        """
        如果外部注入了 on_token_expired, 调用它拿新 token, 换头后重放原请求一次。
        :returns: 新响应, 或者 None 表示「未配置回调/不支持自动刷新」
        """
        cb = self.on_token_expired
        if cb is None:
            return None
        try:
            logger.warning("[Token] 请求命中 401/code=7 失效, 调用 on_token_expired 刷新并重放")
            new_token = cb()
            if not new_token:
                logger.warning("[Token] on_token_expired 返回空, 放弃自动重放")
                return None
            self.set_token(new_token)
            # 重放原请求(同 method/url/kwargs)
            retry = self.session.request(
                method=method,
                url="{}{}".format(self.base_url, url),
                timeout=self.timeout,
                **kwargs
            )
            preview = retry.text[:500] if retry.text else ""
            logger.info("Response(retry): {} | {}".format(retry.status_code, preview))
            allure.attach(
                retry.text,
                name="响应内容(重放) [{}]".format(retry.status_code),
                attachment_type=(
                    allure.attachment_type.JSON
                    if "json" in retry.headers.get("content-type", "")
                    else allure.attachment_type.TEXT
                ),
            )
            return retry
        except Exception as e:
            logger.warning("[Token] 自动刷新重放失败(回退返回原响应): {}".format(e))
            return None

    # 请求

    def request(self, method, url, **kwargs):
        full_url = "{}{}".format(self.base_url, url)

        # 记录请求信息
        logger.info("Request: {} {}".format(method, full_url))
        if "json" in kwargs:
            logger.info("Body: {}".format(json.dumps(kwargs["json"], ensure_ascii=False)))
        if "params" in kwargs:
            logger.info("Params: {}".format(kwargs["params"]))

        # 归档到 Allure
        allure.attach(
            json.dumps({
                "method": method,
                "url": full_url,
                "json": kwargs.get("json"),
                "params": kwargs.get("params"),
                "headers": dict(self.session.headers),
            }, ensure_ascii=False, indent=2),
            name="请求信息",
            attachment_type=allure.attachment_type.JSON,
        )

        try:
            response = self.session.request(
                method=method,
                url=full_url,
                timeout=self.timeout,
                **kwargs
            )
            # 截断超长响应，避免日志爆炸
            preview = response.text[:500] if response.text else ""
            logger.info("Response: {} | {}".format(response.status_code, preview))

            # 归档响应到 Allure
            allure.attach(
                response.text,
                name="响应内容 [{}]".format(response.status_code),
                attachment_type=(
                    allure.attachment_type.JSON
                    if "json" in response.headers.get("content-type", "")
                    else allure.attachment_type.TEXT
                ),
            )

            # ===== TOCTOU 修复: 命中 401/code=7 失效 + 有回调 => 刷新 token 重放一次 =====
            if _is_token_invalid(response):
                new_resp = self._try_auto_refresh_token(method, url, kwargs)
                if new_resp is not None:
                    response = new_resp

            if not response.ok:
                logger.warning("请求返回非成功状态码: {}".format(response.status_code))
            return response

        except requests.exceptions.Timeout:
            msg = "请求超时: {} {}".format(method, full_url)
            logger.error(msg)
            raise APIException(msg)
        except requests.exceptions.ConnectionError:
            msg = "连接失败: {} {}".format(method, full_url)
            logger.error(msg)
            raise APIException(msg)
        except Exception as e:
            msg = "请求异常: {} {} | {}".format(method, full_url, str(e))
            logger.error(msg)
            raise APIException(msg)

    # 便捷方法
    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    # 断言

    def assert_status_code(self, response, expected=200):
        """断言 HTTP 状态码，失败抛 APIException"""
        actual = response.status_code
        if actual != expected:
            msg = "状态码断言失败: 预期 {}, 实际 {}".format(expected, actual)
            logger.error(msg)
            raise APIException(msg, actual, response)
        logger.info("状态码断言通过: {}".format(actual))
        return self

    def assert_business_success(self, response):
        """
        断言 GVA 业务成功: HTTP 200 且 code=0
        GVA 统一响应格式: {"code": 0, "data": ..., "msg": "..."}
        """
        self.assert_status_code(response, 200)
        try:
            data = response.json()
        except Exception as e:
            raise APIException("响应不是合法JSON: {}".format(str(e)), response.status_code, response)
        code = data.get("code")
        if code != 0:
            msg = data.get("msg", "")
            err = "业务码断言失败: 预期 code=0, 实际 code={}, msg={}".format(code, msg)
            logger.error(err)
            raise APIException(err, response.status_code, response)
        logger.info("业务成功断言通过: code=0")
        return self

    def assert_business_error(self, response, expected_code=None):
        """
        断言 GVA 业务失败: code != 0
        :param expected_code: 若指定，进一步校验业务码是否等于 expected_code
        """
        try:
            data = response.json()
        except Exception as e:
            raise APIException("响应不是合法JSON: {}".format(str(e)), response.status_code, response)
        code = data.get("code")
        if code == 0:
            err = "业务码断言失败: 预期 code != 0, 实际 code=0"
            logger.error(err)
            raise APIException(err, response.status_code, response)
        if expected_code is not None and code != expected_code:
            err = "业务码断言失败: 预期 code={}, 实际 code={}".format(expected_code, code)
            logger.error(err)
            raise APIException(err, response.status_code, response)
        logger.info("业务失败断言通过: code={}".format(code))
        return self

    def assert_json_key(self, response, key, expected_value):
        """断言 JSON 响应中的指定字段(顶层 key)"""
        try:
            data = response.json()
        except Exception as e:
            raise APIException("响应不是合法JSON: {}".format(str(e)), response.status_code, response)
        actual = data.get(key)
        if actual != expected_value:
            msg = "JSON断言失败: '{}' 预期 {}, 实际 {}".format(key, expected_value, actual)
            logger.error(msg)
            raise APIException(msg, response.status_code, response)
        logger.info("JSON断言通过: {} = {}".format(key, actual))
        return self
