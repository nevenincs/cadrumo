"""Unit tests for the record-level log secret scrubber.

Exercises :class:`cadrumo.core.logging.SecretScrubbingFilter` end-to-end
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
from typing import Any, cast, override

import pydantic
import pytest

from .. import logging as _logging_mod
from ..config import override_settings
from ..logging import (
    LogExtra,
    SecretScrubbingFilter,
    _prepare_log_directory,
    _scrub_value,
    attach_run_sink,
    configure_logging,
    default_log_file_path,
    detach_run_sink,
    get_logger,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _capture_logger_output() -> tuple[logging.Logger, logging.Logger, logging.Handler, io.StringIO]:
    """Attach a temporary stream handler to the root logger."""

    logger = get_logger("aeat-test_logging")
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


def _render_info(message: str, *args: object) -> str:
    logger, root_logger, handler, stream = _capture_logger_output()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    try:
        logger.info(
            message,
            *args,
            extra={
                "cookie": "<redacted>",
                "bearer_header": "<redacted>",
                "region": "es",
            },
        )
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_root_level)
    return stream.getvalue()


def _force_configure_logging() -> None:
    original_configured = _logging_mod._CONFIGURED
    _logging_mod._CONFIGURED = False
    try:
        _logging_mod.configure_logging()
    finally:
        _logging_mod._CONFIGURED = original_configured or True


def test_default_logging_routes_warnings_to_file_not_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    """Warnings should be persisted for diagnostics without polluting CLI stderr."""

    marker = "warning-route-marker-7f6a3c"
    logger = get_logger("aeat-test_logging.default_route")

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


def test_prepare_log_directory_returns_none_for_creatable_path(tmp_path: Path) -> None:
    """A writable target yields no failure reason and materialises the directory."""

    log_file = tmp_path / "probe-logs" / "cadrumo.log"

    reason = _prepare_log_directory(log_file)

    assert reason is None
    assert log_file.parent.is_dir()


def test_prepare_log_directory_reports_reason_when_path_uncreatable(tmp_path: Path) -> None:
    """A log directory routed under a real file cannot be created and reports why.

    Reproduces the class of failure the Windows PowerShell testimonial hit: an
    ``CADRUMO_LOCAL_STORAGE_ROOT`` that resolves to an inaccessible / non-directory
    path. The helper must return a diagnostic reason string instead of letting
    the underlying ``OSError`` escape.
    """

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("x", encoding="utf-8")
    log_file = blocker / "probe-logs" / "cadrumo.log"

    reason = _prepare_log_directory(log_file)

    assert reason is not None
    assert not log_file.parent.exists()
    # The reason names the concrete OS error type so triage sees the cause.
    assert "Error" in reason


def test_configure_logging_degrades_to_stderr_only_when_log_dir_uncreatable(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An uncreatable log directory must NOT crash startup with a raw traceback.

    Real-behavior reproduction of a Windows PowerShell failure mode: the log
    directory derived from an inaccessible ``CADRUMO_LOCAL_STORAGE_ROOT`` cannot be
    created, and ``configure_logging`` runs at import time — before any CLI
    error boundary. The contract: no exception escapes, logging degrades to
    stderr-only (no ``FileHandler`` for the dead path), and an instructive,
    non-silent diagnostic names the remedy.
    """

    blocker = tmp_path / "storage-root-file"
    blocker.write_text("x", encoding="utf-8")
    dead_log_dir = blocker / "probe-logs"

    root_logger = logging.getLogger()
    original_configured = _logging_mod._CONFIGURED
    try:
        _logging_mod._CONFIGURED = False
        with override_settings(cadrumo_log_dir=dead_log_dir):
            # Must not raise despite the uncreatable directory.
            configure_logging()

        file_handlers = [
            handler
            for handler in root_logger.handlers
            if isinstance(handler, logging.FileHandler) and Path(handler.baseFilename).parent == dead_log_dir
        ]
        assert file_handlers == [], "no FileHandler may point at the uncreatable log directory"
        assert any(isinstance(handler, logging.StreamHandler) for handler in root_logger.handlers), (
            "stderr StreamHandler must remain so diagnostics still surface"
        )

        captured = capsys.readouterr()
        assert "stderr-only" in captured.err
        assert "CADRUMO_LOCAL_STORAGE_ROOT" in captured.err
        assert not dead_log_dir.exists()
    finally:
        # Rebuild the normal configuration so sibling tests see a healthy logger.
        _logging_mod._CONFIGURED = False
        configure_logging()
        _logging_mod._CONFIGURED = original_configured or True


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


def test_secret_scrubbing_maps_key_hints_and_colon_assignments() -> None:
    """Sensitive key hints and colon-delimited assignments scrub the paired placeholder."""

    for case_id, message, args, expected_visible, expected_redacted in (
        (
            "token-placeholder",
            "item %s has token: %s",
            ("safe-item", "token-secret"),
            ("safe-item",),
            ("token-secret",),
        ),
        ("colon-assignment", "token: %s", ("colon-secret",), (), ("colon-secret",)),
    ):
        rendered = _render_info(message, *args)
        for value in expected_visible:
            assert value in rendered, case_id
        for value in expected_redacted:
            assert value not in rendered, case_id
        assert "token: <redacted>" in rendered, case_id


def test_secret_scrubbing_redacts_multiword_passphrase_assignments() -> None:
    """Quoted and unquoted passphrase assignments should not leak sensitive words."""

    for case_id, message, forbidden_values in (
        (
            "unquoted",
            "passphrase=correct horse battery staple status=locked",
            ("correct", "horse", "battery", "staple"),
        ),
        ("quoted", 'passphrase="correct horse battery staple"; status=locked', ("correct horse battery staple",)),
    ):
        rendered = _render_info(message)
        for value in forbidden_values:
            assert value not in rendered, case_id
        assert "passphrase=<redacted>" in rendered, case_id
        assert "status=locked" in rendered, case_id


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
            name="aeat-test_logging",
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
        name="aeat-test_logging",
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


def test_noisy_pdf_library_logger_levels_are_governed_by_dictconfig() -> None:
    """dictConfig owns pdfminer and pikepdf silencing without per-module mutators."""

    _force_configure_logging()

    expected_levels = {"pdfminer": logging.WARNING, "pikepdf._core": logging.WARNING}
    for logger_name, expected_level in expected_levels.items():
        logger = logging.getLogger(logger_name)
        assert logger.level == expected_level, (
            f"{logger_name} logger level should be WARNING ({expected_level}) "
            f"after configure_logging(); got {logger.level}"
        )

    from ...adapters.inbound.pdf.page_text_extraction import __all__ as page_text_extraction_all

    assert "suppress_pdfminer_debug_logging" not in page_text_extraction_all, (
        "suppress_pdfminer_debug_logging still exported from page_text_extraction; "
        "it should have been deleted (centralized in dictConfig)"
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


def test_scrub_value_non_sensitive_overloads_preserve_shape() -> None:
    """Non-sensitive scalar/container inputs preserve their public shape."""

    for value, expected_type, expected in (
        ("hello world", str, "hello world"),
        (("safe-value", "also-safe"), tuple, ("safe-value", "also-safe")),
        (["one", "two"], list, ["one", "two"]),
        ({"alpha", "beta"}, set, {"alpha", "beta"}),
    ):
        result = _scrub_value(value)
        assert isinstance(result, expected_type)
        assert result == expected


def test_scrub_value_mapping_overload_returns_dict() -> None:
    """Mapping input must produce a dict result."""

    result = _scrub_value({"account": "visible", "secret": "hidden"})
    assert isinstance(result, dict)
    assert result["account"] == "visible"
    assert result["secret"] == "<redacted>"


def test_scrub_value_object_overload_passes_through_non_sensitive() -> None:
    """An arbitrary object with a non-sensitive key passes through unchanged."""

    obj = object()
    result = _scrub_value(obj, key="count")
    assert result is obj


def test_scrub_value_sensitive_key_redacts_to_marker() -> None:
    """Any input paired with a sensitive key is redacted to the public marker."""

    for value in ("super-secret", 12345):
        result = _scrub_value(value, key="token")
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
    from ..observability.sink import JsonlRunSink

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
    from ..observability.sink import JsonlRunSink

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
    from ..observability.sink import JsonlRunSink

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


# ---------------------------------------------------------------------------
# contract — LogExtra: typed replacement for the Mapping[str, object] extras boundary
# ---------------------------------------------------------------------------


def test_log_extra_for_logging_materialises_a_plain_dict() -> None:
    """``for_logging`` returns a plain ``dict`` matching the constructed payload."""
    extra = LogExtra({"service_name": "per_modelo_aggregation", "observation_count": 3, "cancelled": False})

    materialised = extra.for_logging()

    assert materialised == {"service_name": "per_modelo_aggregation", "observation_count": 3, "cancelled": False}
    assert isinstance(materialised, dict)


def test_log_extra_rejects_a_non_scalar_value() -> None:
    """A nested mapping is not a loggable scalar; construction must fail loudly."""
    invalid_nested_value: Any = {"inner": "value"}
    with pytest.raises(pydantic.ValidationError):
        LogExtra({"nested": invalid_nested_value})


class _RecordCapturingHandler(logging.Handler):
    """Minimal handler that keeps the raw :class:`logging.LogRecord` instances."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_log_extra_materialised_extra_survives_the_real_logging_pipeline() -> None:
    """The materialised dict flows through the real stdlib logging pipeline's ``extra=``."""
    logger = get_logger("aeat-test_logging.log_extra")
    root_logger = logging.getLogger()
    previous_root_level = root_logger.level
    root_logger.setLevel(logging.INFO)
    handler = _RecordCapturingHandler()
    handler.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    extra = LogExtra({"modelo": "303", "period": "1T", "observation_count": 5})
    try:
        logger.info("ran aggregation", extra=extra.for_logging())
    finally:
        root_logger.removeHandler(handler)
        root_logger.setLevel(previous_root_level)

    assert len(handler.records) == 1
    record = handler.records[0]
    assert record.getMessage() == "ran aggregation"
    record_attributes = vars(record)
    assert record_attributes["modelo"] == "303"
    assert record_attributes["period"] == "1T"
    assert record_attributes["observation_count"] == 5


def test_secret_scrubbing_redacts_a_value_that_merely_contains_a_placeholder() -> None:
    """An inline secret beside a placeholder must not ride out on the placeholder's back.

    A sensitive value is exempted from redaction only when it is nothing but a
    ``%``-format placeholder. A value that merely *contains* one still carries
    its literal secret, so the literal is redacted while the placeholder stays
    in place for the pending ``%``-format pass.
    """
    for case_id, message, args, leaked in (
        ("trailing-placeholder", "token=abc123 %s", ("ok",), "abc123"),
        ("leading-placeholder", "token=%s-abc123", ("ok",), "abc123"),
        ("bare-secret-with-later-arg", "oauth_refresh_token=refresh-123 status=%s", ("ok",), "refresh-123"),
    ):
        rendered = _render_info(message, *args)
        assert leaked not in rendered, case_id
        assert "<redacted>" in rendered, case_id


def test_secret_scrubbing_preserves_placeholder_arity_so_the_record_still_formats() -> None:
    """Redacting around a placeholder must leave every format slot intact.

    ``record.msg`` is scrubbed before ``%``-formatting runs. A scrub that
    consumed a placeholder would leave more args than slots and the stdlib
    would discard the whole line, turning a redaction fix into silent log loss.
    """
    rendered = _render_info("token=abc123 %s", "visible-status")
    assert "abc123" not in rendered
    assert "visible-status" in rendered


def test_secret_scrubbing_leaves_a_pure_placeholder_value_untouched() -> None:
    """A bare ``key=%s`` format string keeps its slot; the arg is scrubbed instead."""
    rendered = _render_info("credential=%s status=%s", "operator-secret", "ok")
    assert "operator-secret" not in rendered
    assert "status=ok" in rendered
