"""Turn Markdown-ish text (what LLMs produce) into WhatsApp formatting, and split long text
into readable chunks without breaking code blocks."""

from __future__ import annotations

import re

SPLIT_MARKER = "<<<SPLIT>>>"
FENCE = "```"

_BOLD_MD = re.compile(r"\*\*(.+?)\*\*")
_BOLD_UNDERSCORE = re.compile(r"__(.+?)__")
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+?)\s*#*\s*$")
_STAR_BULLET = re.compile(r"^(\s*)[*+]\s+")
_FENCE_LANG = re.compile(r"^```[\w+#.-]*\s*$")
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


def to_whatsapp(text: str) -> str:
    """Convert common Markdown to WhatsApp syntax. Code blocks are left untouched
    (apart from removing the language tag, which WhatsApp would display literally)."""
    out: list[str] = []
    in_code = False
    for line in text.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped.startswith(FENCE):
            if _FENCE_LANG.match(stripped):
                out.append(FENCE)
                in_code = not in_code
                continue
        if in_code:
            out.append(line)
            continue
        m = _HEADING.match(line)
        if m:
            heading = _BOLD_MD.sub(r"\1", m.group(1)).strip("* ")
            out.append(f"*{heading}*")
            continue
        line = _STAR_BULLET.sub(r"\1• ", line)
        line = _BOLD_MD.sub(r"*\1*", line)
        line = _BOLD_UNDERSCORE.sub(r"*\1*", line)
        line = _LINK.sub(r"\1 (\2)", line)
        if stripped in {"---", "***", "___"}:
            line = "━━━━━━━━━━"
        out.append(line)
    result = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", result).strip()


def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    """Split text into WhatsApp-sized chunks.

    1. Explicit SPLIT_MARKERs always start a new message (LLM prompts use them between sections).
    2. Otherwise split on blank lines, then lines, packing pieces up to `max_chars`.
    3. If a split lands inside a ``` block, the block is closed and reopened in the next chunk.
    """
    chunks: list[str] = []
    for section in text.split(SPLIT_MARKER):
        section = section.strip()
        if section:
            chunks.extend(_pack(section, max_chars))
    return [c for c in (c.strip() for c in chunks) if c]


def _pack(section: str, max_chars: int) -> list[str]:
    if len(section) <= max_chars:
        return [section]

    # Break into paragraph-ish units, keeping code blocks as single units where possible.
    units = _units(section)
    chunks: list[str] = []
    current = ""
    for unit in units:
        candidate = f"{current}\n\n{unit}" if current else unit
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(unit) <= max_chars:
            current = unit
        else:
            pieces = _split_long_unit(unit, max_chars)
            chunks.extend(pieces[:-1])
            current = pieces[-1]
    if current:
        chunks.append(current)
    return chunks


def _units(section: str) -> list[str]:
    units: list[str] = []
    buf: list[str] = []
    in_code = False
    for line in section.split("\n"):
        if line.strip().startswith(FENCE):
            in_code = not in_code if line.strip().count(FENCE) % 2 == 1 else in_code
        if not in_code and line.strip() == "" and buf:
            units.append("\n".join(buf))
            buf = []
            continue
        buf.append(line)
    if buf:
        units.append("\n".join(buf))
    return [u for u in units if u.strip()]


def _split_long_unit(unit: str, max_chars: int) -> list[str]:
    """Split a single oversized unit by lines; keep code fences balanced across pieces."""
    pieces: list[str] = []
    current: list[str] = []
    size = 0
    in_code = False
    reserve = len(FENCE) + 2
    for line in unit.split("\n"):
        # Extremely long single lines get hard-wrapped.
        while len(line) > max_chars - reserve * 2:
            head, line = line[: max_chars - reserve * 2], line[max_chars - reserve * 2 :]
            current, size, in_code = _flush_line(pieces, current, size, head, in_code, max_chars, reserve)
        current, size, in_code = _flush_line(pieces, current, size, line, in_code, max_chars, reserve)
    if current:
        pieces.append("\n".join(current))
    return pieces


def _flush_line(pieces, current, size, line, in_code, max_chars, reserve):
    if size + len(line) + 1 > max_chars - reserve and current:
        if in_code:
            current.append(FENCE)
        pieces.append("\n".join(current))
        current = [FENCE] if in_code else []
        size = len(FENCE) + 1 if in_code else 0
    current.append(line)
    size += len(line) + 1
    if line.strip().startswith(FENCE) and line.strip().count(FENCE) % 2 == 1:
        in_code = not in_code
    return current, size, in_code


def progress_bar(fraction: float, width: int = 10) -> str:
    fraction = max(0.0, min(1.0, fraction))
    filled = round(fraction * width)
    return "▓" * filled + "░" * (width - filled)
