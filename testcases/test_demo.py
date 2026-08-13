import allure
import pytest
from utils.logger import get_logger

logger = get_logger(__name__)


@allure.feature("数据库模块")
@allure.story("连接验证")
@allure.title("验证数据库连接正常")
@allure.severity(allure.severity_level.BLOCKER)  # 阻塞级用例
@pytest.mark.smoke
@pytest.mark.database
def test_fixture_db_connection(db_client):
    """验证 Fixture 自动注入数据库连接"""
    with allure.step("步骤1：执行版本查询"):
        result = db_client.query_one("SELECT VERSION() as version")
        logger.info(f"MySQL 版本: {result['version']}")
        allure.attach(str(result['version']), "MySQL 版本号")

    with allure.step("步骤2：断言结果不为空"):
        assert result is not None

    allure.attach("数据库连接测试完成", "测试结论")
    logger.info("数据库连接测试通过")


@allure.feature("数据库模块")
@allure.story("数据生命周期")
@allure.title("验证Fixture自动创建并清理测试用户")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.regression
@pytest.mark.database
def test_fixture_auto_user(test_user, db_client):
    """验证 Fixture 自动创建测试用户，且用例结束后自动清理"""
    with allure.step("步骤1：记录测试用户信息"):
        logger.info(f"当前测试用户: {test_user}")
        allure.attach(str(test_user), "Fixture创建的测试用户数据")

    with allure.step("步骤2：数据库断言"):
        user_in_db = db_client.query_one(
            "SELECT * FROM test_users WHERE id = %s",
            (test_user["id"],)
        )
        allure.attach(str(user_in_db), "数据库查询结果")

    with allure.step("步骤3：验证用户名一致"):
        assert user_in_db["username"] == test_user["username"]
        allure.attach("用户名匹配成功", "断言结果")

    logger.info("测试用户数据验证通过")


@allure.feature("API模块")
@allure.story("架构验证")
@allure.title("验证UserApi封装结构正确")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.api
def test_user_api_structure(user_api):
    """验证 UserApi 封装结构正确"""
    with allure.step("步骤1：验证继承自BaseApi的方法"):
        assert hasattr(user_api, "get")
        assert hasattr(user_api, "post")
        allure.attach("BaseApi方法存在", "继承验证")

    with allure.step("步骤2：验证业务方法存在"):
        methods = ["register", "login", "get_user", "update_user", "delete_user", "list_users"]
        for method in methods:
            assert hasattr(user_api, method)
        allure.attach(str(methods), "业务方法列表")

    with allure.step("步骤3：验证base_url配置正确"):
        assert user_api.base_url == "http://127.0.0.1:5000"
        allure.attach(user_api.base_url, "当前Base URL")

    logger.info("UserApi 结构验证通过")


@allure.feature("API模块")
@allure.story("Mock测试")
@allure.title("验证register方法参数构造正确")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.api
def test_user_api_register_mock(user_api, monkeypatch):
    """使用Mock验证register方法参数构造正确"""
    captured = {}

    def mock_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs.get("json")

        class MockResponse:
            status_code = 201

            def json(self):
                return {"code": 0, "data": {"id": 1, "username": "mock_user"}}

        return MockResponse()

    with allure.step("步骤1：注入Mock替换post方法"):
        monkeypatch.setattr(user_api, "post", mock_post)
        allure.attach("monkeypatch替换完成", "Mock注入")

    with allure.step("步骤2：调用业务方法"):
        resp = user_api.register("mock_user", "Pass123!", "mock@test.com")
        allure.attach(str(captured), "捕获的请求参数")

    with allure.step("步骤3：验证参数构造正确"):
        assert resp.status_code == 201
        assert captured["url"] == "/api/register"
        assert captured["json"]["username"] == "mock_user"
        assert captured["json"]["email"] == "mock@test.com"
        allure.attach(str(captured['json']), "请求体JSON")

    logger.info(" UserApi Mock 测试通过")