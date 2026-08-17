# -*- coding: utf-8 -*-
"""
GVA user register data-driven tests (Phase 3)
Loads register_cases from data/test_data.yaml and runs each as a parametrized case.

Template variables (replaced at runtime):
    ${random}         -> unique suffix to avoid dirty data
    ${existing_user} -> pre-register a user, then reuse its name to trigger duplicate

Data isolation:
    - Positive cases (REG_001) create real users; teardown cleans via DB (关联表 + 主表)
    - REG_002 pre-registerd user is also cleaned on teardown
    - Negative cases (REG_003/004/005) do not create users; nothing to clean

Probe-verified GVA behavior:
    - authorityId as string -> code=7, msg contains 'unmarshal'
    - empty password        -> code=7, msg contains 'Password'
    - empty username        -> code=7, msg contains 'Username'
"""
import uuid
from pathlib import Path

import allure
import pytest

from utils.yaml_reader import load_yaml

# Module-level load: YAML is static, no need to reload per test
_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "test_data.yaml"
_REGISTER_CASES = load_yaml(_DATA_FILE)["register_cases"]


def _case_ids():
    """Generate readable pytest ids like REG_001_正常注册"""
    return ["{}_{}".format(c["case_id"], c["case_name"]) for c in _REGISTER_CASES]


@allure.epic("GVA 真实业务测试")
@allure.feature("用户模块")
@allure.story("注册数据驱动")
class TestRegisterDDT:
    """Data-driven register tests driven by test_data.yaml"""

    @allure.title("注册场景: {case_name}")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    @pytest.mark.parametrize("case", _REGISTER_CASES, ids=_case_ids())
    def test_register_scenarios(self, user_api, db_client, case):
        """
        Run one register scenario from YAML.
        Asserts expected_http / expected_code / expected_msg_contains.
        Cleans up any created user via DB fallback on teardown.
        """
        created_user_ids = []  # user IDs to clean on teardown (DB fallback)

        try:
            username = case["username"]
            password = case["password"]
            authority_id = case["authority_id"]

            # Template variable: ${random} -> unique suffix
            if "${random}" in username:
                username = username.replace("${random}", uuid.uuid4().hex[:8])

            # Template variable: ${existing_user} -> pre-register, then reuse name
            if username == "${existing_user}":
                pre_username = "ddt_pre_{}".format(uuid.uuid4().hex[:8])
                pre_resp = user_api.admin_register(
                    username=pre_username,
                    password="Test1234!",
                    nick_name=pre_username,
                )
                assert pre_resp.json().get("code") == 0, \
                    "预注册前置用户失败: {}".format(pre_resp.json())
                created_user_ids.append(pre_resp.json()["data"]["user"]["ID"])
                username = pre_username

            # Execute the case under test
            with allure.step("调用 admin_register"):
                resp = user_api.admin_register(
                    username=username,
                    password=password,
                    nick_name=case.get("nick_name") or username or "empty_user",
                    authority_id=authority_id,
                )

            # If this case also succeeded (e.g. REG_001), record its user for cleanup
            if resp.json().get("code") == 0 and \
                    isinstance(resp.json().get("data"), dict) and \
                    "user" in resp.json()["data"]:
                created_user_ids.append(resp.json()["data"]["user"]["ID"])

            # Assertions
            with allure.step("断言 HTTP 状态码"):
                assert resp.status_code == case["expected_http"], \
                    "期望 HTTP {}, 实际 {}".format(case["expected_http"], resp.status_code)

            with allure.step("断言业务码"):
                actual_code = resp.json().get("code")
                assert actual_code == case["expected_code"], \
                    "期望 code={}, 实际 code={}, msg={}".format(
                        case["expected_code"], actual_code, resp.json().get("msg"))

            expected_msg = case.get("expected_msg_contains") or ""
            if expected_msg:
                with allure.step("断言响应消息包含期望关键词"):
                    actual_msg = resp.json().get("msg", "") or ""
                    assert expected_msg in actual_msg, \
                        "期望 msg 含 '{}', 实际 msg='{}'".format(expected_msg, actual_msg)
        finally:
            # Teardown: clean any created users via DB fallback
            # (关联表 + 主表; GVA deleteUser may lack permission for some roles)
            for uid in created_user_ids:
                try:
                    db_client.execute(
                        "DELETE FROM sys_user_authority WHERE sys_user_id = %s",
                        (uid,),
                    )
                    db_client.execute(
                        "DELETE FROM sys_users WHERE id = %s",
                        (uid,),
                    )
                except Exception as e:
                    # Cleanup failure should not mask test result; just warn
                    allure.attach(
                        str(e),
                        name="cleanup_error_user_{}".format(uid),
                        attachment_type=allure.attachment_type.TEXT,
                    )
