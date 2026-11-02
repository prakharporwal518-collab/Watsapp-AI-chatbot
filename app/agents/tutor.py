"""Shared teaching behaviour for the DSA, Coding (C++/Python) and ML tutor agents."""

from __future__ import annotations

import logging

from app.agents.base import AgentContext, AgentResponse, Intent, ai_unavailable_note
from app.content.curriculum import TOPICS, TRACK_EMOJI, TRACKS, Topic, modules_for_track
from app.content.lessons import get_lesson
from app.llm import prompts
from app.llm.client import LLMError
from app.services import conversation, progress
from app.whatsapp import messages as wa
from app.whatsapp.formatter import SPLIT_MARKER

logger = logging.getLogger(__name__)

STATUS_ICON = {"completed": "✅", "learning": "📖", "not_started": "⬜"}


class TutorAgent:
    name = "tutor"
    tracks: tuple[str, ...] = ()

    async def handle(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        handler = getattr(self, f"on_{intent.name}", None)
        if handler is None:
            return await self.on_question(ctx, intent)
        return await handler(ctx, intent)

    # ------------------------------------------------------------------ menus
    async def on_track_menu(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        track = intent.params.get("track") or self.tracks[0]
        ctx.set_state(track=track, mode=None)
        pmap = await progress.progress_map(ctx.session, ctx.user.id)
        counts = progress.track_counts(pmap, track)
        rows = []
        for i, module in enumerate(modules_for_track(track)):
            done = sum(1 for t in module.topics if pmap.get(t.id) and pmap[t.id].status == "completed")
            rows.append((f"mod:{track}:{i}", module.name, f"{done}/{len(module.topics)} topics completed"))
        body = (
            f"{TRACK_EMOJI[track]} *{TRACKS[track]}*\n"
            f"Completed {counts['completed']}/{counts['total']} topics · {counts['learning']} in progress.\n\n"
            "Pick a module to see its topics 👇"
        )
        resp = AgentResponse([wa.list_menu(body, rows, button="Modules")])
        rec = await progress.recommend_next(ctx.session, ctx.user, track, ctx.now)
        if rec:
            resp.add(wa.buttons(
                f"👉 Suggested next: *{rec.topic.title}* — {rec.reason}.",
                [(f"learn:{rec.topic.id}", "▶️ Start lesson"), (f"quiz:{_quiz_cat_for_track(track)}", "📝 Quiz me")],
            ))
        return resp

    async def on_module_topics(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        track, idx = intent.params["track"], intent.params["module"]
        modules = modules_for_track(track)
        if not 0 <= idx < len(modules):
            return await self.on_track_menu(ctx, Intent("track_menu", self.name, {"track": track}))
        module = modules[idx]
        pmap = await progress.progress_map(ctx.session, ctx.user.id)
        rows = [
            (f"learn:{t.id}", t.title,
             f"{STATUS_ICON[pmap[t.id].status if t.id in pmap else 'not_started']} {t.level.title()} · {t.summary}")
            for t in module.topics
        ]
        resp = AgentResponse()
        for part, start in enumerate(range(0, len(rows), 10)):
            suffix = f" ({part + 1}/{(len(rows) + 9) // 10})" if len(rows) > 10 else ""
            resp.add(wa.list_menu(f"*{module.name}*{suffix}\nTap a topic to start the lesson 👇", rows[start:start + 10], button="Topics"))
        return resp

    # ------------------------------------------------------------------ lessons
    async def on_lesson(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        topic = TOPICS.get(intent.params.get("topic_id", ""))
        if topic is None:
            return await self.on_question(ctx, intent)
        language = intent.params.get("language") or (topic.track if topic.track in ("cpp", "python") else ctx.language)
        await progress.mark_lesson_viewed(ctx.session, ctx.user, topic.id, ctx.now)
        ctx.set_state(topic_id=topic.id, track=topic.track, mode="lesson", simpler_count=None)

        msgs = None
        if ctx.llm_available:
            msgs = await self._ai_lesson(ctx, topic, language)
        if msgs is None:
            msgs = self._curated_lesson(ctx, topic, language)
        resp = AgentResponse(msgs, record_activity=True)
        resp.add(lesson_buttons(topic))
        return resp

    async def _ai_lesson(self, ctx: AgentContext, topic: Topic, language: str) -> list[wa.OutgoingMessage] | None:
        try:
            raw = await ctx.ask_llm(
                prompts.lesson_system(await self._profile(ctx, topic)),
                [{"role": "user", "content": self.lesson_prompt(topic, language)}],
                temperature=0.4,
                max_tokens=2600,
            )
        except LLMError as exc:
            logger.warning("AI lesson failed (%s); using curated content", exc)
            return None
        header = f"{TRACK_EMOJI.get(topic.track, '📘')} *{topic.title}*\n_{topic.module} · {topic.level.title()}_\n{SPLIT_MARKER}"
        return ctx.long_text(header + raw)

    def lesson_prompt(self, topic: Topic, language: str) -> str:
        return prompts.dsa_lesson_prompt(topic.title, topic.summary, language)

    def _curated_lesson(self, ctx: AgentContext, topic: Topic, language: str) -> list[wa.OutgoingMessage]:
        lesson = get_lesson(topic.id)
        head = f"{TRACK_EMOJI.get(topic.track, '📘')} *{topic.title}*\n_{topic.module} · {topic.level.title()}_"
        if not lesson:
            prereq = ", ".join(TOPICS[p].title for p in topic.prerequisites if p in TOPICS)
            body = f"{head}\n\n*In one line:* {topic.summary}"
            if prereq:
                body += f"\n\n*Before this, know:* {prereq}"
            body += (
                "\n\n📌 A full step-by-step lesson for this topic needs the AI tutor, which isn't available right now. "
                "You can still test yourself with *Check understanding* below, or try a flagship lesson like *binary search* or *linear regression*."
            )
            return [wa.text(body)]
        code_map = lesson["code"]
        lang = language if language in code_map else next(iter(code_map))
        lang_name = prompts.LANG_NAMES.get(lang, lang)
        output = f"*Expected output*\n```\n{lesson['output']}\n```"
        if lesson.get("output_note"):
            output += f"\n_{lesson['output_note']}_"
        sections = [
            f"{head}\n\n{lesson['intro']}",
            f"{lesson['diagram']}\n\n{lesson['dry_run']}",
            f"*Code ({lang_name})*\n```\n{code_map[lang]}\n```",
            f"{lesson['line_by_line']}\n\n{output}\n\n{lesson['complexity']}",
            lesson["mistakes"],
        ]
        return ctx.long_text(SPLIT_MARKER.join(sections), markdown=False)

    async def on_simpler(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        topic = TOPICS.get(intent.params.get("topic_id") or ctx.state.get("topic_id") or "")
        if topic is None:
            return AgentResponse([wa.text(
                "No problem! Which topic should I explain more simply? 🙂\n"
                "For example: _explain recursion simply_ or _what is a linked list_."
            )])
        attempt = int(ctx.state.get("simpler_count") or 0) + 1
        ctx.set_state(simpler_count=attempt, topic_id=topic.id, track=topic.track)
        body = None
        if ctx.llm_available:
            try:
                body = await ctx.ask_llm(
                    prompts.lesson_system(await self._profile(ctx, topic)),
                    [{"role": "user", "content": prompts.simpler_prompt(topic.title, attempt)}],
                    temperature=0.7, max_tokens=700,
                )
            except LLMError:
                body = None
        if body is None:
            lesson = get_lesson(topic.id)
            if lesson and attempt == 1:
                body = lesson["simpler"]
            else:
                prereqs = [TOPICS[p] for p in topic.prerequisites if p in TOPICS]
                body = f"Let's slow down 🙂\n\n*{topic.title}* in one line: {topic.summary}"
                if prereqs:
                    body += "\n\nIt builds on: " + ", ".join(f"*{p.title}*" for p in prereqs) + ". Reviewing those first often makes it click."
                body += "\n\nTip: try tracing a tiny example (3–4 elements) on paper, step by step."
        resp = AgentResponse(ctx.long_text(body), record_activity=True)
        buttons = [(f"check:{topic.id}", "✅ Check me"), (f"simpler:{topic.id}", "🤔 Still confused")]
        prereq = next((p for p in topic.prerequisites if p in TOPICS), None)
        buttons.append((f"learn:{prereq}", "📚 Learn basics") if prereq else ("cmd:next", "➡️ Next topic"))
        resp.add(wa.buttons("How is it now?", buttons))
        return resp

    # ------------------------------------------------------------------ free questions
    async def on_question(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        topic = TOPICS.get(intent.params.get("topic_id") or "")
        if topic:
            ctx.set_state(topic_id=topic.id, track=topic.track)
        track = topic.track if topic else intent.params.get("track") or ctx.state.get("track")
        if ctx.llm_available:
            try:
                history = await conversation.recent_turns(ctx.session, ctx.user.id, limit=6)
                raw = await ctx.ask_llm(
                    prompts.lesson_system(await self._profile(ctx, topic)),
                    [*history, {"role": "user", "content": prompts.qa_prompt(intent.text, track)}],
                    temperature=0.4, max_tokens=1800,
                )
                resp = AgentResponse(ctx.long_text(raw), record_activity=True)
                if topic:
                    resp.add(lesson_buttons(topic, first="lesson"))
                return resp
            except LLMError as exc:
                logger.warning("Q&A failed: %s", exc)
        if topic:
            return AgentResponse([
                wa.text(f"*{topic.title}*: {topic.summary}\n\n{ai_unavailable_note()}"),
                lesson_buttons(topic, first="lesson"),
            ])
        return AgentResponse([wa.buttons(
            "I couldn't match that to a topic yet 🤔\n\nTry: _explain binary search_, _what is overfitting_, "
            "_teach me pointers in C++_, or pick a track:",
            [("menu:dsa", "🧩 DSA"), ("menu:ml", "🤖 Machine Learning"), ("cmd:help", "❓ Help")],
        )])

    async def _profile(self, ctx: AgentContext, topic: Topic | None) -> str:
        weak = await progress.weak_topics(ctx.session, ctx.user.id)
        weak_titles = [TOPICS[w.topic_id].title for w in weak[:5] if w.topic_id in TOPICS]
        return prompts.student_profile(ctx.user.level, ctx.language, weak_titles, topic.title if topic else None)


def lesson_buttons(topic: Topic, first: str = "check") -> wa.OutgoingMessage:
    if first == "lesson":
        items = [(f"learn:{topic.id}", "📖 Full lesson"), (f"check:{topic.id}", "✅ Check me"), ("cmd:next", "➡️ Next topic")]
        return wa.buttons("Want to go deeper?", items)
    items = [(f"check:{topic.id}", "✅ Check me"), (f"simpler:{topic.id}", "🤔 Explain simpler"), ("cmd:next", "➡️ Next topic")]
    return wa.buttons("Done reading? Let's make sure it stuck 👇", items)


def _quiz_cat_for_track(track: str) -> str:
    return {"dsa": "dsa", "ml": "ml", "cpp": "cpp", "python": "python"}[track]
