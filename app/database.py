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