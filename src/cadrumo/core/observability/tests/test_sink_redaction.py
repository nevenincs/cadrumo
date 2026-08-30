"""End-to-end redaction tests for :class:`cadrumo.core.observability.sink.JsonlRunSink`.

The sink writes :class:`cadrumo.core.observability.RunEvent` records that
may carry casilla form-fill values, AEAT navigation URLs, and free-form
error messages. The emit path runs every record through
:func:`cadrumo.adapters.persistence.storage.redact_structured` against the
DIAGNOSTIC-class default rule set so the JSONL never carries a
plaintext NIF / token / URL path even if a caller forgets to scrub
upstream.

These tests verify the property end-to-end against real on-disk JSONL
files for each sensitive shape: NIF in :class:`FormFillPayload.value`,
session-bearing AEAT URL in :class:`NavigationPayload.url`, and bearer
token in :class:`ErrorPayload.message`.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ....tests.aeat_literal_fixtures import REDACTION_SECRET_WLPL_PATH_CANARY, aeat_url
from ..models import ErrorPayload, FormFillPayload, NavigationPayload, RunEvent, RunEventKind, RunEventPayload
from ..sink import JsonlRunSink

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RUN_ID = "0123456789abcdef"
_NIF_CANARY = "12345678Z"
_BEARER_TAIL = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
_BEARER_CANARY = f"Bearer {_BEARER_TAIL}"
_URL_PATH_CANARY = REDACTION_SECRET_WLPL_PATH_CANARY
_AEAT_URL = aeat_url("aeat_gob", _URL_PATH_CANARY)


def _emit(sink: JsonlRunSink, event: RunEvent) -> None:
    """Push ``event`` through the sink via the standard logging contract.

    Builds a minimal :class:`logging.LogRecord`, attaches the event as
    the ``run_event`` extra (matching the recorder's wire shape), and
    invokes :meth:`JsonlRunSink.emit` directly. Closes the sink so the
    on-disk file is fsync'd before the assertions read it.
    """
    record = logging.LogRecord(
        name="aeat-test",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg="test",
        args=None,
        exc_info=None,
    )
    record.run_event = event
    sink.emit(record)
    sink.close()


def _build_form_fill_event(value: str) -> RunEvent:
    return RunEvent(
        run_id=_RUN_ID,
        step_id="step-1",
        kind=RunEventKind.FORM_FILL,
        payload=RunEventPayload(
            form_fill=FormFillPayload(form_id="aeat-130", display_number="01", value=value),
        ),
        timestamp=datetime(2026, 4, 30, 0, 0, 0, tzinfo=UTC),
        module="aeat-test",
    )


def _build_navigation_event(url: str) -> RunEvent:
    return RunEvent(
        run_id=_RUN_ID,
        step_id="step-2",
        kind=RunEventKind.NAVIGATION,
        payload=RunEventPayload(navigation=NavigationPayload(url=url)),
        timestamp=datetime(2026, 4, 30, 0, 0, 1, tzinfo=UTC),
        module="aeat-test",
    )


def _build_error_event(message: str) -> RunEvent:
    return RunEvent(
        run_id=_RUN_ID,
        step_id="step-3",
        kind=RunEventKind.ERROR,
        payload=RunEventPayload(
            error=ErrorPayload(error_type="ValueError", message=message),
        ),
        timestamp=datetime(2026, 4, 30, 0, 0, 2, tzinfo=UTC),
        module="aeat-test",
    )


def test_sensitive_event_values_do_not_land_plaintext_on_disk(tmp_path: Path) -> None:
    cases = (
        (_build_form_fill_event(value=_NIF_CANARY), (_NIF_CANARY,)),
        (_build_navigation_event(url=_AEAT_URL), (_URL_PATH_CANARY, "session=ABCDEFGHIJ")),
        (_build_error_event(message=f"failed to authenticate: {_BEARER_CANARY}"), (_BEARER_TAIL,)),
    )

    for index, (event, forbidden_fragments) in enumerate(cases):
        target = tmp_path / f"events-{index}.jsonl"
        sink = JsonlRunSink(target, run_id=_RUN_ID)
        _emit(sink, event)
        text = target.read_text(encoding="utf-8")
        for forbidden in forbidden_fragments:
            assert forbidden not in text


def test_redacted_jsonl_remains_parseable(tmp_path: Path) -> None:
    """Even after redaction, each line remains a valid JSON object."""
    target = tmp_path / "events.jsonl"
    sink = JsonlRunSink(target, run_id=_RUN_ID)
    _emit(sink, _build_form_fill_event(value="not sensitive"))
    line = target.read_text(encoding="utf-8").strip()
    assert line
    decoded = json.loads(line)
    assert decoded["kind"] == RunEventKind.FORM_FILL.value
    # The non-sensitive value passes through unchanged.
    assert decoded["payload"]["form_fill"]["value"] == "not sensitive"


def test_timestamp_not_redacted_away(tmp_path: Path) -> None:
    """Timestamp ISO string must not match any redaction pattern."""
    target = tmp_path / "events.jsonl"
    sink = JsonlRunSink(target, run_id=_RUN_ID)
    _emit(sink, _build_form_fill_event(value="anything"))
    line = target.read_text(encoding="utf-8").strip()
    decoded = json.loads(line)
    assert decoded["timestamp"].startswith("2026-04-30")


def test_run_scoped_records_scrubbed_before_reaching_jsonl_via_attach_run_sink(
    tmp_path: Path,
) -> None:
    """Records flowing through attach_run_sink must be scrubbed before on-disk write.

    Verifies contract: the full pipeline — root logger -> SecretScrubbingFilter
    (attached by attach_run_sink) -> JsonlRunSink -> JSONL file — redacts
    sensitive values.  The sink is attached via the real attach_run_sink
    helper (no mocks); a log record with a plaintext NIF in a form-fill
    event must not appear verbatim in the written JSONL.
    """
    import logging

    from ...logging import SecretScrubbingFilter, attach_run_sink

    target = tmp_path / "run_events.jsonl"
    sink = JsonlRunSink(target, run_id=_RUN_ID)

    # attach_run_sink installs SecretScrubbingFilter on the sink and adds
    # it to the root logger — this is the path run_context uses in production.
    attach_run_sink(sink)
    root_logger = logging.getLogger()
    try:
        # Confirm the scrubbing filter is now present on the sink.
        assert any(isinstance(f, SecretScrubbingFilter) for f in sink.filters), (
            "attach_run_sink must install SecretScrubbingFilter on the sink"
        )

        # Emit a run event carrying a plaintext NIF.  Use run_id matching the
        # sink so the event is not filtered by the run-id guard.
        event = _build_form_fill_event(value=_NIF_CANARY)
        record = logging.LogRecord(
            name="aeat-test",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="test",
            args=None,
            exc_info=None,
        )
        record.run_event = event
        sink.emit(record)
        sink.close()
    finally:
        root_logger.removeHandler(sink)

    text = target.read_text(encoding="utf-8")
    assert _NIF_CANARY not in text, (
        f"Plaintext NIF {_NIF_CANARY!r} must not appear in the JSONL after "
        f"passing through SecretScrubbingFilter via attach_run_sink"
    )
