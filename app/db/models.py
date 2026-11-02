"""Database models. Every learner-owned row hangs off `users.id` with ON DELETE CASCADE,
so deleting a user wipes all of their data (see /deletedata)."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, EncryptedText, utcnow


def _user_fk() -> ForeignKey:
    return ForeignKey("users.id", ondelete="CASCADE")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    wa_id_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    wa_id_encrypted: Mapped[str] = mapped_column(EncryptedText)
    display_name: Mapped[str | None] = mapped_column(EncryptedText, nullable=True)
    level: Mapped[str] = mapped_column(String(20), default="beginner")
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    # Conversation state machine (current mode, active quiz, lesson, pending chunks ...)
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    llm_calls_today: Mapped[int] = mapped_column(Integer, default=0)
    llm_calls_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    preferences: Mapped[UserPreferences] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )
    streak: Mapped[LearningStreak] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[int] = mapped_column(_user_fk(), primary_key=True)
    preferred_language: Mapped[str] = mapped_column(String(10), default="cpp")  # cpp | python
    daily_minutes: Mapped[int] = mapped_column(Integer, default=60)
    goals: Mapped[list] = mapped_column(JSON, default=lambda: ["dsa"])  # dsa, ml, interview, cpp, python
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata")
    reminders_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    reminder_time: Mapped[str] = mapped_column(String(5), default="19:00")  # HH:MM local time
    reminder_consent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reminder_consent_revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_reminder_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    weekly_report_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_weekly_report_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    user: Mapped[User] = relationship(back_populates="preferences")


class LearningTopic(Base):
    """Shared curriculum catalogue (not user data). Seeded from app/content/curriculum.py."""

    __tablename__ = "learning_topics"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)  # e.g. "dsa.binary_search"
    track: Mapped[str] = mapped_column(String(20), index=True)  # dsa | cpp | python | ml
    module: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(120))
    order_index: Mapped[int] = mapped_column(Integer)
    level: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(Text, default="")
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)
    quiz_category: Mapped[str | None] = mapped_column(String(40), nullable=True)


class TopicProgress(Base):
    __tablename__ = "topic_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_topic_progress_user_topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("learning_topics.id"), index=True)
    status: Mapped[str] = mapped_column(String(20), default="not_started")  # not_started|learning|completed
    lessons_viewed: Mapped[int] = mapped_column(Integer, default=0)
    questions_attempted: Mapped[int] = mapped_column(Integer, default=0)
    questions_correct: Mapped[int] = mapped_column(Integer, default=0)
    mastery: Mapped[float] = mapped_column(Float, default=0.0)  # rolling accuracy of recent answers
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class QuizQuestion(Base):
    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_key: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    category: Mapped[str] = mapped_column(String(40), index=True)
    topic_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    qtype: Mapped[str] = mapped_column(String(20))  # mcq | true_false | output | find_error | short
    difficulty: Mapped[str] = mapped_column(String(10), index=True)  # easy | medium | hard
    prompt: Mapped[str] = mapped_column(Text)
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[list] = mapped_column(JSON, default=list)
    answer: Mapped[str] = mapped_column(Text)  # option index (as str) or model answer for "short"
    accepted_keywords: Mapped[list] = mapped_column(JSON, default=list)
    explanation: Mapped[str] = mapped_column(Text, default="")
    option_explanations: Mapped[list] = mapped_column(JSON, default=list)
    source: Mapped[str] = mapped_column(String(10), default="bank")  # bank | ai
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class QuizSession(Base):
    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="quiz")  # quiz | check | revision
    category: Mapped[str] = mapped_column(String(40))
    topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(10), nullable=True)
    question_ids: Mapped[list] = mapped_column(JSON, default=list)
    current_index: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | completed | abandoned
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class QuizAttempt(Base):
    __tablename__ = "quiz_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"), nullable=True
    )
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id", ondelete="CASCADE"))
    topic_id: Mapped[str | None] = mapped_column(String(80), index=True, nullable=True)
    category: Mapped[str] = mapped_column(String(40))
    user_answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean)
    graded_by: Mapped[str] = mapped_column(String(10), default="auto")  # auto | ai | keywords
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class CodingProblem(Base):
    __tablename__ = "coding_problems"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    difficulty: Mapped[str] = mapped_column(String(10), index=True)
    pattern: Mapped[str] = mapped_column(String(60))
    topic_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    statement: Mapped[str] = mapped_column(Text)
    examples: Mapped[str] = mapped_column(Text)
    hints: Mapped[list] = mapped_column(JSON, default=list)
    key_insight: Mapped[str] = mapped_column(Text, default="")
    solution_python: Mapped[str] = mapped_column(Text)
    solution_cpp: Mapped[str] = mapped_column(Text)
    time_complexity: Mapped[str] = mapped_column(String(40))
    space_complexity: Mapped[str] = mapped_column(String(40))
    tags: Mapped[list] = mapped_column(JSON, default=list)


class CodingSubmission(Base):
    __tablename__ = "coding_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    problem_id: Mapped[int | None] = mapped_column(
        ForeignKey("coding_problems.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(20), default="practice")  # practice | interview | review
    language: Mapped[str] = mapped_column(String(10), default="unknown")
    code: Mapped[str] = mapped_column(EncryptedText)
    # We never execute code, so verdicts are honest about their source:
    # ai_correct | ai_needs_work | self_solved | self_unsolved | reviewed
    verdict: Mapped[str] = mapped_column(String(20))
    feedback: Mapped[str] = mapped_column(Text, default="")
    hints_used: Mapped[int] = mapped_column(Integer, default=0)
    complexity_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)


class StudyPlan(Base):
    __tablename__ = "study_plans"
    __table_args__ = (UniqueConstraint("user_id", "plan_date", name="uq_study_plans_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    plan_date: Mapped[date] = mapped_column(Date)
    total_minutes: Mapped[int] = mapped_column(Integer)
    items: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class StudySession(Base):
    """Groups bursts of learning activity; used to *estimate* study time."""

    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    activity_count: Mapped[int] = mapped_column(Integer, default=1)


class RevisionSchedule(Base):
    __tablename__ = "revision_schedules"
    __table_args__ = (UniqueConstraint("user_id", "topic_id", name="uq_revision_schedules_user_topic"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    topic_id: Mapped[str] = mapped_column(ForeignKey("learning_topics.id"))
    due_date: Mapped[date] = mapped_column(Date, index=True)
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    repetitions: Mapped[int] = mapped_column(Integer, default=0)
    ease: Mapped[float] = mapped_column(Float, default=2.5)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class LearningStreak(Base):
    __tablename__ = "learning_streaks"

    user_id: Mapped[int] = mapped_column(_user_fk(), primary_key=True)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    active_dates: Mapped[list] = mapped_column(JSON, default=list)  # last ~60 ISO dates, for reports

    user: Mapped[User] = relationship(back_populates="streak")


class ConversationHistory(Base):
    __tablename__ = "conversation_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(_user_fk(), index=True)
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    agent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content: Mapped[str] = mapped_column(EncryptedText)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
