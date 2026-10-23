from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경변수에서 읽는 앱 설정. 필드명이 그대로 환경변수 이름이 된다(대소문자 무시)."""

    model_config = SettingsConfigDict(extra="ignore")

    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/postgres"
    # 쉼표로 구분. 기본값은 Vite 개발 서버 주소
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
