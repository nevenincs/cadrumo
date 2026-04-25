"""Unit tests for record-level log scrubbing."""

from __future__ import annotations

import io
import logging

import pytest

from .logging import get_logger

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


def _capture_logger_output() -> tuple[logging.Logger, logging.Logger, logging.Handler, io.StringIO]:
    """Attach a temporary stream handler to the root logger."""

    logger = get_logger("aeat.test_logging_scrubbing")
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
