import pytest

from app.agents.intents import classify, looks_like_code


def c(text, state=None, button=None):
    return classify(text, button, state or {})


@pytest.mark.parametrize(
    "text, name, params",
    [
        # Example requests from the project brief
        ("Start DSA Quiz", "quiz_start", {"category": "dsa"}),
        ("Give me 10 Python questions", "quiz_start", {"category": "python", "count": 10}),
        ("Test my Machine Learning knowledge", "quiz_start", {"category": "ml"}),
        ("Give me a medium-level arrays quiz", "quiz_start", {"category": "arrays_strings", "difficulty": "medium"}),
        ("Start a mock coding interview", "interview_start", {}),
        ("My DSA Progress", "progress", {"track": "dsa"}),
        ("My ML Progress", "progress", {"track": "ml"}),
        ("My Weak Topics", "weakness", {}),
        ("My Weekly Report", "weekly", {}),
        ("My Coding Performance", "coding_perf", {}),
        ("What Should I Learn Next?", "next", {}),
        # Commands
        ("/start", "start", {}),
        ("/dsa", "track_menu", {"track": "dsa"}),
        ("/numpy", "lesson", {"topic_id": "ml.numpy"}),
        ("/quiz hard dynamic programming", "quiz_start", {"category": "dynamic_programming", "difficulty": "hard"}),
        ("/progress ml", "progress", {"track": "ml"}),
        ("/streak", "streak", {}),
        ("/dailyplan", "dailyplan", {}),
        ("/revision", "revision", {}),
        # Natural language
        ("explain binary search", "lesson", {"topic_id": "dsa.binary_search"}),
        ("teach me pointers in c++", "lesson", {"topic_id": "cpp.pointers_references", "language": "cpp"}),
        ("what is overfitting?", "lesson", {"topic_id": "ml.overfitting"}),
        ("binery serch", "lesson", {"topic_id": "dsa.binary_search"}),
        ("I don't understand", "simpler", {}),
        ("I can study 2 hours a day", "set_time", {}),
        ("remind me at 7pm", "remind", {}),
        ("stop reminders", "remind", {"args": "off"}),
        ("delete my data", "delete_request", {}),
        ("hi", "greeting", {}),
        ("give me a coding problem", "practice", {}),
        ("study plan for today", "dailyplan", {}),
        ("I prefer python", "set_lang", {"args": "python"}),
        ("I am a complete beginner", "set_level", {"args": "beginner"}),
        ("more", "more", {}),
    ],
)
def test_natural_language(text, name, params):
    intent = c(text)
    assert intent.name == name, (text, intent)
    for k, v in params.items():
        assert intent.params.get(k) == v, (text, intent.params)


def test_question_routes_to_topic_agent():
    intent = c("why does quick sort become slow when the pivot is the smallest element every time")
    assert intent.name == "question"
    assert intent.params["topic_id"] == "dsa.quick_sort"
    assert intent.agent == "dsa"
    assert c("how do I choose k in k-means clustering for my dataset of customers").agent == "ml"


def test_unknown_question_uses_current_track():
    intent = c("can you help me with this assignment", {"track": "ml"})
    assert intent.name == "question" and intent.agent == "ml"


def test_quiz_mode_treats_messages_as_answers_but_allows_escape():
    state = {"mode": "quiz", "quiz_session_id": 1}
    assert c("b", state).name == "quiz_answer"
    assert c("I think it's O(n)", state).name == "quiz_answer"
    assert c("stop", state).name == "quiz_stop"
    assert c("my progress", state).name == "progress"


def test_buttons():
    assert c("", button="learn:dsa.stack").params == {"topic_id": "dsa.stack"}
    assert c("", button="qa:1:2:3").name == "quiz_answer"
    assert c("", button="quiz:mixed").params == {"category": "auto"}
    assert c("", button="quiz:python:easy").params == {"category": "python", "difficulty": "easy"}
    assert c("", button="goal:dsa ml").name == "set_goal"
    assert c("", button="del:confirm").name == "delete_confirm"
    assert c("", button="mod:ml:3").params == {"track": "ml", "module": 3}


def test_delete_confirmation_mode():
    assert c("yes", {"mode": "await_delete_confirm"}).name == "delete_confirm"
    assert c("hmm no", {"mode": "await_delete_confirm"}).name == "delete_cancel"


def test_practice_mode():
    state = {"mode": "practice", "problem_id": 1}
    assert c("hint", state).name == "practice_hint"
    assert c("show solution", state).name == "practice_solution"
    code = "def two_sum(nums, target):\n    seen = {}\n    for i, x in enumerate(nums):\n        return [i]"
    assert c(code, state).name == "practice_submit"


def test_code_detection():
    assert looks_like_code("```\nprint(1)\n```")
    assert looks_like_code("#include <iostream>\nint main() {\n    cout << 1;\n    return 0;\n}")
    assert looks_like_code("def f(x):\n    return x\nprint(f(2))")
    assert not looks_like_code("what is the time complexity of merge sort?")
    assert not looks_like_code("I studied for 2 hours today.\nIt was fun.")
    assert c("#include <bits/stdc++.h>\nint main() {\n  return 0;\n}").name == "code_review"


def test_unknown_command():
    assert c("/foobar").name == "unknown_command"
