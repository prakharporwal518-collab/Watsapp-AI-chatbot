"""Idempotent seeding of shared content (curriculum, quiz bank, coding problems)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.coding_problems import PROBLEMS
from app.content.curriculum import TOPICS
from app.content.quiz_bank import QUESTIONS
from app.db.models import CodingProblem, LearningTopic, QuizQuestion

logger = logging.getLogger(__name__)


async def seed_content(session: AsyncSession) -> dict[str, int]:
    counts = {"topics": 0, "questions": 0, "problems": 0}

    existing_topics = {t.id: t for t in (await session.scalars(select(LearningTopic))).all()}
    for topic in TOPICS.values():
        row = existing_topics.get(topic.id) or LearningTopic(id=topic.id)
        row.track, row.module, row.title = topic.track, topic.module, topic.title
        row.order_index, row.level, row.summary = topic.order_index, topic.level, topic.summary
        row.prerequisites, row.quiz_category = list(topic.prerequisites), topic.quiz_category
        if topic.id not in existing_topics:
            session.add(row)
            counts["topics"] += 1

    existing_q = {
        q.external_key: q
        for q in (await session.scalars(select(QuizQuestion).where(QuizQuestion.source == "bank"))).all()
    }
    for q in QUESTIONS:
        row = existing_q.get(q["key"]) or QuizQuestion(external_key=q["key"], source="bank")
        row.category, row.topic_id, row.qtype, row.difficulty = q["category"], q["topic_id"], q["qtype"], q["difficulty"]
        row.prompt, row.code, row.options, row.answer = q["prompt"], q["code"], q["options"], q["answer"]
        row.explanation, row.option_explanations = q["explanation"], q["option_explanations"]
        row.accepted_keywords = q["keywords"]
        if q["key"] not in existing_q:
            session.add(row)
            counts["questions"] += 1

    existing_p = {p.slug: p for p in (await session.scalars(select(CodingProblem))).all()}
    for p in PROBLEMS:
        row = existing_p.get(p["slug"]) or CodingProblem(slug=p["slug"])
        row.title, row.difficulty, row.pattern, row.topic_id = p["title"], p["difficulty"], p["pattern"], p["topic_id"]
        row.statement, row.examples, row.hints, row.key_insight = p["statement"], p["examples"], p["hints"], p["key_insight"]
        row.solution_python, row.solution_cpp = p["solution_python"], p["solution_cpp"]
        row.time_complexity, row.space_complexity, row.tags = p["time"], p["space"], p["tags"]
        if p["slug"] not in existing_p:
            session.add(row)
            counts["problems"] += 1

    await session.commit()
    logger.info("Content seeded: %s new rows", counts)
    return counts
