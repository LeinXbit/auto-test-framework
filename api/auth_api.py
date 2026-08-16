# -*- coding: utf-8 -*-
"""
GVA 鉴权模块接口封装
    - 获取验证码 /base/captcha
    - 登录        /base/login
    - 登出（JWT 加入黑名单） /jwt/jsonInBlacklist
    - 获取当前用户信息 /user/getUserInfo
    - 修改密码    /user/changePassword
"""
from utils.exceptions import APIException
from utils.logger import get_logger
from api.base_api import BaseApi

logger = get_logger(__name__)


class AuthApi(BaseApi):
    """GVA 鉴权客户端"""

    def __init__(self, base_url, timeout=10, captcha_solver=None):
        super().__init__(base_url, timeout)
        self.solver = captcha_solver

    #  验证码

    def get_captcha(self):
        """
        获取验证码
        :return: dict {captchaId, picPath, captchaLength, openCaptcha}
        """
        resp = self.post("/base/captcha", json={})
        self.assert_business_success(resp)
        data = resp.json()["data"]
        logger.info(
            f"获取验证码成功: captchaId={data.get('captchaId')}, "
            f"openCaptcha={data.get('openCaptcha')}, length={data.get('captchaLength')}"
        )
        return data

    #  登录

    def login(self, username, password, captcha=None, captcha_id=None):
        """
        GVA 登录接口
        :return: requests.Response
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
        自动识别验证码并登录（单次尝试，验证码识别失败将抛错）
        :return: token (str)
        """
        if self.solver is None:
            raise APIException("未配置验证码识别器，无法自动登录")

        def fetch_captcha():
            data = self.get_captcha()
            return data["picPath"], data["captchaId"]

        # 首次获取一次以同步期望长度
        sample = self.get_captcha()
        expected_length = sample.get("captchaLength") or self.solver.expected_length
        self.solver.expected_length = expected_length

        code, captcha_id = self.solver.solve_with_retry(fetch_captcha)
        resp = self.login(username, password, captcha=code, captcha_id=captcha_id)

        try:
            data = resp.json()
        except Exception as e:
            raise APIException(f"登录响应不是合法 JSON: {e}", resp.status_code, resp)

        if resp.status_code != 200 or data.get("code") != 0:
            err = f"登录失败: code={data.get('code')}, msg={data.get('msg')}"
            logger.error(err)
            raise APIException(err, resp.status_code, resp)

        token = data["data"]["token"]
        logger.info(f"登录成功: username={username}, token={token[:30]}...")
        return token

    def login_with_retry(self, username, password, max_round=3):
        """
        多轮登录尝试：单轮验证码识别失败/登录失败时整体重试
        用于 fixture 自动登录时容忍 OCR 偶发失败
        """
        last_err = None
        for round_no in range(1, max_round + 1):
            try:
                token = self.login_with_captcha(username, password)
                if round_no > 1:
                    logger.info(f"登录在第 {round_no} 轮成功")
                return token
            except Exception as e:
                last_err = e
                logger.warning(f"第 {round_no} 轮登录失败: {e}")
        raise APIException(f"登录失败（已重试 {max_round} 轮）: {last_err}")

    #  登出 / JWT 黑名单

    def logout(self):
        """把当前 token 加入 JWT 黑名单，立即失效"""
        resp = self.post("/jwt/jsonInBlacklist", json={})
        self.assert_business_success(resp)
        logger.info("登出成功，token 已加入黑名单")
        return resp

    #  当前用户信息

    def get_self_info(self):
        """
        获取当前登录用户信息
        GVA 实际响应结构: {"code":0,"data":{"userInfo":{...}}}
        """
        resp = self.get("/user/getUserInfo")
        self.assert_business_success(resp)
        return resp.json()["data"]["userInfo"]

    #  修改密码

    def change_password(self, username, password, new_password):
        payload = {
            "username": username,
            "password": password,
            "newPassword": new_password,
        }
        return self.put("/user/changePassword", json=payload)
