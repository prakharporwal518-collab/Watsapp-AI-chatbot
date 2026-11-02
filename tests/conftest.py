from __future__ import annotations

import json
import os
import random
import time
import uuid
from datetime import datetime

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import select

from app.config import Settings
from app.container import build_container
from app.core.kvstore import MemoryKVStore
from app.db.base import Base
from app.db.models import QuizQuestion, QuizSession, User
from app.db.session import create_all
from app.services.seed import seed_content
from app.whatsapp.client import CollectingSender
from app.whatsapp.parser import InboundMessage

APP_SECRET = "test-app-secret"
VERIFY_TOKEN = "test-verify-token"
INTERNAL_TOKEN = "test-internal-token"
FERNET_KEY = Fernet.generate_key().decode()


def make_settings(**overrides) -> Settings:
    base = dict(
        environment="test",
        # Set TEST_DATABASE_URL to run the suite against PostgreSQL (tables are recreated per test).
        database_url=os.environ.get("TEST_DATABASE_URL", "sqlite+aiosqlite:///:memory:"),
        whatsapp_access_token="",
        whatsapp_phone_number_id="",
        whatsapp_verify_token=VERIFY_TOKEN,
        whatsapp_app_secret=APP_SECRET,
        openai_api_key="",
        data_encryption_key=FERNET_KEY,
        identifier_hash_secret="test-hash-secret",
        internal_api_token=INTERNAL_TOKEN,
        rate_limit_per_minute=1000,
        log_level="WARNING",
        default_timezone="Asia/Kolkata",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


class FakeClock:
    def __init__(self, now: datetime | None = None):
        self.now = now or datetime(2026, 11, 2, 10, 0, 0)  # naive UTC (15:30 IST)

    def __call__(self) -> datetime:
        return self.now


class FakeLLM:
    """Scripted LLM. Tests can set `self.handler` to customise responses; every call is recorded."""

    available = True

    def __init__(self):
        self.calls: list[dict] = []
        self.handler = None
        self.fail = False

    async def complete(self, system, messages, *, temperature=0.4, max_tokens=1800, json_mode=False) -> str:
        from app.llm.client import LLMError

        self.calls.append({"system": system, "messages": messages, "json_mode": json_mode})
        if self.fail:
            raise LLMError("simulated failure")
        if self.handler:
            return self.handler(system, messages, json_mode)
        user = messages[-1]["content"]
        if "Classify a WhatsApp message" in system:
            return json.dumps({"intent": "question", "track": "dsa"})
        if "quiz questions" in system:
            n = int(user.split("Create ")[1].split()[0])
            return json.dumps({"questions": [{
                "qtype": "mcq", "prompt": f"AI question {i} {uuid.uuid4().hex[:6]}?", "code": "",
                "options": ["w", "x", "y", "z"], "answer_index": 1, "explanation": "Because x.",
                "option_explanations": ["no", "yes", "no", "no"]} for i in range(n)]})
        if "grade a student's short answer" in system:
            return json.dumps({"correct": True, "feedback": "Good.", "misconception": ""})
        if "You review student code" in system:
            return json.dumps({"language": "python", "verdict": "correct", "summary": "ok",
                               "feedback": "Looks *correct*. Time O(n)."})
        if "supportive technical interviewer" in system:
            return json.dumps({"rating": "optimal", "feedback": "Great approach!"})
        return "AI LESSON PART ONE\n<<<SPLIT>>>\n**AI LESSON PART TWO**\n```cpp\nint main() {}\n```"


async def _build(settings, llm=None, clock=None):
    sender = CollectingSender()
    container = build_container(settings, sender=sender, llm=llm, clock=clock or FakeClock(),
                                kv=MemoryKVStore(), rng=random.Random(42))
    if not settings.database_url.startswith("sqlite"):
        async with container.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    await create_all(container.engine)
    async with container.sessionmaker() as session:
        await seed_content(session)
    return container


async def build_for_http(settings):
    """Container for FastAPI's TestClient, which runs its own event loop. Pooled asyncpg
    connections can't cross event loops, so drop them first (SQLite in-memory must keep its one)."""
    container = await _build(settings)
    if not settings.database_url.startswith("sqlite"):
        await container.engine.dispose()
    return container


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
async def container(clock):
    c = await _build(make_settings(), clock=clock)
    yield c
    await c.close()


@pytest.fixture
def fake_llm():
    return FakeLLM()


@pytest.fixture
async def ai_container(clock, fake_llm):
    c = await _build(make_settings(), llm=fake_llm, clock=clock)
    yield c
    await c.close()


class Chat:
    """Talk to the bot as one student, like WhatsApp would."""

    def __init__(self, container, wa_id: str = "919876543210", name: str = "Asha Verma"):
        self.c = container
        self.wa_id = wa_id
        self.name = name

    async def send(self, text: str = "", button: str | None = None, mtype: str | None = None):
        msg = InboundMessage(
            message_id=f"wamid.{uuid.uuid4().hex}", wa_id=self.wa_id, timestamp=int(time.time()),
            type=mtype or ("interactive" if button else "text"), text=text, button_id=button, profile_name=self.name,
        )
        return await self.c.processor.process(msg, deliver=False)

    async def onboard(self, goal="dsa interview", lang="cpp", level="beginner", minutes="60"):
        await self.send("hi")
        await self.send(button=f"goal:{goal}")
        await self.send(button=f"lang:{lang}")
        await self.send(button=f"level:{level}")
        return await self.send(button=f"time:{minutes}")

    async def user(self) -> User:
        async with self.c.sessionmaker() as s:
            return await s.scalar(select(User).where(User.wa_id_hash == self.c.protector.hash_id(self.wa_id)))

    async def current_question(self) -> QuizQuestion | None:
        u = await self.user()
        sid = (u.state or {}).get("quiz_session_id")
        if not sid:
            return None
        async with self.c.sessionmaker() as s:
            qs = await s.get(QuizSession, sid)
            if qs.current_index >= len(qs.question_ids):
                return None
            return await s.get(QuizQuestion, qs.question_ids[qs.current_index])

    async def answer_current(self, correct: bool = True):
        q = await self.current_question()
        assert q is not None, "no active question"
        if q.qtype == "short":
            return await self.send(q.answer if correct else "no idea")
        idx = int(q.answer) if correct else (int(q.answer) + 1) % len(q.options)
        return await self.send("ABCD"[idx])


def texts(replies) -> str:
    return "\n".join(r.plain_text for r in replies)
