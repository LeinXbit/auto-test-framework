# -*- coding: utf-8 -*-
"""
GVA auth module API wrapper
    - Init DB check /init/checkdb
    - Init DB create /init/initdb
    - Get captcha   /base/captcha
    - Login         /base/login
    - Logout (JWT blacklisted) /jwt/jsonInBlacklist
    - Get current user info /user/getUserInfo
    - Change password /user/changePassword
"""
import os

from utils.exceptions import APIException
from utils.logger import get_logger
from api.base_api import BaseApi

logger = get_logger(__name__)


class AuthApi(BaseApi):
    """GVA auth client"""

    def __init__(self, base_url, timeout=10, captcha_solver=None):
        super().__init__(base_url, timeout)
        self.solver = captcha_solver

    # Captcha

    def get_captcha(self):
        """
        Get captcha
        :return: dict {captchaId, picPath, captchaLength, openCaptcha}
        """
        resp = self.post("/base/captcha", json={})
        self.assert_business_success(resp)
        data = resp.json()["data"]
        logger.info(
            "获取验证码成功: captchaId={}, openCaptcha={}, length={}".format(
                data.get("captchaId"),
                data.get("openCaptcha"),
                data.get("captchaLength"),
            )
        )
        return data

    # Login

    def login(self, username, password, captcha=None, captcha_id=None):
        """
        GVA login endpoint
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
        Auto-recognize captcha and login (single attempt; raises on captcha recognition failure)
        :return: token (str)
        """
        if self.solver is None:
            raise APIException("未配置验证码识别器, 无法自动登录")

        def fetch_captcha():
            data = self.get_captcha()
            return data["picPath"], data["captchaId"]

        # Fetch once first to sync the expected length
        sample = self.get_captcha()
        expected_length = sample.get("captchaLength") or self.solver.expected_length
        self.solver.expected_length = expected_length

        code, captcha_id = self.solver.solve_with_retry(fetch_captcha)
        resp = self.login(username, password, captcha=code, captcha_id=captcha_id)

        try:
            data = resp.json()
        except Exception as e:
            raise APIException("登录响应不是合法 JSON: {}".format(e), resp.status_code, resp)

        if resp.status_code != 200 or data.get("code") != 0:
            err = "登录失败: code={}, msg={}".format(data.get("code"), data.get("msg"))
            logger.error(err)
            raise APIException(err, resp.status_code, resp)

        token = data["data"]["token"]
        logger.info("登录成功: username={}, token={}...".format(username, token[:30]))
        return token

    def login_with_retry(self, username, password, max_round=3):
        """
        Multi-round login attempts: retry the whole flow when a round fails on
        captcha recognition or login. Used by fixtures to tolerate occasional OCR failures.
        """
        last_err = None
        for round_no in range(1, max_round + 1):
            try:
                token = self.login_with_captcha(username, password)
                if round_no > 1:
                    logger.info("登录在第 {} 轮成功".format(round_no))
                return token
            except Exception as e:
                last_err = e
                logger.warning("第 {} 轮登录失败: {}".format(round_no, e))
        raise APIException("登录失败(已重试 {} 轮): {}".format(max_round, last_err))

    # Logout / JWT blacklist

    def logout(self):
        """Add the current token to the JWT blacklist so it is invalidated immediately"""
        resp = self.post("/jwt/jsonInBlacklist", json={})
        self.assert_business_success(resp)
        logger.info("登出成功, token 已加入黑名单")
        return resp

    # Current user info

    def get_self_info(self):
        """
        Get current logged-in user info
        GVA actual response shape: {"code":0,"data":{"userInfo":{...}}}

        Note: change password /user/changePassword belongs to user management and its
              real route is POST (not PUT); it is unified in UserApi.change_password
              and is not duplicated here.
        """
        resp = self.get("/user/getUserInfo")
        self.assert_business_success(resp)
        return resp.json()["data"]["userInfo"]

    # Init DB (bootstrapping, runs WITHOUT token)

    def check_db(self):
        """
        Check whether GVA database has been initialized (POST /init/checkdb).
        Returns the raw Response object. Caller inspects code/msg to decide
        if initdb is needed. Typical behavior:
            - code=0 + data.code=1 -> DB already initialized, redirect to /login
            - code=0 + data.code=0 -> DB not initialized, call initdb next
            - code=7 -> already initialized, msg usually something like '已初始化'
        """
        return self.post("/init/checkdb", json={})

    def init_db(self, admin_password, db_name,
                host=os.getenv('INIT_HOST', '127.0.0.1'), port="3306", user_name="root",
                password="", db_type="mysql", db_path="", template=""):
        """
        Initialize GVA database (POST /init/initdb, request.InitDB schema).
        Runs WITHOUT authentication.
        Required fields by GVA: adminPassword, dbName
        Defaults match local GVA config.
        :return: requests.Response
        """
        payload = {
            "adminPassword": admin_password,
            "dbName": db_name,
            "host": host,
            "port": str(port),
            "userName": user_name,
            "password": password,
            "dbType": db_type,
            "dbPath": db_path,
            "template": template,
        }
        logger.info(
            "初始化数据库: dbType={}, host={}:{}, dbName={}, user={}".format(
                db_type, host, port, db_name, user_name,
            )
        )
        return self.post("/init/initdb", json=payload)
