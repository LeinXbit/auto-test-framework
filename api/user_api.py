# -*- coding: utf-8 -*-
"""
GVA user module API wrapper
Targets real GVA routes /user/*
Docs: http://127.0.0.1:8888/swagger/index.html

Responsibility split:
    - User CRUD / role change / change password belong to this class (UserApi)
    - Current user info getUserInfo belongs to AuthApi.get_self_info and is not duplicated here
"""
from api.base_api import BaseApi


class UserApi(BaseApi):
    """
    User management client (based on real GVA endpoints)
    All write operations go through admin auth by default (x-token injected by fixture)
    """

    # User register / list / delete / set authority

    def admin_register(self, username, password, nick_name=None,
                       phone=None, email=None, authority_id=888, **extra):
        """
        Admin registers a user (real GVA endpoint: POST /user/admin_register)
        :param authority_id: role ID (number), 888 normal user, 9528 user admin
        GVA backend field is uint, must pass a number not a string
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
        """Paginated user list query: POST /user/getUserList"""
        payload = {
            "page": page,
            "pageSize": page_size,
            "keyword": keyword or "",
        }
        return self.post("/user/getUserList", json=payload)

    def delete_user(self, user_id):
        """Delete user: DELETE /user/deleteUser"""
        return self.delete("/user/deleteUser", json={"ID": user_id})

    def set_user_authority(self, user_id, authority_id):
        """Change user role: POST /user/setUserAuthority (authority_id must be a number)"""
        return self.post("/user/setUserAuthority", json={
            "ID": user_id,
            "authorityId": int(authority_id),
        })

    # Change password

    def change_password(self, username, password, new_password):
        """Change password: POST /user/changePassword (real GVA route is POST, not PUT)
        Note: this endpoint validates the current token holder's password;
              username must match the token owner
        """
        payload = {
            "username": username,
            "password": password,
            "newPassword": new_password,
        }
        return self.post("/user/changePassword", json=payload)

    # Self info and admin operations

    def set_self_info(self, user_id, nick_name=None, header_img=None, **extra):
        """Set current user (token holder) info: PUT /user/setSelfInfo
        Note: GVA registers the route as /user/setSelfInfo (lowercase s in 'set'),
        even though the swagger doc shows /user/SetSelfInfo. Only fields present
        in the body are updated.
        """
        payload = {"ID": int(user_id)}
        if nick_name is not None:
            payload["nickName"] = nick_name
        if header_img is not None:
            payload["headerImg"] = header_img
        payload.update(extra)
        return self.put("/user/setSelfInfo", json=payload)

    def reset_password(self, user_id):
        """Admin resets a user's password to default: POST /user/resetPassword
        GVA resets the password to '123456' by default.
        """
        return self.post("/user/resetPassword", json={"ID": int(user_id)})

    def set_user_authorities(self, user_uuid, authority_ids):
        """Set multiple roles for a user (plural): POST /user/setUserAuthorities
        :param user_uuid: the UUID string of the user (not the numeric ID)
        :param authority_ids: list of role IDs
        """
        return self.post("/user/setUserAuthorities", json={
            "uuid": user_uuid,
            "authorityIds": [int(a) for a in authority_ids],
        })
