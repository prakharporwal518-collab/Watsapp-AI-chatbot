from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import IdentityProtector
from app.db.models import LearningStreak, User, UserPreferences


async def get_or_create_user(
    session: AsyncSession,
    protector: IdentityProtector,
    wa_id: str,
    profile_name: str | None,
    default_timezone: str,
    now: datetime,
) -> tuple[User, bool]:
    """Find a learner by hashed WhatsApp ID, creating their isolated profile on first contact."""
    id_hash = protector.hash_id(wa_id)
    user = await session.scalar(
        select(User)
        .where(User.wa_id_hash == id_hash)
        .options(selectinload(User.preferences), selectinload(User.streak))
    )
    created = False
    if user is None:
        user = User(
            wa_id_hash=id_hash,
            wa_id_encrypted=wa_id,
            display_name=(profile_name or "")[:60] or None,
            state={},
            created_at=now,
        )
        user.preferences = UserPreferences(timezone=default_timezone, goals=["dsa"])
        user.streak = LearningStreak(active_dates=[])
        session.add(user)
        await session.flush()
        created = True
    elif profile_name and not user.display_name:
        user.display_name = profile_name[:60]
    user.last_inbound_at = now
    return user, created


def first_name(user: User) -> str:
    name = (user.display_name or "").strip()
    return name.split()[0] if name else "there"


def set_state(user: User, **updates) -> None:
    """Update the JSON conversation state (reassign so SQLAlchemy notices the change)."""
    state = dict(user.state or {})
    for key, value in updates.items():
        if value is None:
            state.pop(key, None)
        else:
            state[key] = value
    user.state = state
