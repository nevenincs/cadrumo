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
from typing import cast

import pytest

from ..logging import (
    SecretScrubbingFilter,
    _scrub_value,
    attach_run_sink,
    default_log_file_path,
    detach_run_sink,
    get_logger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _capture_logger_output() -> tuple[logging.Logger, logging.Logger, logging.Handler, io.StringIO]:
    """Attach a temporary stream handler to the root logger."""

    logger = get_logger("aeat.test_logging")
    root_logger = logging.getLogger()
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setLevel(logging.INFO)
    handler.setFormatter(
        logging.Formatter(
            "%(levelname)s %(message)s | cookie=%(cookie)s | bearer_header=%(bearer_header)s | region=%(region)s",
        ),
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


def test_secret_scrubbing_redacts_unquoted_multiword_passphrase_assignment() -> None:
    """Passphrase assignments should not leak words after the first space."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        logger.info(
            "passphrase=correct horse battery staple status=locked",
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
    assert "correct" not in rendered
    assert "horse" not in rendered
    assert "battery" not in rendered
    assert "staple" not in rendered
    assert "passphrase=<redacted>" in rendered
    assert "status=locked" in rendered


def test_secret_scrubbing_redacts_quoted_multiword_passphrase_assignment() -> None:
    """Quoted passphrase assignments should be redacted as one sensitive value."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        logger.info(
            'passphrase="correct horse battery staple"; status=locked',
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
    assert "correct horse battery staple" not in rendered
    assert "passphrase=<redacted>" in rendered
    assert "status=locked" in rendered


def test_secret_scrubbing_applies_shared_shape_rules_to_plain_text_args() -> None:
    """NIF, URL, and bearer-token shapes should not need local log key hints."""

    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.aaaaaaaaaaaa.bbbbbbbbbbbb"
    try:
        logger.info(
            "taxpayer=%s callback=%s session=%s",
            "12345678Z",
            "https://example.test/private/path?token=secret",
            jwt,
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
    assert "12345678Z" not in rendered
    assert "https://example.test/private/path?token=secret" not in rendered
    assert jwt not in rendered
    assert "taxpayer=sha256:1c9f9632" in rendered
    assert "callback=https://example.test" in rendered
    assert "private/path" not in rendered
    assert "token=secret" not in rendered
    assert "session=token:<redacted>" in rendered


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
    record.__setattr__("args", ["safe-item", "token-secret"])

    filter_.filter(record)
    # The scrubber redacts list args and normalises the container to a
    # tuple — ``logging.LogRecord.args`` is typed ``tuple | Mapping |
    # None`` and ``list`` is not in that union (see SecretScrubbingFilter).
    assert record.args == ("safe-item", "<redacted>")


def test_pdfminer_logger_level_governed_by_dictconfig() -> None:
    """dictConfig must set the pdfminer logger to WARNING via the loggers block.

    Verifies contract: configure_logging() centralises pdfminer silencing so
    neither _pdfplumber.py nor _record_design.py need to mutate it locally.
    """
    import logging

    from .. import logging as _logging_mod

    # Force a fresh dictConfig run by temporarily resetting the guard.
    original_configured = _logging_mod._CONFIGURED
    _logging_mod._CONFIGURED = False
    try:
        _logging_mod.configure_logging()
    finally:
        # Restore so other tests are not affected.
        _logging_mod._CONFIGURED = original_configured or True

    pdfminer_logger = logging.getLogger("pdfminer")
    assert pdfminer_logger.level == logging.WARNING, (
        f"pdfminer logger level should be WARNING ({logging.WARNING}) "
        f"after configure_logging(); got {pdfminer_logger.level}"
    )


def test_pdfplumber_and_record_design_do_not_mutate_pdfminer_logger() -> None:
    """Neither _pdfplumber nor _record_design should re-mutate the pdfminer logger.

    Verifies contract: importing both modules and calling configure_logging()
    leaves the pdfminer logger at WARNING — confirming the per-module
    context-manager silencers have been removed and centralized config governs.
    """
    import logging

    from .. import logging as _logging_mod

    original_configured = _logging_mod._CONFIGURED
    _logging_mod._CONFIGURED = False
    try:
        _logging_mod.configure_logging()
    finally:
        _logging_mod._CONFIGURED = original_configured or True

    # Trigger module imports — side-effects would show up as level mutations.

    pdfminer_logger = logging.getLogger("pdfminer")
    assert pdfminer_logger.level == logging.WARNING, (
        f"pdfminer logger level should remain WARNING after importing both pdf modules; got {pdfminer_logger.level}"
    )

    # Confirm the per-module silencer has been deleted from _pdfplumber's
    # public surface.
    from ...adapters.inbound.pdf._pdfplumber import __all__ as pdfplumber_all

    assert "suppress_pdfminer_debug_logging" not in pdfplumber_all, (
        "suppress_pdfminer_debug_logging still exported from _pdfplumber; "
        "it should have been deleted (centralized in dictConfig)"
    )


def test_pikepdf_core_logger_level_governed_by_dictconfig() -> None:
    """dictConfig must set pikepdf._core to WARNING via the loggers block.

    Verifies contract: configure_logging() centralises pikepdf._core silencing so
    src/aeat/__init__.py no longer needs a bootstrap-time setLevel mutation.
    The level must survive a second configure_logging() call (the guard resets).
    """
    import logging

    from .. import logging as _logging_mod

    original_configured = _logging_mod._CONFIGURED
    _logging_mod._CONFIGURED = False
    try:
        _logging_mod.configure_logging()
    finally:
        _logging_mod._CONFIGURED = original_configured or True

    pikepdf_logger = logging.getLogger("pikepdf._core")
    assert pikepdf_logger.level == logging.WARNING, (
        f"pikepdf._core logger level should be WARNING ({logging.WARNING}) "
        f"after configure_logging(); got {pikepdf_logger.level}"
    )


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


# ---------------------------------------------------------------------------
# contract — _scrub_value overload contract: type preserved per input shape
# ---------------------------------------------------------------------------


def test_scrub_value_str_overload_returns_str() -> None:
    """str input must produce a str result (non-sensitive value passes through)."""

    result = _scrub_value("hello world")
    assert isinstance(result, str)
    assert result == "hello world"


def test_scrub_value_str_overload_redacts_sensitive_key() -> None:
    """str input with a sensitive key must return a redacted str."""

    result = _scrub_value("super-secret", key="token")
    assert isinstance(result, str)
    assert result == "<redacted>"


def test_scrub_value_mapping_overload_returns_dict() -> None:
    """Mapping input must produce a dict result."""

    result = _scrub_value({"account": "visible", "secret": "hidden"})
    assert isinstance(result, dict)
    assert result["account"] == "visible"
    assert result["secret"] == "<redacted>"


def test_scrub_value_tuple_overload_returns_tuple() -> None:
    """tuple input must produce a tuple result with items recursively scrubbed."""

    result = _scrub_value(("safe-value", "also-safe"))
    assert isinstance(result, tuple)
    assert result == ("safe-value", "also-safe")


def test_scrub_value_list_overload_returns_list() -> None:
    """list input must produce a list result with items recursively scrubbed."""

    result = _scrub_value(["one", "two"])
    assert isinstance(result, list)
    assert result == ["one", "two"]


def test_scrub_value_set_overload_returns_set() -> None:
    """set input must produce a set result with items recursively scrubbed."""

    result = _scrub_value({"alpha", "beta"})
    assert isinstance(result, set)
    assert result == {"alpha", "beta"}


def test_scrub_value_object_overload_passes_through_non_sensitive() -> None:
    """An arbitrary object with a non-sensitive key passes through unchanged."""

    obj = object()
    result = _scrub_value(obj, key="count")
    assert result is obj


def test_scrub_value_object_overload_redacts_sensitive_key() -> None:
    """An arbitrary object with a sensitive key is redacted to a str marker."""

    result = _scrub_value(12345, key="token")
    assert isinstance(result, str)
    assert result == "<redacted>"


def test_scrub_value_nested_mapping_scrubs_recursively() -> None:
    """Nested dicts must have their sensitive leaves redacted at every depth."""

    payload = {"outer": {"token": "s3cr3t", "count": 3}}
    result = _scrub_value(payload)
    assert isinstance(result, dict)
    outer_raw = result["outer"]
    assert isinstance(outer_raw, dict)
    outer = cast(dict[str, object], outer_raw)
    assert outer["token"] == "<redacted>"
    assert outer["count"] == 3


# ---------------------------------------------------------------------------
# contract / contract — attach_run_sink / detach_run_sink symmetry
# ---------------------------------------------------------------------------


def test_attach_and_detach_run_sink_are_symmetric(tmp_path: Path) -> None:
    """attach_run_sink then detach_run_sink must restore the root logger to its prior state.

    Real-behavior: wire a real JsonlRunSink, observe root-logger handler list and
    sink filter list before, during, and after the attach/detach cycle.
    """
    from ..observability._sink import JsonlRunSink

    run_id = "a1b2c3d4e5f60001"
    sink = JsonlRunSink(tmp_path / "events.jsonl", run_id=run_id)

    root_logger = logging.getLogger()
    handlers_before = list(root_logger.handlers)
    filters_on_sink_before = list(sink.filters)

    # After construction the sink must carry no filters yet.
    assert filters_on_sink_before == [], "sink should start with no filters"
    assert sink not in handlers_before, "sink must not be on root logger before attach"

    attach_run_sink(sink)

    handlers_during = list(root_logger.handlers)
    assert sink in handlers_during, "sink must be on root logger after attach"
    scrubbing_filters_on_sink = [f for f in sink.filters if isinstance(f, SecretScrubbingFilter)]
    assert len(scrubbing_filters_on_sink) == 1, (
        "attach_run_sink must install exactly one SecretScrubbingFilter on the sink"
    )

    detach_run_sink(sink)

    handlers_after = list(root_logger.handlers)
    assert sink not in handlers_after, "sink must be removed from root logger after detach"
    # Root logger's own handler list is restored to the pre-attach state.
    assert handlers_after == handlers_before, "root logger handlers must be restored after detach"
    # SecretScrubbingFilter must be removed from the sink's filter list on detach.
    remaining_scrubbing = [f for f in sink.filters if isinstance(f, SecretScrubbingFilter)]
    assert remaining_scrubbing == [], "detach_run_sink must remove SecretScrubbingFilter instances from the sink"

    sink.close()


def test_detach_run_sink_is_idempotent_on_filter_removal(tmp_path: Path) -> None:
    """detach_run_sink called twice must not raise and must leave the sink filter-clean."""
    from ..observability._sink import JsonlRunSink

    run_id = "b2c3d4e5f6070002"
    sink = JsonlRunSink(tmp_path / "events.jsonl", run_id=run_id)

    attach_run_sink(sink)
    detach_run_sink(sink)
    # Second detach: handler is already absent from root, filters already gone — no crash.
    detach_run_sink(sink)

    remaining_scrubbing = [f for f in sink.filters if isinstance(f, SecretScrubbingFilter)]
    assert remaining_scrubbing == []

    sink.close()


def test_attach_run_sink_does_not_double_install_scrubbing_filter(tmp_path: Path) -> None:
    """Calling attach_run_sink twice must install SecretScrubbingFilter exactly once."""
    from ..observability._sink import JsonlRunSink

    root_logger = logging.getLogger()
    run_id = "c3d4e5f607080003"
    sink = JsonlRunSink(tmp_path / "events.jsonl", run_id=run_id)

    try:
        attach_run_sink(sink)
        attach_run_sink(sink)  # second call — must be idempotent

        scrubbing_filters = [f for f in sink.filters if isinstance(f, SecretScrubbingFilter)]
        assert len(scrubbing_filters) == 1, "SecretScrubbingFilter must appear exactly once even after two attach calls"
    finally:
        root_logger.removeHandler(sink)
        sink.close()
