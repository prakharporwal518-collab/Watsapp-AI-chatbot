"""Learning progress tracking: activity, streaks, study time, topic mastery and recommendations.

Rules (kept deliberately simple and transparent):
* Opening a lesson marks a topic as *learning* — never *completed*.
* A topic becomes *completed* only after at least COMPLETION_MIN_ATTEMPTS answered questions on it
  with a rolling accuracy ≥ COMPLETION_ACCURACY (from understanding checks, quizzes or revision).
* A topic is *weak* when accuracy < WEAK_ACCURACY over at least WEAK_MIN_ATTEMPTS answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.curriculum import TOPICS, Topic, topics_for_track
from app.db.models import LearningStreak, QuizAttempt, StudySession, TopicProgress, User
from app.services import revision

COMPLETION_MIN_ATTEMPTS = 3
COMPLETION_ACCURACY = 0.7
WEAK_MIN_ATTEMPTS = 3
WEAK_ACCURACY = 0.6
STRONG_MIN_ATTEMPTS = 5
STRONG_ACCURACY = 0.8
ROLLING_WINDOW = 10
SESSION_GAP = timedelta(minutes=15)
SESSION_BASE_MINUTES = 2  # reading time credited for a burst of activity


def user_tz(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.preferences.timezone if user.preferences else "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_date(user: User, now: datetime) -> date:
    return now.replace(tzinfo=UTC).astimezone(user_tz(user)).date()


# ----------------------------------------------------------------------------- streaks
def update_streak(streak: LearningStreak, today: date) -> bool:
    """Count `today` as an active learning day. Returns True if the streak changed."""
    last = streak.last_active_date
    if last == today:
        return False
    if last is not None and last == today - timedelta(days=1):
        streak.current_streak = (streak.current_streak or 0) + 1
    else:
        streak.current_streak = 1
    streak.longest_streak = max(streak.longest_streak or 0, streak.current_streak)
    streak.last_active_date = today
    dates = list(streak.active_dates or [])
    dates.append(today.isoformat())
    streak.active_dates = dates[-60:]
    return True


def effective_streak(streak: LearningStreak | None, today: date) -> int:
    """Current streak as of today (0 if the student missed yesterday and hasn't studied today)."""
    if not streak or not streak.last_active_date:
        return 0
    if streak.last_active_date >= today - timedelta(days=1):
        return streak.current_streak
    return 0


# ----------------------------------------------------------------------------- activity
async def record_activity(session: AsyncSession, user: User, now: datetime) -> None:
    """Called for real learning actions (lessons, answers, practice) — not for 'hi' or menus."""
    if user.streak is None:
        user.streak = LearningStreak(active_dates=[])
    update_streak(user.streak, local_date(user, now))

    last = await session.scalar(
        select(StudySession).where(StudySession.user_id == user.id).order_by(StudySession.last_activity_at.desc()).limit(1)
    )
    if last and now - last.last_activity_at <= SESSION_GAP:
        last.last_activity_at = now
        last.activity_count += 1
    else:
        session.add(StudySession(user_id=user.id, started_at=now, last_activity_at=now, activity_count=1))


async def estimated_study_minutes(session: AsyncSession, user_id: int, since: datetime | None = None) -> int:
    query = select(StudySession).where(StudySession.user_id == user_id)
    if since:
        query = query.where(StudySession.started_at >= since)
    total = 0.0
    for s in (await session.scalars(query)).all():
        total += (s.last_activity_at - s.started_at).total_seconds() / 60 + SESSION_BASE_MINUTES
    return round(total)


# ----------------------------------------------------------------------------- topics
async def get_topic_progress(session: AsyncSession, user_id: int, topic_id: str) -> TopicProgress:
    tp = await session.scalar(
        select(TopicProgress).where(TopicProgress.user_id == user_id, TopicProgress.topic_id == topic_id)
    )
    if tp is None:
        tp = TopicProgress(
            user_id=user_id, topic_id=topic_id, status="not_started",
            lessons_viewed=0, questions_attempted=0, questions_correct=0, mastery=0.0,
        )
        session.add(tp)
    return tp


async def progress_map(session: AsyncSession, user_id: int) -> dict[str, TopicProgress]:
    rows = await session.scalars(select(TopicProgress).where(TopicProgress.user_id == user_id))
    return {r.topic_id: r for r in rows.all()}


async def mark_lesson_viewed(session: AsyncSession, user: User, topic_id: str, now: datetime) -> TopicProgress:
    tp = await get_topic_progress(session, user.id, topic_id)
    tp.lessons_viewed = (tp.lessons_viewed or 0) + 1
    if tp.status == "not_started":
        tp.status = "learning"
        tp.started_at = now
    tp.last_activity_at = now
    return tp


@dataclass
class AnswerOutcome:
    topic_completed_now: bool
    became_weak: bool
    mastery: float


async def record_answer(
    session: AsyncSession, user: User, topic_id: str | None, is_correct: bool, now: datetime
) -> AnswerOutcome:
    """Update topic statistics after a graded answer (the QuizAttempt row must already be added)."""
    if not topic_id or topic_id not in TOPICS:
        return AnswerOutcome(False, False, 0.0)
    await session.flush()
    tp = await get_topic_progress(session, user.id, topic_id)
    was_weak = is_weak(tp)
    tp.questions_attempted = (tp.questions_attempted or 0) + 1
    tp.questions_correct = (tp.questions_correct or 0) + (1 if is_correct else 0)
    tp.last_activity_at = now
    if tp.status == "not_started":
        tp.status = "learning"
        tp.started_at = now

    recent = (
        await session.scalars(
            select(QuizAttempt.is_correct)
            .where(QuizAttempt.user_id == user.id, QuizAttempt.topic_id == topic_id)
            .order_by(QuizAttempt.id.desc())
            .limit(ROLLING_WINDOW)
        )
    ).all()
    tp.mastery = round(sum(1 for r in recent if r) / len(recent), 3) if recent else 0.0

    completed_now = False
    if tp.status != "completed" and tp.questions_attempted >= COMPLETION_MIN_ATTEMPTS and tp.mastery >= COMPLETION_ACCURACY:
        tp.status = "completed"
        tp.completed_at = now
        completed_now = True
        # First revision tomorrow (spaced repetition starts).
        await revision.ensure_scheduled(session, user.id, topic_id, local_date(user, now) + timedelta(days=1))

    became_weak = is_weak(tp) and not was_weak
    if became_weak:
        await revision.ensure_scheduled(session, user.id, topic_id, local_date(user, now) + timedelta(days=1))
    return AnswerOutcome(completed_now, became_weak, tp.mastery)


def accuracy(tp: TopicProgress) -> float:
    return (tp.questions_correct or 0) / tp.questions_attempted if tp.questions_attempted else 0.0


def is_weak(tp: TopicProgress) -> bool:
    return (tp.questions_attempted or 0) >= WEAK_MIN_ATTEMPTS and tp.mastery < WEAK_ACCURACY


def is_strong(tp: TopicProgress) -> bool:
    return (tp.questions_attempted or 0) >= STRONG_MIN_ATTEMPTS and tp.mastery >= STRONG_ACCURACY


async def weak_topics(session: AsyncSession, user_id: int) -> list[TopicProgress]:
    rows = [tp for tp in (await progress_map(session, user_id)).values() if is_weak(tp)]
    return sorted(rows, key=lambda tp: tp.mastery)


async def strong_topics(session: AsyncSession, user_id: int) -> list[TopicProgress]:
    rows = [tp for tp in (await progress_map(session, user_id)).values() if is_strong(tp)]
    return sorted(rows, key=lambda tp: -tp.mastery)


# ----------------------------------------------------------------------------- recommendations
@dataclass
class Recommendation:
    topic: Topic
    reason: str
    kind: str  # revise | continue | new


def primary_track(user: User) -> str:
    goals = (user.preferences.goals if user.preferences else None) or ["dsa"]
    for g in goals:
        if g in ("dsa", "ml", "cpp", "python"):
            return g
    return "ml" if "ml" in goals else "dsa"


async def recommend_next(
    session: AsyncSession, user: User, track: str | None = None, now: datetime | None = None,
    exclude: set[str] | None = None,
) -> Recommendation | None:
    """Priority: due revision / weak topic → topic in progress → next new topic whose prerequisites are done."""
    track = track or (user.state or {}).get("track") or primary_track(user)
    pmap = await progress_map(session, user.id)
    exclude = exclude or set()

    if now is not None:
        for sched in await revision.due_topics(session, user.id, local_date(user, now), limit=5):
            topic = TOPICS.get(sched.topic_id)
            if topic and topic.track == track and topic.id not in exclude:
                return Recommendation(topic, "it's due for revision today (spaced repetition)", "revise")

    weak = [tp for tp in pmap.values() if is_weak(tp) and tp.topic_id not in exclude
            and TOPICS.get(tp.topic_id) and TOPICS[tp.topic_id].track == track]
    if weak:
        tp = min(weak, key=lambda t: t.mastery)
        return Recommendation(TOPICS[tp.topic_id], f"your accuracy here is {round(tp.mastery * 100)}% — let's strengthen it", "revise")

    ordered = topics_for_track(track)
    for topic in ordered:
        tp = pmap.get(topic.id)
        if tp and tp.status == "learning" and topic.id not in exclude:
            return Recommendation(topic, "you started it but haven't passed an understanding check yet", "continue")

    done = {tid for tid, tp in pmap.items() if tp.status == "completed"}
    for topic in ordered:
        if topic.id in done or topic.id in exclude:
            continue
        if all(p in done or (pmap.get(p) and pmap[p].status == "learning") for p in topic.prerequisites):
            first = not pmap
            return Recommendation(topic, "a great starting point" if first else "it's the next step in your learning path", "new")
    return None


def track_counts(pmap: dict[str, TopicProgress], track: str) -> dict[str, int]:
    counts = {"completed": 0, "learning": 0, "not_started": 0, "total": 0}
    for topic in topics_for_track(track):
        counts["total"] += 1
        status = pmap[topic.id].status if topic.id in pmap else "not_started"
        counts[status] = counts.get(status, 0) + 1
    return counts
