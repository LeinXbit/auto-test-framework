import pytest
import uuid

from api.user_api import UserApi
from config.settings import settings
from utils.logger import get_logger
from api.base_api import BaseApi
from db.mysql_client import MySQLClient

logger = get_logger(__name__)

# 数据库连接 Fixture
@pytest.fixture(scope="function")
def db_client():
    """
    每个测试用例自动获得一个数据库连接，
    用例结束后自动关闭，无论成功还是失败
    :return:
    """

    logger.info("[Fixture]创建数据库连接")
    client = MySQLClient(**settings.db_config)
    yield client  #把 client 交给测试用例使用
    client.close()
    logger.info("[Fixture]数据库连接关闭")

# API 客户端 Fixture
@pytest.fixture(scope="function")
def api_client():
    """ 每个测试用例自动获得一个 BaseApi 实例"""
    logger.info("[Fixture]创建 API 客户端")
    client = BaseApi(base_url=settings.base_url)
    yield client
    logger.info("[Fixture] API 客户端已释放")

# 测试用户 Fixture (自动准备 + 自动清理)
@pytest.fixture(scope="function")
def test_user(db_client:MySQLClient):
    """
    前置：在数据库插入一个测试用户
    后置：测试结束后删除该用户（数据不污染）
    :return:
    """
    username = f"auto_{uuid.uuid4().hex[:8]}"
    email = f"{username}@test.com"

    logger.info(f"[Fixture]创建测试用户: {username}")

    db_client.execute(
        "INSERT INTO test_users (username, email) VALUES (%s, %s)",
        (username, email)
    )

    #获取刚插入的用户(带自增ID)
    user = db_client.query_one(
        "SELECT * FROM test_users WHERE username = %s",
        (username,)
    )

    yield user

    logger.info(f"[Fixture]清理测试用户: {username}")
    db_client.execute(
        "DELETE FROM test_users WHERE username = %s",
        (username,)
    )

# Session 级别的 Fixture(整个测试会话只执行一次)
@pytest.fixture(scope="session", autouse=True)
def init_database():
    logger.info(f"[Session Fixture]初始化数据库表结构")
    with MySQLClient(**settings.db_config) as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS test_users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                email VARCHAR(100)
            )
        """)
    yield
    logger.info("[Session Fixture]测试会话结束")

# 业务系统 API Fixture
@pytest.fixture(scope="function")
def user_api():
    """
    每个测试用例自动获得一个 UserApi 实例
    自动继承 BaseApi 的日志、异常处理、Token注入能力
    """
    logger.info("[Fixture] 创建 UserApi 业务客户端")
    api = UserApi(base_url=settings.base_url)
    yield api
    logger.info("[Fixture] UserApi 业务客户端已释放")