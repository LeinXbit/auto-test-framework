# -*- coding: utf-8 -*-
"""
GVA authority (role) and casbin (API permission) module API wrapper
Targets real GVA routes /authority/* and /casbin/*
Docs: http://127.0.0.1:8888/swagger/index.html

Responsibility split:
    - Role CRUD (create / list / update / delete) belong to this class (AuthorityApi)
    - Casbin API permission query / update also belong here (API-level RBAC)
    - Menu-level and button-level permissions are out of scope for Phase 2
"""
from api.base_api import BaseApi


class AuthorityApi(BaseApi):
    """
    Authority (role) and casbin management client (based on real GVA endpoints)
    All write operations go through admin auth by default (x-token injected by fixture)
    """

    # Role CRUD

    def create_authority(self, authority_id, authority_name, parent_id=0, **extra):
        """
        Create a role (real GVA endpoint: POST /authority/createAuthority)
        :param authority_id: role ID (number), must be unique across the system
        :param authority_name: role display name
        :param parent_id: parent role ID (0 = root)
        GVA backend field authorityId is uint, must pass a number not a string
        """
        payload = {
            "authorityId": int(authority_id),
            "authorityName": authority_name,
            "parentId": int(parent_id),
        }
        payload.update(extra)
        return self.post("/authority/createAuthority", json=payload)

    def get_authority_list(self, page=1, page_size=10, keyword=""):
        """Paginated role list query: POST /authority/getAuthorityList"""
        payload = {
            "page": page,
            "pageSize": page_size,
            "keyword": keyword or "",
        }
        return self.post("/authority/getAuthorityList", json=payload)

    def update_authority(self, authority_id, authority_name, parent_id=0, **extra):
        """
        Update a role: POST /authority/updateAuthority
        GVA requires the full SysAuthority object (authorityId + authorityName + parentId)
        """
        payload = {
            "authorityId": int(authority_id),
            "authorityName": authority_name,
            "parentId": int(parent_id),
        }
        payload.update(extra)
        return self.post("/authority/updateAuthority", json=payload)

    def delete_authority(self, authority_id):
        """
        Delete a role: POST /authority/deleteAuthority
        GVA expects a SysAuthority body; sending authorityId is sufficient for deletion
        """
        return self.post("/authority/deleteAuthority", json={
            "authorityId": int(authority_id),
        })

    # Casbin API permission (role -> API path mapping)

    def get_policy_paths(self, authority_id):
        """
        Query API permissions granted to a role: POST /casbin/getPolicyPathByAuthorityId
        Returns the list of (method, path) pairs the role is allowed to call
        """
        return self.post("/casbin/getPolicyPathByAuthorityId", json={
            "authorityId": int(authority_id),
        })

    def update_casbin(self, authority_id, casbin_infos):
        """
        Update API permissions for a role: POST /casbin/UpdateCasbin
        :param casbin_infos: list of dicts with "method" and "path" keys
            e.g. [{"method": "GET", "path": "/user/getUserInfo"}]
        Replaces the role's entire API permission set
        """
        return self.post("/casbin/UpdateCasbin", json={
            "authorityId": int(authority_id),
            "casbinInfos": casbin_infos,
        })
