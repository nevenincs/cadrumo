"""Strict payload checks for ``WorkAmendWizardResult``.

``WorkAmendWizardResult`` used to redeclare the amendment kind/reason,
filing coordinates, actor, timestamps, status, supersession, evidence, and
submission posture as bare strings instead of projecting the canonical
``ModeloRecordPayload`` (:class:`~ModeloRecord`) and
``CalculationRevisionAmendmentKind``. It now derives from
``ModeloRecordPayload`` directly, so a malformed field is refused rather than
accepted.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ....domain.modelos.calculation_revision import CalculationRevisionAmendmentKind
from ....domain.modelos.filing_record import ModeloRecordStatus
from .._modelo_amend_wizard_payloads import WorkAmendWizardResult

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _valid_kwargs(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "filing_record_id": "a" * 64,
        "work_unit_id": "b" * 64,
        "calculation_revision_id": "c" * 64,
        "bucket_id": "bucket-1",
        "modelo": "303",
        "filing_year": 2026,
        "period": Period.from_year_and_code(2026, "1T"),
        "filed_at": datetime(2026, 4, 1, tzinfo=UTC),
        "filed_by": "operator",
        "notes": None,
        "aeat_accepted": False,
        "status": ModeloRecordStatus.VIGENTE,
        "superseded_at": None,
        "superseded_by_filing_record_id": None,
        "external_evidence": None,
        "amends_filing_record_id": "d" * 64,
        "kind": "internal_filing",
        "live_submission": False,
        "operation": "modelo.work.amend_wizard",
        "amendment_kind": CalculationRevisionAmendmentKind.COMPLEMENTARIA,
        "amendment_reason": "corrected an under-reported base",
        # Required but nullable, so every construction site must state it: this
        # row is a COMPLEMENTARIA, not an M303 rectificativa, so it has no motive.
        "m303_rectificativa_motive": None,
        "corrected_casillas": (),
    }
    base.update(overrides)
    return base


def test_work_amend_wizard_result_round_trips_valid_row() -> None:
    result = WorkAmendWizardResult.model_validate(_valid_kwargs())

    assert result.amendment_kind is CalculationRevisionAmendmentKind.COMPLEMENTARIA
    assert result.status is ModeloRecordStatus.VIGENTE
    assert result.kind == "internal_filing"


@pytest.mark.parametrize(
    ("field", "bad_value"),
    (
        ("amendment_kind", "bogus"),
        ("amendment_reason", ""),
        ("filed_by", ""),
        ("filing_year", 0),
        ("filed_at", "not-a-timestamp"),
        ("notes", "x" * 501),
        ("status", "bogus"),
        ("kind", "bogus"),
        ("live_submission", "yes"),
        ("amends_filing_record_id", "not-a-hex-64-id"),
    ),
)
def test_work_amend_wizard_result_refuses_malformed_field(field: str, bad_value: object) -> None:
    """A malformed kind/reason/timestamp/status or an oversized notes string is refused.

    A permissive bare-``str`` shell (the defect this finding reported) would
    have accepted every one of these.
    """
    with pytest.raises(ValidationError):
        WorkAmendWizardResult.model_validate(_valid_kwargs(**{field: bad_value}))
