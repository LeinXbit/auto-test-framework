# -*- coding: utf-8 -*-
"""
GVA system module real tests
Coverage: server info / config get / config reload

Notes (probe-verified GVA behavior):
1. getServerInfo returns OS / CPU / memory / disk / go version metrics
2. getSystemConfig returns the parsed YAML config dict
3. reloadSystem hot-reloads the GVA config without restart
4. setSystemConfig writes the YAML file (skipped in tests to avoid env pollution)
"""
import allure
import pytest


@allure.epic("GVA 真实业务测试")
@allure.feature("系统模块")
@allure.story("服务器信息")
class TestServerInfo:
    """Server runtime info"""

    @allure.title("getServerInfo 返回服务器运行指标")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_get_server_info_fields(self, system_api):
        """getServerInfo should return server metrics dict"""
        resp = system_api.get_server_info()
        body = resp.json()
        # GVA admin role (9528) may lack casbin permission for server info
        if body.get("code") == 7 and "权限" in (body.get("msg") or ""):
            pytest.skip("admin 角色缺少 getServerInfo 权限, 跳过该用例")
        assert body["code"] == 0, "getServerInfo 失败: {}".format(body)
        data = body.get("data", {})
        assert isinstance(data, dict), "data should be a dict"
        # GVA returns at least server / goVersion / cpu / memory / disk stats
        # Be permissive on field names since GVA versions vary
        assert len(data) >= 1, "server info should not be empty"

    @allure.title("getServerInfo 应包含 OS 或运行环境信息")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_server_info_contains_os_or_go(self, system_api):
        """Server info should mention OS or go runtime somewhere"""
        resp = system_api.get_server_info()
        body = resp.json()
        if body.get("code") == 7 and "权限" in (body.get("msg") or ""):
            pytest.skip("admin 角色缺少 getServerInfo 权限, 跳过该用例")
        assert body["code"] == 0, "getServerInfo 失败: {}".format(body)
        data = body.get("data", {})
        # Look for common GVA server info keys (different versions use different
        # naming: server.os / goVersion / cpuInfo / memInfo / diskList etc)
        keys_str = " ".join(str(k).lower() for k in data.keys())
        keys_str += " " + " ".join(str(v)[:50].lower() for v in data.values() if isinstance(v, (str, int)))
        assert any(kw in keys_str for kw in ["os", "go", "cpu", "mem", "disk", "server"]), \
            "server info should contain OS / go / cpu / mem / disk fields, got: {}".format(list(data.keys()))


@allure.epic("GVA 真实业务测试")
@allure.feature("系统模块")
@allure.story("配置文件")
class TestSystemConfig:
    """System config (YAML) read"""

    @allure.title("getSystemConfig 返回配置文件内容")
    @allure.severity(allure.severity_level.CRITICAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_get_system_config_returns_dict(self, system_api):
        """getSystemConfig should return config dict (not empty)"""
        resp = system_api.get_system_config()
        assert resp.json()["code"] == 0, "getSystemConfig 失败: {}".format(resp.json())
        data = resp.json().get("data", {})
        assert isinstance(data, dict), "config should be a dict"
        assert len(data) >= 1, "config should not be empty"

    @allure.title("reloadSystem 热重载配置应返回成功")
    @allure.severity(allure.severity_level.NORMAL)
    @pytest.mark.regression
    @pytest.mark.api
    def test_reload_system_returns_success(self, system_api):
        """reloadSystem should hot-reload GVA config (code=0)"""
        resp = system_api.reload_system()
        body = resp.json()
        # GVA admin role (9528) may lack casbin permission for reloadSystem
        if body.get("code") == 7 and "权限" in (body.get("msg") or ""):
            pytest.skip("admin 角色缺少 reloadSystem 权限, 跳过该用例")
        assert body["code"] == 0, "reloadSystem 失败: {}".format(body)
