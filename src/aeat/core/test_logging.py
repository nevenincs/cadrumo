"""Unit tests for the record-level log secret scrubber.

Exercises :class:`aeat.core.logging.SecretScrubbingFilter` end-to-end
through the standard :mod:`logging` pipeline: tuple ``%``-args, dict
``extra=`` payloads, exception tracebacks, and inline secrets in the
record's message format string. The tests verify that key-paired
secrets (``token=``, ``cookie=``, ``Bearer ...``) collapse to
``<redacted>`` while non-sensitive context (region, status, account,
counts) survives intact.
"""

from __future__ import annotations

import io
import logging
import sys
from pathlib import Path

import pytest

from .logging import SecretScrubbingFilter, default_log_file_path, get_logger

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def _capture_logger_output() -> tuple[logging.Logger, logging.Logger, logging.Handler, io.StringIO]:
    """Attach a temporary stream handler to the root logger."""

    logger = get_logger("aeat.test_logging")
    root_logger = logging.getLogger()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(levelname)s %(message)s | cookie=%(cookie)s | bearer_header=%(bearer_header)s | region=%(region)s"
        )
    )
    root_logger.addHandler(handler)
    return logger, root_logger, handler, stream


def test_default_logging_routes_warnings_to_file_not_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Warnings should be persisted for diagnostics without polluting CLI stderr."""

    marker = "warning-route-marker-7f6a3c"
    logger = get_logger("aeat.test_logging.default_route")

    logger.warning(marker)

    captured = capsys.readouterr()
    assert marker not in captured.err
    assert marker in _read_log_tail(default_log_file_path())


def _read_log_tail(path: Path, *, max_bytes: int = 64 * 1024) -> str:
    with path.open("rb") as handle:
        handle.seek(0, 2)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        return handle.read().decode("utf-8", errors="replace")


def test_secret_scrubbing_redacts_sensitive_fields_in_rendered_output() -> None:
    """Sensitive fields should be redacted across args, extras, and exceptions."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        try:
            raise RuntimeError("oauth_refresh_token=refresh-123 bearer sk-ant-demo-token")
        except RuntimeError:
            logger.exception(
                "credential=%s payload=%s",
                "operator-secret",
                {"pkcs12": "bundle-passphrase", "account": "kept-visible"},
                extra={
                    "cookie": "session-cookie",
                    "bearer_header": "Bearer abc.def.ghi",
                    "region": "es",
                },
            )
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_root_level)

    rendered = stream.getvalue()
    assert "<redacted>" in rendered
    assert "operator-secret" not in rendered
    assert "bundle-passphrase" not in rendered
    assert "session-cookie" not in rendered
    assert "abc.def.ghi" not in rendered
    assert "refresh-123" not in rendered
    assert "kept-visible" in rendered
    assert "region=es" in rendered


def test_secret_scrubbing_redacts_inline_message_text_when_tuple_args_exist() -> None:
    """Inline secrets should still be scrubbed when ``%`` args are present."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        logger.info(
            "oauth_refresh_token=refresh-123 status=%s",
            "ok",
            extra={
                "cookie": "<redacted>",
                "bearer_header": "<redacted>",
                "region": "es",
            },
        )
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_root_level)

    rendered = stream.getvalue()
    assert "refresh-123" not in rendered
    assert "oauth_refresh_token=<redacted>" in rendered
    assert "status=ok" in rendered


def test_secret_scrubbing_maps_key_hints_to_the_correct_placeholder() -> None:
    """Only the placeholder paired with the sensitive key should be scrubbed."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        logger.info(
            "item %s has token: %s",
            "safe-item",
            "token-secret",
            extra={
                "cookie": "<redacted>",
                "bearer_header": "<redacted>",
                "region": "es",
            },
        )
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_root_level)

    rendered = stream.getvalue()
    assert "safe-item" in rendered
    assert "token-secret" not in rendered
    assert "token: <redacted>" in rendered


def test_secret_scrubbing_handles_colon_assignments() -> None:
    """Colon-delimited sensitive placeholders should still be scrubbed."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        logger.info(
            "token: %s",
            "colon-secret",
            extra={
                "cookie": "<redacted>",
                "bearer_header": "<redacted>",
                "region": "es",
            },
        )
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_root_level)

    rendered = stream.getvalue()
    assert "colon-secret" not in rendered
    assert "token: <redacted>" in rendered


def test_secret_scrubbing_preserves_exc_info_for_downstream_handlers() -> None:
    """Scrubbed tracebacks should not destroy the original exception tuple."""

    filter_ = SecretScrubbingFilter()
    try:
        raise RuntimeError("oauth_refresh_token=refresh-123")
    except RuntimeError:
        record = logging.LogRecord(
            name="aeat.test_logging",
            level=logging.ERROR,
            pathname=__file__,
            lineno=0,
            msg="failure",
            args=(),
            exc_info=sys.exc_info(),
        )

    assert record.exc_info is not None
    filter_.filter(record)
    assert record.exc_info is not None
    assert record.exc_text is not None
    assert "refresh-123" not in record.exc_text


def test_secret_scrubbing_uses_context_hints_for_list_args_too() -> None:
    """List-based log args should preserve placeholder-aware scrubbing."""

    filter_ = SecretScrubbingFilter()
    record = logging.LogRecord(
        name="aeat.test_logging",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="item %s has token: %s",
        args=(),
        exc_info=None,
    )
    record.args = ["safe-item", "token-secret"]  # ty: ignore[invalid-assignment]

    filter_.filter(record)
    # The scrubber redacts list args and normalises the container to a
    # tuple — ``logging.LogRecord.args`` is typed ``tuple | Mapping |
    # None`` and ``list`` is not in that union (see SecretScrubbingFilter).
    assert record.args == ("safe-item", "<redacted>")


def test_non_sensitive_fields_pass_through_unchanged() -> None:
    """Ordinary logging fields should remain visible after scrubbing runs."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        logger.info(
            "operation summary=%s",
            {"count": 3, "status": "ok"},
            extra={
                "cookie": "<redacted>",
                "bearer_header": "<redacted>",
                "region": "es",
            },
        )
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_root_level)

    rendered = stream.getvalue()
    assert "count" in rendered
    assert "status" in rendered
    assert "ok" in rendered
    assert "region=es" in rendered
