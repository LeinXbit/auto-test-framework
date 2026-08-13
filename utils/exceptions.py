class FrameworkException(Exception):
    """ 测试框架基础异常 """
    pass

class APIException(FrameworkException):
    """
    接口请求异常
    包含状态码和响应对象，方便定位问题
    """
    def __init__(self, message="", status_code=None, response=None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response

class DBException(FrameworkException):
    """ 数据库操作异常 """
    pass