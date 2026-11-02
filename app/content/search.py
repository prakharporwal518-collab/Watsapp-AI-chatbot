"""Find the curriculum topic a free-text message is talking about."""

from __future__ import annotations

import difflib
import re
from functools import lru_cache

from app.content.curriculum import TOPICS, Topic

_WORD = re.compile(r"[a-z0-9+#]+")


def normalise(text: str) -> str:
    text = text.lower().replace("c++", "cpp").replace("’", "'")
    return " ".join(_WORD.findall(text))


@lru_cache(maxsize=1)
def _phrases() -> list[tuple[str, Topic]]:
    pairs: list[tuple[str, Topic]] = []
    for topic in TOPICS.values():
        phrases = {normalise(topic.title), *(normalise(k) for k in topic.keywords)}
        for phrase in phrases:
            if phrase:
                pairs.append((phrase, topic))
    return pairs


def find_topic(text: str, track_hint: str | None = None) -> Topic | None:
    """Best-matching topic for `text`, or None.

    Longer phrase matches win ("merge sort" beats "merge"); a topic in `track_hint`
    (e.g. the track the student is currently studying) wins ties.
    """
    norm = f" {normalise(text)} "
    if not norm.strip():
        return None
    best: tuple[float, Topic] | None = None
    for phrase, topic in _phrases():
        if f" {phrase} " in norm:
            score = len(phrase) + (3 if track_hint and topic.track == track_hint else 0)
            score -= topic.order_index * 0.001  # earlier topics win exact ties
            if best is None or score > best[0]:
                best = (score, topic)
    if best:
        return best[1]
    return _fuzzy(norm.strip(), track_hint)


def _fuzzy(norm: str, track_hint: str | None) -> Topic | None:
    """Typo tolerance: 'binery serch' → Binary Search. Only for short, topic-like messages."""
    if len(norm.split()) > 6:
        return None
    candidates = [p for p, _ in _phrases() if len(p) >= 4]
    match = difflib.get_close_matches(norm, candidates, n=3, cutoff=0.82)
    if not match:
        return None
    options = [t for p, t in _phrases() if p == match[0]]
    if track_hint:
        for t in options:
            if t.track == track_hint:
                return t
    return options[0]
