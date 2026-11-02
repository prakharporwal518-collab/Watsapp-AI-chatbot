"""Agent 4 — Quiz & Assessment: quizzes, understanding checks, revision sessions and mock interviews."""

from __future__ import annotations

import logging
import re
from collections import defaultdict

from sqlalchemy import select

from app.agents.base import AgentContext, AgentResponse, Intent
from app.agents.intents import looks_like_code
from app.content.curriculum import CATEGORY_GROUPS, QUIZ_CATEGORIES, TOPICS
from app.db.models import CodingProblem, QuizAttempt, QuizQuestion, QuizSession
from app.llm import prompts
from app.llm.client import LLMError, parse_json
from app.services import coding, progress, quiz, revision
from app.services.progress import primary_track
from app.whatsapp import messages as wa

logger = logging.getLogger(__name__)

GROUP_NAMES = {"dsa": "DSA", "ml": "Machine Learning", "cpp": "C++", "python": "Python"}


class QuizAgent:
    name = "quiz"

    async def handle(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        handler = getattr(self, f"on_{intent.name}", None)
        if handler is None:
            return await self.on_quiz_start(ctx, intent)
        return await handler(ctx, intent)

    # ================================================================== starting quizzes
    async def on_quiz_start(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        params = intent.params
        category = params.get("category")
        if category == "auto":
            category = primary_track(ctx.user)
        if not category:
            return self._category_menu()
        categories = CATEGORY_GROUPS.get(category, [category])
        if not all(c in QUIZ_CATEGORIES for c in categories):
            return self._category_menu()
        name = GROUP_NAMES.get(category) or QUIZ_CATEGORIES[category]
        count = max(1, min(int(params.get("count") or ctx.settings.default_quiz_size), ctx.settings.max_quiz_size))
        topic_ids = [params["topic_id"]] if params.get("topic_id") else None
        return await self._start(ctx, "quiz", categories, name, count, params.get("difficulty"), topic_ids)

    def _category_menu(self) -> AgentResponse:
        first = ["dsa", "arrays_strings", "linked_lists", "stack_queue", "trees_graphs", "sorting_searching",
                 "dynamic_programming", "dsa_fundamentals", "cpp", "python"]
        second = ["ml", "numpy_pandas", "supervised", "unsupervised", "ml_algorithms", "deep_learning"]

        def row(cat):
            title = f"{GROUP_NAMES[cat]} (mixed)" if cat in GROUP_NAMES and cat in ("dsa", "ml") else (
                GROUP_NAMES.get(cat) or QUIZ_CATEGORIES[cat])
            return (f"quiz:{cat}", title, "Mixed questions from all topics" if cat in ("dsa", "ml") else "")

        return AgentResponse([
            wa.list_menu("📝 *Quiz time!* Choose a category 👇\n_Tip: you can also type things like "
                         "\"10 medium python questions\"._", [row(c) for c in first], button="DSA & coding"),
            wa.list_menu("…or a Machine Learning category 👇", [row(c) for c in second], button="Machine Learning"),
        ])

    async def on_check(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        topic = TOPICS.get(intent.params.get("topic_id") or ctx.state.get("topic_id") or "")
        if topic is None:
            return await self.on_quiz_start(ctx, Intent("quiz_start", "quiz", {}, ""))
        categories = [topic.quiz_category] if topic.quiz_category else ["dsa_fundamentals"]
        return await self._start(ctx, "check", categories, f"Understanding check: {topic.title}", 3, None, [topic.id],
                                 allow_category_fallback=True)

    async def on_revision(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        due = await revision.due_topics(ctx.session, ctx.user.id, ctx.today, limit=3)
        topic_ids = [d.topic_id for d in due if d.topic_id in TOPICS]
        label = "due for revision"
        if not topic_ids:
            weak = await progress.weak_topics(ctx.session, ctx.user.id)
            topic_ids = [w.topic_id for w in weak[:3]]
            label = "your weakest topics"
        if not topic_ids:
            upcoming = await revision.upcoming(ctx.session, ctx.user.id)
            lines = [f"• {TOPICS[u.topic_id].title} — {u.due_date.strftime('%d %b')}" for u in upcoming if u.topic_id in TOPICS]
            body = "🎉 Nothing is due for revision today."
            body += ("\n\n*Coming up:*\n" + "\n".join(lines)) if lines else (
                "\n\nTopics enter your revision plan when you complete them or when your accuracy drops.")
            return AgentResponse([wa.buttons(body, [("quiz:auto", "📝 Quick quiz"), ("cmd:next", "➡️ Learn something new")])])
        titles = ", ".join(TOPICS[t].title for t in topic_ids)
        resp = await self._start(ctx, "revision", [], f"Revision ({label}): {titles}", min(6, 2 * len(topic_ids)), None,
                                 topic_ids)
        return resp

    async def _start(
        self, ctx: AgentContext, kind: str, categories: list[str], name: str, count: int,
        difficulty: str | None, topic_ids: list[str] | None, allow_category_fallback: bool = False,
    ) -> AgentResponse:
        questions = await quiz.select_questions(ctx.session, ctx.user.id, categories, count, difficulty, topic_ids, ctx.rng)

        if len(questions) < count and ctx.llm_available:
            gen_cat = categories[0] if categories else (TOPICS[topic_ids[0]].quiz_category if topic_ids else "dsa_fundamentals")
            if len(categories) > 1:
                gen_cat = ctx.rng.choice(categories)
            try:
                topic_for_gen = topic_ids[0] if topic_ids else None
                questions += await quiz.generate_questions(
                    ctx.session, _BudgetedLLM(ctx), gen_cat, count - len(questions), difficulty or "medium", topic_for_gen)
            except LLMError:
                pass

        note = ""
        if not questions and allow_category_fallback and categories:
            questions = await quiz.select_questions(ctx.session, ctx.user.id, categories, count, None, None, ctx.rng)
            if questions:
                note = "_I don't have questions on exactly this topic yet, so these are from the same area._\n"
        if not questions:
            diff = f" {difficulty}" if difficulty else ""
            return AgentResponse([wa.buttons(
                f"😕 I don't have{diff} questions for *{name}* right now.",
                [("quiz:auto", "📝 Mixed quiz"), ("cmd:help", "❓ Help")])])

        await self._abandon_active(ctx)
        session = QuizSession(
            user_id=ctx.user.id, kind=kind, category=categories[0] if categories else "revision",
            topic_id=topic_ids[0] if topic_ids and len(topic_ids) == 1 else None, difficulty=difficulty,
            question_ids=[q.id for q in questions], current_index=0, correct_count=0, status="active", started_at=ctx.now,
        )
        ctx.session.add(session)
        await ctx.session.flush()
        ctx.set_state(mode="quiz", quiz_session_id=session.id, revision_topics=topic_ids if kind == "revision" else None)

        if len(questions) < count:
            note += f"_I have {len(questions)} question{'s' if len(questions) != 1 else ''} ready for this right now._\n"
        diff_txt = f" · {difficulty.title()}" if difficulty else ""
        intro = (f"📝 *{name}*\n{len(questions)} question{'s' if len(questions) != 1 else ''}{diff_txt}\n{note}"
                 "Tap an option or reply with the letter. Type *stop* to end anytime.")
        resp = AgentResponse([wa.text(intro)])
        resp.add(*quiz.render_question(questions[0], session.id, 0, len(questions)))
        return resp

    async def _abandon_active(self, ctx: AgentContext) -> None:
        sid = ctx.state.get("quiz_session_id")
        if sid:
            old = await ctx.session.get(QuizSession, sid)
            if old and old.status == "active":
                old.status = "abandoned"
                old.finished_at = ctx.now

    # ================================================================== answering
    async def on_quiz_answer(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        sid = ctx.state.get("quiz_session_id")
        session = await ctx.session.get(QuizSession, sid) if sid else None
        if session is None or session.status != "active":
            ctx.set_state(mode=None, quiz_session_id=None)
            return AgentResponse([wa.buttons("There's no quiz running right now. Want to start one?",
                                             [("quiz:auto", "📝 Start a quiz"), ("cmd:help", "❓ Help")])])
        if session.current_index >= len(session.question_ids):
            return await self._finish(ctx, session, AgentResponse())
        question = await ctx.session.get(QuizQuestion, session.question_ids[session.current_index])
        total = len(session.question_ids)

        button_id = intent.params.get("button_id")
        if button_id and button_id.startswith("qa:"):
            _, b_sid, b_qid, _ = (button_id.split(":") + ["", "", "", ""])[:4]
            if str(b_sid) != str(session.id) or str(b_qid) != str(question.id):
                resp = AgentResponse([wa.text("That button belongs to an earlier question. Here's the current one 👇")])
                resp.add(*quiz.render_question(question, session.id, session.current_index, total))
                return resp

        choice = None
        if question.qtype == "short":
            result = await quiz.grade_short(question, intent.text, _BudgetedLLM(ctx))
        else:
            choice = quiz.parse_choice(question, intent.text, button_id)
            if choice is None:
                letters = "A or B" if len(question.options) == 2 else f"A–{quiz.LETTERS[len(question.options) - 1]}"
                return AgentResponse([wa.text(f"Please answer with {letters} (or tap an option). Type *stop* to end the quiz.")])
            result = quiz.grade_choice(question, choice)

        ctx.session.add(QuizAttempt(
            user_id=ctx.user.id, session_id=session.id, question_id=question.id, topic_id=question.topic_id,
            category=question.category, user_answer=result.user_answer[:500], is_correct=result.correct,
            graded_by=result.graded_by, created_at=ctx.now,
        ))
        outcome = await progress.record_answer(ctx.session, ctx.user, question.topic_id, result.correct, ctx.now)
        session.current_index += 1
        if result.correct:
            session.correct_count += 1

        feedback = quiz.feedback_text(question, result, choice)
        topic = TOPICS.get(question.topic_id or "")
        if outcome.topic_completed_now and topic:
            feedback += f"\n\n🎉 You've now *completed {topic.title}*! It's been added to your revision schedule."
        elif outcome.became_weak and topic:
            feedback += f"\n\n📌 *{topic.title}* looks like a weak spot — I've added it to your revision plan."
        resp = AgentResponse(ctx.long_text(feedback, markdown=False), record_activity=True)

        if session.current_index < total:
            nxt = await ctx.session.get(QuizQuestion, session.question_ids[session.current_index])
            resp.add(*quiz.render_question(nxt, session.id, session.current_index, total))
            return resp
        return await self._finish(ctx, session, resp)

    async def on_quiz_stop(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        sid = ctx.state.get("quiz_session_id")
        session = await ctx.session.get(QuizSession, sid) if sid else None
        ctx.set_state(mode=None, quiz_session_id=None, revision_topics=None)
        if session is None or session.status != "active":
            return AgentResponse([wa.text("No quiz is running. 🙂")])
        session.status = "abandoned"
        session.finished_at = ctx.now
        answered = session.current_index
        if answered == 0:
            return AgentResponse([wa.buttons("Quiz stopped. No questions were answered, so nothing was recorded.",
                                             [("quiz:auto", "📝 New quiz"), ("cmd:help", "❓ Menu")])])
        pct = round(100 * session.correct_count / answered)
        return AgentResponse([wa.buttons(
            f"⏹️ Quiz stopped. You answered {answered} question{'s' if answered != 1 else ''}: "
            f"*{session.correct_count}/{answered}* correct ({pct}%). Your answers have been saved to your progress.",
            [("quiz:auto", "📝 New quiz"), ("cmd:progress", "📊 My progress")])])

    async def _finish(self, ctx: AgentContext, session: QuizSession, resp: AgentResponse) -> AgentResponse:
        session.status = "completed"
        session.finished_at = ctx.now
        attempts = (await ctx.session.scalars(select(QuizAttempt).where(QuizAttempt.session_id == session.id))).all()
        total = len(attempts)
        correct = sum(1 for a in attempts if a.is_correct)
        pct = round(100 * correct / total) if total else 0
        per_topic: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for a in attempts:
            if a.topic_id:
                per_topic[a.topic_id][1] += 1
                per_topic[a.topic_id][0] += int(a.is_correct)

        if session.kind == "revision":
            for topic_id, (c, t) in per_topic.items():
                await revision.apply_review(ctx.session, ctx.user.id, topic_id, c / t, ctx.today, ctx.now)

        emoji = "🏆" if pct >= 80 else "👍" if pct >= 60 else "💪"
        lines = [f"🏁 *{'Check' if session.kind == 'check' else 'Revision' if session.kind == 'revision' else 'Quiz'} complete!*",
                 f"Score: *{correct}/{total}* ({pct}%) {emoji}"]
        if per_topic:
            lines.append("\n*By topic*")
            for topic_id, (c, t) in sorted(per_topic.items(), key=lambda kv: kv[1][0] / kv[1][1]):
                icon = "✅" if c == t else "⚠️" if c / t >= 0.5 else "❌"
                lines.append(f"{icon} {TOPICS[topic_id].title if topic_id in TOPICS else topic_id}: {c}/{t}")
        needs_work = [tid for tid, (c, t) in per_topic.items() if c / t < 0.6 and tid in TOPICS]
        if needs_work:
            lines.append("\n📌 *Revise:* " + ", ".join(TOPICS[t].title for t in needs_work))
        if session.kind == "revision":
            lines.append("\n🗓️ Revision schedule updated — strong topics come back later, weak ones sooner.")
        ctx.set_state(mode=None, quiz_session_id=None, revision_topics=None)
        resp.add(wa.text("\n".join(lines)))

        if session.kind == "check" and session.topic_id in TOPICS:
            topic = TOPICS[session.topic_id]
            tp = await progress.get_topic_progress(ctx.session, ctx.user.id, topic.id)
            if tp.status == "completed":
                resp.add(wa.buttons(f"✅ *{topic.title}* is marked as completed.",
                                    [("cmd:next", "➡️ Next topic"), ("prac:new", "🧑‍💻 Practice problem")]))
            elif pct >= 60:
                resp.add(wa.buttons("Good progress! One more short check will confirm you've mastered it.",
                                    [(f"check:{topic.id}", "✅ Check again"), ("cmd:next", "➡️ Next topic")]))
            else:
                resp.add(wa.buttons("Let's look at it from another angle — that usually helps.",
                                    [(f"simpler:{topic.id}", "🤔 Explain simpler"), (f"learn:{topic.id}", "📖 Re-read lesson")]))
        elif needs_work:
            first = needs_work[0]
            resp.add(wa.buttons("Want to fix the weak spot now?",
                                [(f"learn:{first}", "📖 Review lesson"), ("quiz:auto", "📝 Another quiz"), ("cmd:progress", "📊 Progress")]))
        else:
            resp.add(wa.buttons("What next?", [("quiz:auto", "📝 Another quiz"), ("cmd:next", "➡️ Learn next"),
                                               ("cmd:progress", "📊 Progress")]))
        return resp

    # ================================================================== mock interview
    async def on_interview_start(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        difficulty = intent.params.get("difficulty") or ("easy" if ctx.user.level == "beginner" else "medium")
        problem = await coding.pick_problem(ctx.session, ctx.user.id, difficulty, ctx.rng)
        if problem is None:
            return AgentResponse([wa.text("No interview problems are available right now.")])
        await self._abandon_active(ctx)
        ctx.set_state(mode="interview", problem_id=problem.id, iv_stage="approach", hints_used=0,
                      iv_approach=None, iv_code=None, quiz_session_id=None)
        intro = (
            "🎤 *Mock Coding Interview*\n\nI'll be your interviewer. Three stages:\n"
            "1️⃣ Explain your approach  2️⃣ Write the code  3️⃣ State the complexity\n\n"
            "Type *hint* if you're stuck, or *stop* to end."
        )
        return AgentResponse([
            wa.text(intro),
            wa.text(coding.problem_text(problem, "🧩 Problem")),
            wa.text("*Step 1:* Talk me through your approach in plain words. Start with the brute force — can you do better?"),
        ], record_activity=True)

    async def on_interview_step(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        st = ctx.state
        problem = await ctx.session.get(CodingProblem, st.get("problem_id")) if st.get("problem_id") else None
        if problem is None:
            ctx.set_state(mode=None)
            return await self.on_interview_start(ctx, intent)
        text = intent.text.strip()
        stage = st.get("iv_stage", "approach")

        if text.lower() in {"hint", "give hint", "hint please"}:
            used = int(st.get("hints_used") or 0)
            if used >= len(problem.hints):
                return AgentResponse([wa.text("No more hints — you've got this! Give it your best shot. 💪")])
            ctx.set_state(hints_used=used + 1)
            return AgentResponse([wa.text(f"💡 *Hint {used + 1}:* {problem.hints[used]}")])

        if stage == "approach":
            rating, feedback = "unrated", ""
            if ctx.llm_available:
                try:
                    raw = await ctx.ask_llm(prompts.INTERVIEW_SYSTEM, [{"role": "user", "content": prompts.approach_eval_prompt(
                        f"{problem.title}: {problem.statement}", problem.key_insight, text)}],
                        temperature=0.3, max_tokens=500, json_mode=True)
                    data = parse_json(raw)
                    rating = data.get("rating") if data.get("rating") in ("optimal", "works_suboptimal", "incorrect") else "unrated"
                    feedback = str(data.get("feedback", ""))
                except LLMError:
                    pass
            if not feedback:
                feedback = (f"Thanks for explaining! 📝 Here's what an interviewer would be looking for:\n"
                            f"_{problem.key_insight}_\n\nCompare it with your idea.")
            ctx.set_state(iv_stage="code", iv_approach=rating)
            lang = "C++" if ctx.language == "cpp" else "Python"
            return AgentResponse([*ctx.long_text(feedback),
                                  wa.text(f"*Step 2:* Now write the code in {lang} and paste it here.")], record_activity=True)

        if stage == "code":
            if not looks_like_code(text) and len(text.splitlines()) < 2:
                return AgentResponse([wa.text("Please paste your code (a few lines at least). Type *hint* if you're stuck.")])
            review = await coding.review_code(ctx, text, problem)
            if review.verdict in ("unavailable", "not_code"):
                ctx.set_state(iv_stage="selfcheck", iv_code="(submitted)")
                return AgentResponse([
                    wa.text("I can't review code automatically right now (and I never pretend to run it). Here's a reference solution to compare with:"),
                    *ctx.long_text(coding.solution_text(problem, review.language if review.language in ("cpp", "python") else ctx.language), markdown=False),
                    wa.buttons("Does your solution match in logic and handle the examples?",
                               [("iv:selfpass", "✅ Mine works"), ("iv:selffail", "❌ Mine has bugs")]),
                ], record_activity=True)
            ctx.set_state(iv_stage="complexity", iv_code=review.verdict, iv_lang=review.language)
            return AgentResponse([*ctx.long_text(review.feedback),
                                  wa.text("*Step 3:* What's the time and space complexity of your solution?\n"
                                          "_e.g. \"O(n) time, O(1) space\"_")], record_activity=True)

        if stage == "selfcheck":
            low = text.lower()
            if re.search(r"\b(yes|works|worked|correct|passed|same)\b", low):
                return await self.on_interview_action(ctx, Intent("interview_action", "quiz", {"action": "selfpass"}))
            if re.search(r"\b(no|bug|bugs|wrong|failed|different)\b", low):
                return await self.on_interview_action(ctx, Intent("interview_action", "quiz", {"action": "selffail"}))
            return AgentResponse([wa.buttons("Did your solution work? (Or type *stop* to end the interview.)",
                                             [("iv:selfpass", "✅ Mine works"), ("iv:selffail", "❌ Mine has bugs")])])

        if stage == "complexity":
            return await self._finish_interview(ctx, problem, text)
        return AgentResponse([wa.text("Type *stop* to end the interview.")])

    async def on_interview_action(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        action = intent.params.get("action")
        st = ctx.state
        if action == "stop":
            ctx.set_state(mode=None, iv_stage=None, problem_id=None)
            return AgentResponse([wa.buttons("Interview ended. Practice makes perfect! 💪",
                                             [("cmd:interview", "🎤 New interview"), ("prac:new", "🧑‍💻 Practice")])])
        if action in ("selfpass", "selffail") and st.get("mode") == "interview":
            ctx.set_state(iv_stage="complexity", iv_code="self_solved" if action == "selfpass" else "self_unsolved")
            return AgentResponse([wa.text("*Step 3:* What's the time and space complexity of your solution?\n"
                                          "_e.g. \"O(n) time, O(1) space\"_")])
        return AgentResponse([wa.text("Type *interview* to start a mock interview.")])

    async def _finish_interview(self, ctx: AgentContext, problem: CodingProblem, answer: str) -> AgentResponse:
        st = ctx.state
        found = re.findall(r"o\s*\(([^)]*\)?)\)", answer.lower())
        time_ans = f"O({found[0]})" if found else answer
        space_ans = f"O({found[1]})" if len(found) > 1 else ""
        time_ok = coding.complexity_matches(time_ans, problem.time_complexity)
        space_ok = coding.complexity_matches(space_ans, problem.space_complexity) if space_ans else False

        approach = st.get("iv_approach") or "unrated"
        code_verdict = st.get("iv_code") or "reviewed"
        hints = int(st.get("hints_used") or 0)
        lines = ["📋 *Interview scorecard*", f"Problem: *{problem.title}* ({problem.difficulty})", ""]
        approach_txt = {"optimal": "✅ Optimal", "works_suboptimal": "🟡 Works, not optimal",
                        "incorrect": "❌ Needs rethinking", "unrated": "➖ Not rated (AI unavailable)"}[approach]
        code_txt = {"ai_correct": "✅ Correct (AI review)", "ai_needs_work": "🛠️ Needs work (AI review)",
                    "self_solved": "✅ Works (self-reported)", "self_unsolved": "❌ Had bugs (self-reported)",
                    "reviewed": "➖ Reviewed"}.get(code_verdict, "➖ Reviewed")
        lines += [f"*Approach:* {approach_txt}", f"*Code:* {code_txt}",
                  f"*Time complexity:* {'✅' if time_ok else '❌'} (expected {problem.time_complexity})",
                  f"*Space complexity:* {'✅' if space_ok else '❌'} (expected {problem.space_complexity})",
                  f"*Hints used:* {hints}"]
        tips = []
        if approach in ("works_suboptimal", "incorrect"):
            tips.append(f"Key insight to remember: _{problem.key_insight}_")
        if not time_ok or not space_ok:
            tips.append("Practise stating complexity: count loops for time, extra arrays/maps/recursion depth for space.")
        if hints:
            tips.append("Try the next one with fewer hints — think aloud about brute force first.")
        if tips:
            lines += ["", "*Tips*"] + [f"• {t}" for t in tips]

        await coding.record_submission(ctx, problem, "(interview)", code_verdict if code_verdict != "reviewed" else "reviewed",
                                       "interview", st.get("iv_lang") or ctx.language, hints_used=hints,
                                       complexity_correct=time_ok and space_ok)
        ctx.set_state(mode=None, iv_stage=None, problem_id=None, iv_approach=None, iv_code=None, iv_lang=None, hints_used=None)
        return AgentResponse([wa.text("\n".join(lines)),
                              wa.buttons("Great practice! 🎯", [("cmd:interview", "🎤 Another one"), ("cmd:coding", "📊 Coding stats")])],
                             record_activity=True)


class _BudgetedLLM:
    """Adapter so services that take an LLMClient still respect the per-user daily budget."""

    def __init__(self, ctx: AgentContext):
        self._ctx = ctx
        self.available = ctx.llm_available

    async def complete(self, system, messages, **kwargs) -> str:
        return await self._ctx.ask_llm(system, messages, **kwargs)
