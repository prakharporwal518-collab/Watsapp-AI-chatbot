"""Agent 7 — Main Orchestrator.

A LangGraph state graph: `router` classifies the message, then a conditional edge sends it to one
of the specialised agents. Agents can hand off to each other (e.g. the DSA tutor hands submitted
code to the Coding agent); the graph follows up to MAX_HOPS handoffs. All agents share student
progress through the database session in AgentContext.

        ┌────────┐
 msg ──▶│ router │──┬──▶ dsa ──────┐
        └────────┘  ├──▶ coding ───┤
                    ├──▶ ml ───────┤  handoff? ──▶ (another agent)
                    ├──▶ quiz ─────┤
                    ├──▶ progress ─┤  else ──▶ END
                    ├──▶ planner ──┤
                    └──▶ general ──┘
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents import intents
from app.agents.base import AgentContext, AgentResponse, Intent, main_menu_buttons
from app.agents.coding_agent import CodingAgent
from app.agents.dsa_tutor import DSATutorAgent
from app.agents.ml_tutor import MLTutorAgent
from app.agents.planner_agent import PlannerAgent
from app.agents.progress_agent import ProgressAgent
from app.agents.quiz_agent import QuizAgent
from app.llm import prompts
from app.llm.client import LLMError, parse_json
from app.services import privacy, progress
from app.services.users import first_name
from app.whatsapp import messages as wa

logger = logging.getLogger(__name__)

MAX_HOPS = 3
AGENT_NODES = ("dsa", "coding", "ml", "quiz", "progress", "planner", "general")


class GraphState(TypedDict, total=False):
    text: str
    button_id: str | None
    intent: Intent
    messages: list
    record_activity: bool
    deleted: bool
    hops: int
    trail: list
    handoff_pending: bool


class GeneralAgent:
    """Conversation-level features the orchestrator handles itself: onboarding, help, privacy …"""

    name = "general"

    async def handle(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        handler = getattr(self, f"on_{intent.name}", self.on_help)
        return await handler(ctx, intent)

    async def on_start(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        name = first_name(ctx.user)
        if ctx.user.onboarded and not intent.params.get("force"):
            return await self.on_greeting(ctx, intent)
        ctx.set_state(onboarding="goal")
        text = (
            f"👋 Hi {name}! I'm your personal *programming & ML tutor* on WhatsApp.\n\n"
            "I teach DSA in C++ and Python, Machine Learning from scratch, quiz you, track your progress "
            "and plan your studies — like a private tutor in your pocket. 🎓\n\n"
            "Let's personalise things (takes 20 seconds). *What's your main goal?*"
        )
        return AgentResponse([wa.buttons(text, [("goal:dsa interview", "🧩 DSA & interviews"),
                                                ("goal:ml", "🤖 Machine Learning"), ("goal:dsa ml", "🚀 Both")])])

    async def on_greeting(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        if not ctx.user.onboarded:
            return await self.on_start(ctx, Intent("start", "general"))
        streak = progress.effective_streak(ctx.user.streak, ctx.today)
        line = f"🔥 {streak}-day streak — keep it up!" if streak else "Ready to learn something new today?"
        return AgentResponse([wa.buttons(f"Hey {first_name(ctx.user)}! 👋 {line}\n\nWhat would you like to do?", main_menu_buttons())])

    async def on_thanks(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.buttons("You're welcome! 😊 Happy learning.", main_menu_buttons())])

    async def on_help(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        text = (
            "🤖 *What I can do*\n\n"
            "📖 *Learn* — /dsa · /cpp · /python · /ml · /numpy · /pandas\n"
            "📝 *Practice* — /quiz · /practice · /interview · /revision\n"
            "📊 *Track* — /progress · /weakness · /streak · /report · /coding\n"
            "📅 *Plan* — /dailyplan · /next · /settings · /remind\n"
            "🔒 *Privacy* — /privacy · /deletedata\n\n"
            "You don't need commands — just type naturally:\n"
            "• _explain binary search_\n• _give me 10 python questions_\n• _medium-level arrays quiz_\n"
            "• _what should I learn next?_\n• _I don't understand_\n• paste your code for a review"
        )
        return AgentResponse([wa.list_menu(text, [
            ("menu:dsa", "🧩 DSA", "Data structures & algorithms"),
            ("menu:cpp", "⚙️ C++", "Syntax, OOP, STL"),
            ("menu:python", "🐍 Python", "Basics to data science"),
            ("menu:ml", "🤖 Machine Learning", "Maths to deep learning"),
            ("quiz:auto", "📝 Quiz", "Test yourself"),
            ("cmd:progress", "📊 My progress", "Reports & weak topics"),
            ("cmd:dailyplan", "📅 Today's plan", "Personalised schedule"),
        ], button="Open menu")])

    async def on_privacy(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.text(privacy.PRIVACY_TEXT.format(days=ctx.settings.history_retention_days))])

    async def on_delete_request(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        ctx.set_state(mode="await_delete_confirm")
        return AgentResponse([wa.buttons(
            "⚠️ This permanently deletes *all* your data: progress, quiz history, plans, streaks and chat history. "
            "It can't be undone.\n\nAre you sure?",
            [("del:confirm", "🗑️ Yes, delete all"), ("del:cancel", "Cancel")])])

    async def on_delete_confirm(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        if ctx.state.get("mode") != "await_delete_confirm":
            return await self.on_delete_request(ctx, intent)
        await privacy.delete_user_data(ctx.session, ctx.user)
        resp = AgentResponse([wa.text("✅ All your data has been permanently deleted. "
                                      "If you message me again, you'll start fresh as a new student. Take care! 👋")])
        resp.deleted = True
        return resp

    async def on_delete_cancel(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        ctx.set_state(mode=None)
        return AgentResponse([wa.text("👍 Cancelled — nothing was deleted.")])

    async def on_stop(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        ctx.prefs.reminders_enabled = False
        ctx.prefs.weekly_report_enabled = False
        ctx.prefs.reminder_consent_revoked_at = ctx.now
        ctx.set_state(mode=None)
        return AgentResponse([wa.text("🔕 Okay — no more reminders. I'll only reply when you message me.\n"
                                      "To delete your data entirely, send /deletedata.")])

    async def on_more(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        pending = list(ctx.state.get("pending_chunks") or [])
        if not pending:
            return AgentResponse([wa.text("That's everything for now! 🙂 What next?")])
        limit = ctx.settings.max_chunks_per_reply
        batch, rest = pending[:limit], pending[limit:]
        ctx.set_state(pending_chunks=rest or None)
        if rest:
            batch[-1] += "\n\n_…reply *more* to continue_"
        return AgentResponse([wa.text(c) for c in batch])

    async def on_unsupported(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.text("I can only read text messages for now 🙂 Please type your question, "
                                      "or paste your code as text.")])

    async def on_unknown_command(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.text(f"I don't know the command /{intent.params.get('command')}. Type /help to see what I can do.")])

    async def on_smalltalk(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return AgentResponse([wa.buttons("😊 I'm best at teaching programming, DSA and ML. Shall we learn something?",
                                         main_menu_buttons())])


class Orchestrator:
    def __init__(self):
        self.agents: dict[str, Any] = {
            "dsa": DSATutorAgent(),
            "coding": CodingAgent(),
            "ml": MLTutorAgent(),
            "quiz": QuizAgent(),
            "progress": ProgressAgent(),
            "planner": PlannerAgent(),
            "general": GeneralAgent(),
        }
        self.graph = self._build_graph()

    # ------------------------------------------------------------------ graph
    def _build_graph(self):
        g = StateGraph(GraphState)
        g.add_node("router", self._router_node)
        for name in AGENT_NODES:
            g.add_node(name, self._make_agent_node(name))
        g.add_edge(START, "router")
        g.add_conditional_edges("router", self._route, {n: n for n in AGENT_NODES})
        for name in AGENT_NODES:
            g.add_conditional_edges(name, self._after_agent, {**{n: n for n in AGENT_NODES}, "end": END})
        return g.compile()

    @staticmethod
    def _agent_key(intent: Intent) -> str:
        return "general" if intent.agent == "orchestrator" else intent.agent if intent.agent in AGENT_NODES else "general"

    def _route(self, state: GraphState) -> str:
        return self._agent_key(state["intent"])

    def _after_agent(self, state: GraphState) -> str:
        if state.get("intent") is not None and state.get("handoff_pending"):
            return self._agent_key(state["intent"])
        return "end"

    async def _router_node(self, state: GraphState, config) -> dict:
        ctx: AgentContext = config["configurable"]["ctx"]
        intent = intents.classify(state.get("text", ""), state.get("button_id"), ctx.state)
        intent.params.setdefault("button_id", state.get("button_id"))
        if intent.name == "question" and not intent.params.get("topic_id") and ctx.llm_available:
            intent = await self._llm_route(ctx, intent)
        logger.info("Routed intent=%s agent=%s", intent.name, intent.agent)
        return {"intent": intent, "messages": [], "hops": 0, "trail": []}

    def _make_agent_node(self, name: str):
        async def node(state: GraphState, config) -> dict:
            ctx: AgentContext = config["configurable"]["ctx"]
            intent = state["intent"]
            resp: AgentResponse = await self.agents[name].handle(ctx, intent)
            update: dict = {
                "messages": state.get("messages", []) + resp.messages,
                "record_activity": state.get("record_activity", False) or resp.record_activity,
                "deleted": state.get("deleted", False) or resp.deleted,
                "trail": state.get("trail", []) + [name],
                "handoff_pending": False,
            }
            hops = state.get("hops", 0)
            if resp.handoff is not None and hops < MAX_HOPS:
                resp.handoff.params.setdefault("button_id", None)
                update.update(intent=resp.handoff, hops=hops + 1, handoff_pending=True)
            return update

        return node

    async def _llm_route(self, ctx: AgentContext, intent: Intent) -> Intent:
        """Let the LLM decide the track/agent for open questions the rules couldn't place."""
        try:
            raw = await ctx.ask_llm(prompts.ROUTER_SYSTEM, [{"role": "user", "content": intent.text[:1000]}],
                                    temperature=0.0, max_tokens=60, json_mode=True)
            data = parse_json(raw)
        except LLMError:
            return intent
        track = data.get("track") if data.get("track") in ("dsa", "cpp", "python", "ml") else None
        kind = data.get("intent")
        if kind == "code_review":
            return Intent("code_review", "coding", {"code": intent.text}, intent.text)
        if kind == "quiz":
            return Intent("quiz_start", "quiz", {"category": track or "auto"}, intent.text)
        if kind == "progress":
            return Intent("progress", "progress", {}, intent.text)
        if kind == "plan":
            return Intent("dailyplan", "planner", {}, intent.text)
        if kind == "practice":
            return Intent("practice", "dsa", {}, intent.text)
        if kind == "interview":
            return Intent("interview_start", "quiz", {}, intent.text)
        if kind == "smalltalk":
            return Intent("smalltalk", "orchestrator", {}, intent.text)
        agent = intents.TRACK_AGENT.get(track or "", intent.agent)
        return Intent("question", agent, {**intent.params, "track": track}, intent.text)

    # ------------------------------------------------------------------ entry point
    async def run(self, ctx: AgentContext, text: str, button_id: str | None = None) -> tuple[AgentResponse, list[str]]:
        final = await self.graph.ainvoke({"text": text, "button_id": button_id}, config={"configurable": {"ctx": ctx}})
        resp = AgentResponse(final.get("messages", []), record_activity=final.get("record_activity", False),
                             deleted=final.get("deleted", False))
        return resp, final.get("trail", [])
