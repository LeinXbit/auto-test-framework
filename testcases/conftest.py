# -*- coding: utf-8 -*-
"""
GVA test suite global fixtures
    - admin_token: session-level holder with "refresh-on-request" capability.
                          When BaseApi detects GVA code=7/HTTP 401, the callback forces
                          a re-login to get a new token and replays the original request,
                          eliminating the TOCTOU race caused by single-point logout.
    - auth_api: auth client with admin token injected (auto-refresh callback bound)
    - user_api: user mgmt client with admin token injected (auto-refresh callback bound)
    - db_client: GVA DB connection (for assertions on real tables like sys_users)
    - no_token_api: unauthenticated client (for negative cases: 401 scenarios)
    - temp_user: function-scoped; creates a temp user via real register API, auto-cleans on teardown
    - disposable_token: function-scoped one-shot independent token for logout/invalidation cases
"""
import sys
import uuid
import threading
from pathlib import Path

# Auto-add .vendor to sys.path so the project can load ddddocr/allure/yaml/pymysql
# without polluting system Python.
# Order: project root takes precedence over .vendor so api/* / config/* / utils/*
# are always loaded from the project root. This avoids module mix-ups when
# PYTHONPATH=.vendor is set.
_VENDOR = Path(__file__).resolve().parent.parent / ".vendor"
_PROJ = Path(__file__).resolve().parent.parent
if _VENDOR.exists():
    if str(_PROJ) not in sys.path:
        sys.path.insert(0, str(_PROJ))
    if str(_VENDOR) not in sys.path:
        sys.path.insert(1, str(_VENDOR))

import pytest

from api.auth_api import AuthApi
from api.authority_api import AuthorityApi
from api.user_api import UserApi
from api.menu_api import MenuApi
from api.system_api import SystemApi
from api.file_api import FileApi
from api.sysop_api import SysOpApi
from config.settings import settings
from db.mysql_client import MySQLClient
from utils.captcha_solver import CaptchaSolver
from utils.exceptions import APIException
from utils.logger import get_logger

logger = get_logger(__name__)


# Session level: admin token / captcha solver
#
# Why we need BaseApi.on_token_expired callback + force_renew:
# GVA /jwt/jsonInBlacklist invalidates all tokens of the same account at once
# (single sign-on policy). When disposable_token teardown logs out, the
# session-level admin_token is invalidated as a side effect. A preflight
# _check_alive probe in ensure() can catch most cases but still leaves a TOCTOU
# race (probe passes -> logout invalidates -> actual call hits 401).
# Fix: BaseApi request layer detects 401/code=7 and calls on_token_expired to
# force_renew() (re-login) and replay the original request, with no race window.


class _RefreshingAdminToken:
    """
    Refreshable session-level admin token container.

    Usage:
        holder.ensure()       -> returns current token (auto-login on first call), no liveness probe
        holder.force_renew()  -> ignores current state, re-logins and returns new token (for on_token_expired callback)
    """

    def __init__(self, captcha_solver_):
        self.solver = captcha_solver_
        self._lock = threading.Lock()
        self._token = None
        # Keep the last valid token for session teardown logout
        self._last_valid = None

    # Internal

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

    # Public

    def ensure(self):
        """
        Returns the current usable token. Auto-login on first call.
        Note: this method does NOT do an HTTP liveness probe (TOCTOU risk); token
              invalidation is handled in BaseApi.request, which calls force_renew on code=7.
        """
        with self._lock:
            if self._token is None:
                logger.info("[Token] first login to obtain admin token")
                self._token = self._login_once()
                self._last_valid = self._token
            return self._token

    def force_renew(self):
        """
        Re-login regardless of the current token state; returns the new token string.
        Called by BaseApi.on_token_expired callback when 401/code=7 is hit.
        """
        with self._lock:
            logger.info("[Token] force re-login admin (from on_token_expired callback)")
            self._token = self._login_once()
            self._last_valid = self._token
            return self._token

    def session_token_for_logout(self):
        """For session teardown: returns the last valid token to attempt logout"""
        return self._last_valid


@pytest.fixture(scope="session")
def captcha_solver():
    """Captcha solver (session-scoped to avoid reloading the ddddocr model)"""
    cfg = settings.captcha_config
    return CaptchaSolver(
        expected_length=cfg.get("expected_length"),
        max_retry=cfg.get("max_retry", 5),
    )


@pytest.fixture(scope="session")
def admin_token(captcha_solver):
    """
    Session-level admin token (refreshable holder object)
    - First ensure() logs in; no preflight HTTP liveness probe afterwards (TOCTOU risk)
    - BaseApi.on_token_expired callback force_renews and replays on 401/code=7
    - Teardown: attempts to logout the last valid token (failure only warns, does not block)
    """
    holder = _RefreshingAdminToken(captcha_solver)
    # First login: surface environment issues early (account / password / captcha)
    holder.ensure()
    yield holder
    # session teardown: logout the last valid token
    final_token = holder.session_token_for_logout()
    if final_token:
        auth = AuthApi(base_url=settings.base_url, timeout=settings.timeout)
        auth.set_token(final_token)
        try:
            auth.logout()
            logger.info("[Session] admin 已登出")
        except Exception as e:
            logger.warning("[Session] 登出失败(不影响测试结果): {}".format(e))


def _bind_auto_refresh(api_client, admin_token_holder):
    """
    Bind on_token_expired callback to an API client: when a request hits 401/code=7,
    auto force-relogin and let BaseApi replay the original request.
    """
    api_client.on_token_expired = admin_token_holder.force_renew


# Function-scoped API clients (authenticated, auto-refresh callback bound)

@pytest.fixture(scope="function")
def auth_api(admin_token):
    """Auth client with admin token injected (auto-refresh callback bound)"""
    api = AuthApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def user_api(admin_token):
    """User mgmt client with admin token injected (auto-refresh callback bound)"""
    api = UserApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def authority_api(admin_token):
    """Authority (role) mgmt client with admin token injected (auto-refresh callback bound)"""
    api = AuthorityApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def no_token_api():
    """Unauthenticated client (for negative cases: 401 / unauthorized scenarios)"""
    return AuthApi(base_url=settings.base_url, timeout=settings.timeout)


@pytest.fixture(scope="function")
def menu_api(admin_token):
    """Menu management client with admin token injected (auto-refresh callback bound)"""
    api = MenuApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def system_api(admin_token):
    """System management client with admin token injected (auto-refresh callback bound)"""
    api = SystemApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def file_api(admin_token):
    """File upload & download client with admin token injected (auto-refresh callback bound)"""
    api = FileApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def sysop_api(admin_token):
    """Audit log (SysOperationRecord) client with admin token injected (auto-refresh callback bound)"""
    api = SysOpApi(base_url=settings.base_url, timeout=settings.timeout)
    api.set_token(admin_token.ensure())
    _bind_auto_refresh(api, admin_token)
    yield api


@pytest.fixture(scope="function")
def disposable_token(captcha_solver):
    """
    One-shot independent token (function-scoped; never pollutes admin_token)
    Used by logout / invalidation cases; auto-logs-out on teardown.

    Note: even if GVA invalidates other tokens of the same account (single sign-on),
          any subsequent auth_api/user_api request will hit 401/code=7 and auto re-login
          + replay via on_token_expired, so tests are not affected.
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
    # function teardown: logout with this independent token; does not affect admin_token
    auth.set_token(token)
    try:
        auth.logout()
        logger.info("[Disposable] 一次性 admin token 已登出")
    except Exception as e:
        logger.warning("[Disposable] 一次性 token 登出失败(不影响): {}".format(e))


# Database

@pytest.fixture(scope="function")
def db_client():
    """
    GVA DB connection (function-scoped to avoid long-connection drops)
    Used for assertions on real tables like sys_users
    """
    client = MySQLClient(**settings.db_config)
    yield client
    client.close()


# Business data isolation: temp user

@pytest.fixture(scope="function")
def temp_user(user_api, db_client):
    """
    Create a temp user via the real GVA register API; auto-delete on test teardown.
    admin_register directly returns data.user (includes ID), so no extra list query is needed.
    On cleanup, if the business API fails, fall back to DB (GVA deleteUser may lack
    permissions for some role combinations).
    :return: user object dict (includes ID / userName / authorityId and other real fields)
    """
    username = "auto_{}".format(uuid.uuid4().hex[:8])
    password = "Test1234!"
    resp = user_api.admin_register(
        username=username,
        password=password,
        nick_name=username,
    )
    if resp.json().get("code") != 0:
        raise APIException(
            "测试用户注册失败: {}".format(resp.json()),
            resp.status_code,
            resp,
        )
    # admin_register directly returns the data.user object (includes ID etc.)
    user = resp.json()["data"]["user"]
    logger.info("[Fixture] 已创建临时用户: {} (ID={})".format(username, user.get("ID")))
    yield user
    # Cleanup: try business API first, fall back to DB on failure
    try:
        del_resp = user_api.delete_user(user["ID"])
        if del_resp.json().get("code") == 0:
            logger.info("[Fixture] 已删除临时用户: {}".format(username))
        else:
            logger.warning("[Fixture] 业务删除返回非0: {}, 用 DB 兜底".format(del_resp.json()))
            db_client.execute(
                "DELETE FROM sys_user_authority WHERE sys_user_id = %s",
                (user["ID"],),
            )
            db_client.execute(
                "DELETE FROM sys_users WHERE id = %s",
                (user["ID"],),
            )
    except Exception as e:
        logger.warning("[Fixture] 业务接口删除异常, DB 兜底: {}".format(e))
        db_client.execute(
            "DELETE FROM sys_user_authority WHERE sys_user_id = %s",
            (user["ID"],),
        )
        db_client.execute(
            "DELETE FROM sys_users WHERE id = %s",
            (user["ID"],),
        )


# Business data isolation: temp authority (role)

@pytest.fixture(scope="function")
def temp_authority(authority_api, db_client):
    """
    Create a temp role via the real GVA createAuthority API; auto-delete on teardown.
    Uses a high-range authorityId (900000+) to avoid conflicts with real roles.
    On cleanup, if the business API fails, fall back to DB (sys_authorities table).
    :return: dict with authorityId / authorityName / parentId and other real fields
    """
    authority_id = 900000 + (uuid.uuid4().int % 100000)
    authority_name = "auto_role_{}".format(uuid.uuid4().hex[:6])
    resp = authority_api.create_authority(
        authority_id=authority_id,
        authority_name=authority_name,
        parent_id=0,
    )
    if resp.json().get("code") != 0:
        raise APIException(
            "测试角色创建失败: {}".format(resp.json()),
            resp.status_code,
            resp,
        )
    # createAuthority returns data.authority (includes full SysAuthority object)
    authority = resp.json()["data"].get("authority") or resp.json()["data"]
    authority["authorityId"] = authority["authorityId"] if "authorityId" in authority else authority_id
    logger.info("[Fixture] 已创建临时角色: {} (ID={})".format(authority_name, authority_id))
    yield authority
    # Cleanup: try business API first, fall back to DB
    try:
        del_resp = authority_api.delete_authority(authority_id)
        if del_resp.json().get("code") == 0:
            logger.info("[Fixture] 已删除临时角色: {}".format(authority_name))
        else:
            logger.warning("[Fixture] 业务删除角色返回非0: {}, 用 DB 兜底".format(del_resp.json()))
            db_client.execute(
                "DELETE FROM sys_authorities WHERE authority_id = %s",
                (authority_id,),
            )
    except Exception as e:
        logger.warning("[Fixture] 业务接口删除角色异常, DB 兜底: {}".format(e))
        db_client.execute(
            "DELETE FROM sys_authorities WHERE authority_id = %s",
            (authority_id,),
        )


# Business data isolation: temp menu (base menu)

@pytest.fixture(scope="function")
def temp_menu(menu_api, db_client):
    """
    Create a temp base menu via the real GVA addBaseMenu API; auto-delete on teardown.

    Note: GVA addBaseMenu returns data={} (no menu object, no ID). To obtain the
    real ID, we query getMenuList by the unique name and match by name field.
    On cleanup, the sys_authorities_menus link table may not exist in some GVA
    versions, so each DB delete is wrapped in its own try/except.
    :return: dict with ID / name / path / component and other real fields
    """
    name = MenuApi.random_menu_name()
    path = "/{}".format(name)
    component = "view/{}"
    resp = menu_api.add_base_menu(
        name=name,
        path=path,
        component=component,
        meta={"title": name, "icon": "el-icon-menu"},
    )
    if resp.json().get("code") != 0:
        raise APIException(
            "测试菜单创建失败: {}".format(resp.json()),
            resp.status_code,
            resp,
        )
    # addBaseMenu returns data={} in this GVA version; look up the real ID
    # via getMenuList matching by the unique name.
    body = resp.json()
    menu = body.get("data", {}).get("menu") or dict(body.get("data") or {})
    menu_id = menu.get("ID") or menu.get("id")
    if not menu_id:
        list_resp = menu_api.get_menu_list(page=1, page_size=500, keyword=name)
        # GVA getMenuList may return data as a flat list OR as {list, total, page}
        raw = list_resp.json().get("data")
        if isinstance(raw, list):
            items = raw
        elif isinstance(raw, dict):
            items = raw.get("list", []) or []
        else:
            items = []
        matched = [m for m in items if m.get("name") == name]
        if matched:
            menu_id = matched[0].get("ID") or matched[0].get("id")
            # Merge real DB record fields so downstream tests can use them
            menu.update(matched[0])
    if not menu_id:
        raise APIException(
            "菜单创建成功但无法解析真实 ID (GVA addBaseMenu 未返回 ID 且 getMenuList 未匹配): name={}".format(name),
            resp.status_code,
            resp,
        )
    menu["ID"] = menu_id
    logger.info("[Fixture] 已创建临时菜单: {} (ID={})".format(name, menu_id))
    yield menu
    # Cleanup: try business API first; DB fallback wrapped per-table to
    # tolerate missing sys_authorities_menus link table in some GVA versions.
    try:
        del_resp = menu_api.delete_base_menu(menu_id)
        if del_resp.json().get("code") == 0:
            logger.info("[Fixture] 已删除临时菜单: {}".format(name))
            return
        logger.warning("[Fixture] 业务删除菜单返回非0: {}, 用 DB 兜底".format(del_resp.json()))
    except Exception as e:
        logger.warning("[Fixture] 业务接口删除菜单异常, DB 兜底: {}".format(e))
    # DB fallback: link table first (if exists), then main table
    try:
        db_client.execute(
            "DELETE FROM sys_authorities_menus WHERE sys_base_menu_id = %s",
            (menu_id,),
        )
    except Exception as e_link:
        logger.warning("[Fixture] sys_authorities_menus 清理失败(表可能不存在): {}".format(e_link))
    try:
        db_client.execute(
            "DELETE FROM sys_base_menus WHERE id = %s",
            (menu_id,),
        )
    except Exception as e_main:
        logger.warning("[Fixture] sys_base_menus 清理失败: {}".format(e_main))


# Business data isolation: temp uploaded file

@pytest.fixture(scope="function")
def temp_file(file_api, db_client):
    """
    Upload a small text file via the real GVA upload API; auto-delete on teardown.

    Note: GVA /fileUploadAndDownload/upload returns code=0 but the file object's
    ID field is always 0 (a GVA quirk: the DB row is created but the response
    keeps the zero-value SysFile struct). To obtain the real ID needed for
    find/delete, we query getFileList by the unique url returned from upload.
    """
    content = "pytest temp file {}".format(uuid.uuid4().hex)
    resp = file_api.upload(
        file_bytes=content.encode("utf-8"),
        filename="pytest_{}.txt".format(uuid.uuid4().hex[:8]),
        content_type="text/plain",
    )
    try:
        body = resp.json()
    except Exception as e:
        raise APIException(
            "测试文件上传响应非合法 JSON: {}".format(e),
            resp.status_code,
            resp,
        )
    if body.get("code") != 0:
        raise APIException(
            "测试文件上传失败: {}".format(body),
            resp.status_code,
            resp,
        )
    file_info = body.get("data", {}).get("file") or body.get("data", {})
    # GVA returns ID=0 in upload response; look up the real ID via getFileList.
    # GVA getFileList keyword matches the name field, so we use the unique
    # filename (e.g. pytest_xxxxxxxx.txt) as keyword, then verify by url match.
    file_url = file_info.get("url") or ""
    file_name = file_info.get("name") or ""
    real_id = file_info.get("id") or file_info.get("ID")
    if (not real_id or real_id == 0) and file_name:
        list_resp = file_api.get_file_list(page=1, page_size=500, keyword=file_name)
        items = list_resp.json().get("data", {}).get("list", []) or []
        # Filter by url to ensure exact match (filename keyword may match partial)
        if file_url:
            matched = [m for m in items if m.get("url") == file_url]
        else:
            matched = [m for m in items if m.get("name") == file_name]
        if matched:
            real_id = matched[0].get("ID") or matched[0].get("id")
            # Merge the real DB record fields into file_info so downstream tests
            # can use file_info["ID"] / file_info["name"] / file_info["url"]
            file_info.update(matched[0])
    if not real_id or real_id == 0:
        raise APIException(
            "上传成功但无法解析真实文件 ID (GVA upload 返回 ID=0 且 getFileList 未匹配): name={} url={}".format(file_name, file_url),
            resp.status_code,
            resp,
        )
    # Normalize id field so tests can use file_info["ID"] consistently
    file_info["ID"] = real_id
    logger.info("[Fixture] 已上传临时文件: id={} name={}".format(real_id, file_info.get("name")))
    yield file_info
    # Cleanup: try business API first; skip if test already deleted the file
    if file_info.get("ID") is None:
        logger.info("[Fixture] 文件已被测试用例删除, 跳过清理")
        return
    try:
        file_api.delete_file(real_id)
        logger.info("[Fixture] 已删除临时文件: id={}".format(real_id))
    except Exception as e:
        logger.warning("[Fixture] 业务接口删除文件异常, 跳过 DB 兜底(文件不强制 DB 清理): {}".format(e))

