"""A failed operation without a refusal code names its exception type and code frames in the replay's error."""

from __future__ import annotations

import logging

import pytest

from cadrumo.application.operations import supervisor_execution

from .persona_materialisation import _failure_frames

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_the_supervisors_failure_record_is_kept_per_operation() -> None:
    logger = logging.getLogger(supervisor_execution.__name__)
    with _failure_frames() as failures:
        logger.error(
            "operation failed definition=%s operation=%s diagnostic_ref=%s exception_type=%s "
            "raising_frame=%s application_frame=%s",
            "modelo.work.calculate",
            "op-1",
            "ref",
            "KeyError",
            "calc.py:10",
            "app.py:20",
        )
        logger.error("operation refused definition=%s operation=%s", "modelo.work.calculate", "op-2")
    assert failures.frames == {"op-1": "KeyError raised at calc.py:10 (application frame app.py:20)"}


def test_the_handler_is_removed_when_the_settlement_ends() -> None:
    logger = logging.getLogger(supervisor_execution.__name__)
    with _failure_frames() as failures:
        pass
    assert failures not in logger.handlers
