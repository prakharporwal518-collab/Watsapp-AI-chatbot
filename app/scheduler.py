"""Optional in-process scheduler (ENABLE_SCHEDULER=true).

Use it for a single-instance deployment. With several instances, disable it and trigger
/internal/jobs/* from one place instead (n8n, cron, Render cron job) so reminders aren't duplicated.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.services import conversation, notifications

logger = logging.getLogger(__name__)


def start_scheduler(container) -> AsyncIOScheduler:
    c = container
    scheduler = AsyncIOScheduler(timezone="UTC")

    async def reminders():
        await notifications.send_daily_reminders(c.sessionmaker, c.sender, c.settings, c.clock())

    async def weekly():
        await notifications.send_weekly_reports(c.sessionmaker, c.sender, c.settings, c.clock())

    async def prune():
        async with c.sessionmaker() as session:
            await conversation.prune(session, c.settings.history_retention_days,
                                     c.settings.history_max_messages_per_user, c.clock())
            await session.commit()

    scheduler.add_job(reminders, "interval", minutes=10, id="daily-reminders", max_instances=1, coalesce=True)
    scheduler.add_job(weekly, "interval", minutes=30, id="weekly-reports", max_instances=1, coalesce=True)
    scheduler.add_job(prune, "interval", hours=6, id="prune-history", max_instances=1, coalesce=True)
    scheduler.start()
    logger.info("In-process scheduler started")
    return scheduler
