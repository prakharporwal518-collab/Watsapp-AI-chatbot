"""Agent 2 — C++ & Python Coding Agent: language lessons plus writing, debugging and reviewing code."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, Intent
from app.agents.tutor import TutorAgent
from app.content.curriculum import Topic
from app.db.models import CodingProblem
from app.llm import prompts
from app.services import coding
from app.whatsapp import messages as wa


class CodingAgent(TutorAgent):
    name = "coding"
    tracks = ("cpp", "python")

    def lesson_prompt(self, topic: Topic, language: str) -> str:
        if topic.track in ("cpp", "python"):
            return prompts.language_lesson_prompt(topic.title, topic.summary, topic.track)
        return prompts.dsa_lesson_prompt(topic.title, topic.summary, language)

    async def on_code_review(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        code = intent.params.get("code") or intent.text
        pid = intent.params.get("problem_id")
        problem = await ctx.session.get(CodingProblem, pid) if pid else None
        review = await coding.review_code(ctx, code, problem, request=intent.text if not problem else "")

        if review.verdict == "unavailable":
            if problem:
                ctx.set_state(mode="practice")
                return AgentResponse(
                    [
                        wa.text("🤖 Automatic code review isn't available right now, and I never pretend to run code. "
                                "Compare your code with the reference solution and the examples:"),
                        *ctx.long_text(coding.solution_text(problem, review.language if review.language != "other" else ctx.language),
                                       markdown=False),
                        wa.buttons("Does your code produce the expected output for the examples?",
                                   [("prac:solved", "✅ Yes, it works"), ("prac:unsolved", "❌ It has bugs")]),
                    ],
                    record_activity=True,
                )
            return AgentResponse([wa.text(
                "🤖 Code review needs the AI tutor, which isn't available right now.\n\n"
                "Self-check tips while you wait:\n• Dry-run with a tiny input on paper\n• Test empty input and one element\n"
                "• Check loop bounds (`<` vs `<=`)\n• In C++, watch for int overflow (use long long)"
            )])

        if review.verdict == "not_code":
            return AgentResponse(ctx.long_text(review.feedback or "That doesn't look like code. Paste your code and I'll review it."))

        await coding.record_submission(ctx, problem, code, review.verdict, "practice" if problem else "review",
                                       review.language, review.feedback, int(ctx.state.get("hints_used") or 0))
        resp = AgentResponse(record_activity=True)
        if problem:
            verdict = ("✅ *Looks correct* (AI review — not executed)" if review.verdict == "ai_correct"
                       else "🛠️ *Needs some work* (AI review — not executed)")
            resp.add(wa.text(f"{verdict} for *{problem.title}*"))
        resp.add(*ctx.long_text(review.feedback))
        if problem and review.verdict == "ai_correct":
            ctx.set_state(mode=None, problem_id=None, hints_used=None)
            resp.add(wa.buttons("Nice! What next?", [("prac:new", "⏭️ Next problem"), ("cmd:coding", "📊 Coding stats")]))
        elif problem:
            ctx.set_state(mode="practice")
            resp.add(wa.buttons("Fix it and paste your new version, or:", [("prac:hint", "💡 Hint"), ("prac:solution", "📖 Solution")]))
        return resp
