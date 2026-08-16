import os

import yaml
from pathlib import Path


def _load_env_file(env_path):
    """
    极简 .env 加载器(零外部依赖):
        - 解析 KEY=VALUE, 跳过空行/注释(#)
        - 已存在的环境变量不被覆盖(CI secrets 优先级最高)
        - 不支持引号/转义等复杂语法, 保持简单
    """
    env_path = Path(env_path)
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


class Settings:
    """
    配置管理类：
        - 启动时加载 .env(若存在), 敏感配置优先读环境变量
        - 根据环境变量 TEST_ENV 加载对应的 YAML 配置文件
        - 支持用点号访问嵌套配置
    """

    def __init__(self):
        # 加载 .env(已 gitignore), 不存在则跳过, 不影响 CI 用 secrets 注入
        _load_env_file(Path(__file__).resolve().parent.parent / ".env")

        # 默认对接本地 gin-vue-admin 真实业务
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
        """
        支持环境变量覆盖数据库配置(Docker/CI 场景)
        优先级: 环境变量 > YAML > 内置默认
        密码仅从环境变量读取, 不落 YAML, 避免明文入库
        """
        base_config = self.get("database", {})
        return {
            "host": os.getenv("DB_HOST", base_config.get("host", "127.0.0.1")),
            "port": int(os.getenv("DB_PORT", base_config.get("port", 3306))),
            "user": os.getenv("DB_USER", base_config.get("user", "root")),
            "password": os.getenv("DB_PASSWORD", base_config.get("password", "")),
            "database": os.getenv("DB_DATABASE", base_config.get("database", "gva")),
        }

    @property
    def timeout(self):
        return self.get("timeout", 10)

    @property
    def admin_account(self):
        """GVA 管理员账号（用于 fixture 自动登录）
        优先环境变量, 密码不落 YAML
        """
        return {
            "username": os.getenv("ADMIN_USERNAME", "admin"),
            "password": os.getenv("ADMIN_PASSWORD", "123456"),
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
