"""Tests for the run-context logging filter and stderr suppression filter.

Two related concerns:

* :class:`TestRunContextLoggingFilter` verifies that the
  :func:`aeat.core.logging.get_logger` factory stamps ``run_id`` and
  ``step_id`` attributes onto every :class:`logging.LogRecord`, both
  inside and outside an active
  :func:`aeat.core.observability.run_context`.
* :class:`TestStderrRunEventFilter` verifies that the default stderr
  handler installed by :mod:`aeat.core.logging` drops records that
  carry a ``run_event`` extra — without this, every observability event
  would also print on stderr, spamming long workflows.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import override

import pytest

from ...config import override_settings
from ...logging import get_logger
from .. import run_context

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _CaptureHandler(logging.Handler):
    """Real :class:`logging.Handler` that appends every record it sees.

    Used to assert against the actual :class:`logging.LogRecord`
    attributes the framework's record factory installs, rather than
    against a captured string representation.
    """

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestRunContextLoggingFilter:
    def test_attributes_present_inside_and_outside_run_context(
        self,
        tmp_path: Path,
    ) -> None:
        with override_settings(aeat_runs_dir=str(tmp_path)):
            logger = get_logger("aeat.core.observability.test_logging_filter")
            capture = _CaptureHandler()
            logging.getLogger().addHandler(capture)
            try:
                logger.info("outside")
                with run_context(entrypoint="aeat test", arguments=()) as info:
                    logger.info("inside")
                    inside_run_id = info.run_id
            finally:
                logging.getLogger().removeHandler(capture)

            outside_records = [r for r in capture.records if r.getMessage() == "outside"]
            inside_records = [r for r in capture.records if r.getMessage() == "inside"]
            assert outside_records, "outside log record was not captured"
            assert inside_records, "inside log record was not captured"
            for record in outside_records:
                assert getattr(record, "run_id", None) == ""
                assert getattr(record, "step_id", None) == ""
            for record in inside_records:
                assert getattr(record, "run_id", None) == inside_run_id
                assert getattr(record, "step_id", None) != ""


class TestStderrRunEventFilter:
    """The default stderr handler must drop records carrying ``run_event``.

    :func:`aeat.core.observability.record_event` logs at INFO through
    ``aeat.core.observability``, which propagates to the root stderr
    handler. Without the filter, every event would print on stderr —
    spamming long workflows. The filter drops only records that carry a
    ``run_event`` extra; plain log lines still reach stderr.
    """

    def test_filter_drops_run_event_records(self) -> None:
        from ...logging import _DropRunEventFilter

        filt = _DropRunEventFilter()
        plain = logging.LogRecord(
            name="aeat.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="plain",
            args=None,
            exc_info=None,
        )
        assert filt.filter(plain) is True, "plain records must pass"

        event = logging.LogRecord(
            name="aeat.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=0,
            msg="run event",
            args=None,
            exc_info=None,
        )
        event.run_event = object()  # sentinel — any truthy value qualifies
        assert filt.filter(event) is False, "run_event records must be dropped"

    def test_events_still_reach_jsonl_sink_end_to_end(
        self,
        tmp_path: Path,
    ) -> None:
        """The filter must NOT accidentally drop events from the sink."""
        from .. import GenericPayload, RunEventKind, RunEventPayload, load_events, record_event

        with override_settings(aeat_runs_dir=str(tmp_path)):
            with run_context(entrypoint="aeat test stderr-filter", arguments=()) as info:
                record_event(
                    RunEventKind.NAVIGATION,
                    payload=RunEventPayload(generic=GenericPayload(fields=(("k", "v"),))),
                )
            events = load_events(info.run_id)
            # STEP_START + NAVIGATION + STEP_END = 3 events.
            assert len(events) == 3
            kinds = {e.kind for e in events}
            assert RunEventKind.NAVIGATION in kinds
