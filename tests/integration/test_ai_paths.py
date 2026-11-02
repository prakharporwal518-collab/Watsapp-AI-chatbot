"""Behaviour when an LLM is configured (using a scripted fake — no network)."""

from sqlalchemy import func, select

from app.db.models import CodingSubmission, QuizQuestion
from tests.conftest import Chat, texts


async def test_ai_lesson_is_formatted_and_split(ai_container, fake_llm):
    chat = Chat(ai_container)
    await chat.onboard()
    replies = await chat.send("explain segment trees")
    body = texts(replies)
    assert "AI LESSON PART ONE" in body and "*AI LESSON PART TWO*" in body  # **bold** converted
    assert "```cpp" not in body and "```" in body  # language tag stripped for WhatsApp
    lesson_call = fake_llm.calls[-1]
    assert "Segment Trees" in lesson_call["messages"][-1]["content"]
    assert "STUDENT PROFILE" in lesson_call["system"] and "C++" in lesson_call["system"]


async def test_ml_lessons_use_ml_template(ai_container, fake_llm):
    chat = Chat(ai_container)
    await chat.onboard()
    await chat.send("explain random forest")
    prompt = fake_llm.calls[-1]["messages"][-1]["content"]
    assert "Practice assignment" in prompt or "practice assignment" in prompt
    assert "Mathematical intuition" in prompt


async def test_llm_failure_falls_back_to_curated_lesson(ai_container, fake_llm):
    chat = Chat(ai_container)
    await chat.onboard()
    fake_llm.fail = True
    body = texts(await chat.send("explain binary search"))
    assert "Search for 23" in body  # curated lesson content


async def test_quiz_shortfall_is_filled_with_validated_ai_questions(ai_container, fake_llm):
    chat = Chat(ai_container)
    await chat.onboard()
    out = texts(await chat.send("Give me 15 python questions"))
    assert "15 questions" in out
    async with ai_container.sessionmaker() as s:
        ai = await s.scalar(select(func.count()).select_from(QuizQuestion).where(QuizQuestion.source == "ai"))
    assert ai == 15 - 9  # bank has 9 python questions


async def test_check_on_topic_without_bank_questions_generates_them(ai_container):
    chat = Chat(ai_container)
    await chat.onboard()
    out = texts(await chat.send(button="check:dsa.segment_tree"))
    assert "3 questions" in out
    q = await chat.current_question()
    assert q.source == "ai" and q.topic_id == "dsa.segment_tree"


async def test_ai_code_review_records_honest_verdict(ai_container):
    chat = Chat(ai_container)
    await chat.onboard()
    await chat.send("give me an easy coding problem")
    code = "def solve(nums, target):\n    seen = {}\n    for i, x in enumerate(nums):\n        seen[x] = i\n    return []"
    reply = texts(await chat.send(code))
    assert "AI review — not executed" in reply
    async with ai_container.sessionmaker() as s:
        sub = await s.scalar(select(CodingSubmission))
    assert sub.verdict == "ai_correct" and sub.problem_id is not None
    assert sub.code.startswith("def solve")  # decrypted transparently


async def test_short_answer_graded_by_ai(ai_container):
    chat = Chat(ai_container)
    await chat.onboard()
    await chat.send(button="check:dsa.big_o")
    while (q := await chat.current_question()) is not None:
        if q.qtype == "short":
            out = texts(await chat.send("constants don't change how it grows"))
            assert "Correct" in out and "Model answer" in out
            return
        await chat.answer_current()


async def test_daily_llm_budget_is_enforced(ai_container, fake_llm):
    ai_container.settings.llm_daily_limit_per_user = 2
    chat = Chat(ai_container)
    await chat.onboard()
    await chat.send("explain segment trees")
    await chat.send("explain fenwick trees")
    calls_before = len(fake_llm.calls)
    body = texts(await chat.send("explain binary search"))
    assert len(fake_llm.calls) == calls_before  # no more LLM calls today
    assert "Search for 23" in body  # curated fallback still teaches


async def test_open_question_uses_history_for_follow_ups(ai_container, fake_llm):
    chat = Chat(ai_container)
    await chat.onboard()
    await chat.send("why is quick sort slow when the pivot is always the smallest element in the array")
    await chat.send("and how can randomising the pivot choice actually help with that problem")
    last = fake_llm.calls[-1]["messages"]
    assert any("quick sort" in m["content"] for m in last[:-1])  # earlier turn included as context


async def test_interview_with_ai(ai_container):
    chat = Chat(ai_container)
    await chat.onboard(level="intermediate")
    await chat.send("mock interview")
    assert "Great approach" in texts(await chat.send("sort and use two pointers"))
    code = "def solve(a):\n    a.sort()\n    i = 0\n    j = len(a) - 1\n    return i + j"
    assert "Step 3" in texts(await chat.send(code))
    card = texts(await chat.send("O(n log n) time, O(1) space"))
    assert "Optimal" in card and "Correct (AI review)" in card
