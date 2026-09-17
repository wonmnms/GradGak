from fastapi import FastAPI
from sqlalchemy import text

from app.db import engine

app = FastAPI(title="GradGak API")


@app.get("/health")
def health_check():
    """컨테이너/프로세스가 살아있는지만 확인 (DB 미사용)."""
    return {"status": "ok"}


@app.get("/health/db")
def health_check_db():
    """DB 연결까지 확인."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}
