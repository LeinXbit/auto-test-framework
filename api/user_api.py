# -*- coding: utf-8 -*-
"""用户模块接口封装：对接 GVA 真实路由 /user/*"""
from api.base_api import BaseApi


class UserApi(BaseApi):
    """
    GVA 用户管理模块接口封装（/user 路由）

    GVA 统一响应: {code, data, msg}
    列表类接口的 data 通常为 {list, total, page, pageSize}
    """

    # ===== 注册 =====

    def admin_register(self, username, password, nick_name=None, phone=None,
                       email=None, authority_id="888", **extra):
        """
        管理员创建用户（注册账号）
        GVA 路由: POST /user/admin_register
        入参模型: request.Register
        :param username: 用户名
        :param password: 密码
        :param nick_name: 昵称
        :param phone: 手机号
        :param email: 邮箱
        :param authority_id: 角色 ID（GVA 默认普通用户角色 888）
        :param extra: 其他可选字段 (authorityIds, enable, headerImg)
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

    # ===== 查询 =====

    def get_user_list(self, page=1, page_size=10, keyword=None):
        """
        分页获取用户列表
        GVA 路由: POST /user/getUserList
        入参模型: request.GetUserList
        """
        payload = {
            "page": page,
            "pageSize": page_size,
            "keyword": keyword or "",
        }
        return self.post("/user/getUserList", json=payload)

    def get_user_info(self):
        """
        获取当前登录用户信息
        GVA 路由: GET /user/getUserInfo
        """
        return self.get("/user/getUserInfo")

    # ===== 更新 =====

    def set_user_info(self, user_id, **fields):
        """
        更新用户资料
        GVA 路由: PUT /user/setUserInfo
        入参模型: system.SysUser（部分字段）
        """
        payload = {"ID": user_id}
        payload.update(fields)
        return self.put("/user/setUserInfo", json=payload)

    def set_self_info(self, **fields):
        """
        设置当前用户个人信息
        GVA 路由: PUT /user/setSelfInfo
        """
        return self.put("/user/setSelfInfo", json=fields)

    def change_password(self, old_password, new_password):
        """
        修改密码（当前用户）
        GVA 路由: POST /user/changePassword
        入参模型: request.ChangePasswordReq
        """
        return self.post(
            "/user/changePassword",
            json={"password": old_password, "newPassword": new_password}
        )

    def reset_password(self, user_id):
        """
        重置指定用户密码（管理员操作）
        GVA 路由: POST /user/resetPassword
        入参模型: system.SysUser（只需 ID）
        """
        return self.post("/user/resetPassword", json={"ID": user_id})

    # ===== 删除 =====

    def delete_user(self, user_id):
        """
        删除用户
        GVA 路由: DELETE /user/deleteUser
        入参模型: request.GetById
        """
        return self.delete("/user/deleteUser", json={"ID": user_id})

    # ===== 角色与组织 =====

    def set_user_authority(self, user_id, authority_id):
        """
        更改用户单一角色
        GVA 路由: POST /user/setUserAuthority
        入参模型: request.SetUserAuth
        """
        return self.post(
            "/user/setUserAuthority",
            json={"ID": user_id, "authorityId": authority_id}
        )

    def set_user_authorities(self, user_id, authority_ids):
        """
        设置用户多个角色
        GVA 路由: POST /user/setUserAuthorities
        入参模型: request.SetUserAuthorities
        """
        return self.post(
            "/user/setUserAuthorities",
            json={"ID": user_id, "authorityIds": authority_ids}
        )

    def set_user_departments(self, user_id, dept_ids, primary_dept_id=None):
        """
        设置用户归属部门
        GVA 路由: POST /user/setUserDepartments
        入参模型: request.SetUserDepartments
        """
        payload = {"ID": user_id, "deptIds": dept_ids}
        if primary_dept_id is not None:
            payload["primaryDeptId"] = primary_dept_id
        return self.post("/user/setUserDepartments", json=payload)

    def set_user_positions(self, user_id, position_ids):
        """
        设置用户岗位
        GVA 路由: POST /user/setUserPositions
        入参模型: request.SetUserPositions
        """
        return self.post(
            "/user/setUserPositions",
            json={"ID": user_id, "positionIds": position_ids}
        )
