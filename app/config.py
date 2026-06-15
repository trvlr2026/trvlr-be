from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://trvlr_admin:trvlr_secret@localhost:5432/trvlr_db"

    class Config:
        env_file = ".env"


settings = Settings()
