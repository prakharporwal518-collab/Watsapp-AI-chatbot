"""Agent 3 — Machine Learning Tutor: maths, libraries (NumPy/Pandas/scikit-learn), algorithms and projects."""

from __future__ import annotations

from app.agents.tutor import TutorAgent
from app.content.curriculum import Topic
from app.llm import prompts


class MLTutorAgent(TutorAgent):
    name = "ml"
    tracks = ("ml",)

    def lesson_prompt(self, topic: Topic, language: str) -> str:
        # ML lessons follow the 10-point structure (definition → … → practice assignment), always in Python.
        return prompts.ml_lesson_prompt(topic.title, topic.summary)
