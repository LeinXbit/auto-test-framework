# -*- coding: utf-8 -*-
"""
GVA 测试套件全局 Fixture
    - admin_token:    session 级，自动登录 GVA 拿 token，session 结束后登出
    - auth_api:       已注入 admin token 的鉴权客户端
    - user_api:       已注入 admin token 的用户管理客户端
    - db_client:      GVA 数据库连接（用于断言 sys_users 等真实表）
    - no_token_api:   未鉴权客户端（用于负向用例：401 场景）
    - temp_user:      函数级，通过 GVA 真实注册接口创建临时用户，测试结束自动清理
"""
import sys
import uuid
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
from utils.exceptions import APIException
from utils.logger import get_logger

logger = get_logger(__name__)


# ============ Session 级：admin token / captcha solver ============

@pytest.fixture(scope="session")
def captcha_solver():
    """验证码识别器（session 级，避免反复加载 ddddocr 模型）"""
    cfg = settings.captcha_config
    return CaptchaSolver(
        expected_length=cfg.get("expected_length"),
        max_retry=cfg.get("max_retry", 5),
    )


@pytest.fixture(scope="session")
def admin_token(captcha_solver):
    """
    session 级自动登录，整个测试会话复用同一 token
    会话结束自动登出（JWT 加入黑名单）
    """
    auth = AuthApi(
        base_url=settings.base_url,
        timeout=settings.timeout,
        captcha_solver=captcha_solver,
    )
    token = auth.login_with_retry(
        username=settings.admin_account["username"],
        password=settings.admin_account["password"],
        max_round=3,
    )
    yield token
    # session 结束登出
    auth.set_token(token)
    try:
        auth.logout()
        logger.info("[Session] admin 已登出")
    except Exception as e:
        logger.warning(f"[Session] 登出失败（不影响测试结果）: {e}")


# ============ 函数级：API 客户端（已鉴权） ============

@pytest.fixture(scope="function")
def auth_api(admin_token):
    """已注入 admin token 的鉴权客户端"""
    api = AuthApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token)
    yield api


@pytest.fixture(scope="function")
def user_api(admin_token):
    """已注入 admin token 的用户管理客户端"""
    api = UserApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token)
    yield api


@pytest.fixture(scope="function")
def no_token_api():
    """未鉴权客户端（用于负向用例：401 / 未授权场景）"""
    return AuthApi(base_url=settings.base_url, timeout=settings.timeout)


# ============ 数据库 ============

@pytest.fixture(scope="function")
def db_client():
    """
    GVA 数据库连接（function 级，避免长连接断开）
    用于断言 sys_users 等真实表
    """
    client = MySQLClient(**settings.db_config)
    yield client
    client.close()


# ============ 业务数据隔离：临时用户 ============

@pytest.fixture(scope="function")
def temp_user(user_api, db_client):
    """
    通过 GVA 真实注册接口创建临时用户，测试结束自动删除
    admin_register 接口直接返回 data.user（含 ID），无需再查列表
    清理时业务接口失败立即用 DB 兜底（GVA deleteUser 接口对部分角色组合会权限不足）
    :return: 用户对象 dict（含 ID/userName/authorityId 等真实字段）
    """
    username = f"auto_{uuid.uuid4().hex[:8]}"
    password = "Test1234!"
    resp = user_api.admin_register(
        username=username,
        password=password,
        nick_name=username,
    )
    if resp.json().get("code") != 0:
        raise APIException(
            f"测试用户注册失败: {resp.json()}",
            resp.status_code,
            resp,
        )
    # admin_register 直接返回 data.user 对象（含 ID 等字段）
    user = resp.json()["data"]["user"]
    logger.info(f"[Fixture] 已创建临时用户: {username} (ID={user.get('ID')})")
    yield user
    # 清理：先试业务接口，失败立即用 DB 兜底
    try:
        del_resp = user_api.delete_user(user["ID"])
        if del_resp.json().get("code") == 0:
            logger.info(f"[Fixture] 已删除临时用户: {username}")
        else:
            logger.warning(f"[Fixture] 业务删除返回非0: {del_resp.json()}, 用 DB 兜底")
            db_client.execute(
                "DELETE FROM sys_user_authority WHERE sys_user_id = %s",
                (user["ID"],),
            )
            db_client.execute(
                "DELETE FROM sys_users WHERE id = %s",
                (user["ID"],),
            )
    except Exception as e:
        logger.warning(f"[Fixture] 业务接口删除异常，DB 兜底: {e}")
        db_client.execute(
            "DELETE FROM sys_user_authority WHERE sys_user_id = %s",
            (user["ID"],),
        )
        db_client.execute(
            "DELETE FROM sys_users WHERE id = %s",
            (user["ID"],),
        )

