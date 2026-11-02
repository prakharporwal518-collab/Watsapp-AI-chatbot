"""Content integrity: the curriculum, quiz bank, problems and lessons must be correct, because the bot
presents them to students as facts."""

import contextlib
import copy
import io
import shutil
import subprocess

import pytest

from app.content.coding_problems import PROBLEMS
from app.content.curriculum import CATEGORY_GROUPS, MODULES, QUIZ_CATEGORIES, TOPICS
from app.content.lessons import LESSONS
from app.content.quiz_bank import QUESTIONS
from app.content.search import find_topic


def test_curriculum_covers_all_tracks_and_is_consistent():
    tracks = {t.track for t in TOPICS.values()}
    assert tracks == {"dsa", "cpp", "python", "ml"}
    for topic in TOPICS.values():
        assert topic.quiz_category in QUIZ_CATEGORIES, topic.id
        assert all(p in TOPICS for p in topic.prerequisites), topic.id
        assert topic.summary
    for module in MODULES:
        assert module.topics
    for group in CATEGORY_GROUPS.values():
        assert all(c in QUIZ_CATEGORIES for c in group)


@pytest.mark.parametrize("required", [
    "dsa.recursion", "dsa.big_o", "dsa.binary_search", "dsa.quick_sort", "dsa.circular_queue", "dsa.hash_map",
    "dsa.avl_tree", "dsa.trie", "dsa.dsu", "dsa.segment_tree", "dsa.fenwick_tree", "dsa.kadane", "dsa.dijkstra",
    "dsa.topological_sort", "cpp.pointers_references", "cpp.stl_containers", "python.exceptions", "python.file_handling",
    "ml.gradients", "ml.seaborn", "ml.semi_supervised", "ml.xgboost", "ml.dbscan", "ml.roc_auc", "ml.grid_search",
    "ml.lstm", "ml.transformers", "ml.project_spam", "ml.project_image_classification",
])
def test_brief_topics_exist(required):
    assert required in TOPICS


def test_quiz_bank_integrity():
    keys = [q["key"] for q in QUESTIONS]
    assert len(keys) == len(set(keys))
    assert {q["category"] for q in QUESTIONS} == set(QUIZ_CATEGORIES)
    assert {"mcq", "true_false", "output", "find_error", "short"} <= {q["qtype"] for q in QUESTIONS}
    assert {"easy", "medium", "hard"} == {q["difficulty"] for q in QUESTIONS}
    for q in QUESTIONS:
        assert q["topic_id"] in TOPICS, q["key"]
        if q["qtype"] == "short":
            assert q["keywords"], q["key"]
        else:
            assert 0 <= int(q["answer"]) < len(q["options"]), q["key"]
            assert len(set(q["options"])) == len(q["options"]), q["key"]
        if q["option_explanations"]:
            assert len(q["option_explanations"]) == len(q["options"]), q["key"]


def _run_python_solution(problem):
    ns: dict = {}
    exec(problem["solution_python"], ns)  # noqa: S102 — trusted, repository-owned content
    return ns


@pytest.mark.parametrize("problem", PROBLEMS, ids=lambda p: p["slug"])
def test_python_reference_solutions_pass(problem):
    ns = _run_python_solution(problem)
    fn = ns[problem["function"]]
    if problem["tests"] == "linked_list":
        node_cls, head = ns["ListNode"], None
        for v in [5, 4, 3, 2, 1]:
            head = node_cls(v, head)
        out, cur = [], fn(head)
        while cur:
            out.append(cur.val)
            cur = cur.next
        assert out == [5, 4, 3, 2, 1]
        return
    for args, expected in problem["tests"]:
        assert fn(*copy.deepcopy(args)) == expected, (problem["slug"], args)


@pytest.mark.skipif(not shutil.which("g++"), reason="g++ not installed")
def test_cpp_reference_solutions_compile(tmp_path):
    src = "#include <bits/stdc++.h>\nusing namespace std;\nstruct ListNode{int val; ListNode* next; ListNode(int v):val(v),next(nullptr){}};\n"
    src += "\n".join(p["solution_cpp"] for p in PROBLEMS) + "\nint main(){return 0;}\n"
    (tmp_path / "all.cpp").write_text(src)
    result = subprocess.run(["g++", "-std=c++17", "-Wall", "-Werror", "-fsyntax-only", str(tmp_path / "all.cpp")],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def _lesson_output(code: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(code, {})  # noqa: S102
    return buf.getvalue().strip()


@pytest.mark.parametrize("topic_id", list(LESSONS), ids=str)
def test_lesson_python_code_prints_documented_output(topic_id):
    lesson = LESSONS[topic_id]
    code = lesson["code"]["python"]
    if "numpy" in code:
        pytest.importorskip("numpy")
    if "sklearn" in code:
        pytest.importorskip("sklearn")
    assert _lesson_output(code) == lesson["output"].strip()


@pytest.mark.skipif(not shutil.which("g++"), reason="g++ not installed")
@pytest.mark.parametrize("topic_id", [t for t, lesson in LESSONS.items() if "cpp" in lesson["code"]], ids=str)
def test_lesson_cpp_code_prints_documented_output(topic_id, tmp_path):
    lesson = LESSONS[topic_id]
    (tmp_path / "l.cpp").write_text(lesson["code"]["cpp"])
    exe = tmp_path / "l"
    build = subprocess.run(["g++", "-std=c++17", "-Wall", "-Werror", "-o", str(exe), str(tmp_path / "l.cpp")],
                           capture_output=True, text=True)
    assert build.returncode == 0, build.stderr
    out = subprocess.run([str(exe)], capture_output=True, text=True, timeout=10).stdout.strip()
    assert out == lesson["output"].strip()


def test_lessons_have_all_sections():
    for topic_id, lesson in LESSONS.items():
        assert topic_id in TOPICS
        for key in ("intro", "diagram", "code", "line_by_line", "dry_run", "output", "complexity", "mistakes", "simpler"):
            assert lesson.get(key), (topic_id, key)


@pytest.mark.parametrize("text, expected", [
    ("merge sort", "dsa.merge_sort"), ("what is a trie", "dsa.trie"), ("kmeans", "ml.kmeans"),
    ("explain recursion", "dsa.recursion"), ("pandas groupby", "ml.pandas"), ("I'm a bit confused", None),
    ("tell me something", None),
])
def test_topic_search(text, expected):
    topic = find_topic(text)
    assert (topic.id if topic else None) == expected
