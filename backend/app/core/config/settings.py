from typing import Optional
from pydantic import model_validator
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int

    SQLALCHEMY_DATABASE_URI: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @model_validator(mode='after')
    def set_database_uri(self):
        self.SQLALCHEMY_DATABASE_URI = (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:"
            f"{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:"
            f"{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )
        return self

settings = Settings()
