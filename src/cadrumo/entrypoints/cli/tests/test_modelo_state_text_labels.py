"""Modelo renderer state labels keep text output operator-readable."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core import Period
from ....core.config import override_settings
from ....domain.modelos import ModeloCode, WorkUnit, WorkUnitState, derive_work_unit_id
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from .._modelo_rendering import (
    calculation_observation_lines,
    calculation_revision_lines,
    calculation_revision_payload,
    work_unit_lines,
    work_unit_list_lines,
    work_unit_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_NOW = datetime(2026, 7, 2, 10, 30, tzinfo=UTC)
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_REVISION_ID = "2019-y-siguientes"
_PERIOD = Period.from_year_and_code(2026, "1T")
_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id=_BUCKET_ID,
    modelo="130",
    filing_year=2026,
    period=_PERIOD,
    revision_id=_REVISION_ID,
)


def _draft_revision() -> CalculationRevision:
    calculation_revision_id = derive_calculation_revision_id(
        work_unit_id=_WORK_UNIT_ID,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=None,
        source_provenance=(),
    )
    return CalculationRevision(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=_WORK_UNIT_ID,
        state=CalculationRevisionState.BORRADOR,
        created_at=_NOW,
        updated_at=_NOW,
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _verified_revision() -> CalculationRevision:
    return CalculationRevision(
        calculation_revision_id=_draft_revision().calculation_revision_id,
        work_unit_id=_WORK_UNIT_ID,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        created_at=_NOW,
        updated_at=_NOW,
        verified_at=_NOW,
        verified_by="operator",
        filing_instance_evidence=None,
        source_provenance=(),
    )


def _work_unit(*, filed_revision_id: str | None = None) -> WorkUnit:
    return WorkUnit(
        work_unit_id=_WORK_UNIT_ID,
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode("130"),
        filing_year=2026,
        period=_PERIOD,
        revision_id=_REVISION_ID,
        name="130-2026-1T",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=_draft_revision().calculation_revision_id,
        filed_calculation_revision_id=filed_revision_id,
    )


def test_calculation_revision_text_lines_render_human_state_label_but_payload_keeps_token() -> None:
    revision = _verified_revision()

    with override_settings(cadrumo_output_language="en"):
        lines = calculation_revision_lines(revision)
        observation_lines = calculation_observation_lines(revision)

    assert f"state\t{CalculationRevisionState.VERIFICADO_COMPLETO.value}" not in lines
    assert "state\tverified complete" in lines
    assert f"state\t{CalculationRevisionState.VERIFICADO_COMPLETO.value}" not in observation_lines
    assert "state\tverified complete" in observation_lines
    assert calculation_revision_payload(revision).state == CalculationRevisionState.VERIFICADO_COMPLETO.value


def test_work_unit_text_lines_render_human_state_label_but_payload_keeps_token() -> None:
    unit = _work_unit()

    with override_settings(cadrumo_output_language="en"):
        lines = work_unit_lines(unit)
        list_lines = work_unit_list_lines((unit,), include_discarded=False)

    assert f"state\t{CalculationRevisionState.BORRADOR.value}" not in lines
    assert "state\tdraft" in lines
    assert "\tdraft\t" in "\n".join(list_lines)
    assert CalculationRevisionState.BORRADOR.value not in "\n".join(list_lines)
    assert work_unit_payload(unit).state == WorkUnitState.BORRADOR.value


def test_filed_work_unit_text_state_uses_profile_language_without_changing_payload() -> None:
    revision = _verified_revision()
    unit = _work_unit(filed_revision_id=revision.calculation_revision_id)

    with override_settings(cadrumo_output_language="hu"):
        lines = work_unit_lines(unit)

    assert "state\tBeadva" in lines
    assert f"state\t{CalculationRevisionState.PRESENTADO.value}" not in lines
    assert work_unit_payload(unit).state == CalculationRevisionState.PRESENTADO.value
