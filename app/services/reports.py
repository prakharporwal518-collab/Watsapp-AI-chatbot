"""Progress reports. Every number comes from the database — nothing is estimated except study time,
which is clearly labelled as an estimate."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content.curriculum import CATEGORY_GROUPS, TOPICS, TRACK_EMOJI, TRACKS, modules_for_track
from app.db.models import CodingProblem, CodingSubmission, QuizAttempt, TopicProgress, User
from app.services import progress
from app.whatsapp.formatter import progress_bar


async def quiz_stats(session: AsyncSession, user_id: int, since: datetime | None = None,
                     until: datetime | None = None, categories: list[str] | None = None) -> tuple[int, int]:
    query = select(QuizAttempt.is_correct).where(QuizAttempt.user_id == user_id)
    if since:
        query = query.where(QuizAttempt.created_at >= since)
    if until:
        query = query.where(QuizAttempt.created_at < until)
    if categories:
        query = query.where(QuizAttempt.category.in_(categories))
    rows = (await session.scalars(query)).all()
    return len(rows), sum(1 for r in rows if r)


def pct(correct: int, total: int) -> str:
    return f"{round(100 * correct / total)}%" if total else "—"


async def overall_report(session: AsyncSession, user: User, now: datetime) -> str:
    pmap = await progress.progress_map(session, user.id)
    total_q, correct_q = await quiz_stats(session, user.id)
    subs = (await session.scalars(select(CodingSubmission).where(CodingSubmission.user_id == user.id))).all()
    if not pmap and not total_q and not subs:
        return ("📊 *Your progress*\n\nNothing recorded yet — you're at the very start of your journey! 🚀\n"
                "Open a lesson or take a quiz and I'll start tracking.")
    today = progress.local_date(user, now)
    lines = ["📊 *Your learning progress*", ""]
    for track in ("dsa", "cpp", "python", "ml"):
        c = progress.track_counts(pmap, track)
        if c["completed"] or c["learning"] or track in (user.preferences.goals or []):
            frac = c["completed"] / c["total"] if c["total"] else 0
            lines.append(f"{TRACK_EMOJI[track]} *{TRACKS[track]}*\n{progress_bar(frac)} {c['completed']}/{c['total']} completed · {c['learning']} in progress")
    lines.append("")
    lines.append(f"📝 *Quiz answers:* {total_q} · accuracy {pct(correct_q, total_q)}")
    solved = sum(1 for s in subs if s.verdict in ("ai_correct", "self_solved"))
    lines.append(f"🧑‍💻 *Coding problems:* {len({s.problem_id for s in subs if s.problem_id})} attempted · {solved} solved")
    lines.append(f"🔥 *Streak:* {progress.effective_streak(user.streak, today)} day(s) (best {user.streak.longest_streak if user.streak else 0})")
    minutes = await progress.estimated_study_minutes(session, user.id)
    lines.append(f"⏱️ *Study time:* ≈{_fmt_minutes(minutes)} _(estimated from your activity)_")
    weak = await progress.weak_topics(session, user.id)
    strong = await progress.strong_topics(session, user.id)
    if strong:
        lines.append("\n💪 *Strong:* " + ", ".join(TOPICS[t.topic_id].title for t in strong[:4] if t.topic_id in TOPICS))
    if weak:
        lines.append("⚠️ *Needs work:* " + ", ".join(TOPICS[t.topic_id].title for t in weak[:4] if t.topic_id in TOPICS))
    return "\n".join(lines)


async def track_report(session: AsyncSession, user: User, track: str) -> str:
    pmap = await progress.progress_map(session, user.id)
    c = progress.track_counts(pmap, track)
    total_q, correct_q = await quiz_stats(session, user.id, categories=CATEGORY_GROUPS.get(track))
    lines = [f"{TRACK_EMOJI[track]} *{TRACKS[track]} progress*",
             f"{progress_bar(c['completed'] / c['total'] if c['total'] else 0)} {c['completed']}/{c['total']} topics completed", ""]
    for module in modules_for_track(track):
        done = sum(1 for t in module.topics if t.id in pmap and pmap[t.id].status == "completed")
        learning = sum(1 for t in module.topics if t.id in pmap and pmap[t.id].status == "learning")
        extra = f" · {learning} in progress" if learning else ""
        lines.append(f"*{module.name}*\n{progress_bar(done / len(module.topics), 8)} {done}/{len(module.topics)}{extra}")
    lines.append(f"\n📝 Quiz accuracy in this track: {pct(correct_q, total_q)} ({total_q} answers)")
    in_progress = [TOPICS[t].title for t, tp in pmap.items() if tp.status == "learning" and t in TOPICS and TOPICS[t].track == track]
    if in_progress:
        lines.append("📖 *Currently learning:* " + ", ".join(in_progress[:5]))
    if not total_q and not c["completed"]:
        lines.append("\n_Topics are marked completed only after you pass understanding checks — reading alone doesn't count._")
    return "\n".join(lines)


async def weakness_report(session: AsyncSession, user: User) -> tuple[str, list[str]]:
    weak = await progress.weak_topics(session, user.id)
    pmap = await progress.progress_map(session, user.id)
    borderline = [tp for tp in pmap.values() if tp.questions_attempted >= 2 and 0.6 <= tp.mastery < 0.75 and not progress.is_weak(tp)]
    if not weak and not borderline:
        answered = sum(tp.questions_attempted for tp in pmap.values())
        if answered < 5:
            return ("🔍 *Weak topics*\n\nNot enough data yet — I identify weak topics from your quiz answers "
                    f"(you've answered {answered} so far). Take a couple of quizzes and check again!"), []
        return "🔍 *Weak topics*\n\n🎉 No weak topics right now — your accuracy is solid everywhere you've practised.", []
    lines = ["🔍 *Your weak topics*", "_(based on your recent answers)_", ""]
    for tp in weak[:8]:
        if tp.topic_id in TOPICS:
            lines.append(f"❌ *{TOPICS[tp.topic_id].title}* — {round(tp.mastery * 100)}% recent accuracy ({tp.questions_attempted} answers)")
    for tp in borderline[:4]:
        if tp.topic_id in TOPICS:
            lines.append(f"⚠️ {TOPICS[tp.topic_id].title} — {round(tp.mastery * 100)}% (borderline)")
    lines.append("\n*Plan:* re-read the lesson (or ask me to explain it simpler), then take a revision quiz. "
                 "These topics are in your revision schedule.")
    return "\n".join(lines), [tp.topic_id for tp in weak[:3]]


async def weekly_report(session: AsyncSession, user: User, now: datetime) -> str:
    week_ago = now - timedelta(days=7)
    two_weeks = now - timedelta(days=14)
    total, correct = await quiz_stats(session, user.id, since=week_ago)
    prev_total, prev_correct = await quiz_stats(session, user.id, since=two_weeks, until=week_ago)
    completed = (await session.scalars(select(TopicProgress).where(
        TopicProgress.user_id == user.id, TopicProgress.completed_at >= week_ago))).all()
    studied = (await session.scalars(select(TopicProgress).where(
        TopicProgress.user_id == user.id, TopicProgress.last_activity_at >= week_ago))).all()
    subs = (await session.scalars(select(CodingSubmission).where(
        CodingSubmission.user_id == user.id, CodingSubmission.created_at >= week_ago))).all()
    today = progress.local_date(user, now)
    active = _active_days(user, today, 7)
    minutes = await progress.estimated_study_minutes(session, user.id, since=week_ago)

    lines = ["🗓️ *Your weekly report*", f"_{(today - timedelta(days=6)).strftime('%d %b')} – {today.strftime('%d %b')}_", ""]
    lines.append(f"📅 Active days: *{sum(active)}/7*  {''.join('🟩' if a else '⬜' for a in active)}")
    lines.append(f"⏱️ Study time: ≈{_fmt_minutes(minutes)} _(estimated)_")
    lines.append(f"📖 Topics studied: {len(studied)} · ✅ completed: {len(completed)}")
    trend = ""
    if total and prev_total:
        diff = round(100 * correct / total) - round(100 * prev_correct / prev_total)
        trend = f" ({'+' if diff >= 0 else ''}{diff} pts vs last week)"
    lines.append(f"📝 Quiz answers: {total} · accuracy {pct(correct, total)}{trend}")
    lines.append(f"🧑‍💻 Coding attempts: {len(subs)}")
    if completed:
        lines.append("\n🏅 *Completed this week:* " + ", ".join(TOPICS[t.topic_id].title for t in completed if t.topic_id in TOPICS))
    if not total and not studied and not subs:
        lines.append("\nNo learning activity this week yet. Even 20 minutes a day builds a strong habit! 💪")
    return "\n".join(lines)


async def coding_report(session: AsyncSession, user: User) -> str:
    subs = (await session.scalars(select(CodingSubmission).where(CodingSubmission.user_id == user.id))).all()
    if not subs:
        return ("🧑‍💻 *Coding performance*\n\nNo coding attempts yet. Type *practice* for a problem or *mock interview* "
                "to simulate a real interview.")
    problems = {p.id: p for p in (await session.scalars(select(CodingProblem))).all()}
    solved_ids = {s.problem_id for s in subs if s.verdict in ("ai_correct", "self_solved") and s.problem_id}
    attempted_ids = {s.problem_id for s in subs if s.problem_id}
    by_diff = Counter(problems[i].difficulty for i in solved_ids if i in problems)
    patterns = Counter(problems[i].pattern for i in attempted_ids if i in problems)
    interviews = [s for s in subs if s.mode == "interview"]
    cx = [s.complexity_correct for s in interviews if s.complexity_correct is not None]
    verdicts = Counter(s.verdict for s in subs)
    lines = ["🧑‍💻 *Coding performance*", "",
             f"Problems attempted: *{len(attempted_ids)}* · solved: *{len(solved_ids)}*",
             f"Solved by difficulty: 🟢 {by_diff.get('easy', 0)} · 🟡 {by_diff.get('medium', 0)} · 🔴 {by_diff.get('hard', 0)}",
             f"Verified by AI review: {verdicts.get('ai_correct', 0)} · self-reported: {verdicts.get('self_solved', 0)}",
             f"Code reviews requested: {sum(1 for s in subs if s.mode == 'review')}",
             f"Mock interviews: {len(interviews)}" + (f" · complexity correct in {sum(cx)}/{len(cx)}" if cx else "")]
    if patterns:
        lines.append("\n*Patterns practised:* " + ", ".join(f"{p} ({n})" for p, n in patterns.most_common(6)))
    untried = sorted({p.pattern for p in problems.values()} - set(patterns))
    if untried:
        lines.append("*Try next:* " + ", ".join(untried[:4]))
    lines.append("\n_Note: I never run your code. \"Solved\" means an AI review judged it correct, or you reported it._")
    return "\n".join(lines)


def streak_report(user: User, today: date) -> str:
    current = progress.effective_streak(user.streak, today)
    best = user.streak.longest_streak if user.streak else 0
    active = _active_days(user, today, 7)
    last = user.streak.last_active_date if user.streak else None
    if current == 0:
        msg = "Start a new streak today — one lesson or quiz is enough! 🌱"
    elif last != today:
        msg = "⚠️ You haven't studied today yet — keep your streak alive!"
    elif current >= 7:
        msg = "Incredible consistency! 🏆"
    else:
        msg = "Nice! Come back tomorrow to keep it going. 💪"
    return (f"🔥 *Learning streak*\n\nCurrent: *{current} day{'s' if current != 1 else ''}*\nLongest: {best} day{'s' if best != 1 else ''}\n\n"
            f"Last 7 days: {''.join('🟩' if a else '⬜' for a in active)}\n\n{msg}\n\n"
            "_A day counts when you study: lessons, quizzes, practice — not just saying hi._")


def _active_days(user: User, today: date, days: int) -> list[bool]:
    dates = set(user.streak.active_dates or []) if user.streak else set()
    return [(today - timedelta(days=i)).isoformat() in dates for i in range(days - 1, -1, -1)]


def _fmt_minutes(m: int) -> str:
    return f"{m} min" if m < 60 else f"{m // 60} h {m % 60} min"
