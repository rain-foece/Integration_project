FROM python:3.12-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY system/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ server/
COPY web/ web/

# 网页模式运行
ENV RUN_MODE=web
ENV JWT_SECRET=change-this-to-a-random-string-in-production

EXPOSE 8000

CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]