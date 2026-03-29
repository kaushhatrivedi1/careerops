"""
Database initialization
"""
from app.db.session import engine, Base


async def init_db():
    """Create all tables"""
    async with engine.begin() as conn:
        # Import all models to register them
        from app.models import user, resume, job, evidence  # noqa: F401
        await conn.run_sync(Base.metadata.create_all)

