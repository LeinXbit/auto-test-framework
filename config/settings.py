import os

import yaml
from pathlib import Path


def _load_env_file(env_path):
    """
    Minimal .env loader (zero external deps):
        - Parses KEY=VALUE, skips blank lines and comments (#)
        - Existing env vars are not overridden (CI secrets take precedence)
        - No quotes/escaping; kept intentionally simple
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
    Config manager:
        - Loads .env on startup (if present); sensitive config prefers env vars
        - Loads the YAML config file matching TEST_ENV
        - Supports dot-path access to nested config
    """

    def __init__(self):
        # Load .env (gitignored); skip if missing so CI secrets still work
        _load_env_file(Path(__file__).resolve().parent.parent / ".env")

        # Default to local gin-vue-admin real business
        self.env = os.getenv("TEST_ENV", "go_vue_admin")

        # Locate the config file
        config_dir = Path(__file__).parent / "environments"
        config_file = config_dir / "{}.yaml".format(self.env)

        # Fail fast if missing, to avoid silently using the wrong config
        if not config_file.exists():
            raise FileNotFoundError(
                "配置文件不存在: {}\n请确认环境变量 TEST_ENV={} 是否正确, 或创建该配置环境".format(
                    config_file, self.env
                )
            )

        # Read YAML
        with open(config_file, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def get(self, key, default=None):
        """
        Get config value by dot path
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
        # CI/staging overrides via env var so the same YAML works across envs
        return os.getenv("GVA_BASE_URL", self.get("base_url"))

    @property
    def db_config(self):
        """
        Supports env-var overrides for DB config (Docker / CI scenarios).
        Priority: env var > YAML > built-in default.
        Password is read only from env vars, never stored in YAML.
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
        """GVA admin account (used by fixtures for auto login)
        Prefers env vars; password is never stored in YAML
        """
        return {
            "username": os.getenv("ADMIN_USERNAME", "admin"),
            "password": os.getenv("ADMIN_PASSWORD", "123456"),
        }

    @property
    def captcha_config(self):
        """Captcha recognition config"""
        return self.get("captcha", {}) or {
            "solver": "ddddocr",
            "max_retry": 5,
            "expected_length": 6,
        }

# Global singleton; only one Settings instance for the whole project
settings = Settings()
