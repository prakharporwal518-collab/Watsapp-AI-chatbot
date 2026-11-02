"""Proactive messages: daily reminders and weekly reports — ONLY for students who opted in.

WhatsApp policy: free-form messages are allowed only within 24 hours of the student's last
message. Outside that window we must use a pre-approved template (WHATSAPP_REMINDER_TEMPLATE);
if none is configured, the reminder is skipped rather than breaking the policy.

Trigger these jobs every 10–15 minutes from n8n / cron (POST /internal/jobs/...) or with the
in-process scheduler (ENABLE_SCHEDULER=true).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import Settings
from app.db.models import User, UserPreferences
from app.services import planner, progress, reports
from app.services.users import first_name
from app.whatsapp import messages as wa
from app.whatsapp.client import MessageSender

logger = logging.getLogger(__name__)

SEND_WINDOW = timedelta(hours=3)  # don't send a reminder hours late if the job was down
SERVICE_WINDOW = timedelta(hours=24)


def _local_now(user: User, now: datetime) -> datetime:
    return now.replace(tzinfo=UTC).astimezone(progress.user_tz(user))


def is_due(user: User, now: datetime, last_sent, time_str: str) -> bool:
    local = _local_now(user, now)
    try:
        hh, mm = (int(x) for x in time_str.split(":"))
    except ValueError:
        hh, mm = 19, 0
    target = local.replace(hour=hh, minute=mm, second=0, microsecond=0)
    return last_sent != local.date() and target <= local < target + SEND_WINDOW


async def _opted_in_users(session, column) -> list[User]:
    return list((await session.scalars(
        select(User).join(UserPreferences).where(column.is_(True))
        .options(selectinload(User.preferences), selectinload(User.streak))
    )).all())


async def _deliver(sender: MessageSender, settings: Settings, user: User, now: datetime,
                   free_form: list[wa.OutgoingMessage], template_text: str) -> str:
    to = user.wa_id_encrypted
    if not to:
        return "skipped"
    inside_window = user.last_inbound_at is not None and now - user.last_inbound_at < SERVICE_WINDOW
    if inside_window:
        for m in free_form:
            if not await sender.send(to, m):
                return "failed"
        return "sent"
    if settings.whatsapp_reminder_template:
        ok = await sender.send(to, wa.template(settings.whatsapp_reminder_template, [first_name(user), template_text]))
        return "sent" if ok else "failed"
    return "skipped_no_template"


async def send_daily_reminders(sessionmaker, sender: MessageSender, settings: Settings, now: datetime) -> dict:
    counts = {"sent": 0, "skipped": 0, "skipped_no_template": 0, "failed": 0, "checked": 0}
    async with sessionmaker() as session:
        for user in await _opted_in_users(session, UserPreferences.reminders_enabled):
            counts["checked"] += 1
            prefs = user.preferences
            if not is_due(user, now, prefs.last_reminder_date, prefs.reminder_time):
                continue
            items = await planner.build_plan(session, user, now)
            await planner.save_plan(session, user, items, now)
            streak = progress.effective_streak(user.streak, progress.local_date(user, now))
            summary = "; ".join(f"{i.title} ({i.minutes} min)" for i in items[:3]) or "a quick quiz"
            body = (f"⏰ Hi {first_name(user)}! Time to study.\n\n"
                    + planner.render_plan(items, "today", prefs.daily_minutes)
                    + (f"\n\n🔥 Don't break your {streak}-day streak!" if streak else ""))
            rows = [(i.action, f"{planner.ICONS.get(i.kind, '')} {i.title}", f"{i.minutes} min") for i in items]
            msgs = [wa.list_menu(body, rows, button="Start an item")] if rows else [wa.text(body)]
            result = await _deliver(sender, settings, user, now, msgs, f"Today's plan: {summary}")
            counts[result if result in counts else "failed"] += 1
            if result == "sent":
                prefs.last_reminder_date = progress.local_date(user, now)
        await session.commit()
    logger.info("Daily reminders: %s", counts)
    return counts


async def send_weekly_reports(sessionmaker, sender: MessageSender, settings: Settings, now: datetime) -> dict:
    counts = {"sent": 0, "skipped": 0, "skipped_no_template": 0, "failed": 0, "checked": 0}
    async with sessionmaker() as session:
        for user in await _opted_in_users(session, UserPreferences.weekly_report_enabled):
            counts["checked"] += 1
            prefs = user.preferences
            if _local_now(user, now).weekday() != 6:  # Sundays
                continue
            if not is_due(user, now, prefs.last_weekly_report_date, prefs.reminder_time):
                continue
            text = await reports.weekly_report(session, user, now)
            result = await _deliver(sender, settings, user, now, [wa.text(text)],
                                    "Your weekly learning report is ready — reply REPORT to see it")
            counts[result if result in counts else "failed"] += 1
            if result == "sent":
                prefs.last_weekly_report_date = progress.local_date(user, now)
        await session.commit()
    logger.info("Weekly reports: %s", counts)
    return counts
