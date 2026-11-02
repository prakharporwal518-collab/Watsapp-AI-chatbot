"""Spaced repetition (a simplified SM-2) for topic revision."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RevisionSchedule


def sm2_update(interval: int, repetitions: int, ease: float, accuracy: float) -> tuple[int, int, float]:
    """Return the new (interval_days, repetitions, ease) after a review scored `accuracy` (0..1).

    quality q = round(accuracy × 5). q < 3 → forgotten: start over tomorrow.
    Otherwise intervals grow 1 → 3 → interval × ease, and ease adapts to how easy it felt.
    """
    q = round(max(0.0, min(1.0, accuracy)) * 5)
    if q < 3:
        repetitions = 0
        interval = 1
    else:
        repetitions += 1
        if repetitions == 1:
            interval = 1
        elif repetitions == 2:
            interval = 3
        else:
            interval = max(1, round(interval * ease))
    ease = max(1.3, ease + 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
    return min(interval, 120), repetitions, round(ease, 3)


async def get_schedule(session: AsyncSession, user_id: int, topic_id: str) -> RevisionSchedule | None:
    return await session.scalar(
        select(RevisionSchedule).where(RevisionSchedule.user_id == user_id, RevisionSchedule.topic_id == topic_id)
    )


async def ensure_scheduled(session: AsyncSession, user_id: int, topic_id: str, due: date) -> RevisionSchedule:
    """Make sure a topic is in the revision queue no later than `due`."""
    sched = await get_schedule(session, user_id, topic_id)
    if sched is None:
        sched = RevisionSchedule(user_id=user_id, topic_id=topic_id, due_date=due, interval_days=1, repetitions=0, ease=2.5)
        session.add(sched)
    elif sched.due_date > due:
        sched.due_date = due
    return sched


async def apply_review(
    session: AsyncSession, user_id: int, topic_id: str, accuracy: float, today: date, now: datetime
) -> RevisionSchedule:
    sched = await get_schedule(session, user_id, topic_id)
    if sched is None:
        sched = RevisionSchedule(user_id=user_id, topic_id=topic_id, due_date=today, interval_days=1, repetitions=0, ease=2.5)
        session.add(sched)
    sched.interval_days, sched.repetitions, sched.ease = sm2_update(
        sched.interval_days, sched.repetitions, sched.ease, accuracy
    )
    sched.due_date = today + timedelta(days=sched.interval_days)
    sched.last_reviewed_at = now
    return sched


async def due_topics(session: AsyncSession, user_id: int, today: date, limit: int = 10) -> list[RevisionSchedule]:
    rows = await session.scalars(
        select(RevisionSchedule)
        .where(RevisionSchedule.user_id == user_id, RevisionSchedule.due_date <= today)
        .order_by(RevisionSchedule.due_date)
        .limit(limit)
    )
    return list(rows.all())


async def upcoming(session: AsyncSession, user_id: int, limit: int = 5) -> list[RevisionSchedule]:
    rows = await session.scalars(
        select(RevisionSchedule).where(RevisionSchedule.user_id == user_id).order_by(RevisionSchedule.due_date).limit(limit)
    )
    return list(rows.all())
