import json
import requests

from utils.exceptions import APIException

from utils.logger import get_logger

logger = get_logger(__name__)

class BaseApi:
    """
    Http 请求基类:所有 API 接口的通信出口
        - 统一封装 GET/POST/PUT/DELETE
        - 自动记录请求/响应日志
        - 统一异常处理
        - 支持 Token 鉴权注入
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
        注入鉴权 Token
        :param token:
        :return:
        """
        self.session.headers["Authorization"] = f"Bearer{token}"
        logger.info("Token 已注入请求头")

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

        try:
            response = self.session.request(
                method=method,
                url=full_url,
                timeout=self.timeout,
                **kwargs
            )

            # 记录响应信息
            logger.info(f"Response: {response.status_code} | {response.text[:500]}")

            if not response.ok :
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
            raise APIException

    # 便捷方法
    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    # 断言辅助方法
    def assert_status_code(self, response, expected):
        """
        断言 HTTP 状态码，失败时抛出 APIException 并附带响应
        返回self支持链式调用: api.assert_status_code(resp, 200).assert_json_key(resp, "code", 0)
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