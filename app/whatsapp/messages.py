"""Transport-neutral message types used by agents.

Agents return these objects; the WhatsApp client turns them into Cloud API payloads, while the
dev chat endpoint and tests just inspect them. WhatsApp limits are enforced here so agents
can't accidentally build an invalid payload.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Cloud API limits for interactive messages
MAX_BUTTONS = 3
BUTTON_TITLE_MAX = 20
LIST_ROWS_MAX = 10
LIST_ROW_TITLE_MAX = 24
LIST_ROW_DESC_MAX = 72
LIST_BUTTON_MAX = 20
INTERACTIVE_BODY_MAX = 1024
TEXT_BODY_MAX = 4096


def _clip(text: str, limit: int) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


@dataclass
class Button:
    id: str
    title: str

    def __post_init__(self):
        self.title = _clip(self.title, BUTTON_TITLE_MAX)
        self.id = self.id[:256]


@dataclass
class ListRow:
    id: str
    title: str
    description: str = ""

    def __post_init__(self):
        self.title = _clip(self.title, LIST_ROW_TITLE_MAX)
        self.description = _clip(self.description, LIST_ROW_DESC_MAX) if self.description else ""
        self.id = self.id[:200]


@dataclass
class OutgoingMessage:
    """One WhatsApp message. kind: text | buttons | list | template."""

    kind: str
    body: str = ""
    buttons: list[Button] = field(default_factory=list)
    rows: list[ListRow] = field(default_factory=list)
    list_button: str = "Choose"
    header: str | None = None
    template_name: str | None = None
    template_params: list[str] = field(default_factory=list)

    @property
    def plain_text(self) -> str:
        """A text rendering of the message, used for history, logs and the dev chat UI."""
        parts = [self.body]
        if self.buttons:
            parts.append("Buttons: " + " | ".join(f"[{b.title}]" for b in self.buttons))
        if self.rows:
            parts.append("Options: " + " | ".join(f"[{r.title}]" for r in self.rows))
        if self.template_name:
            parts.append(f"(template {self.template_name}: {', '.join(self.template_params)})")
        return "\n".join(p for p in parts if p)


def text(body: str) -> OutgoingMessage:
    return OutgoingMessage(kind="text", body=body[:TEXT_BODY_MAX])


def buttons(body: str, items: list[tuple[str, str]], header: str | None = None) -> OutgoingMessage:
    """Reply buttons (max 3). `items` = [(id, title), ...]."""
    btns = [Button(id=i, title=t) for i, t in items[:MAX_BUTTONS]]
    return OutgoingMessage(kind="buttons", body=_clip(body, INTERACTIVE_BODY_MAX), buttons=btns, header=header)


def list_menu(
    body: str, rows: list[tuple[str, str, str]], button: str = "Choose", header: str | None = None
) -> OutgoingMessage:
    """Interactive list (max 10 rows). `rows` = [(id, title, description), ...]."""
    lr = [ListRow(id=i, title=t, description=d) for i, t, d in rows[:LIST_ROWS_MAX]]
    return OutgoingMessage(
        kind="list",
        body=_clip(body, INTERACTIVE_BODY_MAX),
        rows=lr,
        list_button=_clip(button, LIST_BUTTON_MAX),
        header=header,
    )


def template(name: str, params: list[str]) -> OutgoingMessage:
    return OutgoingMessage(kind="template", template_name=name, template_params=params)
