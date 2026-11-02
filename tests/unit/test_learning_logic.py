from datetime import date

import pytest

from app.agents.planner_agent import parse_minutes, parse_time
from app.db.models import LearningStreak, QuizQuestion
from app.services import coding, quiz
from app.services.progress import effective_streak, update_streak
from app.services.revision import sm2_update


class TestStreak:
    def test_consecutive_days_extend_streak(self):
        s = LearningStreak(current_streak=0, longest_streak=0, active_dates=[])
        assert update_streak(s, date(2026, 11, 1))
        assert not update_streak(s, date(2026, 11, 1))  # same day counts once
        update_streak(s, date(2026, 11, 2))
        update_streak(s, date(2026, 11, 3))
        assert (s.current_streak, s.longest_streak) == (3, 3)
        assert s.active_dates == ["2026-11-01", "2026-11-02", "2026-11-03"]

    def test_gap_resets_but_keeps_longest(self):
        s = LearningStreak(current_streak=5, longest_streak=5, last_active_date=date(2026, 11, 1), active_dates=[])
        update_streak(s, date(2026, 11, 4))
        assert (s.current_streak, s.longest_streak) == (1, 5)

    def test_effective_streak(self):
        s = LearningStreak(current_streak=4, longest_streak=4, last_active_date=date(2026, 11, 1))
        assert effective_streak(s, date(2026, 11, 1)) == 4
        assert effective_streak(s, date(2026, 11, 2)) == 4  # still alive until today ends
        assert effective_streak(s, date(2026, 11, 3)) == 0
        assert effective_streak(None, date(2026, 11, 3)) == 0


class TestSpacedRepetition:
    def test_intervals_grow_with_good_reviews(self):
        interval, reps, ease = 1, 0, 2.5
        seen = []
        for _ in range(4):
            interval, reps, ease = sm2_update(interval, reps, ease, 1.0)
            seen.append(interval)
        assert seen[0] == 1 and seen[1] == 3
        assert seen[2] > seen[1] and seen[3] > seen[2]
        assert ease > 2.5

    def test_failure_resets(self):
        interval, reps, ease = sm2_update(16, 4, 2.5, 0.2)
        assert (interval, reps) == (1, 0)
        assert ease < 2.5

    def test_ease_has_floor(self):
        ease = 2.5
        for _ in range(20):
            _, _, ease = sm2_update(1, 0, ease, 0.0)
        assert ease == 1.3


def _q(**kw):
    base = dict(id=1, qtype="mcq", options=["a1", "b1", "c1", "d1"], answer="2", prompt="?", difficulty="easy",
                code=None, explanation="because", option_explanations=[], accepted_keywords=[], category="python")
    base.update(kw)
    return QuizQuestion(**base)


class TestQuizEngine:
    @pytest.mark.parametrize("reply, expected", [
        ("c", 2), ("C", 2), ("C)", 2), ("(c)", 2), ("option c", 2), ("answer: c", 2), ("3", 2), ("c1", 2), ("e", None),
        ("5", None), ("maybe", None),
    ])
    def test_parse_choice(self, reply, expected):
        assert quiz.parse_choice(_q(), reply, None) == expected

    def test_parse_true_false(self):
        q = _q(qtype="true_false", options=["True", "False"], answer="1")
        assert quiz.parse_choice(q, "false", None) == 1
        assert quiz.parse_choice(q, "T", None) == 0
        assert quiz.parse_choice(q, "c", None) is None

    def test_button_answer(self):
        assert quiz.parse_choice(_q(), "Option B", "qa:5:1:1") == 1

    def test_grade_choice(self):
        assert quiz.grade_choice(_q(), 2).correct
        assert not quiz.grade_choice(_q(), 0).correct

    def test_keyword_grading(self):
        q = _q(qtype="short", answer="model", accepted_keywords=["top-down|recursion", "bottom-up|table"])
        assert quiz.grade_by_keywords(q, "Memoization is top-down recursion, tabulation is bottom-up").correct
        assert not quiz.grade_by_keywords(q, "they are the same thing").correct

    def test_render_mcq_uses_list_and_true_false_uses_buttons(self):
        mcq = quiz.render_question(_q(), 7, 0, 5)
        assert len(mcq) == 1 and mcq[0].kind == "list" and len(mcq[0].rows) == 4
        assert mcq[0].rows[2].id == "qa:7:1:2"
        tf = quiz.render_question(_q(qtype="true_false", options=["True", "False"], answer="0"), 7, 1, 5)
        assert tf[0].kind == "buttons" and [b.title for b in tf[0].buttons] == ["True", "False"]

    def test_long_question_split_into_text_plus_picker(self):
        msgs = quiz.render_question(_q(code="x = 1\n" * 300), 1, 0, 1)
        assert [m.kind for m in msgs] == ["text", "list"]

    def test_validate_generated(self):
        ok = quiz._validate_generated({"prompt": "Q?", "options": ["a", "b", "c", "d"], "answer_index": 3})
        assert ok and ok["answer_index"] == 3
        assert quiz._validate_generated({"prompt": "Q?", "options": ["a", "a", "c", "d"], "answer_index": 0}) is None
        assert quiz._validate_generated({"prompt": "Q?", "options": ["a", "b"], "answer_index": 5}) is None
        assert quiz._validate_generated({"options": ["a", "b"]}) is None
        tf = quiz._validate_generated({"qtype": "true_false", "prompt": "Q", "options": ["yes", "no"], "answer_index": 0})
        assert tf["options"] == ["True", "False"]

    def test_feedback_explains_wrong_choice(self):
        q = _q(option_explanations=["A is wrong because…", "B is wrong", "C is right", "D is wrong"])
        text = quiz.feedback_text(q, quiz.grade_choice(q, 0), 0)
        assert "Not quite" in text and "C) c1" in text and "A is wrong because" in text


class TestCodingHelpers:
    @pytest.mark.parametrize("answer, expected, ok", [
        ("O(n)", "O(n)", True), ("o(N)", "O(n)", True), ("O(n log n)", "O(n log n)", True),
        ("O(nlogn)", "O(n log n)", True), ("O(n^2)", "O(n²)", True), ("O(log n)", "O(n)", False),
        ("O(m*n)", "O(rows × cols)", True), ("O(V+E)", "O(V + E)", True), ("", "O(1)", False),
    ])
    def test_complexity_matches(self, answer, expected, ok):
        assert coding.complexity_matches(answer, expected) is ok

    def test_detect_language(self):
        assert coding.detect_language("#include <vector>\nint main(){}") == "cpp"
        assert coding.detect_language("def f():\n    return 1") == "python"

    def test_strip_fences(self):
        assert coding.strip_fences("```python\nprint(1)\n```") == "print(1)"


class TestPlannerParsing:
    @pytest.mark.parametrize("text, minutes", [("2 hours", 120), ("1.5 hrs", 90), ("45 minutes", 45), ("/time 90", 90), ("none", None)])
    def test_parse_minutes(self, text, minutes):
        assert parse_minutes(text) == minutes

    @pytest.mark.parametrize("text, hhmm", [("7pm", "19:00"), ("7:30 am", "07:30"), ("21:15", "21:15"),
                                            ("12 am", "00:00"), ("12pm", "12:00"), ("25:00", None), ("13pm", None)])
    def test_parse_time(self, text, hhmm):
        assert parse_time(text) == hhmm
