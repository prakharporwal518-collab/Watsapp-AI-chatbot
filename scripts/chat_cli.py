"""Chat with the tutor in your terminal — no WhatsApp or server needed.

    python scripts/chat_cli.py            # uses DATABASE_URL from .env (default: ./tutor.db)

Buttons are shown as numbered options; type the number to "tap" one.
"""

from __future__ import annotations

import asyncio
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.container import build_container  # noqa: E402
from app.core.logging import configure_logging  # noqa: E402
from app.db.session import create_all  # noqa: E402
from app.services.seed import seed_content  # noqa: E402
from app.whatsapp.parser import InboundMessage  # noqa: E402

WA_ID = "990000000001"


async def main() -> None:
    settings = get_settings()
    configure_logging("WARNING")
    container = build_container(settings)
    await create_all(container.engine)
    async with container.sessionmaker() as session:
        await seed_content(session)

    print("📚 WhatsApp AI Tutor — terminal chat. Type 'quit' to exit.\n")
    options: list[tuple[str, str]] = []
    try:
        while True:
            try:
                text = input("you › ").strip()
            except EOFError:
                break
            if text.lower() in {"quit", "exit"}:
                break
            button = None
            if text.isdigit() and options and 1 <= int(text) <= len(options):
                button, text = options[int(text) - 1]
            msg = InboundMessage(f"cli.{uuid.uuid4().hex}", WA_ID, int(time.time()),
                                 "interactive" if button else "text", text, button, "CLI Student")
            replies = await container.processor.process(msg, deliver=False)
            options = []
            for r in replies:
                print(f"\nbot › {r.body}")
                for item in [*r.buttons, *r.rows]:
                    options.append((item.id, item.title))
                    print(f"   [{len(options)}] {item.title}")
            print()
    finally:
        await container.close()


if __name__ == "__main__":
    asyncio.run(main())
