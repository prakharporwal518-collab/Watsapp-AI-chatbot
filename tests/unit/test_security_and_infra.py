import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.core.kvstore import Deduplicator, MemoryKVStore, RateLimiter
from app.core.security import IdentityProtector, sign_body, verify_meta_signature


class TestSignature:
    def test_valid_signature(self):
        body = b'{"hello": "world"}'
        assert verify_meta_signature(body, sign_body(body, "secret"), "secret")

    def test_tampered_body_rejected(self):
        sig = sign_body(b'{"a": 1}', "secret")
        assert not verify_meta_signature(b'{"a": 2}', sig, "secret")

    def test_wrong_secret_rejected(self):
        body = b"{}"
        assert not verify_meta_signature(body, sign_body(body, "other"), "secret")

    @pytest.mark.parametrize("header", [None, "", "sha1=abc", "abc"])
    def test_missing_or_malformed_header(self, header):
        assert not verify_meta_signature(b"{}", header, "secret")

    def test_missing_secret_rejects_everything(self):
        body = b"{}"
        assert not verify_meta_signature(body, sign_body(body, ""), "")


class TestIdentityProtector:
    def setup_method(self):
        self.p = IdentityProtector("pepper", Fernet.generate_key().decode())

    def test_hash_is_deterministic_and_normalised(self):
        assert self.p.hash_id("+91 98765-43210") == self.p.hash_id("919876543210")
        assert len(self.p.hash_id("919876543210")) == 64

    def test_hash_depends_on_secret(self):
        other = IdentityProtector("different", Fernet.generate_key().decode())
        assert self.p.hash_id("919876543210") != other.hash_id("919876543210")

    def test_encryption_roundtrip(self):
        token = self.p.encrypt("919876543210")
        assert token != "919876543210"
        assert self.p.decrypt(token) == "919876543210"

    def test_wrong_key_returns_none(self):
        token = self.p.encrypt("secret")
        other = IdentityProtector("pepper", Fernet.generate_key().decode())
        assert other.decrypt(token) is None


class TestKVStore:
    async def test_deduplicator(self):
        d = Deduplicator(MemoryKVStore())
        assert await d.first_time("wamid.1")
        assert not await d.first_time("wamid.1")
        assert await d.first_time("wamid.2")

    async def test_ttl_expiry(self):
        now = [0.0]
        store = MemoryKVStore(clock=lambda: now[0])
        assert await store.set_if_absent("k", 10)
        assert not await store.set_if_absent("k", 10)
        now[0] = 11
        assert await store.set_if_absent("k", 10)

    async def test_rate_limiter(self):
        limiter = RateLimiter(MemoryKVStore(), limit=3)
        results = [await limiter.hit("user") for _ in range(5)]
        assert [r[0] for r in results] == [True, True, True, False, False]
        assert (await limiter.hit("someone-else"))[0]


class TestSettings:
    def test_postgres_url_normalised(self):
        s = Settings(_env_file=None, database_url="postgres://u:p@host/db")
        assert s.database_url == "postgresql+asyncpg://u:p@host/db"

    def test_production_requires_secrets(self):
        with pytest.raises(ValueError, match="Missing required production settings"):
            Settings(_env_file=None, environment="production")

    def test_production_forbids_unsigned_webhooks(self):
        full = dict(whatsapp_access_token="t", whatsapp_phone_number_id="1", whatsapp_verify_token="v",
                    whatsapp_app_secret="s", data_encryption_key=Fernet.generate_key().decode(),
                    identifier_hash_secret="h", internal_api_token="i")
        assert Settings(_env_file=None, environment="production", **full).dev_chat_enabled is False
        with pytest.raises(ValueError, match="ALLOW_UNSIGNED_WEBHOOKS"):
            Settings(_env_file=None, environment="production", allow_unsigned_webhooks=True, **full)
