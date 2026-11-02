"""Coding practice helpers: pick problems, review code, record submissions.

The bot never executes student code. Verdicts always say where they came from:
AI review (`ai_correct` / `ai_needs_work`), the student's own report (`self_solved` /
`self_unsolved`), or a plain review without a verdict (`reviewed`).
"""

from __future__ import annotations

import logging
import random
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentContext
from app.db.models import CodingProblem, CodingSubmission
from app.llm import prompts
from app.llm.client import LLMError, parse_json

logger = logging.getLogger(__name__)

LEVEL_TO_DIFFICULTY = {"beginner": "easy", "intermediate": "medium", "advanced": "hard"}


def detect_language(code: str) -> str:
    if re.search(r"#include|std::|cout|cin\s*>>|int main\s*\(|vector<|->|;\s*$", code, re.M):
        return "cpp"
    if re.search(r"^\s*def |^\s*import |print\(|:\s*$|elif |self\.", code, re.M):
        return "python"
    return "other"


def strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[\w+#-]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


async def pick_problem(
    session: AsyncSession, user_id: int, difficulty: str | None, rng: random.Random, topic_id: str | None = None
) -> CodingProblem | None:
    query = select(CodingProblem)
    if difficulty:
        query = query.where(CodingProblem.difficulty == difficulty)
    problems = list((await session.scalars(query)).all())
    if not problems:
        problems = list((await session.scalars(select(CodingProblem))).all())
    if not problems:
        return None
    attempted = set(
        (await session.scalars(select(CodingSubmission.problem_id).where(CodingSubmission.user_id == user_id))).all()
    )
    fresh = [p for p in problems if p.id not in attempted] or problems
    if topic_id:
        on_topic = [p for p in fresh if p.topic_id == topic_id]
        fresh = on_topic or fresh
    return rng.choice(fresh)


def problem_text(p: CodingProblem, title_prefix: str = "🧑‍💻 Practice") -> str:
    tags = ", ".join(t for t in p.tags if t[:1].isupper())  # company-style tags are capitalised
    company = f"\n_Asked in interviews at: {tags}_" if tags else ""
    return (
        f"{title_prefix}: *{p.title}*\n_{p.difficulty.title()} · Pattern: {p.pattern}_{company}\n\n"
        f"{p.statement}\n\n*Example*\n```\n{p.examples}\n```"
    )


def solution_text(p: CodingProblem, language: str) -> str:
    code = p.solution_cpp if language == "cpp" else p.solution_python
    lang_name = "C++" if language == "cpp" else "Python"
    return (
        f"📖 *Solution: {p.title}*\n\n*Key insight:* {p.key_insight}\n\n"
        f"*{lang_name}*\n```\n{code}\n```\n\n"
        f"*Time:* {p.time_complexity}  •  *Space:* {p.space_complexity}"
    )


@dataclass
class Review:
    verdict: str  # ai_correct | ai_needs_work | reviewed | unavailable | not_code
    feedback: str
    language: str


async def review_code(ctx: AgentContext, code: str, problem: CodingProblem | None, request: str = "") -> Review:
    language = detect_language(code)
    if not ctx.llm_available:
        return Review("unavailable", "", language)
    problem_desc = f"{problem.title}: {problem.statement}\nExamples:\n{problem.examples}" if problem else None
    try:
        raw = await ctx.ask_llm(
            prompts.CODE_REVIEW_SYSTEM,
            [{"role": "user", "content": prompts.code_review_prompt(strip_fences(code), problem_desc, request)}],
            temperature=0.2, max_tokens=2200, json_mode=True,
        )
        data = parse_json(raw)
    except LLMError as exc:
        logger.warning("Code review failed: %s", exc)
        return Review("unavailable", "", language)
    verdict_map = {"correct": "ai_correct", "needs_work": "ai_needs_work", "not_code": "not_code"}
    verdict = verdict_map.get(str(data.get("verdict")), "reviewed")
    if not problem and verdict in ("ai_correct", "ai_needs_work"):
        verdict = "reviewed" if verdict == "ai_correct" else "ai_needs_work"
    lang = data.get("language") if data.get("language") in ("cpp", "python") else language
    feedback = str(data.get("feedback") or data.get("summary") or "")
    return Review(verdict, feedback, lang)


async def record_submission(
    ctx: AgentContext, problem: CodingProblem | None, code: str, verdict: str, mode: str,
    language: str = "unknown", feedback: str = "", hints_used: int = 0, complexity_correct: bool | None = None,
) -> CodingSubmission:
    sub = CodingSubmission(
        user_id=ctx.user.id, problem_id=problem.id if problem else None, mode=mode, language=language,
        code=code[:8000], verdict=verdict, feedback=feedback[:4000], hints_used=hints_used,
        complexity_correct=complexity_correct, created_at=ctx.now,
    )
    ctx.session.add(sub)
    return sub


def normalise_complexity(text: str) -> str:
    """'O(N log N)', 'n*log(n)', 'nlogn' → 'nlogn' so complexity answers can be compared."""
    t = text.lower().replace(" ", "").replace("*", "").replace("·", "").replace("×", "")
    t = t.replace("o(", "").replace(")", "").replace("(", "")
    t = t.replace("^2", "²").replace("**2", "²").replace("n2", "n²").replace("sqrt", "√")
    t = t.replace("log₂", "log").replace("log2", "log")
    return t.strip()


# Equivalent ways students write the same multi-variable complexity.
_EQUIVALENTS = {
    "rowscols": {"rowscols", "colsrows", "mn", "nm", "mxn", "nxm", "rc", "cr", "rxc"},
    "amountnumberofcoins": {"amountnumberofcoins", "amountcoins", "coinsamount", "an", "na", "ac", "ca",
                            "nk", "kn", "amountn", "namount", "sn", "ns"},
    "v+e": {"v+e", "e+v", "n+e", "n+m", "m+n", "e+n"},
}


def complexity_matches(answer: str, expected: str) -> bool:
    exp = normalise_complexity(expected)
    ans = normalise_complexity(answer)
    if not ans:
        return False
    return ans == exp or ans in _EQUIVALENTS.get(exp, set())
