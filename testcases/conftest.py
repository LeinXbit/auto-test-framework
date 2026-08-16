# -*- coding: utf-8 -*-
"""
GVA 测试套件全局 Fixture
    - admin_token:    session 级 holder，带「请求时自动刷新」能力
                      当 BaseApi 检测到 GVA code=7/HTTP 401 时, 会通过回调
                      强制重登 admin 拿新 token 并重放原请求 —— 彻底根除单点登出
                      引发的「探测通过、使用时失效」TOCTOU 竞态
    - auth_api:       已注入 admin token 的鉴权客户端(已绑定自动刷新回调)
    - user_api:       已注入 admin token 的用户管理客户端(已绑定自动刷新回调)
    - db_client:      GVA 数据库连接（用于断言 sys_users 等真实表）
    - no_token_api:   未鉴权客户端(用于负向用例:401 场景)
    - temp_user:      函数级，通过 GVA 真实注册接口创建临时用户,测试结束自动清理
    - disposable_token: 函数级，一次性独立 token，专门用于登出/失效类用例
"""
import sys
import uuid
import threading
from pathlib import Path

# 自动把 .vendor 加入 sys.path，使本项目无需污染系统 Python 即可加载 ddddocr/allure/yaml/pymysql
# 顺序：项目根优先于 .vendor，确保 api/* / config/* / utils/* 永远从项目根加载，
# 避免在 PYTHONPATH=.vendor 场景下发生模块错乱
_VENDOR = Path(__file__).resolve().parent.parent / ".vendor"
_PROJ = Path(__file__).resolve().parent.parent
if _VENDOR.exists():
    if str(_PROJ) not in sys.path:
        sys.path.insert(0, str(_PROJ))
    if str(_VENDOR) not in sys.path:
        sys.path.insert(1, str(_VENDOR))

import pytest

from api.auth_api import AuthApi
from api.user_api import UserApi
from config.settings import settings
from db.mysql_client import MySQLClient
from utils.captcha_solver import CaptchaSolver
from utils.exceptions import APIException
from utils.logger import get_logger

logger = get_logger(__name__)


#  Session 级：admin token / captcha solver
#  -------------------------------------------------------------
#  为什么需要 BaseApi.on_token_expired 回调 + force_renew：
#  GVA /jwt/jsonInBlacklist 会把同账号的全部 token 一起失效（单点登录策略）。
#  disposable_token 在登出用例 teardown 时登出, 会连带作废 session 级 admin_token。
#  此前在 ensure() 里前置 _check_alive 探测虽可捕捉大部分, 但仍有 TOCTOU 竞态
#  (探测通过 → 登出作废 → 实际调用时已 401)。
#  解决：BaseApi 请求层命中 401/code=7 时通过 on_token_expired 回调触发
#        force_renew() 强制重登并立即换 token 重放原请求, 无竞态窗口。
#  -------------------------------------------------------------

class _RefreshingAdminToken:
    """
    可刷新的 session 级 admin token 容器

    用法:
        holder.ensure()       → 返回当前 token(首次自动登录), 不做活性探测
        holder.force_renew()  → 无视当前状态直接重登, 返回新 token (给 on_token_expired 回调用)
    """

    def __init__(self, captcha_solver_):
        self.solver = captcha_solver_
        self._lock = threading.Lock()
        self._token = None
        # 为 session teardown 保留最后一颗有效 token，用于登出
        self._last_valid = None

    # ---------- 内部 ----------

    def _login_once(self):
        auth = AuthApi(
            base_url=settings.base_url,
            timeout=settings.timeout,
            captcha_solver=self.solver,
        )
        return auth.login_with_retry(
            username=settings.admin_account["username"],
            password=settings.admin_account["password"],
            max_round=3,
        )

    # ---------- 对外 ----------

    def ensure(self):
        """
        返回当前可用 token。首次调用自动登录。
        注意: 本方法不做 HTTP 活性探测(有 TOCTOU 风险), token 失效检测
              统一交给 BaseApi.request 层, 命中 code=7 时调 force_renew 重登。
        """
        with self._lock:
            if self._token is None:
                logger.info("[Token] 首次登录获取 admin token")
                self._token = self._login_once()
                self._last_valid = self._token
            return self._token

    def force_renew(self):
        """
        无视当前 token 状态直接重登，返回新 token 字符串
        供 BaseApi.on_token_expired 回调在命中 401/code=7 时调用
        """
        with self._lock:
            logger.info("[Token] 强制重登 admin(来自 on_token_expired 回调)")
            self._token = self._login_once()
            self._last_valid = self._token
            return self._token

    def session_token_for_logout(self):
        """session teardown 用: 返回最后一颗曾有效的 token 尝试登出"""
        return self._last_valid


@pytest.fixture(scope="session")
def captcha_solver():
    """验证码识别器(session 级，避免反复加载 ddddocr 模型)"""
    cfg = settings.captcha_config
    return CaptchaSolver(
        expected_length=cfg.get("expected_length"),
        max_retry=cfg.get("max_retry", 5),
    )


@pytest.fixture(scope="session")
def admin_token(captcha_solver):
    """
    session 级 admin token（可刷新 holder 对象）
    - 首次 ensure() 登录; 此后不再前置 HTTP 活性探测(有 TOCTOU 风险)
    - 通过 BaseApi.on_token_expired 回调在请求层命中 401/code=7 时 force_renew 重登 + 重放
    - Teardown: 最后一次尝试把最后一颗有效 token 登出(失败仅告警,不阻塞)
    """
    holder = _RefreshingAdminToken(captcha_solver)
    # 首次登录: 尽早暴露环境问题(账号/密码/验证码)
    holder.ensure()
    yield holder
    # session teardown: 登出最后一颗有效 token
    final_token = holder.session_token_for_logout()
    if final_token:
        auth = AuthApi(base_url=settings.base_url, timeout=settings.timeout)
        auth.set_token(final_token)
        try:
            auth.logout()
            logger.info("[Session] admin 已登出")
        except Exception as e:
            logger.warning(f"[Session] 登出失败(不影响测试结果): {e}")


def _bind_auto_refresh(api_client, admin_token_holder):
    """
    给 API 客户端绑定 on_token_expired 回调: 请求命中 401/code=7 时自动
    强制重登拿新 token 并由 BaseApi 重放原请求。
    """
    api_client.on_token_expired = admin_token_holder.force_renew


#  函数级：API 客户端(已鉴权,已绑定自动刷新回调)

@pytest.fixture(scope="function")
def auth_api(admin_token):
    """已注入 admin token 的鉴权客户端(已绑定自动刷新回调)"""
    api = AuthApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def user_api(admin_token):
    """已注入 admin token 的用户管理客户端(已绑定自动刷新回调)"""
    api = UserApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def no_token_api():
    """未鉴权客户端(用于负向用例:401 / 未授权场景)"""
    return AuthApi(base_url=settings.base_url, timeout=settings.timeout)


@pytest.fixture(scope="function")
def disposable_token(captcha_solver):
    """
    一次性独立 token（函数级，绝对不污染 admin_token）
    用于登出/失效类用例：函数结束时自动登出

    注: 即便 GVA 会把同账号的其它 token 一起失效(单点登录), 下一个
    auth_api/user_api 的任何请求命中 401/code=7 后都会通过 on_token_expired
    自动重登并重放, 不再引发测试失败。
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
    # 函数结束: 用这个独立 token 登出，不影响 admin_token
    auth.set_token(token)
    try:
        auth.logout()
        logger.info("[Disposable] 一次性 admin token 已登出")
    except Exception as e:
        logger.warning(f"[Disposable] 一次性 token 登出失败(不影响): {e}")


#  数据库

@pytest.fixture(scope="function")
def db_client():
    """
    GVA 数据库连接(function 级，避免长连接断开)
    用于断言 sys_users 等真实表
    """
    client = MySQLClient(**settings.db_config)
    yield client
    client.close()


#  业务数据隔离：临时用户

@pytest.fixture(scope="function")
def temp_user(user_api, db_client):
    """
    通过 GVA 真实注册接口创建临时用户，测试结束自动删除
    admin_register 接口直接返回 data.user(含 ID)，无需再查列表
    清理时业务接口失败立即用 DB 兜底(GVA deleteUser 接口对部分角色组合会权限不足)
    :return: 用户对象 dict(含 ID/userName/authorityId 等真实字段)
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
        logger.warning(f"[Fixture] 业务接口删除异常, DB 兜底: {e}")
        db_client.execute(
            "DELETE FROM sys_user_authority WHERE sys_user_id = %s",
            (user["ID"],),
        )
        db_client.execute(
            "DELETE FROM sys_users WHERE id = %s",
            (user["ID"],),
        )
