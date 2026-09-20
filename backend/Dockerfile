FROM python:3.12-slim

WORKDIR /app

# psycopg2-binary가 일부 플랫폼에서 소스 빌드가 필요할 수 있어 최소 빌드 패키지를 설치한다.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
