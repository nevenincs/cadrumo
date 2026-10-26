"""Pin the M136 2023 Q4 effective-close boundary through the application path."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest

from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..work_plazo import modelo_work_deadline_posture

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "d" * 64


def test_m136_2023_q4_posture_uses_january_22_effective_close(
    operation: PinnedAuthorityOperation,
) -> None:
    period = Period.from_year_and_code(2023, "4T")
    selected_revision = operation.revision_for_context("136", filing_year=2023, period=period.registry_token)
    revision_id = selected_revision.id
    created_at = datetime(2023, 1, 1, tzinfo=UTC)
    work_unit = WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo="136",
            filing_year=2023,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("136"),
        filing_year=2023,
        period=period,
        revision_id=revision_id,
        name="136-2023-4T",
        created_at=created_at,
        updated_at=created_at,
    )

    before_effective_close = modelo_work_deadline_posture(
        work_unit,
        reference_on=date(2024, 1, 21),
        operation=operation,
    )
    on_effective_close = modelo_work_deadline_posture(
        work_unit,
        reference_on=date(2024, 1, 22),
        operation=operation,
    )
    after_effective_close = modelo_work_deadline_posture(
        work_unit,
        reference_on=date(2024, 1, 23),
        operation=operation,
    )

    assert before_effective_close is not None
    assert before_effective_close.nominal_closes_on == date(2024, 1, 20)
    assert before_effective_close.closes_on == date(2024, 1, 22)
    assert before_effective_close.days_remaining == 1
    assert before_effective_close.days_overdue is None
    assert before_effective_close.conditional_recargo_preview is None

    assert on_effective_close is not None
    assert on_effective_close.nominal_closes_on == date(2024, 1, 20)
    assert on_effective_close.closes_on == date(2024, 1, 22)
    assert on_effective_close.days_remaining == 0
    assert on_effective_close.days_overdue is None
    assert on_effective_close.conditional_recargo_preview is None

    assert after_effective_close is not None
    assert after_effective_close.nominal_closes_on == date(2024, 1, 20)
    assert after_effective_close.closes_on == date(2024, 1, 22)
    assert after_effective_close.days_remaining is None
    assert after_effective_close.days_overdue == 1
