from config.settings import settings
from utils.logger import get_logger

# 为当前模块创建日志实例
logger = get_logger(__name__)


def test_project_is_alive():
    """验证项目基础环境正常"""
    logger.info("测试项目基础环境...")
    assert 1 + 1 == 2
    logger.info("基础环境验证通过")


def test_config_loaded():
    """验证配置系统能正确加载当前环境的配置"""
    logger.info(f"当前环境: {settings.env}")
    logger.info(f"Base URL: {settings.base_url}")
    logger.info(f"数据库配置: {settings.db_config}")

    assert settings.base_url is not None
    assert settings.db_config is not None
    assert isinstance(settings.timeout, int)
    assert settings.timeout > 0

    logger.info("配置系统验证通过")


def test_config_dot_access():
    """验证点号访问嵌套配置"""
    host = settings.get("database.host")
    port = settings.get("database.port")

    logger.debug(f"数据库主机: {host}, 端口: {port}")

    assert host == "127.0.0.1"
    assert port == 3306


def test_config_default_value():
    """验证访问不存在的配置时返回默认值"""
    result = settings.get("database.not_exist_key", "default_value")
    logger.warning(f"测试默认值: {result}")

    assert result == "default_value"