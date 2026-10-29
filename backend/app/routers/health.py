from fastapi import APIRouter
from sqlalchemy import text

from app.db import engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    """컨테이너/프로세스가 살아있는지만 확인 (DB 미사용)."""
    return {"status": "ok"}


@router.get("/db")
def health_check_db():
    """DB 연결까지 확인."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok", "db": "connected"}
