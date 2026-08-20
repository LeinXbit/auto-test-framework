# -*- coding: utf-8 -*-
"""
GVA system module API wrapper
Targets real GVA routes /system/*
Docs: http://127.0.0.1:8888/swagger/index.html

Covers:
    - Server info (CPU / memory / disk)
    - System config (read YAML config, reload runtime, update config)
"""
from api.base_api import BaseApi


class SystemApi(BaseApi):
    """
    System management client (based on real GVA endpoints)
    All operations go through admin auth by default (x-token injected by fixture)
    """

    def get_server_info(self):
        """Get server runtime info (OS / CPU / memory / disk / go version):
        POST /system/getServerInfo"""
        return self.post("/system/getServerInfo", json={})

    def get_system_config(self):
        """Get GVA config file content: POST /system/getSystemConfig"""
        return self.post("/system/getSystemConfig", json={})

    def set_system_config(self, config_json):
        """Update GVA config file content: POST /system/setSystemConfig
        :param config_json: full config dict (the same shape as getSystemConfig.data)
        """
        return self.post("/system/setSystemConfig", json=config_json)

    def reload_system(self):
        """Hot reload GVA config (re-read from disk): POST /system/reloadSystem"""
        return self.post("/system/reloadSystem", json={})
