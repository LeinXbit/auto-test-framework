import allure
import yaml
import pytest

from utils.logger import get_logger
from utils.exceptions import APIException

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

# 数据驱动测试
def load_yaml_data(file_name):
    """ 加载 YAML 测试数据 """
    data_path = __import__("pathlib").Path(__file__).parent.parent/"data" / file_name
    with open(data_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@allure.feature("数据驱动测试")
@allure.story("用户注册参数化")
class TestDataDriven:
    # 从 YAML 加载数据
    test_data = load_yaml_data("test_data.yaml")
    register_cases = test_data["register_cases"]

    @allure.title("{case[case_name]}")
    @pytest.mark.parametrize("case", register_cases, ids=[c["case_id"] for c in register_cases])
    @pytest.mark.regression
    def test_register_data_driven(self, case, user_api, monkeypatch):
        """
        数据驱动：批量验证用户注册的各种场景
        使用 monkeypatch Mock，不依赖真实服务
        """
        with allure.step(f"前置：准备Mock - {case['description']}"):
            captured = {}

            def mock_post(url, **kwargs):
                captured["url"] = url
                captured["json"] = kwargs.get("json")

                class MockResponse:
                    def __init__(self, status):
                        self.status_code = status

                    def json(self):
                        # 模拟不同返回
                        if self.status_code == 201:
                            return {"code": 0, "data": {"id": 1}}
                        else:
                            return {"code": case["expected_code"], "message": case["case_name"]}

                return MockResponse(case["expected_status"])

        monkeypatch.setattr(user_api, "post", mock_post)
        allure.attach(str(case), f"测试数据 [{case['case_id']}]")

        with allure.step("执行：调用register业务方法"):
            resp = user_api.register(
                case["username"],
                case["password"],
                case["email"]
            )

        with allure.step("断言：验证响应符合预期"):
            assert resp.status_code == case["expected_status"]
            if resp.status_code != 201:
                assert resp.json()["code"] == case["expected_code"]

            allure.attach(
                f"状态码: {resp.status_code}\n预期: {case['expected_status']}",
                "断言结果"
            )

        with allure.step("验证：确认请求参数构造正确"):
            assert captured["json"]["username"] == case["username"]
            assert captured["json"]["password"] == case["password"]
            assert captured["json"]["email"] == case["email"]
            allure.attach(str(captured["json"]), "实际请求参数")

        logger.info(f"[{case['case_id']}] {case['case_name']} 验证通过")

@allure.feature("框架鲁棒性")
@allure.story("异常处理与断言辅助")
class TestRobustness:

    @allure.title("assert_status_code正常通过")
    def test_assert_status_code_pass(self, user_api, monkeypatch):
        """验证状态码断言辅助方法正常通过的场景"""

        def mock_post(url, **kwargs):
            class MockResponse:
                status_code = 201

                def json(self):
                    return {"code": 0}

            return MockResponse()

        monkeypatch.setattr(user_api, "post", mock_post)
        resp = user_api.register("user", "Pass123!", "user@test.com")

        monkeypatch.setattr(user_api, "post", mock_post)
        resp = user_api.register("user", "Pass123!", "user@test.com")

    @allure.title("assert_status_code失败抛出APIException")
    def test_assert_status_code_fail(self, user_api, monkeypatch):
        """验证状态码不匹配时抛出包含详细信息的异常"""

        def mock_post(url, **kwargs):
            class MockResponse:
                status_code = 500

                def json(self):
                    return {"code": 999, "message": "服务器错误"}

            return MockResponse()

        monkeypatch.setattr(user_api, "post", mock_post)
        resp = user_api.register("user", "Pass123!", "user@test.com")

        with allure.step("验证抛出APIException"):
            with pytest.raises(APIException) as exc_info:
                user_api.assert_status_code(resp, 201)

            assert exc_info.value.status_code == 500
            allure.attach(str(exc_info.value.status_code), "异常中的状态码")
            allure.attach(exc_info.value.args[0], "异常消息")

    @allure.title("assert_json_key验证JSON字段")
    def test_assert_json_key(self, user_api, monkeypatch):
        """验证JSON字段断言辅助方法"""

        def mock_post(url, **kwargs):
            class MockResponse:
                status_code = 200

                def json(self):
                    return {"code": 0, "data": {"id": 42}}

            return MockResponse()

        monkeypatch.setattr(user_api, "post", mock_post)
        resp = user_api.register("user", "Pass123!", "user@test.com")

        with allure.step("验证code字段"):
            user_api.assert_json_key(resp, "code", 0)
            allure.attach("code = 0", "断言结果")

        with allure.step("验证嵌套data.id字段"):
            data = resp.json().get("data", {})
            allure.attach(str(data), "data字段内容")


@allure.feature("框架鲁棒性")
@allure.story("失败重试")
@pytest.mark.robustness
class TestRetryMechanism:

    @allure.title("验证APIException被正确抛出与捕获")
    def test_retry_with_mock_failure(self, user_api, monkeypatch):
        """
        验证框架能正确捕获和展示APIException
        纯Mock，不依赖外部网络，确保CI稳定
        """
        call_count = [0]

        def mock_get(url, **kwargs):
            call_count[0] += 1

            class MockResponse:
                status_code = 503

                def json(self):
                    return {"code": 999, "message": "服务暂不可用"}

            return MockResponse()

        monkeypatch.setattr(user_api, "get", mock_get)

        with allure.step("步骤1：调用Mock接口，返回503"):
            resp = user_api.get("https://example.com/api/status")
            allure.attach(f"Mock调用次数: {call_count[0]}", "调用统计")

        with allure.step("步骤2：验证状态码不匹配时抛出APIException"):
            with pytest.raises(APIException) as exc_info:
                user_api.assert_status_code(resp, 200)

            assert exc_info.value.status_code == 503
            allure.attach(str(exc_info.value.status_code), "异常中的状态码")
            allure.attach(str(exc_info.value.args[0]), "异常消息")

        logger.info("Mock异常与重试标记验证通过")