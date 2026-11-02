from app.whatsapp import messages as wa
from app.whatsapp.client import build_payload
from app.whatsapp.formatter import SPLIT_MARKER, chunk_text, progress_bar, to_whatsapp
from app.whatsapp.parser import parse_webhook


def _payload(messages, contacts=None):
    return {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {
        "messaging_product": "whatsapp",
        "contacts": contacts or [{"wa_id": "919876543210", "profile": {"name": "Asha"}}],
        "messages": messages}}]}]}


class TestParser:
    def test_text_message(self):
        msgs = parse_webhook(_payload([{"from": "919876543210", "id": "wamid.1", "timestamp": "1700000000",
                                        "type": "text", "text": {"body": "hello"}}]))
        assert len(msgs) == 1
        m = msgs[0]
        assert (m.wa_id, m.message_id, m.text, m.profile_name, m.is_supported) == ("919876543210", "wamid.1", "hello", "Asha", True)

    def test_button_and_list_replies(self):
        msgs = parse_webhook(_payload([
            {"from": "1", "id": "a", "type": "interactive", "interactive": {"type": "button_reply", "button_reply": {"id": "cmd:next", "title": "Next"}}},
            {"from": "1", "id": "b", "type": "interactive", "interactive": {"type": "list_reply", "list_reply": {"id": "learn:dsa.stack", "title": "Stacks"}}},
            {"from": "1", "id": "c", "type": "button", "button": {"payload": "cmd:dailyplan", "text": "Plan"}},
        ]))
        assert [m.button_id for m in msgs] == ["cmd:next", "learn:dsa.stack", "cmd:dailyplan"]

    def test_status_updates_and_other_objects_ignored(self):
        status = {"object": "whatsapp_business_account", "entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "read"}]}}]}]}
        assert parse_webhook(status) == []
        assert parse_webhook({"object": "page"}) == []
        assert parse_webhook([]) == []  # type: ignore[arg-type]

    def test_malformed_message_skipped(self):
        msgs = parse_webhook(_payload([{"type": "text"}, {"from": "1", "id": "ok", "type": "text", "text": {"body": "hi"}}]))
        assert [m.message_id for m in msgs] == ["ok"]

    def test_media_is_unsupported(self):
        msgs = parse_webhook(_payload([{"from": "1", "id": "img", "type": "image", "image": {"id": "x"}}]))
        assert not msgs[0].is_supported


class TestFormatter:
    def test_markdown_to_whatsapp(self):
        out = to_whatsapp("## Heading\n**bold** and __also__\n* item\n[link](https://x.y)\n---")
        assert out.splitlines() == ["*Heading*", "*bold* and *also*", "• item", "link (https://x.y)", "━━━━━━━━━━"]

    def test_code_blocks_untouched_but_language_removed(self):
        out = to_whatsapp("```cpp\nint **p = 0; // **not bold**\n```")
        assert out == "```\nint **p = 0; // **not bold**\n```"

    def test_split_marker_creates_messages(self):
        assert chunk_text(f"one{SPLIT_MARKER}two\n{SPLIT_MARKER}  {SPLIT_MARKER}three") == ["one", "two", "three"]

    def test_long_text_respects_limit(self):
        text = "\n\n".join(f"Paragraph {i} " + "word " * 40 for i in range(30))
        chunks = chunk_text(text, 500)
        assert len(chunks) > 1
        assert all(len(c) <= 500 for c in chunks)
        assert "".join(chunks).replace("\n", "").replace(" ", "") == text.replace("\n", "").replace(" ", "")

    def test_code_fences_stay_balanced(self):
        code = "```\n" + "\n".join(f"line_{i} = {i} * {i}  # some comment" for i in range(80)) + "\n```"
        chunks = chunk_text("Intro\n\n" + code, 600)
        assert len(chunks) > 2
        for c in chunks:
            assert c.count("```") % 2 == 0, c
            assert len(c) <= 600

    def test_single_huge_line_is_wrapped(self):
        chunks = chunk_text("x" * 3000, 1000)
        assert all(len(c) <= 1000 for c in chunks)

    def test_progress_bar(self):
        assert progress_bar(0.5, 10) == "▓▓▓▓▓░░░░░"
        assert progress_bar(2, 4) == "▓▓▓▓"
        assert progress_bar(-1, 4) == "░░░░"


class TestMessages:
    def test_button_limits_enforced(self):
        msg = wa.buttons("b" * 2000, [("1", "A very long button title indeed"), ("2", "b"), ("3", "c"), ("4", "d")])
        assert len(msg.buttons) == 3
        assert all(len(b.title) <= wa.BUTTON_TITLE_MAX for b in msg.buttons)
        assert len(msg.body) <= wa.INTERACTIVE_BODY_MAX

    def test_list_limits_enforced(self):
        msg = wa.list_menu("body", [(str(i), "T" * 40, "D" * 100) for i in range(15)], button="A very long button label")
        assert len(msg.rows) == 10
        assert all(len(r.title) <= 24 and len(r.description) <= 72 for r in msg.rows)
        assert len(msg.list_button) <= 20

    def test_payload_shapes(self):
        p = build_payload("91999", wa.text("hi"))
        assert p["type"] == "text" and p["text"]["body"] == "hi" and p["to"] == "91999"
        p = build_payload("91999", wa.buttons("pick", [("a", "A")]))
        assert p["interactive"]["type"] == "button"
        assert p["interactive"]["action"]["buttons"][0]["reply"] == {"id": "a", "title": "A"}
        p = build_payload("91999", wa.list_menu("pick", [("r1", "Row", "desc")], header="Head"))
        assert p["interactive"]["action"]["sections"][0]["rows"][0] == {"id": "r1", "title": "Row", "description": "desc"}
        p = build_payload("91999", wa.template("daily_reminder", ["Asha", "plan"]))
        assert p["template"]["components"][0]["parameters"][1] == {"type": "text", "text": "plan"}
