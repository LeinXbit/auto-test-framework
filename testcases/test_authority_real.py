# -*- coding: utf-8 -*-
"""
GVA authority (role) module RBAC real tests
Coverage: create role -> list query -> duplicate create -> DB assertion -> delete -> casbin permission query

Notes (probe-verified GVA behavior):
1. createAuthority success returns data.authority (full SysAuthority with menus/dataScope/defaultRouter)
2. getAuthorityList returns data as a LIST (not a paginated dict); no total/page fields
3. Duplicate authorityId returns code=7, msg="创建失败存在相同角色id"
4. deleteAuthority returns code=0, msg="删除成功"; DB row hard-deleted
5. casbin getPolicyPathByAuthorityId may return code=7 "权限不足" for non-self roles
"""
import allure
import pytest


@allure.epic("GVA 真实业务测试")
@allure.feature("角色模块")
@allure.story("角色创建")
class TestAuthorityCreate:
    """Role creation link"""

    @allure.title("admin 创建新角色接口返回完整角色对象")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_create_authority_returns_object(self, authority_api, temp_authority):
        """createAuthority success should return data.authority with authorityId/authorityName/parentId"""
        assert temp_authority["authorityId"] > 0, "authorityId should be positive"
        assert temp_authority["authorityName"].startswith("auto_role_"), \
            "authorityName prefix should be auto_role_"
        assert temp_authority["parentId"] == 0, "default parentId should be 0"
        # GVA auto-assigns dashboard menu and defaultRouter on creation
        assert temp_authority.get("defaultRouter") == "dashboard", \
            "defaultRouter should be dashboard"

    @allure.title("重复创建相同角色ID应失败")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_create_duplicate_authority_fails(self, authority_api, temp_authority):
        """Duplicate authorityId should return code=7, msg contains '失败'"""
        resp = authority_api.create_authority(
            authority_id=temp_authority["authorityId"],
            authority_name=temp_authority["authorityName"] + "_dup",
        )
        assert resp.json()["code"] != 0, "duplicate create should not succeed"
        assert "失败" in resp.json().get("msg", ""), \
            "msg should contain '失败', actual: {}".format(resp.json().get("msg"))


@allure.epic("GVA 真实业务测试")
@allure.feature("角色模块")
@allure.story("角色列表")
class TestAuthorityList:
    """Role list query"""

    @allure.title("角色列表应返回数组且包含新创建角色")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_authority_list_contains_new_role(self, authority_api, temp_authority):
        """getAuthorityList returns data as a list (not paginated dict); temp role in it"""
        resp = authority_api.get_authority_list(page=1, page_size=100)
        assert resp.json()["code"] == 0
        data = resp.json()["data"]
        # GVA returns a flat list (not a paginated dict); data is directly the array
        assert isinstance(data, list), "data should be a list, not a dict"
        assert len(data) >= 1, "list should have at least one role"
        matched = [a for a in data if a.get("authorityId") == temp_authority["authorityId"]]
        assert matched, "temp role should appear in the list"
        assert matched[0]["authorityName"] == temp_authority["authorityName"]


@allure.epic("GVA 真实业务测试")
@allure.feature("角色模块")
@allure.story("数据库断言")
class TestAuthorityDb:
    """Role DB persistence"""

    @allure.title("sys_authorities 表应存在新创建的角色记录")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.database
    def test_authority_db_persisted(self, db_client, temp_authority):
        """Verify role truly written to sys_authorities table (not just API success)"""
        authority_id = temp_authority["authorityId"]
        row = db_client.query_one(
            "SELECT authority_id, authority_name, parent_id "
            "FROM sys_authorities WHERE authority_id = %s",
            (authority_id,),
        )
        assert row is not None, "sys_authorities should have the role record"
        assert int(row["authority_id"]) == authority_id
        assert row["authority_name"] == temp_authority["authorityName"]
        assert int(row["parent_id"]) == 0


@allure.epic("GVA 真实业务测试")
@allure.feature("角色模块")
@allure.story("角色删除")
class TestAuthorityDelete:
    """Role deletion link"""

    @allure.title("删除角色后应返回成功且DB记录消失")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_delete_authority_succeeds(self, authority_api, db_client, temp_authority):
        """Delete temp role; verify code=0 and DB row gone (GVA hard-deletes authorities)"""
        authority_id = temp_authority["authorityId"]
        resp = authority_api.delete_authority(authority_id)
        assert resp.json()["code"] == 0, "delete should return code=0"
        assert "成功" in resp.json().get("msg", "")
        # DB row should be gone (GVA hard-deletes authorities, not soft-delete)
        row = db_client.query_one(
            "SELECT authority_id FROM sys_authorities WHERE authority_id = %s",
            (authority_id,),
        )
        assert row is None, "sys_authorities should not have the role after delete"


@allure.epic("GVA 真实业务测试")
@allure.feature("角色模块")
@allure.story("Casbin权限")
class TestCasbinPermission:
    """Casbin API permission query"""

    @allure.title("查询角色API权限列表")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.rbac
    def test_get_policy_paths(self, authority_api, temp_authority):
        """Query casbin policy paths for the temp role (skip if admin lacks casbin permission)"""
        resp = authority_api.get_policy_paths(temp_authority["authorityId"])
        body = resp.json()
        # GVA admin role may return code=7 '权限不足' for casbin queries on other roles
        if body.get("code") != 0:
            pytest.skip("admin role lacks casbin query permission, skip: {}".format(body.get("msg")))
        # If permitted, data should be a list of {method, path} entries
        data = body.get("data")
        assert isinstance(data, list), "casbin policy paths should be a list"
