from config.settings import settings
from utils.logger import get_logger
from db.mysql_client import MySQLClient

logger = get_logger(__name__)


def test_mysql_connection():
    """验证能连接 MySQL 并执行查询"""
    db = MySQLClient(**settings.db_config)

    # 查询数据库版本
    result = db.query_one("SELECT VERSION() as version")
    logger.info(f"MySQL 版本: {result['version']}")

    assert result is not None
    assert "version" in result

    db.close()
    logger.info("数据库连接测试通过")


def test_mysql_crud():
    """验证数据库增删改查"""
    db = MySQLClient(**settings.db_config)

    # 1. 创建测试表（如果不存在）
    db.execute("""
        CREATE TABLE IF NOT EXISTS test_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            email VARCHAR(100)
        )
    """)

    # 2. 插入数据
    db.execute(
        "INSERT INTO test_users (username, email) VALUES (%s, %s)",
        ("test_user", "test@example.com")
    )

    # 3. 查询验证
    user = db.query_one("SELECT * FROM test_users WHERE username = %s", ("test_user",))
    assert user["username"] == "test_user"
    assert user["email"] == "test@example.com"
    logger.info(f"查询到用户: {user}")

    # 4. 更新数据
    db.execute(
        "UPDATE test_users SET email = %s WHERE username = %s",
        ("updated@example.com", "test_user")
    )
    updated = db.query_one("SELECT email FROM test_users WHERE username = %s", ("test_user",))
    assert updated["email"] == "updated@example.com"

    # 5. 删除数据
    db.execute("DELETE FROM test_users WHERE username = %s", ("test_user",))
    deleted = db.query_one("SELECT * FROM test_users WHERE username = %s", ("test_user",))
    assert deleted is None

    db.close()
    logger.info("数据库 CRUD 测试通过")


def test_mysql_with_context():
    """验证上下文管理器（with 语句）"""
    with MySQLClient(**settings.db_config) as db:
        result = db.query_one("SELECT 1 as num")
        assert result["num"] == 1
    logger.info("上下文管理器测试通过")