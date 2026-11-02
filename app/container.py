"""Wires all components together. Tests build a container with fakes (sender, LLM, clock)."""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from app.agents.orchestrator import Orchestrator
from app.config import Settings
from app.core.kvstore import Deduplicator, KVStore, RateLimiter, build_kv_store
from app.core.security import IdentityProtector, set_protector
from app.db.base import utcnow
from app.db.session import build_engine, build_sessionmaker
from app.llm.client import LLMClient, build_llm
from app.services.pipeline import MessageProcessor
from app.whatsapp.client import CollectingSender, MessageSender, WhatsAppCloudClient

logger = logging.getLogger(__name__)


@dataclass
class Container:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: object
    protector: IdentityProtector
    kv: KVStore
    dedup: Deduplicator
    rate_limiter: RateLimiter
    sender: MessageSender
    llm: LLMClient
    orchestrator: Orchestrator
    processor: MessageProcessor
    clock: Callable[[], datetime] = field(default=utcnow)

    async def close(self) -> None:
        await self.sender.close()
        await self.kv.close()
        await self.engine.dispose()


def build_container(
    settings: Settings,
    sender: MessageSender | None = None,
    llm: LLMClient | None = None,
    clock: Callable[[], datetime] | None = None,
    kv: KVStore | None = None,
    rng: random.Random | None = None,
) -> Container:
    protector = IdentityProtector(settings.identifier_hash_secret, settings.data_encryption_key)
    set_protector(protector)  # used by EncryptedText columns
    engine = build_engine(settings.database_url)
    sessionmaker = build_sessionmaker(engine)
    kv = kv or build_kv_store(settings.redis_url)
    if sender is None:
        if settings.whatsapp_enabled:
            sender = WhatsAppCloudClient(
                settings.whatsapp_access_token, settings.whatsapp_phone_number_id, settings.whatsapp_api_version,
                settings.whatsapp_api_base_url, settings.whatsapp_template_language,
            )
        else:
            logger.warning("WhatsApp is not configured — replies are only visible via /dev chat and the CLI")
            sender = CollectingSender()
    llm = llm or build_llm(settings.openai_api_key, settings.openai_model, settings.openai_base_url, settings.llm_timeout_seconds)
    clock = clock or utcnow
    orchestrator = Orchestrator()
    rate_limiter = RateLimiter(kv, settings.rate_limit_per_minute)
    processor = MessageProcessor(settings, sessionmaker, protector, llm, sender, rate_limiter, orchestrator, clock, rng)
    return Container(settings, engine, sessionmaker, protector, kv, Deduplicator(kv), rate_limiter, sender, llm,
                     orchestrator, processor, clock)
