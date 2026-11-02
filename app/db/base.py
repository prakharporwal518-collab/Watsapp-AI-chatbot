from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import MetaData, Text
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

from app.core.security import get_protector

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class EncryptedText(TypeDecorator):
    """Text column that is transparently Fernet-encrypted at rest."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return get_protector().encrypt(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return get_protector().decrypt(value) if value is not None else None
