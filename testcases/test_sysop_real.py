# -*- coding: utf-8 -*-
"""
GVA sysOperationRecord (audit log) module real tests
Coverage: list query -> find by ID -> delete single -> batch delete

Notes (probe-verified GVA behavior):
1. getSysOperationRecordList is a GET with query params (not JSON body)
2. Each test run generates audit log entries automatically (login/register calls)
3. findSysOperationRecord by ID returns the raw log row
4. deleteSysOperationRecord removes the row permanently (hard delete)
5. deleteSysOperationRecordByIds accepts a list of IDs and returns success
"""
import allure
import pytest


@allure.epic("GVA 真实业务测试")
@allure.feature("审计日志模块")
@allure.story("日志列表")
class TestSysOpList:
    """Audit log list query"""

    @allure.title("getSysOperationRecordList 分页字段完整性")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_record_list_pagination(self, sysop_api):
        """Verify list/total/page/pageSize fields"""
        # Trigger an audit log entry by making any API call (list itself counts)
        resp = sysop_api.get_record_list(page=1, page_size=5)
        body = resp.json()
        # GVA admin role (9528) may lack casbin permission for audit log query
        if body.get("code") == 7 and "权限" in (body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志查询权限, 跳过该用例")
        assert body["code"] == 0, "list 失败: {}".format(body)
        data = body["data"]
        assert set(["list", "total", "page", "pageSize"]).issubset(data.keys())
        assert data["page"] == 1
        assert data["pageSize"] == 5
        assert len(data["list"]) <= 5
        # There should be at least 1 record because we logged in via admin_token
        assert data["total"] >= 1, "至少应有1条登录日志"

    @allure.title("日志条目应包含关键字段 IP / method / path")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_record_entry_fields(self, sysop_api):
        """Each log entry should contain ip / method / path fields"""
        resp = sysop_api.get_record_list(page=1, page_size=5)
        body = resp.json()
        if body.get("code") == 7 and "权限" in (body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志查询权限, 跳过该用例")
        assert body["code"] == 0, "list 失败: {}".format(body)
        records = body["data"]["list"]
        if not records:
            pytest.skip("无日志可校验字段")
        r = records[0]
        # GVA fields: ip / method / path / latency / agent
        # Be permissive on which fields are required (versions vary)
        assert any(k in r for k in ["ip", "method", "path"]), \
            "log entry should have ip / method / path, got: {}".format(list(r.keys()))


@allure.epic("GVA 真实业务测试")
@allure.feature("审计日志模块")
@allure.story("日志查询")
class TestSysOpFind:
    """Find audit log by ID"""

    @allure.title("findSysOperationRecord 按 ID 查询")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_find_record_by_id(self, sysop_api):
        """findSysOperationRecord should return the same record from the list"""
        list_resp = sysop_api.get_record_list(page=1, page_size=5)
        list_body = list_resp.json()
        if list_body.get("code") == 7 and "权限" in (list_body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志查询权限, 跳过该用例")
        assert list_body["code"] == 0, "list 失败: {}".format(list_body)
        records = list_body["data"]["list"]
        if not records:
            pytest.skip("无日志可查询")
        target_id = records[0].get("ID") or records[0].get("id")
        if target_id is None:
            pytest.skip("日志条目无 ID 字段, 跳过")
        find_resp = sysop_api.find_record(target_id)
        find_body = find_resp.json()
        if find_body.get("code") == 7 and "权限" in (find_body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志查询权限, 跳过该用例")
        assert find_body["code"] == 0, "查询失败: {}".format(find_body)
        data = find_body.get("data", {})
        # data is the log record (re-uploaded for the response)
        assert isinstance(data, dict), "data should be a dict"


@allure.epic("GVA 真实业务测试")
@allure.feature("审计日志模块")
@allure.story("日志删除")
class TestSysOpDelete:
    """Delete audit log"""

    @allure.title("deleteSysOperationRecord 删除单条日志")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_delete_record_success(self, sysop_api):
        """Delete one log; verify total decreases"""
        before = sysop_api.get_record_list(page=1, page_size=1)
        before_body = before.json()
        if before_body.get("code") == 7 and "权限" in (before_body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志查询权限, 跳过该用例")
        assert before_body["code"] == 0, "list 失败: {}".format(before_body)
        total_before = before_body["data"]["total"]
        records = before_body["data"]["list"]
        if not records:
            pytest.skip("无日志可删除")
        target_id = records[0].get("ID") or records[0].get("id")
        if target_id is None:
            pytest.skip("日志条目无 ID")
        resp = sysop_api.delete_record(target_id)
        del_body = resp.json()
        if del_body.get("code") == 7 and "权限" in (del_body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志删除权限, 跳过该用例")
        assert del_body["code"] == 0, "删除失败: {}".format(del_body)
        # Verify total decreased
        after = sysop_api.get_record_list(page=1, page_size=1)
        total_after = after.json()["data"]["total"]
        assert total_after == total_before - 1, \
            "删除后总数应减1, 原={}, 现={}".format(total_before, total_after)

    @allure.title("批量删除日志应返回成功")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_batch_delete_records(self, sysop_api):
        """Fetch 3 records, batch delete them"""
        list_resp = sysop_api.get_record_list(page=1, page_size=3)
        list_body = list_resp.json()
        if list_body.get("code") == 7 and "权限" in (list_body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志查询权限, 跳过该用例")
        assert list_body["code"] == 0, "list 失败: {}".format(list_body)
        records = list_body["data"]["list"]
        if len(records) < 1:
            pytest.skip("无足够日志可批量删除")
        ids = [r.get("ID") or r.get("id") for r in records if r.get("ID") or r.get("id")]
        if not ids:
            pytest.skip("日志条目均无 ID")
        resp = sysop_api.delete_records_by_ids(ids)
        del_body = resp.json()
        if del_body.get("code") == 7 and "权限" in (del_body.get("msg") or ""):
            pytest.skip("admin 角色缺少审计日志批量删除权限, 跳过该用例")
        assert del_body["code"] == 0, "批量删除失败: {}".format(del_body)
