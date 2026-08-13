# 使用官方 Python 3.11 轻量镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 先复制依赖文件（利用 Docker 缓存层，依赖不变时不重复安装）
COPY requirements.txt .

# 安装依赖（使用清华源加速）
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目代码
COPY . .

# 设置默认环境变量
ENV TEST_ENV=test

# 默认命令：运行测试
CMD ["pytest"]