"""Conversation history: gives the LLM context for follow-up questions.

Content is encrypted at rest (EncryptedText) and pruned by age and per-user count.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationHistory

MAX_STORED_CHARS = 2000


async def add_turn(session: AsyncSession, user_id: int, role: str, content: str, agent: str | None, now: datetime) -> None:
    if not content:
        return
    session.add(ConversationHistory(user_id=user_id, role=role, content=content[:MAX_STORED_CHARS], agent=agent, created_at=now))


async def recent_turns(session: AsyncSession, user_id: int, limit: int = 8) -> list[dict]:
    rows = (
        await session.scalars(
            select(ConversationHistory)
            .where(ConversationHistory.user_id == user_id)
            .order_by(ConversationHistory.id.desc())
            .limit(limit)
        )
    ).all()
    return [{"role": r.role, "content": r.content[:1200]} for r in reversed(rows)]


async def prune(session: AsyncSession, retention_days: int, max_per_user: int, now: datetime) -> int:
    """Delete old history. Returns rows removed."""
    cutoff = now - timedelta(days=retention_days)
    result = await session.execute(delete(ConversationHistory).where(ConversationHistory.created_at < cutoff))
    removed = result.rowcount or 0

    user_ids = (await session.scalars(select(ConversationHistory.user_id).distinct())).all()
    for uid in user_ids:
        keep_ids = (
            await session.scalars(
                select(ConversationHistory.id)
                .where(ConversationHistory.user_id == uid)
                .order_by(ConversationHistory.id.desc())
                .limit(max_per_user)
            )
        ).all()
        if keep_ids:
            res = await session.execute(
                delete(ConversationHistory).where(
                    ConversationHistory.user_id == uid, ConversationHistory.id < min(keep_ids)
                )
            )
            removed += res.rowcount or 0
    return removed
