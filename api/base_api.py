import json
import requests

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
            logger.error(f"请求超时: {method} {full_url}")
            raise
        except requests.exceptions.ConnectionError:
            logger.error(f"连接失败: {method} {full_url}")
            raise
        except Exception as e:
            logger.error(f"请求异常: {method} {full_url} | {str(e)}")
            raise

    # 便捷方法
    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)