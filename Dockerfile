# Official Python 3.11 slim image
FROM python:3.11-slim

WORKDIR /app

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install deps to .vendor so pytest.ini (pythonpath = .vendor) can find them
# Also set PYTHONPATH so the project modules + .vendor are both importable
RUN pip install --no-cache-dir --target .vendor -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple

# Copy project source
COPY . .

# Default env: tests run against a reachable GVA (override at runtime)
ENV TEST_ENV=ci \
    PYTHONPATH=/app:/app/.vendor

# Default command: run the full test suite
CMD ["pytest"]
