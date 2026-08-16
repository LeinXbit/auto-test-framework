# -*- coding: utf-8 -*-
"""
HTTP request base class: unified gateway for all API calls
    - Wraps GET/POST/PUT/DELETE
    - Auto-logs request/response + archives to Allure
    - Unified exception handling
    - Supports GVA x-token auth injection
    - Provides GVA business code assertions (code=0 success / non-zero failure)
    - [TOCTOU fix] When a request is rejected by GVA with code=7/HTTP 401,
        if on_token_expired callback is injected, it will refresh the token
        and replay the original request once
"""
import json

import allure
import requests

from utils.exceptions import APIException
from utils.logger import get_logger

logger = get_logger(__name__)

# Typical GVA token-invalid signature: HTTP 401 + code=7 with these msg keywords
_TOKEN_INVALID_MESSAGES = (
    "异地登陆",
    "令牌失效",
    "未登录",
    "非法访问",
    "请登录",
)


def _is_token_invalid(response):
    """Detect GVA 'remote login or token expired / not logged in' style responses (module-level function to avoid Python 3.7 @staticmethod binding issues)."""
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
    Business API base class. All API modules inherit from this.
    """

    # Class-level default so hasattr/getattr work on the class object too; instance __init__ overrides it
    on_token_expired = None

    def __init__(self, base_url, timeout=10):
        self.base_url = base_url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        # Optional callback: triggered when a request hits GVA code=7/HTTP 401 (remote login / token expired).
        # Returns a new valid token string; request() will then swap the token and replay the original request once.
        # Signature: () -> str
        # Typical scenario: session-level admin_token auto re-login after being invalidated by a single logout.
        self.on_token_expired = None

    # Auth

    def set_token(self, token):
        """GVA uses x-token header for auth"""
        if not token:
            raise APIException("Token 不能为空")
        self.session.headers["x-token"] = token
        logger.info("x-token 已注入请求头")

    # Internal

    def _try_auto_refresh_token(self, method, url, kwargs):
        """
        If on_token_expired is injected, call it to get a new token, swap the header, and replay the original request once.
        :returns: new response, or None if no callback configured / refresh not supported
        """
        cb = self.on_token_expired
        if cb is None:
            return None
        try:
            logger.warning("[Token] request hit 401/code=7 invalid, calling on_token_expired to refresh and replay")
            new_token = cb()
            if not new_token:
                logger.warning("[Token] on_token_expired returned empty, giving up auto replay")
                return None
            self.set_token(new_token)
            # Replay the original request (same method/url/kwargs)
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
            logger.warning("[Token] auto refresh replay failed (falling back to original response): {}".format(e))
            return None

    # Request

    def request(self, method, url, **kwargs):
        full_url = "{}{}".format(self.base_url, url)

        # Log request info
        logger.info("Request: {} {}".format(method, full_url))
        if "json" in kwargs:
            logger.info("Body: {}".format(json.dumps(kwargs["json"], ensure_ascii=False)))
        if "params" in kwargs:
            logger.info("Params: {}".format(kwargs["params"]))

        # Archive to Allure
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
            # Truncate overlong responses to avoid log explosion
            preview = response.text[:500] if response.text else ""
            logger.info("Response: {} | {}".format(response.status_code, preview))

            # Archive response to Allure
            allure.attach(
                response.text,
                name="响应内容 [{}]".format(response.status_code),
                attachment_type=(
                    allure.attachment_type.JSON
                    if "json" in response.headers.get("content-type", "")
                    else allure.attachment_type.TEXT
                ),
            )

            # TOCTOU fix: hit 401/code=7 invalid + has callback => refresh token and replay once
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

    # Convenience methods
    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    # Assertions

    def assert_status_code(self, response, expected=200):
        """Assert HTTP status code; raise APIException on failure"""
        actual = response.status_code
        if actual != expected:
            msg = "状态码断言失败: 预期 {}, 实际 {}".format(expected, actual)
            logger.error(msg)
            raise APIException(msg, actual, response)
        logger.info("状态码断言通过: {}".format(actual))
        return self

    def assert_business_success(self, response):
        """
        Assert GVA business success: HTTP 200 and code=0
        GVA unified response format: {"code": 0, "data": ..., "msg": "..."}
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
        Assert GVA business failure: code != 0
        :param expected_code: if specified, further verify the business code equals expected_code
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
        """Assert a top-level key in the JSON response"""
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
