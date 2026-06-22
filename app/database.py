from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings, SettingsConfigDict


from sqlalchemy.pool import NullPool
import sys

class Settings(BaseSettings):
    DATABASE_URL: str
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    GOOGLE_AI_API_KEY: str | None = None
    ELASTIC_CLOUD_ID: str | None = None
    ELASTIC_URL: str | None = None
    ELASTIC_API_KEY: str | None = None
    ELASTIC_USERNAME: str | None = None
    ELASTIC_PASSWORD: str | None = None
    ELASTIC_V2_INDEX_READ_ALIAS: str = "product_master_v2_read"
    ELASTIC_V2_INDEX_WRITE_ALIAS: str = "product_master_v2_write"
    ELASTIC_V2_INDEX_NAME: str = "product_master_v2_0001"
    ELASTIC_V2_TIMEOUT_SECONDS: int = 10

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()


class Base(DeclarativeBase):
    pass


is_testing = "pytest" in sys.modules
engine_kwargs = {"poolclass": NullPool} if is_testing else {}

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    **engine_kwargs
)


AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
