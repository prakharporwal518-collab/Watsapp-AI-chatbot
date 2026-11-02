"""End-to-end conversations through the real pipeline, orchestrator and database (offline LLM)."""

from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.db.models import (
    CodingSubmission,
    ConversationHistory,
    QuizAttempt,
    RevisionSchedule,
    StudyPlan,
    TopicProgress,
    User,
)
from app.services.privacy import USER_TABLES
from tests.conftest import Chat, texts


async def _progress(chat: Chat, topic_id: str) -> TopicProgress | None:
    user = await chat.user()
    async with chat.c.sessionmaker() as s:
        return await s.scalar(select(TopicProgress).where(TopicProgress.user_id == user.id, TopicProgress.topic_id == topic_id))


async def test_onboarding_saves_preferences(container):
    chat = Chat(container)
    first = await chat.send("hello")
    assert "main goal" in texts(first)
    final = await chat.onboard(goal="dsa ml", lang="python", level="intermediate", minutes="90")
    assert "All set, Asha" in texts(final)
    async with container.sessionmaker() as s:
        from sqlalchemy.orm import selectinload

        user = await s.scalar(select(User).options(selectinload(User.preferences)))
        assert user.onboarded and user.level == "intermediate"
        assert user.preferences.goals == ["dsa", "ml"]
        assert user.preferences.preferred_language == "python"
        assert user.preferences.daily_minutes == 90
        assert user.preferences.reminders_enabled is False  # no consent given yet


async def test_lesson_alone_never_completes_a_topic(container):
    chat = Chat(container)
    await chat.onboard()
    replies = await chat.send("explain binary search")
    body = texts(replies)
    assert "Binary Search" in body and "```" in body and "Common mistakes" in body
    assert replies[-1].kind == "buttons"
    for _ in range(3):
        await chat.send("explain binary search")
    tp = await _progress(chat, "dsa.binary_search")
    assert tp.status == "learning" and tp.lessons_viewed == 4


async def test_understanding_check_completes_topic(container):
    chat = Chat(container)
    await chat.onboard()
    await chat.send("explain binary search")
    start = await chat.send(button="check:dsa.binary_search")
    assert "Understanding check" in texts(start)
    for _ in range(3):
        out = await chat.answer_current(correct=True)
    body = texts(out)
    assert "completed Binary Search" in body and "3/3" in body
    tp = await _progress(chat, "dsa.binary_search")
    assert tp.status == "completed" and tp.questions_correct == 3 and tp.mastery == 1.0
    user = await chat.user()
    async with container.sessionmaker() as s:
        sched = await s.scalar(select(RevisionSchedule).where(RevisionSchedule.user_id == user.id))
        assert sched.topic_id == "dsa.binary_search"


async def test_wrong_answers_mark_weak_topic_and_schedule_revision(container):
    chat = Chat(container)
    await chat.onboard()
    await chat.send(button="check:dsa.binary_search")
    for _ in range(3):
        await chat.answer_current(correct=False)
    tp = await _progress(chat, "dsa.binary_search")
    assert tp.status == "learning" and tp.mastery == 0.0
    weak = texts(await chat.send("my weak topics"))
    assert "Binary Search" in weak and "0%" in weak
    rec = texts(await chat.send("what should I learn next?"))
    assert "Binary Search" in rec


async def test_quiz_scores_match_database(container):
    chat = Chat(container)
    await chat.onboard()
    out = await chat.send("Give me 4 python questions")
    assert "4 questions" in texts(out)
    pattern = [True, False, True, True]
    for ok in pattern:
        out = await chat.answer_current(correct=ok)
    summary = texts(out)
    assert "3/4" in summary and "75%" in summary
    user = await chat.user()
    async with container.sessionmaker() as s:
        rows = (await s.scalars(select(QuizAttempt).where(QuizAttempt.user_id == user.id))).all()
    assert [r.is_correct for r in rows] == pattern
    progress = texts(await chat.send("/progress"))
    assert "Quiz answers:* 4" in progress and "75%" in progress


async def test_invalid_answer_does_not_advance(container):
    chat = Chat(container)
    await chat.onboard()
    await chat.send("Give me 2 python questions")
    q1 = await chat.current_question()
    reply = texts(await chat.send("banana"))
    assert "Please answer with" in reply
    assert (await chat.current_question()).id == q1.id


async def test_stale_button_is_rejected(container):
    chat = Chat(container)
    await chat.onboard()
    await chat.send("Give me 3 python questions")
    q1 = await chat.current_question()
    await chat.answer_current()
    user = await chat.user()
    stale = await chat.send(button=f"qa:{user.state['quiz_session_id']}:{q1.id}:0")
    assert "earlier question" in texts(stale)


async def test_stop_quiz_keeps_answered_results(container):
    chat = Chat(container)
    await chat.onboard()
    await chat.send("Give me 5 python questions")
    await chat.answer_current(correct=True)
    stopped = texts(await chat.send("stop"))
    assert "1/1" in stopped
    assert (await chat.user()).state.get("mode") is None
    assert "no quiz running" in texts(await chat.send("b")).lower()


async def test_difficulty_filter_is_respected(container):
    chat = Chat(container)
    await chat.onboard()
    await chat.send("Give me a hard python quiz")
    q = await chat.current_question()
    assert q.difficulty == "hard" and q.category == "python"


async def test_reports_with_no_data_do_not_invent_numbers(container):
    chat = Chat(container)
    await chat.onboard()
    assert "Nothing recorded yet" in texts(await chat.send("/progress"))
    assert "Not enough data yet" in texts(await chat.send("/weakness"))
    assert "No coding attempts yet" in texts(await chat.send("my coding performance"))
    weekly = texts(await chat.send("weekly report"))
    assert "Quiz answers: 0" in weekly


async def test_streak_counts_learning_days_only(container, clock):
    chat = Chat(container)
    await chat.onboard()
    await chat.send("hi")
    assert "Current: *0 days*" in texts(await chat.send("/streak"))
    await chat.send("explain stacks")
    clock.now += timedelta(days=1)
    await chat.send("explain recursion")
    streak = texts(await chat.send("/streak"))
    assert "Current: *2 days*" in streak


async def test_revision_flow_updates_schedule(container, clock):
    chat = Chat(container)
    await chat.onboard()
    await chat.send(button="check:dsa.binary_search")
    for _ in range(3):
        await chat.answer_current(correct=True)
    assert "Nothing is due" in texts(await chat.send("/revision"))
    clock.now += timedelta(days=1)
    start = texts(await chat.send("/revision"))
    assert "Revision" in start and "Binary Search" in start
    out = None
    while await chat.current_question():
        out = await chat.answer_current(correct=True)
    assert "Revision schedule updated" in texts(out)
    user = await chat.user()
    async with container.sessionmaker() as s:
        sched = await s.scalar(select(RevisionSchedule).where(RevisionSchedule.user_id == user.id))
    assert sched.repetitions == 1 and sched.due_date > clock.now.date()


async def test_daily_plan_is_saved_without_duplicates(container):
    chat = Chat(container)
    await chat.onboard(minutes="120")
    await chat.send(button="check:dsa.binary_search")
    for _ in range(3):
        await chat.answer_current(correct=False)
    plan = await chat.send("/dailyplan")
    rows = [r.id for r in plan[0].rows]
    assert len(rows) == len(set(rows))
    assert not ("simpler:dsa.binary_search" in rows and "learn:dsa.binary_search" in rows)
    async with container.sessionmaker() as s:
        assert (await s.scalar(select(func.count()).select_from(StudyPlan))) == 1


async def test_practice_problem_hint_solution_and_self_report(container):
    chat = Chat(container)
    await chat.onboard()
    problem = texts(await chat.send("give me an easy coding problem"))
    assert "Practice" in problem and "Example" in problem
    assert "Hint 1/3" in texts(await chat.send("hint"))
    solution = texts(await chat.send("show solution"))
    assert "Solution" in solution and "Time:" in solution
    done = texts(await chat.send(button="prac:solved"))
    assert "self-reported" in done
    async with container.sessionmaker() as s:
        sub = await s.scalar(select(CodingSubmission))
    assert sub.verdict == "self_solved" and sub.hints_used == 1
    assert "solved: *1*" in texts(await chat.send("my coding performance"))


async def test_code_review_without_ai_is_honest(container):
    chat = Chat(container)
    await chat.onboard()
    reply = texts(await chat.send("#include <iostream>\nint main() {\n    std::cout << 1;\n    return 0;\n}"))
    assert "needs the AI tutor" in reply
    async with container.sessionmaker() as s:
        assert (await s.scalar(select(func.count()).select_from(CodingSubmission))) == 0


async def test_mock_interview_offline(container):
    chat = Chat(container)
    await chat.onboard()
    start = texts(await chat.send("Start a mock coding interview"))
    assert "Step 1" in start
    assert "Step 2" in texts(await chat.send("I would use a loop and a hash map"))
    code = "def solve(nums):\n    seen = {}\n    for x in nums:\n        seen[x] = True\n    return seen"
    assert "reference solution" in texts(await chat.send(code))
    assert "Step 3" in texts(await chat.send("yes it works"))
    card = texts(await chat.send("O(n) time and O(1) space"))
    assert "Interview scorecard" in card and "Not rated (AI unavailable)" in card
    async with container.sessionmaker() as s:
        sub = await s.scalar(select(CodingSubmission))
    assert sub.mode == "interview" and sub.verdict == "self_solved"


async def test_long_content_paginates_with_more(container):
    container.settings.max_chunks_per_reply = 2
    chat = Chat(container)
    await chat.onboard()
    first = await chat.send("explain binary search")
    assert "reply *more*" in texts(first)
    more = texts(await chat.send("more"))
    assert "Common mistakes" in more or "Line by line" in more


async def test_settings_and_reminder_consent(container):
    chat = Chat(container)
    await chat.onboard()
    assert "120 minutes" in texts(await chat.send("I can study 2 hours a day"))
    assert "19:30" in texts(await chat.send("remind me at 7:30 pm"))
    user = await chat.user()
    async with container.sessionmaker() as s:
        from app.db.models import UserPreferences

        prefs = await s.get(UserPreferences, user.id)
        assert prefs.reminders_enabled and prefs.reminder_consent_at is not None
    assert "turned off" in texts(await chat.send("stop reminders"))
    settings = texts(await chat.send("/settings"))
    assert "Daily reminder: off" in settings and "120 min" in settings


async def test_delete_my_data_removes_everything(container):
    chat = Chat(container)
    await chat.onboard()
    await chat.send("explain stacks")
    await chat.send("Give me 2 python questions")
    await chat.answer_current()
    other = Chat(container, wa_id="447700900123", name="Other")
    await other.onboard()

    assert "Are you sure" in texts(await chat.send("delete my data"))
    assert "permanently deleted" in texts(await chat.send(button="del:confirm"))
    async with container.sessionmaker() as s:
        assert (await s.scalar(select(func.count()).select_from(User))) == 1  # only the other student
        other_user = await s.scalar(select(User))
        for model in USER_TABLES:
            count = await s.scalar(select(func.count()).select_from(model).where(model.user_id != other_user.id))
            assert count == 0, model.__tablename__
    # Talking again starts a brand-new profile
    assert "main goal" in texts(await chat.send("hi"))


async def test_students_are_isolated(container):
    a, b = Chat(container, "911111111111", "A"), Chat(container, "922222222222", "B")
    await a.onboard()
    await b.onboard()
    await a.send(button="check:dsa.binary_search")
    for _ in range(3):
        await a.answer_current(correct=True)
    assert "Nothing recorded yet" in texts(await b.send("/progress"))


async def test_conversation_history_is_pruned(container, clock):
    chat = Chat(container)
    await chat.onboard()
    from app.services import conversation

    clock.now += timedelta(days=40)
    await chat.send("hi")
    async with container.sessionmaker() as s:
        removed = await conversation.prune(s, retention_days=30, max_per_user=60, now=clock.now)
        await s.commit()
        remaining = await s.scalar(select(func.count()).select_from(ConversationHistory))
    assert removed > 0 and remaining == 2  # only today's "hi" + reply


async def test_errors_return_friendly_message(container, monkeypatch):
    chat = Chat(container)
    await chat.onboard()

    async def boom(*args, **kwargs):
        raise RuntimeError("database exploded")

    monkeypatch.setattr(container.orchestrator, "run", boom)
    reply = texts(await chat.send("explain stacks"))
    assert "something went wrong" in reply


async def test_rate_limit_warns_once(container):
    container.processor.rate_limiter.limit = 3
    chat = Chat(container)
    results = [await chat.send("hi") for _ in range(6)]
    assert "sending messages very quickly" in texts(results[3])
    assert results[4] == [] and results[5] == []


async def test_reminder_job_respects_consent_window_and_template(container, clock):
    from app.services import notifications

    opted_in, silent = Chat(container, "910000000001", "Opt"), Chat(container, "910000000002", "Silent")
    await opted_in.onboard()
    await silent.onboard()
    await opted_in.send("/remind 16:00")  # 16:00 IST == 10:30 UTC
    container.sender.clear()

    clock.now = datetime(2026, 11, 2, 10, 0)  # 15:30 IST — too early
    result = await notifications.send_daily_reminders(container.sessionmaker, container.sender, container.settings, clock.now)
    assert result["sent"] == 0

    clock.now = datetime(2026, 11, 2, 10, 45)  # 16:15 IST
    result = await notifications.send_daily_reminders(container.sessionmaker, container.sender, container.settings, clock.now)
    assert result["sent"] == 1
    assert [to for to, _ in container.sender.sent] == ["910000000001"]  # never the student who didn't opt in
    assert "Time to study" in container.sender.sent[0][1].body

    # Same day again → not re-sent
    result = await notifications.send_daily_reminders(container.sessionmaker, container.sender, container.settings, clock.now)
    assert result["sent"] == 0

    # Two days later, outside WhatsApp's 24h window and no template configured → skipped (policy-safe)
    clock.now += timedelta(days=2)
    result = await notifications.send_daily_reminders(container.sessionmaker, container.sender, container.settings, clock.now)
    assert result["skipped_no_template"] == 1 and result["sent"] == 0

    # With an approved template configured, it is sent as a template message
    container.settings.whatsapp_reminder_template = "daily_study_reminder"
    clock.now += timedelta(days=1)
    container.sender.clear()
    result = await notifications.send_daily_reminders(container.sessionmaker, container.sender, container.settings, clock.now)
    assert result["sent"] == 1 and container.sender.sent[0][1].kind == "template"
