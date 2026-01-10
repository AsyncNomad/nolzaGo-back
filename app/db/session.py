from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base


settings = get_settings()
engine = create_async_engine(settings.database_url, future=True, echo=settings.debug)
SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def init_models() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Ensure newly added columns exist without manual migration
        try:
            await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profile_image_url VARCHAR"))
        except Exception as exc:  # pragma: no cover
            print(f"[init_models] alter users.profile_image_url skipped/failed: {exc}")


async def get_db():
    async with SessionLocal() as session:
        yield session
