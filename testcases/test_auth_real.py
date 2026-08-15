# -*- coding: utf-8 -*-
"""
GVA 真实鉴权链路测试（对接本地 http://127.0.0.1:8888）
覆盖：验证码、登录、用户信息、登出、未授权访问
"""
import allure
import pytest

from utils.exceptions import APIException


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("验证码链路")
class TestCaptcha:
    """验证码生成接口测试"""

    @allure.title("获取验证码并校验字段完整性")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_get_captcha_fields(self):
        """验证 /base/captcha 返回字段齐全，openCaptcha 为 True"""
        from api.auth_api import AuthApi

        with allure.step("步骤1：构造未鉴权客户端"):
            api = AuthApi(base_url="http://127.0.0.1:8888")
            allure.attach("BaseApi 不带 token", "客户端类型")

        with allure.step("步骤2：调用 /base/captcha"):
            resp = api.get_captcha()
            allure.attach(str(resp), "完整响应")

        with allure.step("步骤3：断言关键字段"):
            assert "captchaId" in resp and resp["captchaId"], "captchaId 不能为空"
            assert "picPath" in resp and resp["picPath"].startswith("data:image"), \
                "picPath 应为 data:image/png;base64 前缀"
            assert resp.get("captchaLength") == 6, "GVA 默认验证码长度 6"
            assert resp.get("openCaptcha") is True, "本环境 openCaptcha 应为 True"

        allure.attach(
            f"captchaId={resp['captchaId']}\nlength={resp['captchaLength']}\nopen={resp['openCaptcha']}",
            "验证码元信息"
        )


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("登录链路")
class TestLoginFlow:
    """登录链路测试：使用 session 级 admin_token fixture"""

    @allure.title("admin 登录后 token 非空且可用")
    @allure.severity(allure.severity_level.BLOCKER)
    @pytest.mark.smoke
    def test_admin_token_available(self, admin_token):
        """验证 session 级 admin_token 成功获取"""
        with allure.step("步骤1：检查 admin_token 已注入"):
            assert admin_token, "admin_token 不应为空"
            assert isinstance(admin_token, str) and len(admin_token) > 20, \
                "token 应为长度 > 20 的 JWT 字符串"
            allure.attach(f"{admin_token[:30]}...", "token 前缀")

        with allure.step("步骤2：token 应是 JWT 格式（含两个点）"):
            assert admin_token.count(".") == 2, "JWT 由 header.payload.signature 组成，应包含 2 个点"

    @allure.title("使用 token 获取当前用户信息")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.smoke
    @pytest.mark.api
    def test_get_self_info_with_token(self, auth_api):
        """使用 admin token 调用 /user/getUserInfo，应返回 admin 用户信息"""
        with allure.step("步骤1：调用 /user/getUserInfo"):
            resp = auth_api.get_self_info()
            allure.attach(str(resp), "用户信息")

        with allure.step("步骤2：断言用户名是 admin"):
            assert resp.get("userName") == "admin", \
                f"期望 admin, 实际 {resp.get('userName')}"
            assert resp.get("nickName"), "nickName 不应为空"
            assert resp.get("authorityId") is not None, "authorityId 不应为空"

        allure.attach(
            f"userName={resp.get('userName')}\nnickName={resp.get('nickName')}\nauthorityId={resp.get('authorityId')}",
            "用户关键字段"
        )


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("未授权访问")
class TestUnauthorized:
    """未授权访问负向用例"""

    @allure.title("未携带 token 访问受保护接口应失败")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_no_token_get_user_info(self, no_token_client):
        """未携带 x-token 调用 /user/getUserInfo 应返回 401 或业务错误"""
        with allure.step("步骤1：未鉴权调用受保护接口"):
            resp = no_token_client.get_user_info()
            allure.attach(f"HTTP {resp.status_code}\n{resp.text}", "响应")

        with allure.step("步骤2：断言未被授权"):
            # GVA 对未授权访问的常见表现：HTTP 401 或业务 code != 0
            is_http_unauthorized = resp.status_code == 401
            try:
                body = resp.json()
                is_business_fail = body.get("code") != 0
                err_msg = body.get("msg", "")
            except Exception:
                body, is_business_fail, err_msg = {}, False, ""

            assert is_http_unauthorized or is_business_fail, \
                f"未授权访问应失败，实际 status={resp.status_code}, body={body}"

            allure.attach(
                f"status={resp.status_code}\ncode={body.get('code') if body else 'N/A'}\nmsg={err_msg}",
                "未授权响应"
            )


@allure.epic("GVA 真实业务测试")
@allure.feature("鉴权模块")
@allure.story("登出黑名单")
class TestLogout:
    """JWT 黑名单（登出）测试"""

    @allure.title("登出后旧 token 不可再访问受保护接口")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    def test_logout_invalidates_token(self):
        """
        端到端：单独登录拿 token -> 用 token 验证可用 -> 登出 -> 用旧 token 应失败
        使用独立 AuthApi 实例，不污染 session 级 admin_token
        """
        from api.auth_api import AuthApi
        from config.settings import settings
        from utils.captcha_solver import CaptchaSolver

        with allure.step("步骤1：独立登录获取临时 token"):
            cfg = settings.captcha_config
            solver = CaptchaSolver(
                expected_length=cfg.get("expected_length", 6),
                max_retry=cfg.get("max_retry", 5),
            )
            auth = AuthApi(
                base_url=settings.base_url,
                timeout=settings.timeout,
                captcha_solver=solver,
            )
            token = auth.login_with_retry(
                username=settings.admin_account["username"],
                password=settings.admin_account["password"],
                max_round=3,
            )
            allure.attach(f"{token[:30]}...", "临时 token")

        with allure.step("步骤2：验证 token 可用"):
            auth.set_token(token)
            user_info = auth.get_self_info()
            assert user_info.get("userName") == "admin", "登录态下应能获取用户信息"
            allure.attach(str(user_info), "登录态用户信息")

        with allure.step("步骤3：调用 /jwt/jsonInBlacklist 登出"):
            logout_resp = auth.logout()
            allure.attach(str(logout_resp.json()), "登出响应")

        with allure.step("步骤4：用旧 token 再次访问应失败"):
            resp = auth.get("/user/getUserInfo")
            allure.attach(f"HTTP {resp.status_code}\n{resp.text}", "旧 token 响应")

            is_http_401 = resp.status_code == 401
            try:
                is_business_fail = resp.json().get("code") != 0
            except Exception:
                is_business_fail = False

            assert is_http_401 or is_business_fail, \
                f"登出后旧 token 应失效，实际 status={resp.status_code}, body={resp.text}"

        allure.attach("登出黑名单生效", "测试结论")
