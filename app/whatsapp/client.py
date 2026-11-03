"""Outbound messaging: the official WhatsApp Cloud API client plus an in-memory sender for tests/dev."""

from __future__ import annotations

import asyncio
import logging
from typing import Protocol

import httpx

from app.whatsapp.messages import OutgoingMessage

logger = logging.getLogger(__name__)


class MessageSender(Protocol):
    async def send(self, to: str, message: OutgoingMessage) -> bool: ...
    async def mark_read(self, message_id: str) -> None: ...
    async def close(self) -> None: ...


def build_payload(to: str, msg: OutgoingMessage) -> dict:
    base = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": to}
    if msg.kind == "text":
        base.update(type="text", text={"preview_url": False, "body": msg.body})
    elif msg.kind == "buttons":
        interactive: dict = {
            "type": "button",
            "body": {"text": msg.body},
            "action": {
                "buttons": [{"type": "reply", "reply": {"id": b.id, "title": b.title}} for b in msg.buttons]
            },
        }
        if msg.header:
            interactive["header"] = {"type": "text", "text": msg.header[:60]}
        base.update(type="interactive", interactive=interactive)
    elif msg.kind == "list":
        interactive = {
            "type": "list",
            "body": {"text": msg.body},
            "action": {
                "button": msg.list_button,
                "sections": [
                    {
                        "title": (msg.header or "Options")[:24],
                        "rows": [
                            {"id": r.id, "title": r.title, **({"description": r.description} if r.description else {})}
                            for r in msg.rows
                        ],
                    }
                ],
            },
        }
        if msg.header:
            interactive["header"] = {"type": "text", "text": msg.header[:60]}
        base.update(type="interactive", interactive=interactive)
    elif msg.kind == "template":
        template: dict = {"name": msg.template_name, "language": {"code": "en"}}
        if msg.template_params:
            template["components"] = [
                {"type": "body", "parameters": [{"type": "text", "text": p} for p in msg.template_params]}
            ]
        base.update(type="template", template=template)
    else:
        raise ValueError(f"Unknown message kind: {msg.kind}")
    return base


class WhatsAppCloudClient:
    """Sends messages through Meta's Graph API with retries on rate limits / server errors."""

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        api_version: str = "v25.0",
        base_url: str = "https://graph.facebook.com",
        template_language: str = "en",
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 3,
    ):
        self._url = f"{base_url.rstrip('/')}/{api_version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
        self._http = http_client or httpx.AsyncClient(timeout=20.0)
        self._template_language = template_language
        self._max_retries = max_retries

    async def _post(self, payload: dict) -> bool:
        delay = 1.0
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._http.post(self._url, json=payload, headers=self._headers)
            except httpx.HTTPError as exc:
                logger.warning("WhatsApp API network error (attempt %d): %s", attempt, type(exc).__name__)
            else:
                if resp.status_code < 300:
                    return True
                retriable = resp.status_code == 429 or resp.status_code >= 500
                # Don't log the body verbatim at INFO: it can echo the recipient number.
                logger.error("WhatsApp API error %s (attempt %d)", resp.status_code, attempt)
                logger.debug("WhatsApp API error body: %s", resp.text[:500])
                if not retriable:
                    return False
            if attempt < self._max_retries:
                await asyncio.sleep(delay)
                delay *= 2
        return False

    async def send(self, to: str, message: OutgoingMessage) -> bool:
        payload = build_payload(to, message)
        if message.kind == "template":
            payload["template"]["language"]["code"] = self._template_language
        return await self._post(payload)

    async def mark_read(self, message_id: str) -> None:
        await self._post({"messaging_product": "whatsapp", "status": "read", "message_id": message_id})

    async def close(self) -> None:
        await self._http.aclose()


class CollectingSender:
    """Stores messages instead of sending them. Used by tests, /dev/chat and when WhatsApp isn't configured."""

    def __init__(self):
        self.sent: list[tuple[str, OutgoingMessage]] = []

    async def send(self, to: str, message: OutgoingMessage) -> bool:
        self.sent.append((to, message))
        if len(self.sent) > 2000:  # bounded, so a long-running dev server can't grow forever
            del self.sent[:1000]
        return True

    async def mark_read(self, message_id: str) -> None:
        return None

    async def close(self) -> None:
        return None

    def for_user(self, to: str) -> list[OutgoingMessage]:
        return [m for t, m in self.sent if t == to]

    def clear(self) -> None:
        self.sent.clear()
