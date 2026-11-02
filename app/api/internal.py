"""Job endpoints for schedulers (n8n, cron, Render cron jobs). Protected by a bearer token."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException, Request

from app.services import conversation, notifications

router = APIRouter(prefix="/internal/jobs", tags=["jobs"])


def _authorise(request: Request, authorization: str | None) -> None:
    expected = request.app.state.container.settings.internal_api_token
    if not expected:
        raise HTTPException(status_code=503, detail="INTERNAL_API_TOKEN is not configured")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("/daily-reminders")
async def daily_reminders(request: Request, authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    c = request.app.state.container
    return await notifications.send_daily_reminders(c.sessionmaker, c.sender, c.settings, c.clock())


@router.post("/weekly-reports")
async def weekly_reports(request: Request, authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    c = request.app.state.container
    return await notifications.send_weekly_reports(c.sessionmaker, c.sender, c.settings, c.clock())


@router.post("/prune-history")
async def prune_history(request: Request, authorization: str | None = Header(default=None)):
    _authorise(request, authorization)
    c = request.app.state.container
    async with c.sessionmaker() as session:
        removed = await conversation.prune(session, c.settings.history_retention_days,
                                           c.settings.history_max_messages_per_user, c.clock())
        await session.commit()
    return {"removed": removed}
