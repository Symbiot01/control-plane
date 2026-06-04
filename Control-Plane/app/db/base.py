"""SQLAlchemy declarative base. Models inherit from this."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all DB models."""

    pass
