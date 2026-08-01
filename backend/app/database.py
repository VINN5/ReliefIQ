"""
Database connection layer.

This is the ONLY module that should configure the SQLAlchemy engine or
session. Models import `Base` from here; routes/services get a session
via the `get_db` dependency below. Nothing else should talk to the
engine directly — that keeps connection handling in one place.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

# The engine manages the actual pool of connections to Postgres.
engine = create_engine(settings.database_url)

# Each request gets its own Session from this factory.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# All ORM models (created in app/models/) will inherit from this.
Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session and guarantees
    it's closed after the request, even if an error occurs.

    Usage in a route:
        def my_route(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()