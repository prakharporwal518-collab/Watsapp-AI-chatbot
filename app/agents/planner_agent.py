"""Agent 6 — Study Planner: daily plans, preferences (time, goals, language, level, timezone) and
opt-in reminders. Reminders are only ever sent after explicit consent and stop on request."""

from __future__ import annotations

import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.agents.base import AgentContext, AgentResponse, Intent, main_menu_buttons
from app.services import planner
from app.services.users import first_name
from app.whatsapp import messages as wa

TZ_ALIASES = {"ist": "Asia/Kolkata", "india": "Asia/Kolkata", "utc": "UTC", "gmt": "UTC", "pst": "America/Los_Angeles",
              "est": "America/New_York", "bst": "Europe/London", "cet": "Europe/Berlin", "sgt": "Asia/Singapore"}
LEVELS = {"beginner": "beginner", "newbie": "beginner", "intermediate": "intermediate", "advanced": "advanced", "expert": "advanced"}


def parse_minutes(text: str) -> int | None:
    t = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h)\b", t)
    if m:
        return int(float(m.group(1)) * 60)
    m = re.search(r"(\d{1,3})\s*(minutes?|mins?|m)?\b", t)
    return int(m.group(1)) if m else None


def parse_time(text: str) -> str | None:
    """'7pm' → '19:00', '7:30 am' → '07:30', '21:15' → '21:15'. A bare number is read as 24-hour time."""
    m = re.search(r"\b(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm)?\b", text.lower())
    if not m:
        return None
    hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ampm and not 1 <= hour <= 12:
        return None
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if not (0 <= hour < 24 and 0 <= minute < 60):
        return None
    return f"{hour:02d}:{minute:02d}"


class PlannerAgent:
    name = "planner"

    async def handle(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        handler = getattr(self, f"on_{intent.name}", self.on_dailyplan)
        return await handler(ctx, intent)

    # ------------------------------------------------------------------ plan
    async def on_dailyplan(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        items = await planner.build_plan(ctx.session, ctx.user, ctx.now)
        await planner.save_plan(ctx.session, ctx.user, items, ctx.now)
        text = planner.render_plan(items, ctx.today.strftime("%a %d %b"), ctx.prefs.daily_minutes)
        rows = [(i.action, f"{planner.ICONS.get(i.kind, '')} {i.title}", f"{i.minutes} min · {i.detail}".strip(" ·"))
                for i in items]
        resp = AgentResponse([wa.list_menu(text, rows, button="Start an item")])
        if not ctx.prefs.reminders_enabled:
            resp.add(wa.buttons("Want a daily reminder with your plan? (You can stop anytime.)",
                                [("remind:on", "🔔 Yes, remind me"), ("cmd:settings", "⚙️ Settings")]))
        return resp

    # ------------------------------------------------------------------ settings
    async def on_settings(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        p = ctx.prefs
        reminder = f"on at {p.reminder_time}" if p.reminders_enabled else "off"
        text = (
            "⚙️ *Your settings*\n\n"
            f"🎯 Goals: {', '.join(p.goals or ['dsa'])}\n"
            f"💻 Coding language: {'C++' if p.preferred_language == 'cpp' else 'Python'}\n"
            f"📈 Level: {ctx.user.level}\n"
            f"⏱️ Daily study time: {p.daily_minutes} min\n"
            f"🌍 Timezone: {p.timezone}\n"
            f"🔔 Daily reminder: {reminder}\n"
            f"🗓️ Weekly report message: {'on' if p.weekly_report_enabled else 'off'}\n\n"
            "*Change with:*\n"
            "• /time 90 — daily minutes\n• /goal dsa ml interview\n• /lang python  or  /lang cpp\n"
            "• /level beginner|intermediate|advanced\n• /timezone Asia/Kolkata\n"
            "• /remind 7pm  ·  /remind off  ·  /remind weekly on\n\n"
            "Or just say it: _\"I can study 2 hours a day\"_ 🙂"
        )
        return AgentResponse([wa.text(text)])

    async def on_set_time(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        minutes = parse_minutes(intent.params.get("args") or intent.text)
        if not minutes:
            return AgentResponse([wa.text("How many minutes can you study per day? e.g. */time 60* or \"I can study 2 hours a day\".")])
        ctx.prefs.daily_minutes = max(10, min(minutes, 480))
        if intent.params.get("onboarding"):
            return await self._finish_onboarding(ctx)
        return AgentResponse([wa.buttons(f"✅ Got it — {ctx.prefs.daily_minutes} minutes a day. I'll size your daily plans to fit.",
                                         [("cmd:dailyplan", "📅 Today's plan")])])

    async def on_set_goal(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        args = (intent.params.get("args") or intent.text).lower().replace("c++", "cpp")
        found = []
        for key, words in (("dsa", ("dsa", "data structure", "algorithm", "both")), ("ml", ("ml", "machine learning", "ai", "both")),
                           ("interview", ("interview", "placement", "job")), ("cpp", ("cpp",)), ("python", ("python",))):
            if any(re.search(rf"\b{re.escape(w)}\b", args) for w in words):
                found.append(key)
        if not found:
            return AgentResponse([wa.text("Which goals? e.g. */goal dsa ml interview* — options: dsa, ml, cpp, python, interview.")])
        ctx.prefs.goals = found
        if intent.params.get("onboarding"):
            return self._ask_language()
        return AgentResponse([wa.text(f"🎯 Goals updated: {', '.join(found)}. Your plans and recommendations will follow these.")])

    async def on_set_lang(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        args = (intent.params.get("args") or intent.text).lower()
        lang = "python" if "python" in args else "cpp" if ("cpp" in args or "c++" in args) else None
        if not lang:
            return AgentResponse([wa.text("Choose */lang cpp* or */lang python*.")])
        ctx.prefs.preferred_language = lang
        if intent.params.get("onboarding"):
            return self._ask_level()
        return AgentResponse([wa.text(f"💻 Code examples will now be in {'C++' if lang == 'cpp' else 'Python'}.")])

    async def on_set_level(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        args = (intent.params.get("args") or intent.text).lower()
        level = next((v for k, v in LEVELS.items() if k in args), None)
        if not level:
            return AgentResponse([wa.text("Choose */level beginner*, *intermediate* or *advanced*.")])
        ctx.user.level = level
        if intent.params.get("onboarding"):
            return self._ask_time()
        return AgentResponse([wa.text(f"📈 Level set to *{level}*. I'll adjust explanations and problem difficulty.")])

    async def on_set_timezone(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        raw = (intent.params.get("args") or "").strip()
        tz = TZ_ALIASES.get(raw.lower(), raw)
        try:
            ZoneInfo(tz)
        except (ZoneInfoNotFoundError, ValueError):
            return AgentResponse([wa.text("Please send a timezone like */timezone Asia/Kolkata* or */timezone Europe/London*.")])
        ctx.prefs.timezone = tz
        return AgentResponse([wa.text(f"🌍 Timezone set to {tz}. Reminders and streaks now follow your local day.")])

    async def on_remind(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        args = (intent.params.get("args") or "").lower().strip()
        p = ctx.prefs
        if args.startswith("weekly"):
            p.weekly_report_enabled = "off" not in args
            return AgentResponse([wa.text("🗓️ Weekly report messages " + ("enabled (Sundays)." if p.weekly_report_enabled else "disabled."))])
        if args in ("off", "stop", "no", "disable") or re.search(r"\b(off|stop|disable|no more)\b", args):
            p.reminders_enabled = False
            p.weekly_report_enabled = False
            p.reminder_consent_revoked_at = ctx.now
            return AgentResponse([wa.text("🔕 Reminders turned off. I won't message you unless you write to me first. "
                                          "Turn them back on anytime with */remind on*.")])
        if args == "no thanks":
            return AgentResponse([wa.text("No problem — no reminders. 🙂")])
        when = parse_time(args) if args not in ("on", "") else None
        p.reminders_enabled = True
        p.reminder_consent_at = ctx.now
        p.reminder_consent_revoked_at = None
        if when:
            p.reminder_time = when
        return AgentResponse([wa.text(
            f"🔔 Done! I'll send your study plan every day at *{p.reminder_time}* ({p.timezone}).\n\n"
            "Change the time with */remind 8pm*. Stop anytime with */remind off* or by saying \"stop reminders\".")])

    # ------------------------------------------------------------------ onboarding steps
    def _ask_language(self) -> AgentResponse:
        return AgentResponse([wa.buttons("Which language do you want code examples in?",
                                         [("lang:cpp", "C++"), ("lang:python", "Python")])])

    def _ask_level(self) -> AgentResponse:
        return AgentResponse([wa.buttons("How would you rate your programming level right now?",
                                         [("level:beginner", "🌱 Beginner"), ("level:intermediate", "🌿 Intermediate"),
                                          ("level:advanced", "🌳 Advanced")])])

    def _ask_time(self) -> AgentResponse:
        return AgentResponse([wa.list_menu("How much time can you study per day?",
                                           [("time:20", "20 minutes", ""), ("time:30", "30 minutes", ""), ("time:60", "1 hour", ""),
                                            ("time:90", "1.5 hours", ""), ("time:120", "2 hours", ""), ("time:180", "3+ hours", "")],
                                           button="Choose time")])

    async def _finish_onboarding(self, ctx: AgentContext) -> AgentResponse:
        ctx.user.onboarded = True
        ctx.set_state(onboarding=None)
        name = first_name(ctx.user)
        text = (f"🎉 All set, {name}! Here's how I'll help:\n\n"
                "📖 Lessons with code, dry runs and complexity\n📝 Quizzes that find your weak spots\n"
                "🧑‍💻 Coding practice & mock interviews\n📊 Progress tracking and revision reminders\n\n"
                "Just talk to me normally — e.g. _\"explain binary search\"_ or _\"give me 5 python questions\"_.")
        return AgentResponse([
            wa.buttons(text, main_menu_buttons()),
            wa.buttons("Would you like a daily reminder with your study plan? You can turn it off anytime.",
                       [("remind:on", "🔔 Yes please"), ("remind:no thanks", "No thanks")]),
        ])
