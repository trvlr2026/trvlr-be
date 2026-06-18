from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://trvlr_admin:trvlr2026!@localhost:5432/trvlr_db"

    # Auth
    auth_enabled: bool = False  # Toggle to skip auth in dev
    jwt_secret: str = "super-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440  # 24 hours

    # Google OAuth
    google_client_id: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
