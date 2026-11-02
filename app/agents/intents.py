"""Rule-based intent detection.

Fast, free and predictable: handles button taps, /commands and common natural-language phrasings.
The orchestrator only asks the LLM to classify when these rules can't decide.
"""

from __future__ import annotations

import re

from app.agents.base import Intent
from app.content.curriculum import TOPICS
from app.content.search import find_topic, normalise

TRACK_AGENT = {"dsa": "dsa", "cpp": "coding", "python": "coding", "ml": "ml"}

COMMANDS = {
    "start": ("start", "orchestrator"),
    "help": ("help", "orchestrator"),
    "menu": ("help", "orchestrator"),
    "dsa": ("track_menu", "dsa"),
    "cpp": ("track_menu", "coding"),
    "python": ("track_menu", "coding"),
    "ml": ("track_menu", "ml"),
    "numpy": ("lesson", "ml"),
    "pandas": ("lesson", "ml"),
    "quiz": ("quiz_start", "quiz"),
    "progress": ("progress", "progress"),
    "weakness": ("weakness", "progress"),
    "weak": ("weakness", "progress"),
    "report": ("weekly", "progress"),
    "weekly": ("weekly", "progress"),
    "coding": ("coding_perf", "progress"),
    "streak": ("streak", "progress"),
    "next": ("next", "progress"),
    "revision": ("revision", "quiz"),
    "revise": ("revision", "quiz"),
    "dailyplan": ("dailyplan", "planner"),
    "plan": ("dailyplan", "planner"),
    "practice": ("practice", "dsa"),
    "challenge": ("practice", "dsa"),
    "interview": ("interview_start", "quiz"),
    "settings": ("settings", "planner"),
    "remind": ("remind", "planner"),
    "time": ("set_time", "planner"),
    "goal": ("set_goal", "planner"),
    "lang": ("set_lang", "planner"),
    "level": ("set_level", "planner"),
    "timezone": ("set_timezone", "planner"),
    "privacy": ("privacy", "orchestrator"),
    "deletedata": ("delete_request", "orchestrator"),
    "stop": ("stop", "orchestrator"),
    "more": ("more", "orchestrator"),
}

CATEGORY_KEYWORDS: list[tuple[str, str]] = [
    # (phrase, category or group) — longest phrases first
    ("machine learning algorithms", "ml_algorithms"),
    ("unsupervised learning", "unsupervised"),
    ("supervised learning", "supervised"),
    ("dynamic programming", "dynamic_programming"),
    ("sorting and searching", "sorting_searching"),
    ("stack and queue", "stack_queue"),
    ("stacks and queues", "stack_queue"),
    ("trees and graphs", "trees_graphs"),
    ("numpy and pandas", "numpy_pandas"),
    ("deep learning", "deep_learning"),
    ("neural network", "deep_learning"),
    ("linked list", "linked_lists"),
    ("linked lists", "linked_lists"),
    ("machine learning", "ml"),
    ("unsupervised", "unsupervised"),
    ("supervised", "supervised"),
    ("arrays", "arrays_strings"),
    ("array", "arrays_strings"),
    ("strings", "arrays_strings"),
    ("string", "arrays_strings"),
    ("sorting", "sorting_searching"),
    ("searching", "sorting_searching"),
    ("stack", "stack_queue"),
    ("queue", "stack_queue"),
    ("trees", "trees_graphs"),
    ("tree", "trees_graphs"),
    ("graphs", "trees_graphs"),
    ("graph", "trees_graphs"),
    ("dp", "dynamic_programming"),
    ("numpy", "numpy_pandas"),
    ("pandas", "numpy_pandas"),
    ("fundamentals", "dsa_fundamentals"),
    ("python", "python"),
    ("cpp", "cpp"),
    ("dsa", "dsa"),
    ("ml", "ml"),
    ("ai", "ml"),
]

GREETINGS = {"hi", "hii", "hiii", "hello", "hey", "heyy", "namaste", "hola", "yo", "good morning",
             "good evening", "good afternoon", "hi there", "hello there", "start"}
THANKS = {"thanks", "thank you", "thanku", "ty", "thx", "ok thanks", "great thanks", "nice", "cool", "ok", "okay"}

_RE = {
    "simpler": re.compile(
        r"(i\s*(do\s*not|don'?t|dont|didn'?t|did\s*not)\s*(understand|get)|not\s*clear|confus|"
        r"explain\s*(it\s*)?(again|simpl|easi|different)|simpler|easier\s*(way|example)|samajh\s*nahi|samjha\s*nahi|"
        r"too\s*(hard|difficult|complex))"
    ),
    "more": re.compile(r"^(more|continue|next part|go on|aage)$"),
    "weak": re.compile(r"\b(weak|weakness|weaknesses|weak (topics|areas)|where am i (weak|lacking)|struggling)\b"),
    "weekly": re.compile(r"\b(weekly report|week report|this week|my report|report card)\b|^report$"),
    "coding_perf": re.compile(r"\b(coding (performance|stats|progress)|problems solved|my submissions)\b"),
    "next": re.compile(r"(what (should|do) i (learn|study|do) next|what next|next topic|recommend (a |the )?(topic|next)|what to learn)"),
    "streak": re.compile(r"\bstreak\b"),
    "progress": re.compile(r"\b(progress|how am i doing|my stats|my performance|completed topics|my scores?)\b"),
    "revision": re.compile(r"\b(revision|revise|review (my )?topics|spaced repetition)\b"),
    "plan": re.compile(r"\b(study plan|daily plan|today'?s plan|plan for today|what should i (do|study) today|schedule for today|plan my day)\b"),
    "interview": re.compile(r"\b(mock (coding )?interview|interview (practice|prep|me)|start (a |an )?interview)\b"),
    "practice": re.compile(r"\b(coding (problem|question|challenge)|practice (problem|question)|daily (coding )?challenge|give me a problem|leetcode|practice coding|dsa problem)\b"),
    "quiz": re.compile(
        r"\b(quiz|quizzes|test me|test my|mcqs?|\d+ (\w+ ){0,3}questions|"
        r"(give|ask|send) me (some |a few )?(\w+ )?questions|practice questions)\b"
    ),
    "stop_quiz": re.compile(r"^(stop|quit|exit|end|cancel|stop quiz|end quiz|quit quiz|exit quiz|stop interview|end interview)$"),
    "privacy": re.compile(r"\b(privacy|what data|my data)\b"),
    "delete": re.compile(r"\b(delete (all )?my (data|account|profile)|forget me|erase my data)\b"),
    "reminder_off": re.compile(r"\b(stop|disable|turn off|no more|unsubscribe)\b.*\b(reminders?|notifications?|messages)\b"),
    "reminder_on": re.compile(r"\b(remind me|set (a )?reminder|daily reminder|enable reminders?|turn on reminders?)\b"),
    "study_time": re.compile(r"\b(\d{1,3})\s*(minutes?|mins?|hours?|hrs?|h)\b.*\b(day|daily|per day|a day|everyday)\b|\bi can study\b|\bi have (\d{1,3})\s*(minutes?|mins?|hours?|hrs?)"),
    "lang_pref": re.compile(r"\b(prefer|use|switch( to)?|change (my )?language( to)?|teach me in|code in|i code in)\b.*\b(python|cpp)\b"),
    "goal": re.compile(r"\b(my goal is|goal|i want to (learn|focus on|prepare for)|focus on|preparing for)\b"),
    "level": re.compile(r"\bi(?:'?m| am) (an? )?(complete |absolute )?(beginner|intermediate|advanced|newbie|expert)\b"),
    "teach": re.compile(r"\b(teach( me)?|explain|what is|what are|what's|whats|learn|lesson on|tell me about|introduce|intro to|basics of|how does|how do)\b"),
    "help": re.compile(r"^(help|menu|commands|options|what can you do\??|features|how to use|guide)$"),
}

_CODE_LINE = re.compile(
    r"^\s*(def|class|for|while|if|elif|else|try|except|with)\b.*:\s*$"  # python block headers
    r"|;\s*(//.*)?$|[{}]\s*$"  # C++ statement / brace endings
    r"|^\s*#include|^\s*return\b|^\s*(import|from)\s+\w+"
    r"|^\s*(int|long|void|bool|string|vector<|auto|char|double|float|const|struct|template)\b"
    r"|^\s*[\w.\[\]]+\s*[+\-*/%]?=\s*[^=\s]"  # assignment
    r"|^\s*\w+(\.\w+)*\(.*\)\s*$"  # bare function call
)


def looks_like_code(text: str) -> bool:
    if "```" in text:
        return True
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    score = sum(1 for line in lines if _CODE_LINE.search(line))
    return score >= 2 and score / len(lines) >= 0.5


def _quiz_params(norm: str) -> dict:
    params: dict = {}
    m = re.search(r"\b(\d{1,2})\b", norm)
    if m:
        params["count"] = int(m.group(1))
    for diff in ("easy", "medium", "hard"):
        if re.search(rf"\b{diff}\b", norm):
            params["difficulty"] = diff
    padded = f" {norm} "
    for phrase, cat in CATEGORY_KEYWORDS:
        if f" {phrase} " in padded:
            params["category"] = cat
            break
    if "category" not in params:
        topic = find_topic(norm)
        if topic and topic.quiz_category:
            params["category"] = topic.quiz_category
            params["topic_id"] = topic.id
    return params


def parse_button(button_id: str, text: str) -> Intent | None:
    parts = button_id.split(":")
    kind = parts[0]
    if kind == "qa":
        return Intent("quiz_answer", "quiz", {}, text)
    if kind == "menu" and len(parts) > 1:
        return Intent("track_menu", TRACK_AGENT.get(parts[1], "dsa"), {"track": parts[1]}, text)
    if kind == "mod" and len(parts) > 2:
        return Intent("module_topics", TRACK_AGENT.get(parts[1], "dsa"), {"track": parts[1], "module": int(parts[2])}, text)
    if kind == "learn" and len(parts) > 1:
        topic_id = ":".join(parts[1:])
        track = topic_id.split(".")[0]
        return Intent("lesson", TRACK_AGENT.get(track, "dsa"), {"topic_id": topic_id}, text)
    if kind == "simpler" and len(parts) > 1:
        topic_id = ":".join(parts[1:])
        return Intent("simpler", TRACK_AGENT.get(topic_id.split(".")[0], "dsa"), {"topic_id": topic_id}, text)
    if kind == "check" and len(parts) > 1:
        return Intent("check", "quiz", {"topic_id": ":".join(parts[1:])}, text)
    if kind == "quiz":
        params: dict = {}
        if len(parts) > 1:
            params["category"] = "auto" if parts[1] in ("mixed", "auto") else parts[1]
        if len(parts) > 2:
            params["difficulty"] = parts[2]
        return Intent("quiz_start", "quiz", params, text)
    if kind == "prac":
        action = parts[1] if len(parts) > 1 else "new"
        if action in ("hint", "solution", "solved", "unsolved"):
            return Intent(f"practice_{action}", "dsa", {}, text)
        if action == "new":
            return Intent("practice", "dsa", {"difficulty": parts[2]} if len(parts) > 2 else {}, text)
    if kind == "iv":
        return Intent("interview_action", "quiz", {"action": parts[1] if len(parts) > 1 else ""}, text)
    if kind == "del":
        return Intent("delete_confirm" if parts[-1] == "confirm" else "delete_cancel", "orchestrator", {}, text)
    if kind == "remind":
        return Intent("remind", "planner", {"args": parts[1] if len(parts) > 1 else "on"}, text)
    if kind in ("goal", "lang", "level", "time") and len(parts) > 1:
        # Onboarding / settings buttons
        return Intent(f"set_{kind}", "planner", {"args": parts[1], "onboarding": True}, text)
    if kind == "cmd" and len(parts) > 1 and parts[1] in COMMANDS:
        name, agent = COMMANDS[parts[1]]
        return Intent(name, agent, {}, text)
    return None


def parse_command(text: str) -> Intent | None:
    m = re.match(r"^/(\w+)\s*(.*)$", text.strip(), re.S)
    if not m:
        return None
    cmd, args = m.group(1).lower(), m.group(2).strip()
    if cmd not in COMMANDS:
        return Intent("unknown_command", "orchestrator", {"command": cmd}, text)
    name, agent = COMMANDS[cmd]
    params: dict = {"args": args}
    if name == "track_menu":
        params["track"] = cmd
    elif cmd in ("numpy", "pandas"):
        params["topic_id"] = f"ml.{cmd}"
    elif name == "quiz_start":
        params.update(_quiz_params(normalise(args)))
    elif name in ("progress", "next") and args:
        track = _track_from(normalise(args))
        if track:
            params["track"] = track
    elif name == "practice" and args:
        d = re.search(r"\b(easy|medium|hard)\b", args.lower())
        if d:
            params["difficulty"] = d.group(1)
    return Intent(name, agent, params, text)


def _track_from(norm: str) -> str | None:
    padded = f" {norm} "
    for phrase, track in ((" machine learning ", "ml"), (" ml ", "ml"), (" dsa ", "dsa"), (" cpp ", "cpp"),
                          (" python ", "python"), (" data structures ", "dsa"), (" coding ", "dsa")):
        if phrase in padded:
            return track
    return None


def classify(text: str, button_id: str | None, state: dict) -> Intent:
    """Main entry point: turn a message (plus conversation state) into an Intent."""
    text = (text or "").strip()
    if button_id:
        intent = parse_button(button_id, text)
        if intent:
            return intent
    if text.startswith("/"):
        cmd = parse_command(text)
        if cmd:
            return cmd

    norm = normalise(text)
    lowered = text.lower().strip()
    mode = state.get("mode")

    # --- conversation modes that expect a specific reply ----------------------------
    if mode == "await_delete_confirm":
        if norm in {"yes", "y", "confirm", "delete", "yes delete"}:
            return Intent("delete_confirm", "orchestrator", {}, text)
        return Intent("delete_cancel", "orchestrator", {}, text)
    if mode in ("quiz", "interview") and _RE["stop_quiz"].match(norm):
        return Intent("quiz_stop" if mode == "quiz" else "interview_action", "quiz",
                      {} if mode == "quiz" else {"action": "stop"}, text)
    if mode == "quiz" and not _is_escape(norm):
        return Intent("quiz_answer", "quiz", {}, text)
    if mode == "interview" and not _is_escape(norm):
        return Intent("interview_step", "quiz", {}, text)
    if mode == "practice":
        if norm in {"hint", "give hint", "another hint", "next hint"}:
            return Intent("practice_hint", "dsa", {}, text)
        if norm in {"solution", "show solution", "answer", "show answer", "i give up"}:
            return Intent("practice_solution", "dsa", {}, text)
        if looks_like_code(text):
            return Intent("practice_submit", "dsa", {"code": text}, text)
    if mode == "practice_selfcheck":
        if norm in {"yes", "y", "solved", "i solved it", "yes i did", "done"}:
            return Intent("practice_solved", "dsa", {}, text)
        if norm in {"no", "n", "not yet", "nope"}:
            return Intent("practice_unsolved", "dsa", {}, text)

    if not norm:
        return Intent("unsupported", "orchestrator", {}, text)
    if norm in {"a", "b", "c", "d"}:
        # Looks like a quiz answer but no quiz is running — the quiz agent explains that.
        return Intent("quiz_answer", "quiz", {}, text)

    # --- simple conversational intents ---------------------------------------------
    if norm in GREETINGS:
        return Intent("greeting", "orchestrator", {}, text)
    if norm in THANKS:
        return Intent("thanks", "orchestrator", {}, text)
    if _RE["help"].match(norm):
        return Intent("help", "orchestrator", {}, text)
    if _RE["more"].match(norm):
        return Intent("more", "orchestrator", {}, text)
    if _RE["delete"].search(norm):
        return Intent("delete_request", "orchestrator", {}, text)
    if _RE["reminder_off"].search(lowered):
        return Intent("remind", "planner", {"args": "off"}, text)
    if norm in {"stop", "unsubscribe"}:
        return Intent("stop", "orchestrator", {}, text)

    # --- code pasted → code review ----------------------------------------------------
    if looks_like_code(text):
        return Intent("code_review", "coding", {"code": text}, text)

    # --- explicit learning-management requests ---------------------------------------
    if _RE["simpler"].search(lowered):
        return Intent("simpler", _agent_for_state(state), {"topic_id": state.get("topic_id")}, text)
    if _RE["interview"].search(norm):
        return Intent("interview_start", "quiz", {}, text)
    if _RE["reminder_on"].search(lowered):
        return Intent("remind", "planner", {"args": lowered}, text)
    if _RE["study_time"].search(lowered) and not _RE["quiz"].search(norm):
        return Intent("set_time", "planner", {"args": lowered}, text)
    if _RE["lang_pref"].search(norm):
        return Intent("set_lang", "planner", {"args": "python" if "python" in norm else "cpp"}, text)
    if _RE["level"].search(lowered):
        return Intent("set_level", "planner", {"args": _RE["level"].search(lowered).group(3)}, text)
    if _RE["weak"].search(norm):
        return Intent("weakness", "progress", {}, text)
    if _RE["weekly"].search(norm):
        return Intent("weekly", "progress", {}, text)
    if _RE["coding_perf"].search(norm):
        return Intent("coding_perf", "progress", {}, text)
    if _RE["next"].search(norm):
        return Intent("next", "progress", {"track": _track_from(norm)} if _track_from(norm) else {}, text)
    if _RE["streak"].search(norm):
        return Intent("streak", "progress", {}, text)
    if _RE["plan"].search(lowered):
        return Intent("dailyplan", "planner", {}, text)
    if _RE["revision"].search(norm) and not _RE["teach"].search(norm):
        return Intent("revision", "quiz", {}, text)
    if _RE["practice"].search(norm):
        d = re.search(r"\b(easy|medium|hard)\b", norm)
        return Intent("practice", "dsa", {"difficulty": d.group(1)} if d else {}, text)
    if _RE["quiz"].search(norm) and not _RE["teach"].search(norm):
        return Intent("quiz_start", "quiz", _quiz_params(norm), text)
    if _RE["progress"].search(norm):
        return Intent("progress", "progress", {"track": _track_from(norm)} if _track_from(norm) else {}, text)
    if _RE["privacy"].search(norm):
        return Intent("privacy", "orchestrator", {}, text)
    if _RE["goal"].search(norm) and _track_from(norm) or "interview" in norm and _RE["goal"].search(norm):
        return Intent("set_goal", "planner", {"args": norm}, text)

    # --- track menus ---------------------------------------------------------------------
    track_words = {"dsa": "dsa", "data structures": "dsa", "data structures and algorithms": "dsa", "cpp": "cpp",
                   "python": "python", "ml": "ml", "machine learning": "ml", "learn dsa": "dsa", "learn ml": "ml",
                   "learn python": "python", "learn cpp": "cpp", "learn machine learning": "ml"}
    if norm in track_words:
        track = track_words[norm]
        return Intent("track_menu", TRACK_AGENT[track], {"track": track}, text)

    # --- topics: lessons and questions ----------------------------------------------------
    hint = state.get("track")
    if "cpp" in norm.split() or "python" in norm.split():
        lang = "python" if "python" in norm.split() else "cpp"
    else:
        lang = None
    topic = find_topic(text, hint)
    if topic:
        params = {"topic_id": topic.id}
        if lang:
            params["language"] = lang
        agent = TRACK_AGENT.get(topic.track, "dsa")
        words = norm.split()
        is_lesson_request = bool(_RE["teach"].search(norm)) and len(words) <= 12 or len(words) <= 4
        return Intent("lesson" if is_lesson_request else "question", agent, params, text)

    agent = _agent_for_state(state)
    return Intent("question", agent, {"track": state.get("track")}, text)


def _is_escape(norm: str) -> bool:
    """Messages that should break out of a quiz/interview instead of being treated as an answer."""
    return bool(
        _RE["help"].match(norm)
        or any(_RE[k].search(norm) for k in ("progress", "plan", "weekly", "coding_perf", "streak", "weak", "privacy"))
        or norm in {"menu", "help", "start over", "hi", "hello"}
    )


def _agent_for_state(state: dict) -> str:
    topic_id = state.get("topic_id")
    if topic_id and topic_id in TOPICS:
        return TRACK_AGENT.get(TOPICS[topic_id].track, "dsa")
    return TRACK_AGENT.get(state.get("track") or "", "dsa")
