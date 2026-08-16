import pymysql
from pymysql.cursors import DictCursor

from utils.logger import get_logger

logger = get_logger(__name__)

class MySQLClient:
    """
    MySQL 数据库客户端
        - 封装常用查询/执行操作
        - 自动记录执行的 SQL
        - 支持上下文管理器(with 语句)
    """
    def __init__(self, host, port, user, password, database):
        self.config = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": "utf8mb4",
            "cursorclass": pymysql.cursors.DictCursor, # 返回字典格式
            "autocommit": True
        }
        self.conn = None
        self._connect()

    def _connect(self):
        """
        建立连接
        :return:
        """
        try:
            self.conn = pymysql.connect(**self.config)
            logger.info(f"数据库连接成功: {self.config['host']}:{self.config['port']}/{self.config['database']}")

        except Exception as e:
            logger.info(f"数据库连接失败: {e}")
            raise

    def query_one(self, sql, params=None):
        """
        查询单条记录
        :param sql:
        :param params:
        :return:
        """
        logger.debug(f"SQL: {sql} | Params: {params}")
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            result = cursor.fetchone()
            logger.debug(f"Result: {result}")
            return result

    def query_all(self, sql, params=None):
        """
        查询多条记录
        :param sql:
        :param params:
        :return:
        """
        logger.debug(f"SQL: {sql} | Params: {params}")
        with self.conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def execute(self, sql, params=None):
        """
        执行 INSERT/UPDATE/DELETE
        :param sql:
        :param params:
        :return:
        """
        logger.info(f"SQL Execute: {sql} | Params: {params}")
        with self.conn.cursor() as cursor:
            affected = cursor.execute(sql, params)
            logger.info(f"受影响的行数: {affected}")

    def close(self):
        """ 关闭连接 """
        if self.conn:
            self.conn.close()
            logger.info("数据库已关闭")

    def __enter__(self):
        """ 支持 with 语句 """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()