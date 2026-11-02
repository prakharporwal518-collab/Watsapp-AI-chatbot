"""HTTP-level tests: webhook verification, signatures, duplicates, background processing, job auth."""

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.security import sign_body
from app.main import create_app
from tests.conftest import APP_SECRET, INTERNAL_TOKEN, VERIFY_TOKEN, build_for_http, make_settings


@pytest.fixture
async def client():
    container = await build_for_http(make_settings())
    app = create_app(container.settings, container=container)
    with TestClient(app) as tc:
        yield tc, container


def _message_payload(text="hi", msg_id="wamid.ABC", wa_id="919876543210", mtype="text"):
    message = {"from": wa_id, "id": msg_id, "timestamp": "1700000000", "type": mtype}
    if mtype == "text":
        message["text"] = {"body": text}
    else:
        message[mtype] = {"id": "media-id"}
    return {"object": "whatsapp_business_account", "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
        "messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"},
        "contacts": [{"wa_id": wa_id, "profile": {"name": "Asha"}}], "messages": [message]}}]}]}


def _post(tc, payload, secret=APP_SECRET):
    raw = json.dumps(payload).encode()
    return tc.post("/webhook", content=raw, headers={"X-Hub-Signature-256": sign_body(raw, secret),
                                                     "Content-Type": "application/json"})


def test_verification_handshake(client):
    tc, _ = client
    ok = tc.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    bad = tc.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "1"})
    assert bad.status_code == 403


def test_invalid_signature_rejected(client):
    tc, container = client
    assert _post(tc, _message_payload(), secret="attacker").status_code == 401
    raw = json.dumps(_message_payload()).encode()
    assert tc.post("/webhook", content=raw).status_code == 401  # no signature header at all
    assert container.sender.sent == []


def test_message_processed_and_reply_sent(client):
    tc, container = client
    resp = _post(tc, _message_payload("hi"))
    assert resp.status_code == 200 and resp.json()["accepted"] == 1
    # Background task ran: onboarding message sent to the student's real number.
    assert container.sender.sent
    to, msg = container.sender.sent[0]
    assert to == "919876543210"
    assert "What's your main goal" in msg.body


def test_duplicate_messages_processed_once(client):
    tc, container = client
    _post(tc, _message_payload("hi", msg_id="wamid.DUP"))
    count = len(container.sender.sent)
    again = _post(tc, _message_payload("hi", msg_id="wamid.DUP"))
    assert again.status_code == 200 and again.json()["accepted"] == 0
    assert len(container.sender.sent) == count


def test_status_only_payload_is_acknowledged(client):
    tc, container = client
    payload = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [{"id": "x"}]}}]}]}
    resp = _post(tc, payload)
    assert resp.status_code == 200 and resp.json()["accepted"] == 0


def test_media_message_gets_friendly_reply(client):
    tc, container = client
    _post(tc, _message_payload(msg_id="wamid.T1"))  # onboard first contact
    container.sender.clear()
    _post(tc, _message_payload(msg_id="wamid.IMG", mtype="image"))
    assert "only read text" in container.sender.sent[0][1].body


def test_bad_json_and_oversized_payload(client):
    tc, _ = client
    raw = b"not json"
    assert tc.post("/webhook", content=raw, headers={"X-Hub-Signature-256": sign_body(raw, APP_SECRET)}).status_code == 400
    big = b"x" * 1_000_001
    assert tc.post("/webhook", content=big, headers={"X-Hub-Signature-256": sign_body(big, APP_SECRET)}).status_code == 413


def test_phone_number_not_stored_in_plaintext(client):
    tc, container = client
    _post(tc, _message_payload("hi", msg_id="wamid.PII"))

    async def raw_rows():
        # Read raw column values, bypassing the EncryptedText decryption.
        async with container.engine.connect() as conn:
            return (await conn.execute(text("SELECT wa_id_hash, wa_id_encrypted, display_name FROM users"))).all()

    rows = tc.portal.call(raw_rows)  # run in the TestClient's event loop
    assert rows
    for wa_hash, wa_enc, name in rows:
        assert "919876543210" not in wa_hash and "919876543210" not in wa_enc
        assert name != "Asha"  # profile name is encrypted too


def test_health_and_root(client):
    tc, _ = client
    assert tc.get("/health").json()["database"] is True
    assert tc.get("/").json()["status"] == "running"


def test_internal_jobs_require_token(client):
    tc, _ = client
    assert tc.post("/internal/jobs/daily-reminders").status_code == 401
    assert tc.post("/internal/jobs/daily-reminders", headers={"Authorization": "Bearer nope"}).status_code == 401
    ok = tc.post("/internal/jobs/daily-reminders", headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"})
    assert ok.status_code == 200 and "sent" in ok.json()
    assert tc.post("/internal/jobs/prune-history", headers={"Authorization": f"Bearer {INTERNAL_TOKEN}"}).status_code == 200


def test_dev_chat(client):
    tc, _ = client
    r = tc.post("/dev/chat", json={"user": "dev", "text": "hi"})
    assert r.status_code == 200 and r.json()["replies"][0]["buttons"]
    assert tc.get("/dev").status_code == 200


async def test_dev_chat_disabled_in_production():
    from cryptography.fernet import Fernet

    settings = make_settings(environment="production", whatsapp_access_token="t", whatsapp_phone_number_id="1",
                             data_encryption_key=Fernet.generate_key().decode())
    container = await build_for_http(settings)
    app = create_app(settings, container=container)
    with TestClient(app) as tc:
        assert tc.post("/dev/chat", json={"text": "hi"}).status_code == 404
        assert tc.get("/docs").status_code == 404
