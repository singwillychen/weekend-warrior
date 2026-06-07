# database.py — 非同步 PostgreSQL 連線（SQLAlchemy 2.0）
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://ww_admin:ww_secure_2026@db:5432/weekend_warrior"
    )
    secret_key: str = os.getenv("SECRET_KEY", "change_this_secret")
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 小時

    class Config:
        env_file = ".env"


settings = Settings()

# asyncpg 驅動 — 確保 URL 使用 +asyncpg
db_url = settings.database_url.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace(
    "postgres://", "postgresql+asyncpg://"
)

engine = create_async_engine(db_url, echo=False, pool_pre_ping=True)

AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
