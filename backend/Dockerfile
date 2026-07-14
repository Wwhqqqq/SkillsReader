FROM python:3.12-slim

WORKDIR /app

# ---------- 系统依赖 ----------
RUN sed -i 's|deb.debian.org|mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# ---------- pip 使用清华镜像 ----------
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip config set global.trusted-host pypi.tuna.tsinghua.edu.cn

# ---------- 先拷贝依赖文件（充分利用 Docker 层缓存）----------
COPY backend/pyproject.toml /app/backend/pyproject.toml

# 安装 Python 依赖（pyproject.toml 不变时此层将命中缓存，跳过重新下载）
WORKDIR /app/backend
RUN pip install --no-cache-dir -e .

# ---------- 再拷贝应用代码 ----------
COPY backend/app /app/backend/app
COPY config /app/config

ENV PYTHONPATH=/app/backend
ENV TZ=Asia/Shanghai

WORKDIR /app
COPY .env.example /app/.env

CMD ["python", "-m", "app.main"]
