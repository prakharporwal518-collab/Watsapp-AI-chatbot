"""Security helpers: webhook signature verification, identifier hashing and field encryption."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_DEV_SECRET = "dev-only-insecure-secret-do-not-use-in-production"


def verify_meta_signature(raw_body: bytes, signature_header: str | None, app_secret: str) -> bool:
    """Validate Meta's `X-Hub-Signature-256: sha256=<hex>` header against the raw request body."""
    if not signature_header or not app_secret:
        return False
    if not signature_header.startswith("sha256="):
        return False
    received = signature_header.split("=", 1)[1].strip()
    expected = hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(received, expected)


def sign_body(raw_body: bytes, app_secret: str) -> str:
    """Build a signature header the same way Meta does (used by tests and local tools)."""
    return "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()


class IdentityProtector:
    """Hashes WhatsApp IDs for lookups and encrypts them (plus other PII) at rest.

    * `hash_id` → deterministic HMAC-SHA256, used as the DB lookup key. Without the secret
      it cannot be reversed or brute-forced cheaply.
    * `encrypt` / `decrypt` → Fernet (AES-128-CBC + HMAC). Needed because we must know the real
      number to send messages back.
    """

    def __init__(self, hash_secret: str, encryption_key: str):
        if not hash_secret:
            logger.warning("IDENTIFIER_HASH_SECRET not set — using an insecure development secret")
            hash_secret = _DEV_SECRET
        if not encryption_key:
            logger.warning("DATA_ENCRYPTION_KEY not set — using an insecure development key")
            encryption_key = base64.urlsafe_b64encode(hashlib.sha256(_DEV_SECRET.encode()).digest()).decode()
        self._hash_secret = hash_secret.encode()
        self._fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)

    def hash_id(self, wa_id: str) -> str:
        normalised = "".join(ch for ch in wa_id if ch.isdigit())
        return hmac.new(self._hash_secret, normalised.encode(), hashlib.sha256).hexdigest()

    def encrypt(self, value: str | None) -> str | None:
        if value is None:
            return None
        return self._fernet.encrypt(value.encode()).decode()

    def decrypt(self, token: str | None) -> str | None:
        if token is None:
            return None
        try:
            return self._fernet.decrypt(token.encode()).decode()
        except InvalidToken:
            logger.error("Failed to decrypt a stored value (wrong DATA_ENCRYPTION_KEY?)")
            return None


def user_ref(id_hash: str) -> str:
    """Short, non-reversible reference that is safe to print in logs."""
    return f"u:{id_hash[:10]}"


# A process-wide protector, configured at startup. Used by the EncryptedText column type.
_protector: IdentityProtector | None = None


def set_protector(protector: IdentityProtector) -> None:
    global _protector
    _protector = protector


def get_protector() -> IdentityProtector:
    global _protector
    if _protector is None:
        _protector = IdentityProtector("", "")
    return _protector
