"""WhatsApp Cloud API webhook: verification handshake (GET) and incoming messages (POST)."""

from __future__ import annotations

import hmac
import json
import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from app.core.security import verify_meta_signature
from app.whatsapp.parser import parse_webhook

logger = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"])

MAX_BODY_BYTES = 1_000_000


@router.get("/webhook", response_class=PlainTextResponse)
async def verify_webhook(
    request: Request,
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    """Meta calls this once when you register the webhook URL."""
    expected = request.app.state.container.settings.whatsapp_verify_token
    if mode == "subscribe" and expected and hmac.compare_digest(token, expected):
        logger.info("Webhook verified by Meta")
        return challenge
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def receive_webhook(request: Request, background: BackgroundTasks):
    container = request.app.state.container
    settings = container.settings
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload too large")

    if not settings.allow_unsigned_webhooks:
        if not verify_meta_signature(raw, request.headers.get("X-Hub-Signature-256"), settings.whatsapp_app_secret):
            logger.warning("Rejected webhook with invalid signature")
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    accepted = 0
    for message in parse_webhook(payload):
        # Meta retries deliveries; process each message ID only once.
        if not await container.dedup.first_time(message.message_id):
            logger.info("Duplicate message ignored")
            continue
        accepted += 1
        # Reply 200 immediately; do the (possibly slow, LLM-backed) work in the background.
        background.add_task(container.processor.process, message)
    return {"status": "ok", "accepted": accepted}
