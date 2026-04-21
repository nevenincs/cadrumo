"""Verify the run-context logging filter injects run_id / step_id attributes."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from ..logging import get_logger
from . import run_context

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


class _CaptureHandler(logging.Handler):
    """Real logging handler that appends every record it sees."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestRunContextLoggingFilter:
    def test_attributes_present_inside_and_outside_run_context(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path))
        logger = get_logger("aeat.observability.test_logging_filter")
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
