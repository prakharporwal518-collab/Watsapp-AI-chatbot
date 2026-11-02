"""Daily study plan generation."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.curriculum import TOPICS, TRACKS
from app.db.models import StudyPlan, User
from app.services import progress, revision


@dataclass
class PlanItem:
    kind: str  # revise | learn | practice | quiz | interview
    title: str
    minutes: int
    action: str  # button id that starts this item
    detail: str = ""


def learning_tracks(goals: list[str]) -> list[str]:
    tracks = [g for g in goals if g in TRACKS]
    if "interview" in goals and "dsa" not in tracks:
        tracks.insert(0, "dsa")
    return tracks or ["dsa"]


async def build_plan(session: AsyncSession, user: User, now) -> list[PlanItem]:
    prefs = user.preferences
    budget = max(10, min(prefs.daily_minutes if prefs else 60, 480))
    goals = (prefs.goals if prefs else None) or ["dsa"]
    today = progress.local_date(user, now)
    learn_minutes = 15 if budget < 45 else 25 if budget < 120 else 40

    candidates: list[PlanItem] = []
    due = await revision.due_topics(session, user.id, today, limit=2)
    for d in due:
        if d.topic_id in TOPICS:
            candidates.append(PlanItem("revise", f"Revise {TOPICS[d.topic_id].title}", 10, "cmd:revision", "spaced repetition"))
    if not due:
        weak = await progress.weak_topics(session, user.id)
        if weak and weak[0].topic_id in TOPICS:
            t = TOPICS[weak[0].topic_id]
            candidates.append(PlanItem("revise", f"Strengthen {t.title}", 10, f"simpler:{t.id}", "weak topic"))

    in_plan = {d.topic_id for d in due} | {c.action.split(":", 1)[1] for c in candidates if c.action.startswith("simpler:")}
    learn_items = []
    for track in learning_tracks(goals):
        rec = await progress.recommend_next(session, user, track, exclude=in_plan)
        if rec:
            learn_items.append(PlanItem("learn", f"Learn {rec.topic.title}", learn_minutes, f"learn:{rec.topic.id}", TRACKS[track]))

    quiz_item = PlanItem("quiz", "Daily quiz (5 questions)", 10, "quiz:auto", "mixed")
    practice_item = None
    if any(g in goals for g in ("dsa", "interview", "cpp", "python")):
        diff = {"beginner": "easy", "intermediate": "medium", "advanced": "hard"}.get(user.level, "easy")
        practice_item = PlanItem("practice", f"Solve 1 {diff} coding problem", 20, f"prac:new:{diff}", "coding practice")
    interview_item = PlanItem("interview", "Mock coding interview", 30, "cmd:interview") if "interview" in goals else None

    ordered = candidates + learn_items[:1] + [quiz_item]
    if practice_item:
        ordered.append(practice_item)
    ordered += learn_items[1:]
    if interview_item:
        ordered.append(interview_item)

    plan: list[PlanItem] = []
    remaining = budget
    for item in ordered:
        if item.minutes <= remaining:
            plan.append(item)
            remaining -= item.minutes
    if not plan and ordered:  # tiny budget: at least one thing
        first = ordered[0]
        first.minutes = budget
        plan.append(first)
    return plan


async def save_plan(session: AsyncSession, user: User, items: list[PlanItem], now) -> StudyPlan:
    today = progress.local_date(user, now)
    plan = await session.scalar(select(StudyPlan).where(StudyPlan.user_id == user.id, StudyPlan.plan_date == today))
    if plan is None:
        plan = StudyPlan(user_id=user.id, plan_date=today, total_minutes=0, items=[], created_at=now)
        session.add(plan)
    plan.items = [asdict(i) for i in items]
    plan.total_minutes = sum(i.minutes for i in items)
    return plan


ICONS = {"revise": "🔁", "learn": "📖", "practice": "🧑‍💻", "quiz": "📝", "interview": "🎤"}


def render_plan(items: list[PlanItem], date_label: str, budget: int) -> str:
    total = sum(i.minutes for i in items)
    lines = [f"📅 *Your study plan — {date_label}*", f"_{total} of your {budget} min_", ""]
    for n, item in enumerate(items, 1):
        detail = f" _({item.detail})_" if item.detail else ""
        lines.append(f"{n}. {ICONS.get(item.kind, '•')} {item.title} — {item.minutes} min{detail}")
    lines.append("\nTap an item below to start 👇")
    return "\n".join(lines)
