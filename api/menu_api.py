# -*- coding: utf-8 -*-
"""
GVA menu module API wrapper
Targets real GVA routes /menu/* and /menu/* role association routes
Docs: http://127.0.0.1:8888/swagger/index.html

Responsibility split:
    - Base menu CRUD (add / list / tree / update / delete) belong to this class
    - Role-menu association (getMenuAuthority / addMenuAuthority) also here
    - Dynamic routes getMenu (current user menus) also here
"""
import uuid

from api.base_api import BaseApi


class MenuApi(BaseApi):
    """
    Menu management client (based on real GVA endpoints)
    All write operations go through admin auth by default (x-token injected by fixture)
    """

    # Dynamic routes (current user)

    def get_menu(self):
        """Get current user dynamic routes: POST /menu/getMenu"""
        return self.post("/menu/getMenu", json={})

    # Base menu CRUD

    def get_menu_list(self, page=1, page_size=10, keyword=""):
        """Paginated base menu list: POST /menu/getMenuList"""
        return self.post("/menu/getMenuList", json={
            "page": page,
            "pageSize": page_size,
            "keyword": keyword or "",
        })

    def get_base_menu_tree(self):
        """Get full base menu tree: POST /menu/getBaseMenuTree"""
        return self.post("/menu/getBaseMenuTree", json={})

    def get_base_menu_by_id(self, menu_id):
        """Get a single menu by ID: POST /menu/getBaseMenuById"""
        return self.post("/menu/getBaseMenuById", json={"ID": menu_id})

    def add_base_menu(self, name, path, component, sort=0, parent_id=0,
                      meta=None, **extra):
        """
        Add a base menu: POST /menu/addBaseMenu
        Required fields: name (unique route name), path, component
        GVA meta usually contains title / icon
        """
        menu = {
            "name": name,
            "path": path,
            "component": component,
            "sort": sort,
            "parentId": parent_id,
            "meta": meta or {"title": name, "icon": "el-icon-menu"},
        }
        menu.update(extra)
        return self.post("/menu/addBaseMenu", json=menu)

    def update_base_menu(self, menu_id, name=None, path=None, component=None,
                         sort=None, parent_id=None, meta=None, **extra):
        """Update a base menu: POST /menu/updateBaseMenu (full SysBaseMenu)"""
        menu = {"ID": menu_id}
        if name is not None:
            menu["name"] = name
        if path is not None:
            menu["path"] = path
        if component is not None:
            menu["component"] = component
        if sort is not None:
            menu["sort"] = sort
        if parent_id is not None:
            menu["parentId"] = parent_id
        if meta is not None:
            menu["meta"] = meta
        menu.update(extra)
        return self.post("/menu/updateBaseMenu", json=menu)

    def delete_base_menu(self, menu_id):
        """Delete a base menu by ID: POST /menu/deleteBaseMenu"""
        return self.post("/menu/deleteBaseMenu", json={"ID": menu_id})

    # Role-menu association

    def get_menu_authority(self, authority_id):
        """Get menus assigned to a role: POST /menu/getMenuAuthority"""
        return self.post("/menu/getMenuAuthority", json={
            "authorityId": int(authority_id),
        })

    def add_menu_authority(self, authority_id, menu_ids):
        """Assign menus to a role: POST /menu/addMenuAuthority"""
        return self.post("/menu/addMenuAuthority", json={
            "authorityId": int(authority_id),
            "menuIds": [int(m) for m in menu_ids],
        })

    def get_menu_roles(self, menu_id):
        """Get role IDs that have access to a menu: GET /menu/getMenuRoles?menuId="""
        return self.get("/menu/getMenuRoles", params={"menuId": int(menu_id)})

    def set_menu_roles(self, menu_id, role_ids):
        """Set roles for a menu: POST /menu/setMenuRoles"""
        return self.post("/menu/setMenuRoles", json={
            "menuId": int(menu_id),
            "roleIds": [int(r) for r in role_ids],
        })

    # Convenience: build a unique menu name to avoid conflicts in tests

    @staticmethod
    def random_menu_name(prefix="auto_menu"):
        """Unique menu route name (GVA menu name must be unique)"""
        return "{}_{}".format(prefix, uuid.uuid4().hex[:8])
