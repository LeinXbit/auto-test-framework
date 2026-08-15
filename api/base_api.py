# -*- coding: utf-8 -*-
"""
HTTP 请求基类：所有 API 接口的通信出口
    - 统一封装 GET/POST/PUT/DELETE
    - 自动记录请求/响应日志 + 自动归档到 Allure
    - 统一异常处理
    - 支持 GVA 的 x-token 鉴权注入
    - 提供 GVA 业务码断言（code=0 成功 / 非 0 失败）
"""
import json

import allure
import requests

from utils.exceptions import APIException
from utils.logger import get_logger

logger = get_logger(__name__)


class BaseApi:
    """
    业务 API 基类：所有 API 模块继承此类
    """

    def __init__(self, base_url, timeout=10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ============ 鉴权 ============

    def set_token(self, token):
        """GVA 使用 x-token 头部鉴权"""
        if not token:
            raise APIException("Token 不能为空")
        self.session.headers["x-token"] = token
        logger.info("x-token 已注入请求头")

    # ============ 请求 ============

    def request(self, method, url, **kwargs):
        full_url = f"{self.base_url}{url}"

        # 记录请求信息
        logger.info(f"Request: {method} {full_url}")
        if "json" in kwargs:
            logger.info(f"Body: {json.dumps(kwargs['json'], ensure_ascii=False)}")
        if "params" in kwargs:
            logger.info(f"Params: {kwargs['params']}")

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
            logger.info(f"Response: {response.status_code} | {preview}")

            # 归档响应到 Allure
            allure.attach(
                response.text,
                name=f"响应内容 [{response.status_code}]",
                attachment_type=allure.attachment_type.JSON if "json" in response.headers.get("content-type", "") else allure.attachment_type.TEXT,
            )

            if not response.ok:
                logger.warning(f"请求返回非成功状态码: {response.status_code}")
            return response

        except requests.exceptions.Timeout:
            msg = f"请求超时: {method} {full_url}"
            logger.error(msg)
            raise APIException(msg)
        except requests.exceptions.ConnectionError:
            msg = f"连接失败: {method} {full_url}"
            logger.error(msg)
            raise APIException(msg)
        except Exception as e:
            msg = f"请求异常: {method} {full_url} | {str(e)}"
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

    # ============ 断言 ============

    def assert_status_code(self, response, expected=200):
        """断言 HTTP 状态码，失败抛 APIException"""
        actual = response.status_code
        if actual != expected:
            msg = f"状态码断言失败: 预期 {expected}, 实际 {actual}"
            logger.error(msg)
            raise APIException(msg, actual, response)
        logger.info(f"状态码断言通过: {actual}")
        return self

    def assert_business_success(self, response):
        """
        断言 GVA 业务成功：HTTP 200 且 code=0
        GVA 统一响应格式: {"code": 0, "data": ..., "msg": "..."}
        """
        self.assert_status_code(response, 200)
        try:
            data = response.json()
        except Exception as e:
            raise APIException(f"响应不是合法JSON: {str(e)}", response.status_code, response)
        code = data.get("code")
        if code != 0:
            msg = data.get("msg", "")
            err = f"业务码断言失败: 预期 code=0, 实际 code={code}, msg={msg}"
            logger.error(err)
            raise APIException(err, response.status_code, response)
        logger.info("业务成功断言通过: code=0")
        return self

    def assert_business_error(self, response, expected_code=None):
        """
        断言 GVA 业务失败：code != 0
        :param expected_code: 若指定，进一步校验业务码是否等于 expected_code
        """
        try:
            data = response.json()
        except Exception as e:
            raise APIException(f"响应不是合法JSON: {str(e)}", response.status_code, response)
        code = data.get("code")
        if code == 0:
            err = "业务码断言失败: 预期 code != 0, 实际 code=0"
            logger.error(err)
            raise APIException(err, response.status_code, response)
        if expected_code is not None and code != expected_code:
            err = f"业务码断言失败: 预期 code={expected_code}, 实际 code={code}"
            logger.error(err)
            raise APIException(err, response.status_code, response)
        logger.info(f"业务失败断言通过: code={code}")
        return self

    def assert_json_key(self, response, key, expected_value):
        """断言 JSON 响应中的指定字段（顶层 key）"""
        try:
            data = response.json()
        except Exception as e:
            raise APIException(f"响应不是合法JSON: {str(e)}", response.status_code, response)
        actual = data.get(key)
        if actual != expected_value:
            msg = f"JSON断言失败: '{key}' 预期 {expected_value}, 实际 {actual}"
            logger.error(msg)
            raise APIException(msg, response.status_code, response)
        logger.info(f"JSON断言通过: {key} = {actual}")
        return self
