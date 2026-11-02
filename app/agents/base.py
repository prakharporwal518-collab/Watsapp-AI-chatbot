"""Shared building blocks for all agents."""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.db.models import User
from app.llm.client import LLMClient, LLMError
from app.services.progress import local_date
from app.services.users import set_state
from app.whatsapp import messages as wa
from app.whatsapp.formatter import chunk_text, to_whatsapp

logger = logging.getLogger(__name__)


@dataclass
class Intent:
    """What the student wants. `agent` decides which specialised agent handles it."""

    name: str
    agent: str
    params: dict = field(default_factory=dict)
    text: str = ""


@dataclass
class AgentResponse:
    messages: list[wa.OutgoingMessage] = field(default_factory=list)
    handoff: Intent | None = None  # ask the orchestrator to route to another agent
    record_activity: bool = False  # counts towards streak/study time (real learning only)
    deleted: bool = False  # the student deleted their data; nothing more may be saved

    def add(self, *msgs: wa.OutgoingMessage) -> AgentResponse:
        self.messages.extend(msgs)
        return self


class LLMBudgetExceeded(LLMError):
    pass


@dataclass
class AgentContext:
    session: AsyncSession
    user: User
    llm: LLMClient
    settings: Settings
    now: datetime  # naive UTC
    rng: random.Random = field(default_factory=random.Random)

    @property
    def prefs(self):
        return self.user.preferences

    @property
    def today(self) -> date:
        return local_date(self.user, self.now)

    @property
    def language(self) -> str:
        return (self.prefs.preferred_language if self.prefs else None) or "cpp"

    @property
    def state(self) -> dict:
        return dict(self.user.state or {})

    def set_state(self, **updates) -> None:
        set_state(self.user, **updates)

    @property
    def llm_available(self) -> bool:
        return self.llm.available

    async def ask_llm(self, system: str, messages: list[dict], **kwargs) -> str:
        """Call the LLM while enforcing a per-student daily budget (cost control / abuse protection)."""
        if not self.llm.available:
            raise LLMError("LLM not configured")
        today = self.today
        if self.user.llm_calls_date != today:
            self.user.llm_calls_date = today
            self.user.llm_calls_today = 0
        if self.user.llm_calls_today >= self.settings.llm_daily_limit_per_user:
            raise LLMBudgetExceeded("Daily AI limit reached")
        self.user.llm_calls_today += 1
        return await self.llm.complete(system, messages, **kwargs)

    def long_text(self, raw: str, *, markdown: bool = True) -> list[wa.OutgoingMessage]:
        """Format and split long content into WhatsApp-sized messages.

        If there are more chunks than `max_chunks_per_reply`, the rest is stored and the student
        can type *more* to continue — keeps the chat readable and avoids message floods.
        """
        body = to_whatsapp(raw) if markdown else raw
        chunks = chunk_text(body, self.settings.max_message_chars)
        limit = self.settings.max_chunks_per_reply
        if len(chunks) > limit:
            shown, rest = chunks[: limit], chunks[limit:]
            self.set_state(pending_chunks=rest)
            shown[-1] += "\n\n_…reply *more* to continue_"
            chunks = shown
        else:
            self.set_state(pending_chunks=None)
        return [wa.text(c) for c in chunks]


def main_menu_buttons() -> list[tuple[str, str]]:
    return [("cmd:dailyplan", "📅 Today's plan"), ("quiz:mixed", "📝 Quick quiz"), ("cmd:next", "➡️ What next?")]


def ai_unavailable_note() -> str:
    return "_(Detailed AI explanations are temporarily unavailable, so here's the curated version.)_"
