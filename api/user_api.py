from api.base_api import BaseApi

class UserApi(BaseApi):
    """
    用户模块接口封装
    将原始 HTTP 请求转换为语义方法
    """

    def register(self, username: str, password: str, email: str):
        """ 用户注册 """
        return self.post(
            "/api/register",
            json={
                "username": username,
                "password": password,
                "email": email
            }
        )

    def login(self, username: str, password: str):
        """ 用户登录 """
        return self.post(
            "/api/login",
            json={
                "username": username,
                "password": password
            }
        )

    def get_user(self, user_id: int):
        """获取用户信息"""
        return self.get(f"/api/user/{user_id}")

    def update_user(self, user_id: int, **kwargs):
        """更新用户信息"""
        return self.put(f"/api/user/{user_id}", json=kwargs)

    def delete_user(self, user_id: int):
        """删除用户"""
        return self.delete(f"/api/user/{user_id}")

    def list_users(self, page: int = 1, size: int = 10):
        """获取用户列表"""
        return self.get(
            "/api/users",
            params={"page": page, "size": size}
        )
