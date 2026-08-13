import pytest
from utils.logger import get_logger

logger = get_logger(__name__)


def test_fixture_db_connection(db_client):
    """验证 Fixture 自动注入数据库连接"""
    result = db_client.query_one("SELECT VERSION() as version")
    logger.info(f"MySQL 版本: {result['version']}")
    assert result is not None


def test_fixture_auto_user(test_user, db_client):
    """验证 Fixture 自动创建测试用户，且用例结束后自动清理"""
    logger.info(f"当前测试用户: {test_user}")

    user_in_db = db_client.query_one(
        "SELECT * FROM test_users WHERE id = %s",
        (test_user["id"],)
    )
    assert user_in_db["username"] == test_user["username"]
    logger.info("测试用户数据验证通过")


def test_user_api_structure(user_api):
    """
    验证 UserApi 封装结构正确
    不依赖真实服务，只验证方法存在和继承关系
    """
    # 验证继承自 BaseApi
    assert hasattr(user_api, "get")
    assert hasattr(user_api, "post")
    assert hasattr(user_api, "put")
    assert hasattr(user_api, "delete")

    # 验证业务方法存在
    assert hasattr(user_api, "register")
    assert hasattr(user_api, "login")
    assert hasattr(user_api, "get_user")
    assert hasattr(user_api, "update_user")
    assert hasattr(user_api, "delete_user")
    assert hasattr(user_api, "list_users")

    # 验证 base_url 被正确注入
    assert user_api.base_url == "http://127.0.0.1:5000"

    logger.info("UserApi 结构验证通过")


def test_user_api_register_mock(user_api, monkeypatch):
    """
    使用 pytest 的 monkeypatch 模拟网络响应
    验证 register 方法构造的请求参数正确
    （不依赖真实服务，展示单元测试能力）
    """
    captured = {}  # 捕获调用参数

    def mock_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")

        class MockResponse:
            status_code = 201

            def json(self):
                return {"code": 0, "data": {"id": 1, "username": "mock_user"}}

        return MockResponse()

    # 替换 user_api 的 post 方法为 mock
    monkeypatch.setattr(user_api, "post", mock_post)

    # 调用业务方法
    resp = user_api.register("mock_user", "Pass123!", "mock@test.com")

    # 验证业务方法构造了正确的请求
    assert resp.status_code == 201
    assert captured["url"] == "/api/register"
    assert captured["json"]["username"] == "mock_user"
    assert captured["json"]["email"] == "mock@test.com"

    logger.info("UserApi Mock 测试通过（验证参数构造正确）")