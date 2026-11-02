"""Agent 1 — DSA Tutor: DSA lessons, dry runs, complexity, and coding practice problems."""

from __future__ import annotations

from app.agents.base import AgentContext, AgentResponse, Intent
from app.agents.tutor import TutorAgent
from app.db.models import CodingProblem
from app.services import coding
from app.whatsapp import messages as wa


class DSATutorAgent(TutorAgent):
    name = "dsa"
    tracks = ("dsa",)

    # ------------------------------------------------------------------ practice problems
    async def on_practice(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        difficulty = intent.params.get("difficulty") or coding.LEVEL_TO_DIFFICULTY.get(ctx.user.level, "easy")
        topic_id = ctx.state.get("topic_id") if ctx.state.get("track") == "dsa" else None
        problem = await coding.pick_problem(ctx.session, ctx.user.id, difficulty, ctx.rng, topic_id)
        if problem is None:
            return AgentResponse([wa.text("No practice problems are loaded yet. Please try again later.")])
        ctx.set_state(mode="practice", problem_id=problem.id, hints_used=0)
        lang = "C++" if ctx.language == "cpp" else "Python"
        return AgentResponse(
            [
                wa.text(coding.problem_text(problem)),
                wa.buttons(
                    f"Write your solution in {lang} and paste it here. Think about the brute force first, then optimise. 💪",
                    [("prac:hint", "💡 Hint"), ("prac:solution", "📖 Solution"), (f"prac:new:{difficulty}", "⏭️ Another one")],
                ),
            ],
            record_activity=True,
        )

    async def _current_problem(self, ctx: AgentContext) -> CodingProblem | None:
        pid = ctx.state.get("problem_id")
        return await ctx.session.get(CodingProblem, pid) if pid else None

    async def on_practice_hint(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        problem = await self._current_problem(ctx)
        if problem is None:
            return await self.on_practice(ctx, intent)
        used = int(ctx.state.get("hints_used") or 0)
        if used >= len(problem.hints):
            return AgentResponse([wa.buttons("That was the last hint! Try coding it, or see the full solution.",
                                             [("prac:solution", "📖 Solution")])])
        ctx.set_state(hints_used=used + 1, mode="practice")
        more = used + 1 < len(problem.hints)
        btns = [("prac:hint", "💡 Next hint")] if more else []
        btns.append(("prac:solution", "📖 Solution"))
        return AgentResponse([wa.buttons(f"💡 *Hint {used + 1}/{len(problem.hints)}:* {problem.hints[used]}", btns)],
                             record_activity=True)

    async def on_practice_solution(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        problem = await self._current_problem(ctx)
        if problem is None:
            return await self.on_practice(ctx, intent)
        ctx.set_state(mode="practice_selfcheck")
        return AgentResponse(
            [
                *ctx.long_text(coding.solution_text(problem, ctx.language), markdown=False),
                wa.buttons("Be honest 🙂 — had you solved it before looking?",
                           [("prac:solved", "✅ I solved it"), ("prac:unsolved", "❌ Not yet")]),
            ],
            record_activity=True,
        )

    async def _self_report(self, ctx: AgentContext, solved: bool) -> AgentResponse:
        problem = await self._current_problem(ctx)
        if problem is None:
            return AgentResponse([wa.text("Got it! Type *practice* for a new problem.")])
        await coding.record_submission(
            ctx, problem, "(self-reported, no code submitted)", "self_solved" if solved else "self_unsolved",
            "practice", hints_used=int(ctx.state.get("hints_used") or 0),
        )
        ctx.set_state(mode=None, problem_id=None, hints_used=None)
        msg = ("🎉 Great work! Recorded as solved (self-reported)." if solved else
               "👍 No worries — recorded. Re-type the solution from memory tomorrow; that's how patterns stick.")
        return AgentResponse([wa.buttons(msg, [("prac:new", "⏭️ Next problem"), ("cmd:coding", "📊 My coding stats"),
                                               ("cmd:next", "➡️ What next?")])], record_activity=True)

    async def on_practice_solved(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return await self._self_report(ctx, True)

    async def on_practice_unsolved(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        return await self._self_report(ctx, False)

    async def on_practice_submit(self, ctx: AgentContext, intent: Intent) -> AgentResponse:
        # Hand the code to the Coding Agent, which owns code review.
        return AgentResponse(handoff=Intent("code_review", "coding",
                                            {"code": intent.params.get("code", intent.text),
                                             "problem_id": ctx.state.get("problem_id")}, intent.text))
