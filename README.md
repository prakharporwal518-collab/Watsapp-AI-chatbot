# 📚 WhatsApp AI Tutor: DSA, C++, Python & Machine Learning

A personal programming tutor that lives in WhatsApp. It teaches **Data Structures & Algorithms in C++ and
Python**, **Machine Learning from maths to transformers**, quizzes you, finds your weak topics, plans your
study day and runs mock coding interviews. It remembers your progress across conversations.

Built with **FastAPI**, the **official WhatsApp Cloud API**, **LangGraph** multi-agent orchestration,
**OpenAI**, **SQLAlchemy** (PostgreSQL/SQLite) and **Alembic**.

```
You:  explain binary search
Bot:  🧩 Binary Search — Searching and Sorting · Beginner
      Binary Search finds a target in a sorted array by repeatedly checking the middle…
      [diagram] [dry run] [C++ code] [line-by-line] [expected output] [complexity] [common mistakes]
      [✅ Check me] [🤔 Explain simpler] [➡️ Next topic]
You:  I don't understand
Bot:  Simpler version 🙂 Think of a dictionary. To find "mango" you open the middle…
You:  ✅ Check me
Bot:  📝 Understanding check: Binary Search · Q1/3 …
      🎉 You've now completed Binary Search! It's been added to your revision schedule.
```

---

## ✨ Features

| | |
|---|---|
| 📖 **Lessons** | 155 topics across 4 tracks (DSA, C++, Python, ML). Each lesson follows a fixed teaching method: explanation → analogy → diagram → code → line-by-line → dry run → output → complexity → mistakes. ML lessons follow a 10-point structure ending in a practice assignment. |
| 🤔 **"I don't understand"** | Re-explains with a new, easier analogy, and suggests prerequisite topics. |
| 📝 **Quizzes** | 117 hand-checked questions in 14 categories (MCQ, true/false, predict-the-output, find-the-error, short answer, easy/medium/hard). With an OpenAI key, extra questions are generated and validated. Every answer gets an explanation and reasons why the other options are wrong. |
| 🧑‍💻 **Coding practice** | 14 interview problems (Two Sum → Trapping Rain Water) with hints, C++/Python solutions and AI code review. |
| 🎤 **Mock interviews** | Staged interview (approach → code → complexity) with a scorecard. |
| 📊 **Progress tracking** | Per-topic mastery, weak and strong topics, streaks, weekly reports, coding stats and estimated study time. |
| 🔁 **Spaced repetition** | Completed and weak topics come back for revision on an SM-2 schedule. |
| 📅 **Study planner** | Daily plan sized to your available time and goals, with optional reminders (opt-in only). |
| 🔒 **Privacy** | Phone numbers hashed and encrypted, chat history encrypted and auto-deleted, `/deletedata` wipes everything. |

### Honesty rules (built in, and covered by tests)
- Opening a lesson **never** marks a topic complete. A topic is completed only after ≥3 answered questions with ≥70% recent accuracy.
- Every score and report comes from the database. With no data, reports say so instead of showing numbers.
- The bot **never runs your code**. Verdicts are labelled as *AI review* or *self-reported*.
- Study time is shown as an **estimate** from activity timestamps.

---

## 🚀 Quick start (local, no WhatsApp needed, about 2 minutes)

```bash
git clone https://github.com/prakharporwal518-collab/Watsapp-AI-chatbot.git
cd Watsapp-AI-chatbot
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open **http://localhost:8000/dev** to get a WhatsApp-style chat page in your browser. Or chat in the terminal:

```bash
python scripts/chat_cli.py
```

It works **without any API keys**, using the curated lessons, quiz bank and problems. Add `OPENAI_API_KEY`
to `.env` to unlock AI lessons for every topic, free-form Q&A, generated quizzes and code review.

To connect real WhatsApp, follow **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

---

## 💬 Commands

Natural language works everywhere, so commands are optional.

| Command | What it does | Or just say… |
|---|---|---|
| `/start` | Start / onboarding | "hi" |
| `/help` | Menu of features | "what can you do" |
| `/dsa` `/cpp` `/python` `/ml` | Open a learning track | "learn machine learning" |
| `/numpy` `/pandas` | NumPy / Pandas lessons | "explain pandas groupby" |
| `/quiz` | Start a quiz | "Give me a medium-level arrays quiz", "10 Python questions" |
| `/practice` | Coding problem | "give me a hard coding problem" |
| `/interview` | Mock coding interview | "Start a mock coding interview" |
| `/progress` | Overall or per-track progress | "My DSA progress" |
| `/weakness` | Weak topics | "My weak topics" |
| `/report` | Weekly report | "My weekly report" |
| `/coding` | Coding performance | "My coding performance" |
| `/revision` | Spaced-repetition revision quiz | "revise" |
| `/dailyplan` | Today's study plan | "what should I do today?" |
| `/streak` | Learning streak | "my streak" |
| `/next` | Recommended next topic | "What should I learn next?" |
| `/settings` `/time` `/goal` `/lang` `/level` `/timezone` | Preferences | "I can study 2 hours a day", "I prefer Python" |
| `/remind 7pm` · `/remind off` | Daily reminders (opt-in) | "remind me at 7pm", "stop reminders" |
| `/privacy` · `/deletedata` | Privacy info / delete everything | "delete my data" |
| `more` | Continue a long lesson | |

---

## 🏗️ Architecture

```mermaid
flowchart LR
    WA[WhatsApp user] <--> Meta[Meta WhatsApp Cloud API]
    Meta -- webhook POST (signed) --> API[FastAPI /webhook]
    API --> SEC{Signature check<br/>dedup · rate limit}
    SEC --> PIPE[Message pipeline]
    PIPE --> ORCH[LangGraph Orchestrator]
    ORCH --> DSA[DSA Tutor]
    ORCH --> CODE[C++/Python Coding Agent]
    ORCH --> ML[ML Tutor]
    ORCH --> QUIZ[Quiz & Assessment]
    ORCH --> PROG[Progress Tracker]
    ORCH --> PLAN[Study Planner]
    DSA & CODE & ML & QUIZ & PROG & PLAN <--> DB[(PostgreSQL)]
    DSA & CODE & ML & QUIZ -.-> LLM[OpenAI]
    PIPE -- replies --> Meta
    N8N[n8n / cron] -- /internal/jobs --> API
```

- **7 agents**: the orchestrator classifies each message (fast rules first, LLM only for ambiguous
  questions) and routes it to a specialist. Agents can hand off to each other; for example, code pasted
  during practice goes from the DSA tutor to the coding agent.
- **Shared state**: all agents read and write the same per-student database rows.
- **Offline-first**: every feature has a non-AI path, so the bot degrades gracefully if OpenAI is down
  or a student hits their daily AI budget.

Full details: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

### Project structure

```
app/
├── main.py              FastAPI app & lifespan        ├── agents/          the 7 agents + intent router
├── config.py            settings from env vars        │   ├── orchestrator.py   LangGraph graph (Agent 7)
├── container.py         dependency wiring             │   ├── dsa_tutor.py      Agent 1
├── scheduler.py         optional in-process jobs      │   ├── coding_agent.py   Agent 2
├── api/                 webhook, health, jobs, dev    │   ├── ml_tutor.py       Agent 3
├── core/                security, logging, kv store   │   ├── quiz_agent.py     Agent 4
├── db/                  models & sessions             │   ├── progress_agent.py Agent 5
├── content/             curriculum, quiz bank,        │   ├── planner_agent.py  Agent 6
│                        problems, curated lessons     │   └── intents.py        NL understanding
├── llm/                 OpenAI client & prompts       └── services/        progress, quiz, revision,
└── whatsapp/            parser, formatter, client                         planner, reports, privacy…
alembic/                 database migrations
tests/                   unit + integration tests (240)
automation/n8n/          importable n8n workflow for reminders
docs/                    architecture & deployment guides
```

---

## 🧪 Testing

```bash
pytest -q                     # 240 tests, ~15 s, SQLite in-memory, no network
ruff check .
TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost/tutor_test pytest -q   # same suite on PostgreSQL
```

The tests cover the webhook security (signatures, duplicates, oversized payloads), every learning flow
end to end, the AI paths (with a scripted fake LLM), privacy deletion, reminders and WhatsApp's 24-hour
rule. They also check content correctness: every Python reference solution runs against test cases, all
C++ solutions compile with `-Wall -Werror`, and every lesson's code prints exactly the output the lesson
claims.

---

## 🔐 Security & privacy

- **Webhook signatures**: `X-Hub-Signature-256` (HMAC-SHA256 with your app secret) is verified on every request.
- **Duplicate protection**: WhatsApp message IDs are remembered for 48 h (Redis or in-memory), so Meta's retries are processed once.
- **Rate limiting**: 20 messages/minute per student by default, plus a daily AI-call budget per student to cap cost.
- **PII**: phone numbers are stored as an HMAC hash (for lookup) and Fernet-encrypted (for replying). Names, chat history and submitted code are encrypted at rest. Logs only ever show a short hash prefix.
- **Isolation**: every learner-owned row is keyed by user ID; tests verify one student never sees another's data.
- **Retention**: chat history is pruned after `HISTORY_RETENTION_DAYS` (default 30).
- **Control**: `/deletedata` hard-deletes everything; `/remind off` / "stop" revokes reminder consent.
- **No secrets in code**: everything comes from environment variables (`.env.example`). Production refuses to start without the required secrets.
- **Messaging policy**: proactive messages are only sent to opted-in students; outside the 24-hour window only an approved template is used, otherwise the message is skipped.

---

## 🗺️ Roadmap / ideas for contributors

- Run student code safely in a sandbox (e.g. Judge0) for real test-case verdicts
- Voice notes → speech-to-text questions
- Images of handwritten code → OCR review
- Hindi / Hinglish explanations
- Leaderboards and study groups
- RAG over a curated notes corpus for even more grounded answers

Contributions are welcome: open an issue or PR. Please run `pytest` and `ruff check .` first.

## 📄 License

MIT. See [LICENSE](LICENSE).
