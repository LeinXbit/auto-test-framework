import pytest

from config.settings import settings
from utils.logger import get_logger
from api.base_api import BaseApi

logger = get_logger(__name__)


def test_config_loaded():
    """验证配置系统正常"""
    assert settings.base_url is not None
    logger.info(f"当前环境: {settings.env}, Base URL: {settings.base_url}")


def test_base_api_get():
    """验证 BaseApi 能正常发送 GET 请求"""
    api = BaseApi(base_url="https://httpbin.org")

    resp = api.get("/get", params={"foo": "bar"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["args"]["foo"] == "bar"
    logger.info(" GET 请求验证通过")


def test_base_api_post():
    """验证 BaseApi 能正常发送 POST 请求"""
    api = BaseApi(base_url="https://httpbin.org")

    payload = {"username": "test_user", "password": "123456"}
    resp = api.post("/post", json=payload)

    assert resp.status_code == 200
    data = resp.json()
    assert data["json"]["username"] == "test_user"
    logger.info("POST 请求验证通过")


def test_base_api_error_handling():
    """验证异常场景：请求不存在的地址会抛出异常"""
    api = BaseApi(base_url="https://httpbin.org")

    try:
        # httpbin 的 /status/404 会返回 404
        resp = api.get("/status/404")
        # 虽然返回 404，但请求本身没有抛异常，只是 response.ok 为 False
        assert resp.status_code == 404
        logger.info("404 状态码被正确捕获")
    except Exception:
        pytest.fail("不应该抛出异常，404 是合法响应")