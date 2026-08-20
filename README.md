# Auto Test Framework

基于 Pytest + Allure + Requests 的接口自动化测试框架.

## 技术栈
- Python 3.11 + Pytest
- Requests(HTTP请求)
- Allure(测试报告)
- PyMySQL(数据库断言)
- Docker + GitHub Actions(CI/CD)

## 项目目录

```
auto-test-framework/
├── api/            # 接口封装层 (Page Object 思想)
│   ├── base_api.py         # 基类: token 注入 / 自动刷新 / 重试
│   ├── auth_api.py         # 鉴权: initdb / captcha / login / logout
│   ├── authority_api.py    # 角色权限: CRUD / casbin 策略
│   ├── user_api.py         # 用户: 注册 / 列表 / 改密 / 删除
│   ├── menu_api.py         # 菜单: 路由 / CRUD / 角色关联
│   ├── file_api.py         # 文件: 上传 / 查询 / 删除
│   ├── system_api.py       # 系统: serverInfo / config / reload
│   └── sysop_api.py        # 审计日志: 查询 / 删除
├── testcases/      # 测试用例层 (61 个用例)
│   ├── conftest.py         # 全局 fixture: token/db/临时数据
│   └── test_*_real.py      # 9 个真实业务测试模块
├── utils/          # 工具层
│   ├── captcha_solver.py   # ddddocr 验证码自动识别
│   ├── data_factory.py     # Builder 模式随机数据生成
│   ├── mysql_client.py     # PyMySQL 数据库客户端
│   ├── yaml_reader.py      # 测试数据加载器
│   ├── logger.py           # loguru 日志
│   └── exceptions.py       # APIException 等
├── config/         # 多环境配置
│   ├── environments/       # ci.yaml / go_vue_admin.yaml
│   └── settings.py
├── data/test_data.yaml    # 参数化测试数据 (模板变量 ${random} / ${existing_user})
├── .env.example           # 环境变量模板 (DB_PASSWORD 占位)
├── pytest.ini             # 6 类 marker 定义
├── requirements.txt
├── Dockerfile             # Python 3.11 slim 镜像
├── docker-compose.yml
└── .github/workflows/ci.yml  # GitHub Actions (selfhosted + github-built 双模式)

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
