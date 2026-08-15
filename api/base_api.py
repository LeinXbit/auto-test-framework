import json
import requests

from utils.exceptions import APIException

from utils.logger import get_logger

logger = get_logger(__name__)

# Allure 为可选依赖：仅 pytest 运行时使用，不强制耦合
try:
    import allure
except ImportError:  # pragma: no cover - 仅在未安装 allure-pytest 时兜底
    allure = None


class BaseApi:
    """
    Http 请求基类：所有 API 接口的通信出口
        - 统一封装 GET/POST/PUT/DELETE
        - 自动记录请求/响应日志，并归档到 Allure
        - 统一异常处理
        - 支持 GVA 的 x-token 鉴权注入
        - 提供 GVA 业务码（code==0）断言辅助
    """

    def __init__(self, base_url, timeout=10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })

    def set_token(self, token):
        """
        注入鉴权 Token（GVA 使用 x-token header，而非 Authorization: Bearer）
        :param token: GVA 登录返回的 jwt token 原文
        """
        if not token:
            raise APIException("Token 不能为空")
        self.session.headers["x-token"] = token
        logger.info("x-token 已注入请求头")

    def clear_token(self):
        """清除 Token（用于登出/未鉴权场景）"""
        self.session.headers.pop("x-token", None)
        logger.info("x-token 已清除")

    def request(self, method, url, **kwargs):
        """
        统一请求方法
        :param method:
        :param url:
        :param kwargs:
        :return:
        """
        full_url = f"{self.base_url}{url}"

        # 记录请求信息
        logger.info(f"Request: {method} {full_url}")
        if "json" in kwargs:
            logger.info(f"Body: {json.dumps(kwargs['json'], ensure_ascii=False)}")
        if "params" in kwargs:
            logger.info(f"Params: {kwargs['params']}")

        # 归档请求信息到 Allure
        if allure is not None:
            req_attach = f"{method} {full_url}"
            if "json" in kwargs:
                req_attach += f"\nBody: {json.dumps(kwargs['json'], ensure_ascii=False)}"
            if "params" in kwargs:
                req_attach += f"\nParams: {kwargs['params']}"
            allure.attach(req_attach, "Request", attachment_type=allure.attachment_type.TEXT)

        try:
            response = self.session.request(
                method=method,
                url=full_url,
                timeout=self.timeout,
                **kwargs
            )

            # 记录响应信息
            logger.info(f"Response: {response.status_code} | {response.text[:500]}")

            # 归档响应到 Allure
            if allure is not None:
                allure.attach(
                    f"HTTP {response.status_code}\n{response.text}",
                    "Response",
                    attachment_type=allure.attachment_type.TEXT
                )

            if not response.ok:
                logger.warning(f"请求返回非成功状态码:{response.status_code}")

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

    # ===== 断言辅助方法 =====

    def assert_status_code(self, response, expected):
        """
        断言 HTTP 状态码，失败时抛出 APIException 并附带响应
        返回self支持链式调用
        :param response:
        :param expected:
        :return:
        """
        actual = response.status_code
        if actual != expected:
            msg = f"状态码断言失败: 预期 {expected}, 实际 {actual}"
            logger.error(msg)
            raise APIException(msg, actual, response)
        logger.info(f"状态码断言通过: {actual}")
        return self

    def assert_json_key(self, response, key, expected_value):
        """ 断言JSON响应中的指定字段 """
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

    def assert_business_success(self, response):
        """
        GVA 统一响应格式断言：HTTP 200 + body.code == 0
        用于业务接口的成功断言
        :param response:
        :return:
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

    def assert_business_error(self, response, expected_code):
        """
        断言 GVA 业务错误码（HTTP 200，但 body.code 为指定错误码）
        用于负向用例：期望业务失败的场景
        :param response:
        :param expected_code:
        :return:
        """
        try:
            data = response.json()
        except Exception as e:
            raise APIException(f"响应不是合法JSON: {str(e)}", response.status_code, response)

        code = data.get("code")
        if code != expected_code:
            msg = data.get("msg", "")
            err = f"业务错误码断言失败: 预期 code={expected_code}, 实际 code={code}, msg={msg}"
            logger.error(err)
            raise APIException(err, response.status_code, response)

        logger.info(f"业务错误码断言通过: code={code}")
        return self

    def extract(self, response, *json_path, default=None):
        """
        从 JSON 响应中按层级路径取值
        :param response:
        :param json_path: 例如 extract(resp, "data", "token")
        :param default:
        :return:
        """
        try:
            data = response.json()
        except Exception as e:
            raise APIException(f"响应不是合法JSON: {str(e)}", response.status_code, response)

        cur = data
        for key in json_path:
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                return default
        return cur
