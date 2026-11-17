"""A worker's progress report may mark settlements only among the operations it reports."""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from ..worker_authorization import WorkerOperationsAdvanced

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RUNNING, _SETTLED = "a" * 64, "b" * 64


def test_a_report_marks_which_of_its_operations_settled() -> None:
    report = WorkerOperationsAdvanced(request_id=uuid4(), operation_ids=(_RUNNING, _SETTLED), settled=(_SETTLED,))

    assert WorkerOperationsAdvanced.model_validate_json(report.model_dump_json()).settled == (_SETTLED,)


def test_a_report_without_settlements_reads_as_none_settled() -> None:
    report = WorkerOperationsAdvanced(request_id=uuid4(), operation_ids=(_RUNNING,))

    assert report.settled == ()


def test_a_settlement_outside_the_report_is_refused() -> None:
    with pytest.raises(ValidationError, match="one of the reported operations"):
        WorkerOperationsAdvanced(request_id=uuid4(), operation_ids=(_RUNNING,), settled=(_SETTLED,))
