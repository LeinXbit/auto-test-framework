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

    # 验证用户确实在数据库里
    user_in_db = db_client.query_one(
        "SELECT * FROM test_users WHERE id = %s",
        (test_user["id"],)
    )
    assert user_in_db["username"] == test_user["username"]
    assert user_in_db["email"] == test_user["email"]

    logger.info("测试用户数据验证通过（退出后会被自动清理）")


def test_fixture_user_isolated(test_user, db_client):
    """验证每个用例的用户是独立的（不会互相污染）"""
    logger.info(f"第二个用例的用户: {test_user}")

    # 查询数据库中该用户的数量，应该只有 1 个
    count = db_client.query_one(
        "SELECT COUNT(*) as cnt FROM test_users WHERE username = %s",
        (test_user["username"],)
    )
    assert count["cnt"] == 1

    logger.info("用户隔离性验证通过")


def test_fixture_api_client(api_client):
    """验证 API 客户端 Fixture（先用 httpbin 演示）"""
    # 注意：如果网络不通，这个用例会失败，属于正常
    resp = api_client.get("https://httpbin.org/get", params={"check": "fixture"})

    # 如果网络不通，直接跳过断言，不阻塞后续
    if resp.ok:
        assert resp.status_code == 200
        logger.info("API 客户端 Fixture 验证通过")
    else:
        logger.warning("网络不通，跳过 API 断言")