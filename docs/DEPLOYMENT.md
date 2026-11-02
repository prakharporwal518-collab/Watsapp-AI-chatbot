# Deployment & WhatsApp setup

Meta's dashboard changes often. If a menu name below doesn't match exactly, look for the closest
equivalent, or check Meta's official *WhatsApp Cloud API → Get Started* guide.

## 1. Generate your secrets

```bash
python scripts/generate_secrets.py
```

Copy the output into `.env` locally, or into your host's environment variables. **Back up
`DATA_ENCRYPTION_KEY` and `IDENTIFIER_HASH_SECRET`**: if they change, stored phone numbers and history
can no longer be read.

## 2. Create the WhatsApp app (Meta for Developers)

1. Go to <https://developers.facebook.com/> → **My Apps → Create App** → choose the *Business* type.
2. Add the **WhatsApp** product to the app.
3. Under **WhatsApp → API Setup** you get:
   - a test **Phone number ID** → `WHATSAPP_PHONE_NUMBER_ID`
   - a temporary **access token** (expires after about 24 h) → `WHATSAPP_ACCESS_TOKEN`
   - a field to add up to 5 **recipient numbers** for testing. Add your own number and verify it.
4. **App settings → Basic → App secret** → `WHATSAPP_APP_SECRET` (used to verify webhook signatures).
5. For a token that doesn't expire: **Business Settings → Users → System users** → add a system user →
   *Generate token* with the `whatsapp_business_messaging` and `whatsapp_business_management` permissions.

## 3. Run locally with a public URL (for testing)

Meta must reach your webhook over HTTPS. With [ngrok](https://ngrok.com/):

```bash
uvicorn app.main:app --port 8000
ngrok http 8000            # gives https://xxxx.ngrok-free.app
```

Then in **WhatsApp → Configuration → Webhook**:
- **Callback URL**: `https://xxxx.ngrok-free.app/webhook`
- **Verify token**: the value of `WHATSAPP_VERIFY_TOKEN`
- Click **Verify and save**, then **subscribe to the `messages` field**.

Send "hi" from your registered number to the test number, and the bot should reply. 🎉

## 4. Deploy

### Option A: Render (Blueprint, easiest)
1. Push this repo to GitHub.
2. On Render: **New → Blueprint** → select the repo. `render.yaml` creates the web service and a PostgreSQL database.
3. Fill the secret env vars it asks for (WhatsApp, OpenAI, the three generated secrets).
4. After deploy, set the WhatsApp webhook URL to `https://<your-service>.onrender.com/webhook`.
5. Check `https://<your-service>.onrender.com/health` → `{"status": "ok", "database": true, ...}`.

> Free tiers sleep when idle and can have database time limits. Check Render's current free-tier rules.
> A sleeping service makes the first reply slow (Meta retries webhooks, and duplicates are ignored).

### Option B: Railway
1. **New Project → Deploy from GitHub repo**, then add a **PostgreSQL** plugin.
2. Set `DATABASE_URL` to the plugin's connection string (`postgres://` is converted automatically), plus all other env vars from `.env.example` with `ENVIRONMENT=production`.
3. Railway detects the `Procfile` (it runs migrations, then starts uvicorn).

### Option C: Docker (any VPS)
```bash
cp .env.example .env    # fill in, set ENVIRONMENT=production
docker compose up -d --build
```
This starts the API, PostgreSQL and Redis. Put Caddy/Nginx with HTTPS in front of port 8000.

### Production checklist
- `ENVIRONMENT=production`: the app refuses to start if a required secret is missing, and it disables `/docs` and the dev chat.
- `AUTO_CREATE_TABLES=false`. Migrations run with `alembic upgrade head` (already in the start commands).
- `LOG_JSON=true` for structured logs.
- Set `REDIS_URL` if you run more than one instance (shared dedup and rate limits).
- Use a permanent system-user access token.

## 5. Reminders (opt-in)

Students opt in with `/remind 7pm` (or the button after onboarding) and opt out with `/remind off` or "stop".

WhatsApp only allows free-form messages within **24 hours** of the student's last message. For reminders
outside that window, create a template:

1. **WhatsApp Manager → Message templates → Create** → category **Utility**.
2. Name: `daily_study_reminder` (any name, set it in `WHATSAPP_REMINDER_TEMPLATE`).
3. Body, with exactly two variables:
   `Hi {{1}}! {{2}} Reply to this message to start studying.`
4. Submit for approval, then set `WHATSAPP_REMINDER_TEMPLATE=daily_study_reminder`.

Without a template, reminders are only sent inside the 24 h window, and the rest are skipped
(counted as `skipped_no_template` in the job response).

**Trigger the jobs** with one of:
- **n8n** (recommended): import `automation/n8n/tutor-scheduled-jobs.json`. See [automation/n8n/README.md](../automation/n8n/README.md).
- **cron / Render cron job**: `curl -X POST -H "Authorization: Bearer $INTERNAL_API_TOKEN" https://<app>/internal/jobs/daily-reminders` every 15 min.
- **In-process**: `ENABLE_SCHEDULER=true` (single instance only, or reminders would be duplicated).

## 6. Database migrations

```bash
alembic upgrade head                              # apply
alembic revision --autogenerate -m "add field"    # after changing app/db/models.py
alembic check                                     # verify models and migrations match
```

## 7. Troubleshooting

| Symptom | Fix |
|---|---|
| Webhook "Verify and save" fails | `WHATSAPP_VERIFY_TOKEN` mismatch, or the URL isn't reachable over HTTPS (check `/health`) |
| Logs show `Rejected webhook with invalid signature` | Wrong `WHATSAPP_APP_SECRET` (it's the *app secret*, not the access token) |
| Bot receives but never replies | Expired access token, or the recipient isn't in the test-number allow-list. Check logs for `WhatsApp API error 401/400` |
| Replies only to some messages | Rate limit hit (`RATE_LIMIT_PER_MINUTE`) |
| "Detailed AI explanations are temporarily unavailable" | No or invalid `OPENAI_API_KEY`, OpenAI outage, or the student's daily AI budget was used up |
