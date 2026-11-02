"""Print fresh secrets to paste into your .env file.

    python scripts/generate_secrets.py
"""

import secrets

from cryptography.fernet import Fernet

print(f"DATA_ENCRYPTION_KEY={Fernet.generate_key().decode()}")
print(f"IDENTIFIER_HASH_SECRET={secrets.token_urlsafe(32)}")
print(f"INTERNAL_API_TOKEN={secrets.token_urlsafe(32)}")
print(f"WHATSAPP_VERIFY_TOKEN={secrets.token_urlsafe(24)}")
print("\nKeep these safe. Changing DATA_ENCRYPTION_KEY or IDENTIFIER_HASH_SECRET later makes existing data unreadable.")
