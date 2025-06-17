"""Database base configuration and session management."""

import os
from pathlib import Path
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

# Create declarative base
Base = declarative_base()

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./storyteller.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=os.getenv("DATABASE_ECHO", "false").lower() == "true"
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """Initialize database tables."""
    # Import models to ensure they're registered
    from . import models  # noqa: F401
    
    Base.metadata.create_all(bind=engine)