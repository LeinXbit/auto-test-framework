# -*- coding: utf-8 -*-
"""
GVA 测试套件全局 Fixture
    - admin_token:    session 级，自动登录 GVA 拿 token，session 结束后登出
    - auth_api:       已注入 admin token 的鉴权客户端
    - user_api:       已注入 admin token 的用户管理客户端
    - db_client:       GVA 数据库连接（用于断言 sys_users 等真实表）
    - no_token_api:   未鉴权客户端（用于负向用例：401 场景）
"""
import sys
from pathlib import Path

# 自动把 .vendor 加入 sys.path，使本项目无需污染系统 Python 即可加载 ddddocr/allure/yaml/pymysql
_VENDOR = Path(__file__).resolve().parent.parent / ".vendor"
if _VENDOR.exists():
    sys.path.insert(0, str(_VENDOR))

import pytest

from api.auth_api import AuthApi
from api.user_api import UserApi
from config.settings import settings
from db.mysql_client import MySQLClient
from utils.captcha_solver import CaptchaSolver
from utils.logger import get_logger

logger = get_logger(__name__)


# ========== Session 级：admin token ==========

@pytest.fixture(scope="session")
def captcha_solver():
    """验证码识别器（session 级，单例）"""
    cfg = settings.captcha_config
    solver = CaptchaSolver(
        expected_length=cfg.get("expected_length", 6),
        max_retry=cfg.get("max_retry", 5),
    )
    yield solver


@pytest.fixture(scope="session")
def admin_token(captcha_solver):
    """
    Session 级 admin token：整个测试会话只登录一次
    会话结束后调用 /jwt/jsonInBlacklist 登出
    :return: token 字符串
    """
    auth = AuthApi(
        base_url=settings.base_url,
        timeout=settings.timeout,
        captcha_solver=captcha_solver,
    )

    logger.info("[Session] 开始登录 GVA admin")
    token = auth.login_with_retry(
        username=settings.admin_account["username"],
        password=settings.admin_account["password"],
        max_round=3,
    )
    logger.info(f"[Session] admin 登录成功, token={token[:20]}...")

    yield token

    # 登出（token 加入黑名单）
    auth.set_token(token)
    try:
        auth.logout()
        logger.info("[Session] admin 已登出")
    except Exception as e:
        logger.warning(f"[Session] 登出失败（不影响测试结果）: {e}")


# ========== Function 级：API 客户端 ==========

@pytest.fixture(scope="function")
def auth_api(admin_token):
    """
    鉴权模块客户端（已注入 admin token）
    用于：登录态相关断言、登出、获取用户信息等
    """
    api = AuthApi(
        base_url=settings.base_url,
        timeout=settings.timeout,
        captcha_solver=None,  # 复用 admin_token 已登录，无需再次识别
    )
    api.set_token(admin_token)
    yield api


@pytest.fixture(scope="function")
def user_api(admin_token):
    """
    用户管理客户端（已注入 admin token）
    用于：用户 CRUD、角色分配等
    """
    api = UserApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token)
    yield api


@pytest.fixture(scope="function")
def no_token_client():
    """
    未注入 token 的客户端（用于负向用例：401 未授权）
    """
    api = UserApi(base_url=settings.base_url, timeout=settings.timeout)
    api.clear_token()
    yield api


# ========== Function 级：数据库 ==========

@pytest.fixture(scope="function")
def db_client():
    """
    GVA 数据库连接（用于断言 sys_users 等真实表）
    :return: MySQLClient
    """
    logger.info("[Fixture] 创建 GVA 数据库连接")
    client = MySQLClient(**settings.db_config)
    yield client
    client.close()
    logger.info("[Fixture] 数据库连接已关闭")


# ========== 业务数据 Fixture：测试用户 ==========

@pytest.fixture(scope="function")
def temp_user(user_api, db_client):
    """
    创建一个临时测试用户（业务隔离）
    前置：调用 GVA 真实注册接口
    后置：删除该用户（业务层 + 数据库兜底）
    :return: dict {ID, userName, nickName, ...}
    """
    import uuid
    username = f"auto_{uuid.uuid4().hex[:8]}"
    password = "Test1234!"

    logger.info(f"[Fixture] 注册测试用户: {username}")

    # 调用真实注册接口
    resp = user_api.admin_register(
        username=username,
        password=password,
        nick_name=username,
    )
    if resp.json().get("code") != 0:
        # 注册失败时通过 APIException 让用例标记 ERROR
        from utils.exceptions import APIException
        raise APIException(
            f"测试用户注册失败: {resp.json()}",
            resp.status_code, resp
        )

    # 从用户列表中找到刚创建用户的 ID
    list_resp = user_api.get_user_list(page=1, page_size=100, keyword=username)
    users = list_resp.json().get("data", {}).get("list", [])
    if not users:
        from utils.exceptions import APIException
        raise APIException(f"无法从用户列表查到测试用户: {username}")

    user = users[0]
    logger.info(f"[Fixture] 测试用户已创建: ID={user.get('ID')}, userName={user.get('userName')}")

    yield user

    # 清理：先走业务接口删除，数据库兜底
    logger.info(f"[Fixture] 清理测试用户: ID={user.get('ID')}")
    try:
        user_api.delete_user(user["ID"])
    except Exception as e:
        logger.warning(f"[Fixture] 业务接口删除失败，数据库兜底: {e}")
        db_client.execute(
            "DELETE FROM sys_users WHERE user_name = %s",
            (username,)
        )
