"""Quiz engine: choose questions, render them for WhatsApp, parse and grade answers."""

from __future__ import annotations

import logging
import math
import random
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.curriculum import QUIZ_CATEGORIES, TOPICS
from app.db.models import QuizAttempt, QuizQuestion
from app.llm import prompts
from app.llm.client import LLMClient, LLMError, parse_json
from app.whatsapp import messages as wa

logger = logging.getLogger(__name__)

LETTERS = "ABCD"
QTYPE_LABEL = {
    "mcq": "Multiple choice",
    "true_false": "True / False",
    "output": "Predict the output",
    "find_error": "Find the error",
    "short": "Short answer",
}
DIFF_EMOJI = {"easy": "🟢", "medium": "🟡", "hard": "🔴"}


# ----------------------------------------------------------------------------- selection
async def select_questions(
    session: AsyncSession,
    user_id: int,
    categories: list[str],
    count: int,
    difficulty: str | None = None,
    topic_ids: list[str] | None = None,
    rng: random.Random | None = None,
) -> list[QuizQuestion]:
    """Pick questions, preferring ones this student hasn't answered recently."""
    rng = rng or random.Random()
    query = select(QuizQuestion)
    if topic_ids:
        query = query.where(QuizQuestion.topic_id.in_(topic_ids))
    else:
        query = query.where(QuizQuestion.category.in_(categories))
    if difficulty:
        query = query.where(QuizQuestion.difficulty == difficulty)
    pool = list((await session.scalars(query)).all())

    recent = set(
        (
            await session.scalars(
                select(QuizAttempt.question_id).where(QuizAttempt.user_id == user_id).order_by(QuizAttempt.id.desc()).limit(60)
            )
        ).all()
    )
    fresh = [q for q in pool if q.id not in recent]
    seen = [q for q in pool if q.id in recent]
    rng.shuffle(fresh)
    rng.shuffle(seen)
    chosen = (fresh + seen)[:count]
    if not difficulty:  # gentle ramp: easy → medium → hard
        order = {"easy": 0, "medium": 1, "hard": 2}
        chosen.sort(key=lambda q: order.get(q.difficulty, 1))
    return chosen


async def generate_questions(
    session: AsyncSession,
    llm: LLMClient,
    category: str,
    count: int,
    difficulty: str,
    topic_id: str | None = None,
) -> list[QuizQuestion]:
    """Ask the LLM for extra questions; only well-formed ones are stored and returned."""
    if not llm.available or count <= 0:
        return []
    existing = (await session.scalars(select(QuizQuestion.prompt).where(QuizQuestion.category == category).limit(30))).all()
    topic_title = TOPICS[topic_id].title if topic_id and topic_id in TOPICS else None
    try:
        raw = await llm.complete(
            prompts.QUIZ_GEN_SYSTEM,
            [{"role": "user", "content": prompts.quiz_gen_prompt(
                QUIZ_CATEGORIES.get(category, category), topic_title, difficulty, count, list(existing))}],
            temperature=0.7,
            max_tokens=2500,
            json_mode=True,
        )
        data = parse_json(raw)
    except LLMError as exc:
        logger.warning("Quiz generation failed: %s", exc)
        return []

    created: list[QuizQuestion] = []
    default_topic = topic_id or _default_topic_for(category)
    for item in (data.get("questions") or [])[:count]:
        q = _validate_generated(item)
        if not q:
            continue
        row = QuizQuestion(
            category=category, topic_id=default_topic, qtype=q["qtype"], difficulty=difficulty,
            prompt=q["prompt"], code=q["code"] or None, options=q["options"], answer=str(q["answer_index"]),
            explanation=q["explanation"], option_explanations=q["option_explanations"], accepted_keywords=[],
            source="ai",
        )
        session.add(row)
        created.append(row)
    await session.flush()
    return created


def _default_topic_for(category: str) -> str | None:
    for t in TOPICS.values():
        if t.quiz_category == category:
            return t.id
    return None


def _validate_generated(item: dict) -> dict | None:
    try:
        qtype = item.get("qtype", "mcq")
        if qtype not in {"mcq", "output", "find_error", "true_false"}:
            qtype = "mcq"
        options = [str(o).strip() for o in item["options"]]
        idx = int(item["answer_index"])
        prompt = str(item["prompt"]).strip()
    except (KeyError, TypeError, ValueError):
        return None
    if qtype == "true_false":
        options = ["True", "False"]
    if not prompt or len(options) not in (2, 3, 4) or not 0 <= idx < len(options) or len(set(options)) != len(options):
        return None
    why = item.get("option_explanations") or []
    if not isinstance(why, list) or len(why) != len(options):
        why = []
    return {
        "qtype": qtype,
        "prompt": prompt[:600],
        "code": str(item.get("code") or "")[:900],
        "options": [o[:120] for o in options],
        "answer_index": idx,
        "explanation": str(item.get("explanation") or "")[:700],
        "option_explanations": [str(w)[:200] for w in why],
    }


# ----------------------------------------------------------------------------- rendering
def render_question(q: QuizQuestion, session_id: int, index: int, total: int) -> list[wa.OutgoingMessage]:
    header = f"*Q{index + 1}/{total}* · {DIFF_EMOJI.get(q.difficulty, '')} {q.difficulty.title()} · _{QTYPE_LABEL.get(q.qtype, 'Question')}_"
    body = f"{header}\n\n{q.prompt}"
    if q.code:
        body += f"\n```\n{q.code}\n```"

    if q.qtype == "short":
        return [wa.text(body + "\n\n✍️ Type your answer in your own words.")]

    if q.qtype == "true_false":
        items = [(f"qa:{session_id}:{q.id}:{i}", opt) for i, opt in enumerate(q.options)]
        return _interactive(body, items, use_list=False)

    body += "\n\n" + "\n".join(f"*{LETTERS[i]})* {opt}" for i, opt in enumerate(q.options))
    if len(q.options) <= 3:
        items = [(f"qa:{session_id}:{q.id}:{i}", f"Option {LETTERS[i]}") for i in range(len(q.options))]
        return _interactive(body, items, use_list=False)
    rows = [(f"qa:{session_id}:{q.id}:{i}", f"Option {LETTERS[i]}", opt) for i, opt in enumerate(q.options)]
    return _interactive(body, rows, use_list=True)


def _interactive(body: str, items: list, use_list: bool) -> list[wa.OutgoingMessage]:
    prompt_text = "Pick your answer 👇 (or type A, B, C, D)" if use_list else "Pick your answer 👇"
    if len(body) <= wa.INTERACTIVE_BODY_MAX - 60:
        msg = wa.list_menu(body, items, button="Answer") if use_list else wa.buttons(body, items)
        return [msg]
    follow = wa.list_menu(prompt_text, items, button="Answer") if use_list else wa.buttons(prompt_text, items)
    return [wa.text(body), follow]


# ----------------------------------------------------------------------------- answers
_TRUE = {"true", "t", "yes", "y", "correct", "right"}
_FALSE = {"false", "f", "no", "n", "wrong", "incorrect"}


def parse_choice(q: QuizQuestion, text: str, button_id: str | None) -> int | None:
    """Turn a reply ('b', 'B)', '2', 'option c', 'true', a button id …) into an option index."""
    if button_id and button_id.startswith("qa:"):
        try:
            return int(button_id.rsplit(":", 1)[1])
        except ValueError:
            return None
    t = text.strip().lower()
    n = len(q.options)
    if q.qtype == "true_false":
        if t in _TRUE or t in {"a", "1"}:
            return 0
        if t in _FALSE or t in {"b", "2"}:
            return 1
    m = re.fullmatch(r"(?:option|ans(?:wer)?|choice)?\s*[:\-]?\s*\(?([a-d])\)?[.)]?", t)
    if m and LETTERS.lower().index(m.group(1)) < n:
        return LETTERS.lower().index(m.group(1))
    m = re.fullmatch(r"(?:option)?\s*([1-4])[.)]?", t)
    if m and int(m.group(1)) <= n:
        return int(m.group(1)) - 1
    for i, opt in enumerate(q.options):
        if t == opt.strip().lower():
            return i
    return None


@dataclass
class GradeResult:
    correct: bool
    graded_by: str
    feedback: str = ""
    user_answer: str = ""


def grade_choice(q: QuizQuestion, choice: int) -> GradeResult:
    return GradeResult(correct=str(choice) == str(q.answer), graded_by="auto", user_answer=LETTERS[choice])


async def grade_short(q: QuizQuestion, answer: str, llm: LLMClient) -> GradeResult:
    if llm.available:
        try:
            raw = await llm.complete(
                prompts.GRADE_SYSTEM,
                [{"role": "user", "content": prompts.grade_prompt(q.prompt, q.answer, answer)}],
                temperature=0.0, max_tokens=400, json_mode=True,
            )
            data = parse_json(raw)
            fb = str(data.get("feedback", ""))
            if data.get("misconception"):
                fb += f"\n_Misconception:_ {data['misconception']}"
            return GradeResult(bool(data.get("correct")), "ai", fb, answer)
        except LLMError as exc:
            logger.warning("AI grading failed, falling back to keywords: %s", exc)
    return grade_by_keywords(q, answer)


def grade_by_keywords(q: QuizQuestion, answer: str) -> GradeResult:
    groups = q.accepted_keywords or []
    text = " " + re.sub(r"[^a-z0-9 ]+", " ", answer.lower()) + " "
    text_compact = answer.lower()
    matched = 0
    for group in groups:
        alts = [a.strip().lower() for a in group.split("|") if a.strip()]
        if any(f" {a} " in text or (("-" in a or " " in a) and a in text_compact) for a in alts):
            matched += 1
    needed = max(1, math.ceil(len(groups) * 0.6)) if groups else 1
    correct = matched >= needed
    fb = "Your answer covers the key idea." if correct else "Your answer is missing some key ideas."
    return GradeResult(correct, "keywords", fb, answer)


def feedback_text(q: QuizQuestion, result: GradeResult, choice: int | None) -> str:
    lines = ["✅ *Correct!*" if result.correct else "❌ *Not quite.*"]
    if q.qtype == "short":
        if result.feedback:
            lines.append(result.feedback)
        lines.append(f"\n*Model answer:* {q.answer}")
    else:
        ans = int(q.answer)
        lines.append(f"*Answer:* {LETTERS[ans]}) {q.options[ans]}")
    if q.explanation:
        lines.append(f"*Why:* {q.explanation}")
    if q.qtype != "short" and q.option_explanations:
        ans = int(q.answer)
        others = [
            f"• {LETTERS[i]}) {q.option_explanations[i]}"
            for i in range(len(q.options))
            if i != ans and i < len(q.option_explanations) and q.option_explanations[i]
        ]
        if not result.correct and choice is not None and choice != ans and choice < len(q.option_explanations):
            lines.append(f"*Your choice ({LETTERS[choice]}):* {q.option_explanations[choice]}")
        elif others:
            lines.append("*Other options:*\n" + "\n".join(others))
    return "\n".join(lines)
