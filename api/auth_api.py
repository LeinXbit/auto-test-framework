# -*- coding: utf-8 -*-
"""鉴权模块接口封装：GVA 登录链路 /base/captcha /base/login /jwt/jsonInBlacklist"""
from api.base_api import BaseApi
from utils.captcha_solver import CaptchaSolver
from utils.exceptions import APIException
from utils.logger import get_logger

logger = get_logger(__name__)


class AuthApi(BaseApi):
    """
    GVA 鉴权模块：封装验证码、登录、登出
    """

    def __init__(self, base_url, timeout=10, captcha_solver: CaptchaSolver = None):
        super().__init__(base_url, timeout)
        self.solver = captcha_solver

    # ===== 验证码 =====

    def get_captcha(self):
        """
        获取验证码
        :return: dict {captchaId, picPath, captchaLength, openCaptcha}
        """
        resp = self.post("/base/captcha", json={})
        self.assert_business_success(resp)
        data = resp.json()["data"]
        logger.info(
            f"获取验证码成功: captchaId={data['captchaId']}, "
            f"openCaptcha={data.get('openCaptcha')}, length={data.get('captchaLength')}"
        )
        return data

    # ===== 登录 =====

    def login(self, username, password, captcha=None, captcha_id=None):
        """
        用户登录
        :param username:
        :param password:
        :param captcha: 验证码文本（开启验证码时必传）
        :param captcha_id: 验证码 id（开启验证码时必传）
        :return: GVA 统一响应，data 中含 user 与 token
        """
        payload = {
            "username": username,
            "password": password,
            "captcha": captcha or "",
            "captchaId": captcha_id or "",
        }
        return self.post("/base/login", json=payload)

    def login_with_captcha(self, username, password):
        """
        自动处理验证码的登录流程：
            1. 拉取验证码
            2. OCR 识别（带重试）
            3. 调用登录
        :param username:
        :param password:
        :return: token 字符串
        :raises APIException: 登录失败
        """
        if self.solver is None:
            raise APIException("未配置验证码识别器，无法自动登录")

        def fetch_captcha():
            data = self.get_captcha()
            return data["picPath"], data["captchaId"]

        # 期望长度根据服务端 captchaLength 决定（GVA 默认 6）
        sample = self.get_captcha()
        expected_length = sample.get("captchaLength") or self.solver.expected_length
        self.solver.expected_length = expected_length

        # 用 solve_with_retry 拿到合法长度的验证码
        code, captcha_id = self.solver.solve_with_retry(fetch_captcha)

        resp = self.login(username, password, captcha=code, captcha_id=captcha_id)
        if resp.status_code != 200 or resp.json().get("code") != 0:
            # 登录失败可能是 OCR 误识，调用方应做整体重试
            raise APIException(
                f"登录失败: code={resp.json().get('code')}, msg={resp.json().get('msg')}",
                resp.status_code, resp
            )

        token = resp.json()["data"]["token"]
        logger.info(f"登录成功: username={username}, token={token[:20]}...")
        return token

    def login_with_retry(self, username, password, max_round=3):
        """
        完整登录重试：单次 OCR 识别不一定准，整体重试拿到 token
        :param username:
        :param password:
        :param max_round: OCR + 登录的整体重试轮数
        :return: token
        """
        last_err = None
        for i in range(1, max_round + 1):
            try:
                return self.login_with_captcha(username, password)
            except APIException as e:
                last_err = e
                logger.warning(f"第 {i}/{max_round} 轮登录失败: {e.args[0] if e.args else e}")
        raise APIException(f"多次登录重试均失败: {last_err}")

    # ===== 登出 =====

    def logout(self):
        """将当前 token 加入黑名单（登出）"""
        resp = self.post("/jwt/jsonInBlacklist", json={})
        self.assert_business_success(resp)
        logger.info("登出成功，token 已加入黑名单")
        return resp

    # ===== 当前用户信息 =====

    def get_self_info(self):
        """
        获取当前登录用户信息
        GVA 实际响应结构: {"code":0,"data":{"userInfo":{...}}}
        """
        resp = self.get("/user/getUserInfo")
        self.assert_business_success(resp)
        return resp.json()["data"]["userInfo"]
