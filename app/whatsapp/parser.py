"""Parse incoming WhatsApp Cloud API webhook payloads into simple InboundMessage objects."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class InboundMessage:
    message_id: str
    wa_id: str
    timestamp: int
    type: str  # text | interactive | button | image | audio | ...
    text: str = ""
    button_id: str | None = None
    profile_name: str | None = None

    @property
    def is_supported(self) -> bool:
        return self.type in {"text", "interactive", "button"}


def parse_webhook(payload: dict) -> list[InboundMessage]:
    """Extract user messages from a webhook payload. Delivery/read status updates are ignored."""
    messages: list[InboundMessage] = []
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return messages

    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            names = {
                c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", []) or []
            }
            for raw in value.get("messages", []) or []:
                try:
                    messages.append(_parse_message(raw, names))
                except (KeyError, TypeError, ValueError):
                    logger.warning("Skipping malformed message in webhook payload")
    return messages


def _parse_message(raw: dict, names: dict) -> InboundMessage:
    mtype = raw["type"]
    msg = InboundMessage(
        message_id=raw["id"],
        wa_id=raw["from"],
        timestamp=int(raw.get("timestamp", 0)),
        type=mtype,
        profile_name=names.get(raw["from"]),
    )
    if mtype == "text":
        msg.text = (raw.get("text") or {}).get("body", "")
    elif mtype == "interactive":
        inter = raw.get("interactive") or {}
        reply = inter.get("button_reply") or inter.get("list_reply") or {}
        msg.button_id = reply.get("id")
        msg.text = reply.get("title", "")
    elif mtype == "button":  # quick-reply button on a template message
        btn = raw.get("button") or {}
        msg.button_id = btn.get("payload")
        msg.text = btn.get("text", "")
    return msg
