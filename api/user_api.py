# -*- coding: utf-8 -*-
"""
GVA 用户模块接口封装
对接 GVA 真实路由 /user/*
文档：http://127.0.0.1:8888/swagger/index.html
"""
from api.base_api import BaseApi


class UserApi(BaseApi):
    """
    用户管理客户端（基于 GVA 真实接口）
    所有写操作默认走管理员鉴权（由 fixture 注入 x-token）
    """

    # ===== 用户注册 / 列表 / 删除 / 设置权限 =====

    def admin_register(self, username, password, nick_name=None,
                       phone=None, email=None, authority_id=888, **extra):
        """
        管理员注册用户（GVA 真实接口：POST /user/admin_register）
        :param authority_id: 角色ID（数字），888 普通用户，9528 用户管理员
        GVA 后端字段为 uint，必须传数字而非字符串
        """
        payload = {
            "userName": username,
            "passWord": password,
            "authorityId": authority_id,
            "nickName": nick_name or username,
            "phone": phone or "",
            "email": email or "",
        }
        payload.update(extra)
        return self.post("/user/admin_register", json=payload)

    def get_user_list(self, page=1, page_size=10, keyword=None):
        """分页查询用户列表：POST /user/getUserList"""
        payload = {
            "page": page,
            "pageSize": page_size,
            "keyword": keyword or "",
        }
        return self.post("/user/getUserList", json=payload)

    def delete_user(self, user_id):
        """删除用户：DELETE /user/deleteUser"""
        return self.delete("/user/deleteUser", json={"ID": user_id})

    def set_user_authority(self, user_id, authority_id):
        """修改用户角色：POST /user/setUserAuthority（authority_id 必须为数字）"""
        return self.post("/user/setUserAuthority", json={
            "ID": user_id,
            "authorityId": int(authority_id),
        })

    # ===== 当前用户信息（与 AuthApi 一致，便于直接调用） =====

    def get_self_info(self):
        """获取当前登录用户信息：GET /user/getUserInfo"""
        resp = self.get("/user/getUserInfo")
        return resp.json()

    def change_password(self, username, password, new_password):
        """修改密码：POST /user/changePassword（GVA 真实路由为 POST，非 PUT）
        注意：此接口校验当前登录用户的密码，username 字段需匹配 token 持有者
        """
        payload = {
            "username": username,
            "password": password,
            "newPassword": new_password,
        }
        return self.post("/user/changePassword", json=payload)
