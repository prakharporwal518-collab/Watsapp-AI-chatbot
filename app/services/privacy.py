"""Data privacy controls: full deletion of a learner's data."""

from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    CodingSubmission,
    ConversationHistory,
    LearningStreak,
    QuizAttempt,
    QuizSession,
    RevisionSchedule,
    StudyPlan,
    StudySession,
    TopicProgress,
    User,
    UserPreferences,
)

USER_TABLES = (QuizAttempt, QuizSession, TopicProgress, CodingSubmission, StudyPlan, StudySession,
               RevisionSchedule, ConversationHistory, LearningStreak, UserPreferences)

PRIVACY_TEXT = (
    "🔒 *Your privacy*\n\n"
    "*What I store:* your learning progress (topics, quiz answers, streaks, plans, coding attempts), your settings, "
    "and recent chat messages so I can answer follow-up questions.\n\n"
    "*How it's protected:*\n"
    "• Your phone number is stored encrypted, and looked up only via a one-way hash\n"
    "• Chat history and submitted code are encrypted at rest\n"
    "• Chat history is automatically deleted after {days} days\n"
    "• Your data is never shared or sold, and it's isolated from other students\n\n"
    "*Your controls:*\n"
    "• /remind off — stop all reminders\n"
    "• /deletedata — permanently delete everything about you"
)


async def delete_user_data(session: AsyncSession, user: User) -> None:
    """Hard-delete every row belonging to this user (explicitly, so it works on any database)."""
    uid = user.id
    for model in USER_TABLES:
        await session.execute(delete(model).where(model.user_id == uid))
    await session.execute(delete(User).where(User.id == uid))
    session.expunge(user)
