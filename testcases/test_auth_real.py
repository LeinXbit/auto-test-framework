# -*- coding: utf-8 -*-
"""
GVA 真实鉴权链路测试
覆盖: 验证码 → 登录 → 用户信息 → 登出 → 未授权访问
"""
import allure
import pytest

from api.auth_api import AuthApi
from utils.captcha_solver import CaptchaSolver
from utils.exceptions import APIException
from config.settings import settings


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
