"""Modelo renderer state labels keep text output operator-readable."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....core.config import override_settings
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope, revision_covering
from ....domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.work_unit import WorkUnit, WorkUnitState, derive_work_unit_id
from ..modelo_rendering import (
    work_unit_lines,
    work_unit_list_lines,
    work_unit_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_YEAR = filing_year_envelope().horizon

_NOW = datetime(1980, 7, 2, 10, 30, tzinfo=UTC)
_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_REVISION_ID = str(revision_covering("130", _YEAR).id)
_PERIOD = Period.from_year_and_code(_YEAR, "1T")
_REGISTRY_SNAPSHOT_REF = RegistrySnapshotRef(
    modelo="130",
    revision_id=_REVISION_ID,
    modelo_year=_YEAR,
    period="1T",
)
_WORK_UNIT_ID = derive_work_unit_id(
    bucket_id=_BUCKET_ID,
    modelo="130",
    filing_year=_YEAR,
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
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
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
        registry_snapshot_ref=_REGISTRY_SNAPSHOT_REF,
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
        filing_year=_YEAR,
        period=_PERIOD,
        revision_id=_REVISION_ID,
        name=f"130-{_YEAR}-1T",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=_draft_revision().calculation_revision_id,
        filed_calculation_revision_id=filed_revision_id,
    )


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

    assert "state\tBenyújtottként rögzítve" in lines
    assert f"state\t{CalculationRevisionState.PRESENTADO.value}" not in lines
    assert work_unit_payload(unit).state == CalculationRevisionState.PRESENTADO.value
