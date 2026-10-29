from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Iterator[Session]:
    """라우터에서 Depends(get_db)로 받아 쓰는 DB 세션. 요청이 끝나면 닫힌다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
