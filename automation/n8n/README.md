# n8n automation

The tutor never messages a student on its own schedule unless something triggers it. You can use
**either** the built-in scheduler (`ENABLE_SCHEDULER=true`, good for one instance) **or** n8n
(recommended when you deploy on a free tier that sleeps, or run several instances).

`tutor-scheduled-jobs.json` calls the app's protected job endpoints:

| Schedule | Endpoint | What it does |
|---|---|---|
| every 15 min | `POST /internal/jobs/daily-reminders` | Sends today's study plan to students who **opted in**, at their chosen local time |
| every 15 min | `POST /internal/jobs/weekly-reports` | On Sundays, sends the weekly report to students who opted in |
| every 6 h | `POST /internal/jobs/prune-history` | Deletes chat history older than `HISTORY_RETENTION_DAYS` |

The jobs are safe to call repeatedly: each student gets at most one reminder per day and one report per week.

## Setup

1. In n8n: **Workflows → Import from file** → choose `tutor-scheduled-jobs.json`.
2. Create a credential of type **Header Auth** named `Tutor internal API token`:
   - Name: `Authorization`
   - Value: `Bearer <your INTERNAL_API_TOKEN>`
3. In the three HTTP Request nodes, replace `https://YOUR-APP-URL` with your deployed URL
   (e.g. `https://whatsapp-ai-tutor.onrender.com`).
4. Run the workflow once manually — each node should return JSON like `{"sent": 0, "checked": 1, ...}`.
5. Publish/activate the workflow.

> On free hosting tiers that sleep when idle, the regular ping may also wake the server before
> reminder time. Check your host's current free-tier rules.
