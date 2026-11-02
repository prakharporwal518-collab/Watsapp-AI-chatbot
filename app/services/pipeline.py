"""The message pipeline: one inbound WhatsApp message → agents → replies sent back."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from datetime import datetime

from app.agents.base import AgentContext
from app.agents.orchestrator import Orchestrator
from app.config import Settings
from app.core.kvstore import RateLimiter
from app.core.logging import request_id_var
from app.core.security import IdentityProtector, user_ref
from app.llm.client import LLMClient
from app.services import conversation, progress
from app.services.users import get_or_create_user
from app.whatsapp import messages as wa
from app.whatsapp.client import MessageSender
from app.whatsapp.parser import InboundMessage

logger = logging.getLogger(__name__)

MAX_INBOUND_CHARS = 4000
ERROR_TEXT = ("😕 Sorry, something went wrong on my side while handling that. Please try again in a moment. "
              "If it keeps happening, type /help.")


class MessageProcessor:
    def __init__(
        self,
        settings: Settings,
        sessionmaker,
        protector: IdentityProtector,
        llm: LLMClient,
        sender: MessageSender,
        rate_limiter: RateLimiter,
        orchestrator: Orchestrator,
        clock: Callable[[], datetime],
        rng: random.Random | None = None,
    ):
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.protector = protector
        self.llm = llm
        self.sender = sender
        self.rate_limiter = rate_limiter
        self.orchestrator = orchestrator
        self.clock = clock
        self.rng = rng or random.Random()
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, key: str) -> asyncio.Lock:
        # Serialise messages from the same student so their conversation state can't race.
        if len(self._locks) > 10_000:
            self._locks = {k: v for k, v in self._locks.items() if v.locked()}
        return self._locks.setdefault(key, asyncio.Lock())

    async def process(self, msg: InboundMessage, deliver: bool = True) -> list[wa.OutgoingMessage]:
        id_hash = self.protector.hash_id(msg.wa_id)
        token = request_id_var.set(f"{user_ref(id_hash)}:{msg.message_id[-8:]}")
        try:
            allowed, count = await self.rate_limiter.hit(id_hash)
            if not allowed:
                logger.warning("Rate limit exceeded (%d msgs/min)", count)
                if count == self.rate_limiter.limit + 1:
                    replies = [wa.text("⏳ You're sending messages very quickly. Please wait a minute and try again.")]
                    if deliver:
                        await self._send(msg.wa_id, replies)
                    return replies
                return []

            async with self._lock_for(id_hash):
                replies = await self._handle(msg)
            if deliver:
                await self._send(msg.wa_id, replies)
            return replies
        finally:
            request_id_var.reset(token)

    async def _handle(self, msg: InboundMessage) -> list[wa.OutgoingMessage]:
        now = self.clock()
        text = (msg.text or "")[:MAX_INBOUND_CHARS]
        async with self.sessionmaker() as session:
            try:
                user, created = await get_or_create_user(
                    session, self.protector, msg.wa_id, msg.profile_name, self.settings.default_timezone, now
                )
                if created:
                    logger.info("New student registered")
                ctx = AgentContext(session=session, user=user, llm=self.llm, settings=self.settings, now=now, rng=self.rng)

                if not msg.is_supported:
                    text, button_id = "", None
                else:
                    button_id = msg.button_id
                if created and not button_id and not text.startswith("/"):
                    text = "/start"  # first contact always starts onboarding

                resp, trail = await self.orchestrator.run(ctx, text, button_id)
                logger.info("Handled by %s → %d message(s)", "→".join(trail) or "-", len(resp.messages))

                if resp.deleted:
                    await session.commit()
                    return resp.messages

                if resp.record_activity:
                    await progress.record_activity(session, user, now)
                agent = trail[-1] if trail else None
                await conversation.add_turn(session, user.id, "user", msg.text or f"[{msg.type}]", None, now)
                for out in resp.messages:
                    if out.body:  # text, buttons and lists all carry useful context for follow-ups
                        await conversation.add_turn(session, user.id, "assistant", out.body, agent, now)
                await session.commit()
                return resp.messages
            except Exception:
                logger.exception("Failed to process message")
                await session.rollback()
                return [wa.text(ERROR_TEXT)]

    async def _send(self, to: str, replies: list[wa.OutgoingMessage]) -> None:
        for reply in replies:
            ok = await self.sender.send(to, reply)
            if not ok:
                logger.error("Failed to deliver a %s message", reply.kind)
                break
