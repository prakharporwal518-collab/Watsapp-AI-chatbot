import logging

from app.core.logging import RedactSecretsFilter, configure_logging, redact


def test_redacts_meta_verify_token_in_urls():
    url = "/webhook?hub.mode=subscribe&hub.challenge=123&hub.verify_token=SuperSecret-r5&hub_verify_token=SuperSecret-r5"
    out = redact(url)
    assert "SuperSecret" not in out
    assert "hub.challenge=123" in out  # harmless values are kept
    assert out.count("***") == 2


def test_redacts_access_tokens():
    assert redact("GET /x?access_token=EAAabc123&x=1") == "GET /x?access_token=***&x=1"


def test_filter_masks_uvicorn_style_access_log_args():
    # uvicorn.access logs: '%s - "%s %s HTTP/%s" %d' with the full path as an argument.
    record = logging.LogRecord(
        "uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d',
        ("1.2.3.4:5", "GET", "/webhook?hub.verify_token=SuperSecret&hub.challenge=9", "1.1", 200), None,
    )
    RedactSecretsFilter().filter(record)
    message = record.getMessage()
    assert "SuperSecret" not in message
    assert "hub.verify_token=***" in message and "200" in message


def test_uvicorn_loggers_get_the_filter():
    configure_logging("INFO")
    configure_logging("INFO")  # idempotent: no duplicate filters
    access = logging.getLogger("uvicorn.access")
    assert sum(isinstance(f, RedactSecretsFilter) for f in access.filters) == 1
