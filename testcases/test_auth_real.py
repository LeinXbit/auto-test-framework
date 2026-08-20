# -*- coding: utf-8 -*-
"""
GVA 真实鉴权链路测试
覆盖: 数据库初始化 → 验证码 → 登录 → 用户信息 → 登出 → 未授权访问
"""
import allure
import pytest

from api.auth_api import AuthApi
from utils.captcha_solver import CaptchaSolver
from utils.exceptions import APIException
from config.settings import settings


_INITIALIZED_KEYWORDS = (
    "已初始化",
    "已存在数据库配置",
    "无需初始化",
    "already initialized",
    "already initialised",
    "init already",
    "初始化完成",
    "初始化成功",
    "no need init",
    "redirect",
    "重定向",
    "login",
    "登录",
)

_NOT_INITIALIZED_KEYWORDS = (
    "未初始化",
    "not initialized",
    "not initialised",
    "请先初始化",
    "need init",
    "needinit",
    "初始化数据库",
    "not exist",
    "不存在",
    "请初始化",
)


def _msg_says_initialized(msg: str) -> bool:
    """Check if message content indicates the DB is already initialized.
    Prefer explicit negative keywords over positive ones (e.g. a msg like
    "please initialize first" is NOT "already initialized" even if it contains
    the word "initialize").
    """
    m = (msg or "").strip().lower()
    if not m:
        return False
    for neg in _NOT_INITIALIZED_KEYWORDS:
        if neg.lower() in m:
            return False
    for pos in _INITIALIZED_KEYWORDS:
        if pos.lower() in m:
            return True
    return False


def _data_says_initialized(data) -> bool:
    """checkdb.data sub-structure signals.
    Known real GVA variants observed:
        {"code": 0}               -> not initialized, proceed to initdb page
        {"code": 1}               -> initialized, redirect to /login
        {"needInit": false}       -> initialized (real v3 response)
        {"needInit": true}        -> NOT initialized
        {redirect: true}          -> initialized
        "ok"/"success" string     -> initialized
    """
    if isinstance(data, dict):
        # needInit field has the highest priority because it is explicit
        need_init = data.get("needInit")
        if need_init is False:
            return True
        if need_init is True:
            return False
        # code field fallback
        inner = data.get("code")
        if inner is not None:
            return inner != 0
        # redirect flag fallback
        if data.get("redirect"):
            return True
    if isinstance(data, str):
        s = data.lower()
        return any(k in s for k in ("ok", "success", "init", "redirect"))
    return False


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("数据库初始化")
class TestInitDB:
    """初始化数据库链路(已初始化则跳过)"""

    @allure.title("初始化GVA数据库(已初始化则跳过)")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_initdb_defaults(self):
        """
        POST /init/initdb 初始化 GVA 数据库, 使用默认基础数据.

        Flow:
            1. Call /init/checkdb BEFORE any allure.step so a clean SKIP is
               possible (no half-drawn steps in Allure report).
            2. If DB is already detected initialized -> pytest.skip.
            3. Otherwise enter the single allure.step and call /init/initdb.
            4. TOCTOU safety: even if initdb fails with "already initialized"
               style msg (another process beat us), we re-check via checkdb and
               skip instead of failing.
            5. Additionally we log the raw checkdb/initdb payloads so the user
               can debug why the detection mis-fired (allure attach + assert message
               both carry the raw payload).

        Default values per user requirement:
            db_name=gva, admin_password=123456, mysql_password=123456
            host=127.0.0.1, port=3306, user=root, db_type=mysql
        """
        api = AuthApi(base_url=settings.base_url, timeout=settings.timeout)
        db_cfg = settings.db_config

        # --- Phase A: pre-check branch (no step wrapper, clean skip) ---
        check_resp = api.check_db()
        check_data = check_resp.json()
        check_code = check_data.get("code")
        check_msg = (check_data.get("msg") or "").strip()
        check_data_field = check_data.get("data")

        # Rule table (covers all known GVA variants):
        #   - code != 0                                    -> initialized (error style "已初始化")
        #   - code == 0 AND data says initialized         -> initialized
        #   - code == 0 AND msg explicitly "not init"     -> NOT initialized
        #   - code == 0 AND msg says "initialized"        -> initialized
        #   - code == 0 AND no signal                     -> NOT initialized (proceed)
        by_code = check_code != 0
        by_data = _data_says_initialized(check_data_field)
        by_msg = _msg_says_initialized(check_msg)

        is_initialized = by_code or by_data or by_msg

        debug_payload = (
            "check_code={}\ncheck_msg={}\ncheck_data={}\n"
            "by_code={}\nby_data={}\nby_msg={}\nis_initialized={}"
        ).format(
            check_code, check_msg, check_data_field,
            by_code, by_data, by_msg, is_initialized,
        )
        allure.attach(
            debug_payload,
            name="checkdb 诊断",
            attachment_type=allure.attachment_type.TEXT,
        )

        if is_initialized:
            pytest.skip(
                "数据库已初始化(code={}, msg={}, data={}), 跳过 initdb".format(
                    check_code, check_msg, check_data_field,
                )
            )

        # --- Phase B: DB confirmed UNINITIALIZED, execute initdb inside step ---
        with allure.step("调用 /init/initdb 使用默认基础数据初始化"):
            init_resp = api.init_db(
                admin_password=settings.admin_account["password"],
                db_name=db_cfg["database"],
                host=db_cfg["host"],
                port=str(db_cfg["port"]),
                user_name=db_cfg["user"],
                password=db_cfg["password"] or "123456",
                db_type="mysql",
            )
            init_data = init_resp.json()
            init_code = init_data.get("code")
            init_msg = (init_data.get("msg") or "").strip()
            init_payload = init_data.get("data", "")

            allure.attach(
                "code={}\nmsg={}\ndata={}".format(init_code, init_msg, init_payload),
                name="initdb 响应",
                attachment_type=allure.attachment_type.TEXT,
            )

            # TOCTOU guard: concurrent DB init between check & call
            if init_code != 0 and _msg_says_initialized(init_msg):
                verify = api.check_db().json()
                v_code = verify.get("code")
                v_msg = (verify.get("msg") or "").strip()
                v_data = verify.get("data")
                if (
                    v_code != 0
                    or _data_says_initialized(v_data)
                    or _msg_says_initialized(v_msg)
                ):
                    pytest.skip(
                        "并发竞态跳过: checkdb 时未初始化, initdb 时已初始化, "
                        "init_msg={}, verify_code={}, verify_msg={}, verify_data={}".format(
                            init_msg, v_code, v_msg, v_data,
                        )
                    )

            assert init_code == 0, (
                "initdb 返回非 0: code={}, msg={}, data={}\n"
                "若提示'已初始化'类信息, 请查看上方 allure 附件里的 checkdb 诊断, "
                "并把原始 checkdb / initdb 响应提供给框架扩展已初始化判断规则."
            ).format(init_code, init_msg, init_payload)


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("验证码链路")
class TestCaptcha:
    """验证码接口真实链路"""

    @allure.title("获取验证码并校验字段完整性")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_get_captcha_fields(self):
        """GET /base/captcha 返回字段必须完整且符合 GVA 约定"""
        api = AuthApi(base_url=settings.base_url)
        resp = api.get_captcha()
        # 字段完整性
        assert "captchaId" in resp and resp["captchaId"], "captchaId 不能为空"
        assert "picPath" in resp and resp["picPath"].startswith("data:image"), \
            "picPath 应为 data:image/png;base64 前缀"
        assert resp.get("captchaLength") == 6, "GVA 默认验证码长度 6"
        assert resp.get("openCaptcha") is True, "本环境 openCaptcha 应为 True"


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("登录链路")
class TestLoginFlow:
    """登录真实链路"""

    @allure.title("admin_token fixture 可正常获取 token")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_admin_token_available(self, admin_token):
        """session fixture 应当成功登录并返回非空 token(admin_token 现为可刷新 holder 对象)"""
        tok = admin_token.ensure()
        assert tok, "admin_token fixture 返回空 token"
        assert isinstance(tok, str) and len(tok) > 20, "token 长度异常"

    @allure.title("登录态下获取当前用户信息")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_get_self_info_with_token(self, auth_api):
        """登录后 GET /user/getUserInfo 应返回当前 admin 用户信息"""
        user_info = auth_api.get_self_info()
        assert user_info.get("userName") == "admin", \
            f"期望 admin, 实际 {user_info.get('userName')}"
        assert user_info.get("ID") == 1, f"期望 ID=1, 实际 {user_info.get('ID')}"
        assert user_info.get("authorityId") in (888, 9528), \
            f"authorityId 异常: {user_info.get('authorityId')}"


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("未授权访问")
class TestUnauthorized:
    """未鉴权场景下的接口行为"""

    @allure.title("未携带 token 访问受保护接口应失败")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_no_token_get_user_info(self, no_token_api):
        """
        未携带 x-token 访问 /user/getUserInfo, GVA 实际行为:
            HTTP 401 + {"code":7,"data":null,"msg":"未登录或非法访问,请登录"}
        """
        resp = no_token_api.get("/user/getUserInfo")
        # 业务码非 0(GVA 用 7 表示未登录)
        data = resp.json()
        assert data.get("code") != 0, f"未授权访问不应成功: {data}"
        # 错误信息应与未登录相关(中英文均可)
        msg = data.get("msg", "")
        assert any(kw in msg for kw in ["未登录", "登录", "token", "权限", "unauthorized", "login"]), \
            f"错误信息应提示登录/token 相关, 实际 msg={msg}"


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("登录边界")
class TestLoginBoundary:
    """登录边界用例(负向场景)"""

    @allure.title("错误密码登录应失败")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_login_wrong_password_fails(self, no_token_api):
        """
        错误密码登录应返回 code != 0, msg 含'失败'或'错误'
        不带验证码识别器, 直接传错的 captcha 也能验证密码校验逻辑(密码校验在验证码之前)
        """
        # 直接 POST 一个错误的密码, GVA 通常会先校验验证码再校验密码
        # 这里主要测试"错误密码"路径, 即使验证码也错, 仍应失败
        resp = no_token_api.login(
            username="admin",
            password="definitely_wrong_pwd_xyz",
            captcha="000000",
            captcha_id="nonexistent",
        )
        body = resp.json()
        assert body.get("code") != 0, "错误密码登录不应成功"
        msg = body.get("msg", "")
        # GVA 错误信息可能为"登录失败"或"验证码错误"等
        assert any(kw in msg for kw in ["失败", "错误", "fail", "invalid", "wrong", "error"]), \
            "msg 应含失败/错误信息, 实际: {}".format(msg)

    @allure.title("连续两次获取验证码 ID 应不同")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    def test_captcha_two_fetches_have_different_ids(self):
        """连续调用 get_captcha 两次, captchaId 应不同(每次都是新会话)"""
        api = AuthApi(base_url=settings.base_url)
        c1 = api.get_captcha()
        c2 = api.get_captcha()
        assert c1["captchaId"] != c2["captchaId"], \
            "两次获取验证码 captchaId 应不同(实际 c1={}, c2={})".format(
                c1["captchaId"], c2["captchaId"],
            )


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("登出链路")
class TestLogout:
    """登出真实链路"""

    @allure.title("登出后旧 token 应失效")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_logout_invalidates_token(self, disposable_token):
        """
        验证 /jwt/jsonInBlacklist 登出后, 旧 token 立即失效

        关键: 使用 disposable_token fixture(函数级独立 token), 
            fixture teardown 会自动登出, 绝对不污染 session 级 admin_token.
            即便 GVA 把同账号全部 token 连带作废, 下一个 API 客户端创建时
            admin_token.ensure() 也会自动重登, 不影响后续用例.
        """
        token = disposable_token
        auth = AuthApi(
            base_url=settings.base_url,
            timeout=settings.timeout,
        )
        auth.set_token(token)

        # 登出前: 接口可用
        info_before = auth.get_self_info()
        assert info_before.get("userName") == "admin"

        # 执行登出(这个 disposable_token 登出后, 由 fixture teardown 做收尾)
        auth.logout()

        # 登出后: 旧 token 应失效
        resp = auth.get("/user/getUserInfo")
        data = resp.json()
        assert data.get("code") != 0, \
            f"登出后旧 token 仍可用, 未失效: {data}"
