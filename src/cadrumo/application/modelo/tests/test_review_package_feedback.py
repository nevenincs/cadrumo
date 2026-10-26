"""Inward validation rules for review-package feedback payloads."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.casilla_id import validated_casilla_id
from ....core.period import Period
from ....domain.modelos.calculation_revision import derive_calculation_revision_id
from ....domain.modelos.work_unit import derive_work_unit_id
from ..review_package_feedback import build_feedback_package

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 7, 4, 12, 0, tzinfo=UTC)
_BASE_CASILLA = validated_casilla_id("base", surface="test_review_package_feedback")
_CUOTA_CASILLA = validated_casilla_id("cuota", surface="test_review_package_feedback")
_PLACEHOLDER_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id="originator-bucket",
    modelo="303",
    filing_year=2026,
    period=Period.from_year_and_code(2026, "1T"),
    revision_id="feedback-placeholder-revision",
)
_PLACEHOLDER_REVISION_ID = derive_calculation_revision_id(
    work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
    input_values_by_casilla_id={_BASE_CASILLA: "0.00"},
    binding_overrides={},
    casilla_values={_CUOTA_CASILLA: Decimal("0.00")},
    source_transaction_ids=(),
    filing_instance_evidence=None,
    source_provenance=(),
)


@pytest.mark.parametrize(
    "submitted_at",
    (
        pytest.param(datetime(2026, 7, 3, 12, 0), id="naive"),
        pytest.param(datetime(2026, 7, 3, 14, 0, tzinfo=timezone(timedelta(hours=2))), id="non-utc"),
    ),
)
def test_build_feedback_package_refuses_a_naive_or_non_utc_submitted_at(submitted_at: datetime) -> None:
    """A feedback document must carry one explicit UTC ``submitted_at`` instant."""
    with pytest.raises(ValidationError, match="datetime must be"):
        build_feedback_package(
            bucket_id="originator-bucket",
            work_unit_id=_PLACEHOLDER_WORK_UNIT_ID,
            calculation_revision_id=_PLACEHOLDER_REVISION_ID,
            note="approved",
            submitted_by="accountant",
            submitted_at=submitted_at,
        )
