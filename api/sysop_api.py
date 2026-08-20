# -*- coding: utf-8 -*-
"""
GVA sysOperationRecord (audit log) module API wrapper
Targets real GVA routes /sysOperationRecord/*
Docs: http://127.0.0.1:8888/swagger/index.html

Covers:
    - Paginated list query (GET)
    - Find by ID
    - Delete single record
    - Batch delete by IDs
"""
from api.base_api import BaseApi


class SysOpApi(BaseApi):
    """
    Audit log (SysOperationRecord) management client
    All operations go through admin auth by default (x-token injected by fixture)
    """

    def get_record_list(self, page=1, page_size=10, keyword="", **extra):
        """
        Paginated audit log list: GET /sysOperationRecord/getSysOperationRecordList
        GVA uses query params (not JSON body) for this GET endpoint
        """
        params = {
            "page": page,
            "pageSize": page_size,
            "keyword": keyword or "",
        }
        params.update(extra)
        return self.get(
            "/sysOperationRecord/getSysOperationRecordList",
            params=params,
        )

    def find_record(self, record_id):
        """Find a single audit log by ID: POST /sysOperationRecord/findSysOperationRecord"""
        return self.post("/sysOperationRecord/findSysOperationRecord", json={
            "id": int(record_id),
        })

    def delete_record(self, record_id):
        """Delete a single audit log: POST /sysOperationRecord/deleteSysOperationRecord"""
        return self.post("/sysOperationRecord/deleteSysOperationRecord", json={
            "id": int(record_id),
        })

    def delete_records_by_ids(self, ids):
        """Batch delete audit logs: POST /sysOperationRecord/deleteSysOperationRecordByIds"""
        return self.post(
            "/sysOperationRecord/deleteSysOperationRecordByIds",
            json={"ids": [int(i) for i in ids]},
        )
