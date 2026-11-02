"""Agent 5 — Progress Tracking: reports, weak topics, streaks and 'what should I learn next?'."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, Intent
from app.content.curriculum import TOPICS
from app.services import progress, reports
from app.whatsapp import messages as wa


class ProgressAgent:
    name = "progress"

    async def handle(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        handler = getattr(self, f"on_{intent.name}", self.on_progress)
        return await handler(ctx, intent)

    async def on_progress(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        track = intent.params.get("track")
        text = (await reports.track_report(ctx.session, ctx.user, track) if track
                else await reports.overall_report(ctx.session, ctx.user, ctx.now))
        return AgentResponse([wa.text(text), wa.buttons(
            "Dig deeper:", [("cmd:weakness", "🔍 Weak topics"), ("cmd:weekly", "🗓️ Weekly report"), ("cmd:next", "➡️ What next?")])])

    async def on_weakness(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        text, weak_ids = await reports.weakness_report(ctx.session, ctx.user)
        resp = AgentResponse([wa.text(text)])
        if weak_ids:
            first = weak_ids[0]
            resp.add(wa.buttons(f"Start with *{TOPICS[first].title}*?", [
                (f"simpler:{first}", "🤔 Explain simply"), ("cmd:revision", "🔁 Revision quiz"), (f"learn:{first}", "📖 Lesson")]))
        else:
            resp.add(wa.buttons("Keep going:", [("quiz:auto", "📝 Take a quiz"), ("cmd:next", "➡️ What next?")]))
        return resp

    async def on_weekly(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.text(await reports.weekly_report(ctx.session, ctx.user, ctx.now)),
                              wa.buttons("Next steps:", [("cmd:dailyplan", "📅 Today's plan"), ("cmd:weakness", "🔍 Weak topics")])])

    async def on_coding_perf(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.text(await reports.coding_report(ctx.session, ctx.user)),
                              wa.buttons("Practice:", [("prac:new", "🧑‍💻 Problem"), ("cmd:interview", "🎤 Mock interview")])])

    async def on_streak(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.buttons(reports.streak_report(ctx.user, ctx.today),
                                         [("cmd:next", "📖 Study now"), ("quiz:auto", "📝 Quick quiz")])])

    async def on_next(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        rec = await progress.recommend_next(ctx.session, ctx.user, intent.params.get("track"), ctx.now)
        if rec is None:
            return AgentResponse([wa.buttons("🎓 You've completed every topic in this track — amazing! Try another track:",
                                             [("menu:dsa", "🧩 DSA"), ("menu:ml", "🤖 ML"), ("menu:python", "🐍 Python")])])
        topic = rec.topic
        icon = {"revise": "🔁", "continue": "📖", "new": "🆕"}[rec.kind]
        body = (f"{icon} *Recommended next: {topic.title}*\n_{topic.module} · {topic.level.title()}_\n\n"
                f"Why: {rec.reason}.\n\n{topic.summary}")
        buttons = [(f"learn:{topic.id}", "▶️ Start lesson"), (f"check:{topic.id}", "✅ Test me first")]
        buttons.append(("cmd:revision", "🔁 Revise") if rec.kind == "revise" else (f"menu:{topic.track}", "📚 All topics"))
        return AgentResponse([wa.buttons(body, buttons)])
