"""Owning contract probes extracted from native integration scenarios."""

from __future__ import annotations

from datetime import date

import pytest

from cadrumo.application.modelo.work_plazo import ModeloWorkDeadlinePosture
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.tests.published_authority import published_legal_reference
from cadrumo.domain.deadlines.festivos import DeadlineHolidayCoverage
from cadrumo.entrypoints.cli._modelo_rendering import _work_unit_deadline_output_from_posture

_RECARGO_LEGAL_REF = "ley-58-2003:art-27.2"

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_overdue_posture_fallback_emits_null_preview_without_rate_wording(
    *,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """The real renderer emits a null preview and no displayed-rate warning."""
    deadline, notices = _work_unit_deadline_output_from_posture(
        ModeloWorkDeadlinePosture(
            closes_on=date(2026, 1, 30),
            nominal_closes_on=date(2026, 1, 30),
            holiday_coverage=DeadlineHolidayCoverage.NATIONAL_ONLY,
            days_overdue=1,
        ),
    )

    assert deadline is not None
    assert deadline.days_overdue == 1
    assert deadline.conditional_recargo_preview is None
    assert deadline.model_dump(mode="json")["conditional_recargo_preview"] is None
    assert len(notices) == 1
    context = notices[0].context
    assert context is not None
    assert context["legal_refs"] == _RECARGO_LEGAL_REF
    assert context["article_27_assessment_status"] == "unassessed"
    message = notices[0].message.lower()
    assert "displayed rate" not in message
    assert "previsualización no evaluada" not in message

    legal_entry = published_legal_reference(_RECARGO_LEGAL_REF)
    assert legal_entry.corpus_ref
    assert legal_entry.required_text
