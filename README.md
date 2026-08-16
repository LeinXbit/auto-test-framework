# Auto Test Framework

基于 Pytest + Allure + Requests 的企业级接口自动化测试框架.

## 技术栈
- Python 3.7 + Pytest
- Requests(HTTP请求)
- Allure(测试报告)
- PyMySQL(数据库断言)
- Docker + GitHub Actions(CI/CD)

## 项目目录

```
auto-test-framework/
├-- api/                    # 接口封装层(Page Object思想)
│   ├-- __init__.py
│   ├-- base_api.py         # 基类: 统一请求方法, 异常处理
│   └-- user_api.py         # 用户模块接口封装
├-- config/
│   ├-- __init__.py
│   ├-- settings.py         # 配置类
│   └-- environments/
│       ├-- dev.yaml
│       ├-- test.yaml
│       └-- prod.yaml
├-- data/                   # 测试数据
│   ├-- __init__.py
│   └-- test_data.yaml
├-- db/                     # 数据库操作
│   ├-- __init__.py
│   └-- mysql_client.py
├-- logs/                   # 日志目录(gitignore)
├-- reports/                # 报告目录(gitignore)
├-- testcases/              # 测试用例
│   ├-- __init__.py
│   ├-- conftest.py         # Pytest全局Fixture
│   └-- test_user.py
├-- utils/                  # 工具类
│   ├-- __init__.py
│   ├-- logger.py           # 日志封装
│   └-- yaml_reader.py      # YAML读取
├-- Dockerfile              # 容器化
├-- Jenkinsfile             # CI流水线
├-- pytest.ini              # Pytest配置
├-- requirements.txt
└-- README.md
```

## 快速开始

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 启动测试环境(MySQL)
docker-compose up -d mysql

# 3. 运行测试
pytest

# 4. 查看报告
allure serve reports/allure-results
