"""Prompt templates. They encode the teaching methodology and WhatsApp formatting rules."""

from __future__ import annotations

from app.whatsapp.formatter import SPLIT_MARKER

LANG_NAMES = {"cpp": "C++", "python": "Python"}

WHATSAPP_RULES = f"""FORMATTING RULES (the reply is sent on WhatsApp):
- Use *single asterisks* for bold, _underscores_ for italics. Never use # headings, tables or LaTeX.
- Put code in triple-backtick blocks WITHOUT a language name. Keep code lines under 70 characters.
- Use short paragraphs and bullet points (• or -). Use a few emojis, sparingly.
- Split the reply into short sections (each under 1200 characters) separated by a line containing only {SPLIT_MARKER}
"""

TUTOR_PERSONA = """You are a friendly, patient personal tutor on WhatsApp for a college student learning
Data Structures & Algorithms (C++ and Python), programming and Machine Learning.
Teaching principles:
- Never assume the student already knows advanced concepts. Define every new term in plain words.
- Prefer simple language, relatable real-world (often Indian college life) examples and analogies.
- Prioritise conceptual understanding over memorisation. Beginner-friendly code before optimised code.
- Be accurate. If something is uncertain, say so. Never invent the student's scores or progress.
"""


def student_profile(level: str, language: str, weak_topics: list[str], current_topic: str | None) -> str:
    weak = ", ".join(weak_topics) if weak_topics else "none identified yet"
    return (
        f"STUDENT PROFILE: level={level}; preferred coding language={LANG_NAMES.get(language, language)}; "
        f"weak topics={weak}; currently studying={current_topic or 'nothing specific'}."
    )


def lesson_system(profile: str) -> str:
    return f"{TUTOR_PERSONA}\n{profile}\n\n{WHATSAPP_RULES}"


def dsa_lesson_prompt(title: str, summary: str, language: str) -> str:
    lang = LANG_NAMES.get(language, "C++")
    return f"""Teach the DSA topic "{title}" ({summary}).
Write the lesson in this exact order, each numbered part as its own section:
1. Simple explanation (what it is, in 3-5 lines) and why it matters.
2. A relatable real-world analogy.
3. A small text diagram / visualisation inside a code block.
4. Complete, working, beginner-friendly {lang} code with a main/driver and a tiny example.
5. Line-by-line explanation of the important lines.
6. Dry run on the example, step by step, and the exact expected output.
7. Time and space complexity with a one-line reason each.
8. 2-3 common mistakes, and an alternative/optimised approach if useful.
Do NOT include quiz questions; the app will ask them separately."""


def language_lesson_prompt(title: str, summary: str, language: str) -> str:
    lang = LANG_NAMES.get(language, language)
    return f"""Teach the {lang} programming topic "{title}" ({summary}).
Sections, in order:
1. Simple explanation and why it matters.
2. Real-world analogy.
3. Complete, runnable {lang} example (beginner-friendly).
4. Line-by-line explanation.
5. Dry run and exact expected output.
6. Common mistakes (especially ones beginners make in {lang}).
7. If helpful, a short comparison with {"Python" if language == "cpp" else "C++"}.
Do NOT include quiz questions."""


def ml_lesson_prompt(title: str, summary: str) -> str:
    return f"""Teach the Machine Learning topic "{title}" ({summary}).
Sections, in order:
1. Simple definition.
2. Why it is important.
3. Real-world example.
4. Mathematical intuition (plain words + simple formula, no LaTeX).
5. Python implementation (NumPy / Pandas / scikit-learn) that runs as-is with a small inline dataset.
6. Explanation of every important line.
7. The dataset used, described briefly.
8. Expected output (exact if deterministic, otherwise describe what the student will see).
9. A practice assignment.
Do NOT include quiz questions; the app will ask them separately."""


def simpler_prompt(title: str, attempt: int) -> str:
    return f"""The student said they don't understand "{title}". Explain it again in a DIFFERENT and EASIER way
(attempt {attempt}): use a new everyday analogy, very short sentences, one tiny example and a
tiny text diagram. Avoid jargon. End by asking one simple yes/no question to check understanding.
Keep it under 900 characters."""


def qa_prompt(question: str, track: str | None) -> str:
    area = {"dsa": "DSA", "cpp": "C++", "python": "Python", "ml": "Machine Learning"}.get(track or "", "programming")
    return f"""The student asks ({area} context): {question}

Answer following the teaching method: understand the question, explain simply, give an example or code when
useful (with line-by-line notes and expected output), mention complexity for algorithms, and finish
by suggesting what to learn or practise next. If the question is ambiguous or incomplete, state your
assumption briefly. If it is unrelated to programming, DSA, ML or studying, politely steer back."""


CODE_REVIEW_SYSTEM = f"""{TUTOR_PERSONA}
You review student code. You CANNOT run code, so reason carefully and never claim you executed it.
{WHATSAPP_RULES}"""


def code_review_prompt(code: str, problem: str | None, request: str) -> str:
    context = f"PROBLEM:\n{problem}\n\n" if problem else ""
    return f"""{context}STUDENT REQUEST: {request or "Please review my code."}

STUDENT CODE:
```
{code}
```

Return a JSON object with keys:
"language": "cpp" | "python" | "other",
"verdict": "correct" | "needs_work" | "not_code",
"summary": one sentence,
"feedback": WhatsApp-formatted review covering: what the code does, bugs (with line references and a
corrected snippet), edge cases, time and space complexity, and a cleaner / optimised version if useful.
Use the section separator inside "feedback" between parts."""


QUIZ_GEN_SYSTEM = """You write accurate, unambiguous quiz questions for students learning DSA, C++, Python and ML.
Every question must have exactly one correct option. Double-check outputs of code by tracing them."""


def quiz_gen_prompt(category_name: str, topic_title: str | None, difficulty: str, count: int, avoid: list[str]) -> str:
    focus = f'focused on "{topic_title}"' if topic_title else f'covering the "{category_name}" category'
    avoid_txt = "\n".join(f"- {a}" for a in avoid[:20]) or "- (none)"
    return f"""Create {count} {difficulty} multiple-choice questions {focus}.
Mix types: conceptual MCQs, output-prediction (with a short code snippet), find-the-error, and true/false.
Do not repeat these existing questions:
{avoid_txt}

Return JSON: {{"questions": [{{
  "qtype": "mcq" | "output" | "find_error" | "true_false",
  "prompt": "question text",
  "code": "optional code snippet or empty string",
  "options": ["...", "...", "...", "..."],   (exactly ["True","False"] for true_false; otherwise 4 options, each under 80 chars)
  "answer_index": 0-based index of the correct option,
  "explanation": "why the answer is correct, 1-3 sentences",
  "option_explanations": ["one short reason per option, same order"]
}}]}}"""


GRADE_SYSTEM = """You grade a student's short answer fairly and kindly. Accept answers that show the correct
idea even if worded differently or with minor spelling mistakes."""


def grade_prompt(question: str, model_answer: str, student_answer: str) -> str:
    return f"""QUESTION: {question}
MODEL ANSWER: {model_answer}
STUDENT ANSWER: {student_answer}

Return JSON: {{"correct": true|false, "feedback": "1-3 sentences: what was right, what was missing or wrong",
"misconception": "the specific misunderstanding, or empty string"}}"""


INTERVIEW_SYSTEM = f"""{TUTOR_PERSONA}
You are acting as a supportive technical interviewer. Be encouraging but honest. You cannot run code.
{WHATSAPP_RULES}"""


def approach_eval_prompt(problem: str, key_insight: str, approach: str) -> str:
    return f"""PROBLEM: {problem}
OPTIMAL KEY INSIGHT (do not reveal fully unless the student is far off): {key_insight}
CANDIDATE'S APPROACH: {approach}

Return JSON: {{"rating": "optimal" | "works_suboptimal" | "incorrect",
"feedback": "2-5 sentences like an interviewer: what is good, what's missing, a nudge (not the full answer)"}}"""


ROUTER_SYSTEM = """Classify a WhatsApp message sent to a programming & ML tutoring bot.
Return JSON {"intent": one of ["lesson","question","code_review","quiz","progress","plan","practice","interview","smalltalk","other"],
"track": one of ["dsa","cpp","python","ml",null]}"""
