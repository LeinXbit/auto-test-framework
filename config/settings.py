import os
import  yaml
from pathlib import Path



class Settings:
    """
    配置管理类：
        -根据环境变量 TEST_ENV 加载对应的 YAML 配置文件
        -支持用点号访问嵌套配置
    """

    def __init__(self):
        # 从环境变量读取当前环境，默认 go_vue_admin（本地真实业务）
        self.env = os.getenv("TEST_ENV", "go_vue_admin")

        # 定位配置文件路径
        config_dir = Path(__file__).parent / "environments"
        config_file = config_dir / f"{self.env}.yaml"

        # 如果文件不存在，直接报错，防止静默使用错误配置
        if not config_file.exists():
            raise FileNotFoundError(
                f"配置文件不存在: {config_file}\n"
                f"请确认环境变量 TEST_ENV={self.env} 是否正确，或创建该配置环境"
            )

        # 读取 YAML
        with open(config_file, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def get(self, key, default=None):
        """
        根据点号路径获取配置值
        :param key:
        :param default:
        :return:
        """
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    @property
    def base_url(self):
        return self.get("base_url")

    @property
    def db_config(self):
        """支持环境变量覆盖数据库配置（Docker 场景）"""
        base_config = self.get("database", {})
        return {
            "host": os.getenv("DB_HOST", base_config.get("host", "127.0.0.1")),
            "port": int(os.getenv("DB_PORT", base_config.get("port", 3306))),
            "user": base_config.get("user", "root"),
            "password": base_config.get("password", ""),
            "database": base_config.get("database", "test_db"),
        }

    @property
    def timeout(self):
        return self.get("timeout", 10)

    @property
    def admin_account(self):
        """管理员账号配置（用于 fixture 自动登录 GVA）"""
        return self.get("admin", {}) or {
            "username": "admin",
            "password": "123456",
        }

    @property
    def captcha_config(self):
        """验证码识别配置"""
        return self.get("captcha", {}) or {
            "solver": "ddddocr",
            "max_retry": 5,
            "expected_length": 6,
        }

# 全局单例，整个项目只创建一个 Settings 实例
settings = Settings()