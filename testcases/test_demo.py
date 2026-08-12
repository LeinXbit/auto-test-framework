from config.settings import settings


def test_project_is_alive():
    """验证项目基础环境正常"""
    assert 1 + 1 == 2


def test_config_loaded():
    """验证配置系统能正确加载当前环境的配置"""
    print(f"\n[当前环境] {settings.env}")
    print(f"[Base URL] {settings.base_url}")
    print(f"[数据库配置] {settings.db_config}")

    # 只验证配置存在且格式正确，不硬编码具体值
    assert settings.base_url is not None
    assert settings.db_config is not None
    assert isinstance(settings.timeout, int)
    assert settings.timeout > 0


def test_config_dot_access():
    """验证点号访问嵌套配置"""
    host = settings.get("database.host")
    port = settings.get("database.port")

    assert host == "127.0.0.1"
    assert port == 3306


def test_config_default_value():
    """验证访问不存在的配置时返回默认值"""
    result = settings.get("database.not_exist_key", "default_value")
    assert result == "default_value"