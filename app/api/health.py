from __future__ import annotations

from fastapi import APIRouter, Request
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    c = request.app.state.container
    db_ok = True
    try:
        async with c.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "database": db_ok,
        "llm": c.llm.available,
        "whatsapp": c.settings.whatsapp_enabled,
        "environment": c.settings.environment,
    }
