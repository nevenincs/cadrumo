from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core import Period
from ....core.resources import resources
from ....domain.calculations.registry import CasillaId, InputKind, validated_casilla_id
from ....domain.deadlines import EntityType, IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from ....domain.modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ....domain.modelos._codes import ModeloCode
from ....domain.modelos._row_models import Modelo349OperadorRow, ModeloDetailRow
from ....domain.modelos._work_unit import WorkUnit, derive_work_unit_id
from ....tests.registry_observations import registry_grounded_observations
from .._revision_replay_inputs import revision_filing_replay_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 27, 12, 45, tzinfo=UTC)
_BUCKET_ID = "revision-replay-inputs"
_M390_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio",
    surface="_M390_EJERCICIO_CASILLA",
)
_M390_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id(
    "decl.tipo-declaracion",
    surface="_M390_TIPO_DECLARACION_CASILLA",
)


def _work_unit(*, modelo: str, filing_year: int, period_code: str) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=filing_year, period=period_code)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=snapshot.revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=snapshot.revision.id,
        name=f"{modelo}-{filing_year}-{period_code}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _revision(
    work_unit: WorkUnit,
    *,
    input_values_by_casilla_id: dict[CasillaId, str] | None = None,
    binding_overrides: dict[str, str] | None = None,
    relation_overrides: dict[str, str] | None = None,
    casilla_values: dict[CasillaId, Decimal] | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
) -> CalculationRevision:
    inputs = input_values_by_casilla_id or {}
    bindings = binding_overrides or {}
    relations = relation_overrides or {}
    values = casilla_values or {}
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=inputs,
            binding_overrides=bindings,
            relation_overrides=relations,
            casilla_values=values,
            detail_rows=detail_rows,
        ),
        work_unit_id=work_unit.work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id=inputs,
        binding_overrides=bindings,
        relation_overrides=relations,
        detail_rows=detail_rows,
        casilla_values=values,
        observations=registry_grounded_observations(
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            casilla_values=values,
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def test_revision_replay_inputs_include_calculated_informational_casillas() -> None:
    work_unit = _work_unit(modelo="390", filing_year=2025, period_code="0A")
    revision = _revision(
        work_unit,
        casilla_values={
            _M390_EJERCICIO_CASILLA: Decimal("2025"),
            _M390_TIPO_DECLARACION_CASILLA: Decimal("0"),
        },
    )

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert replay_inputs[_M390_EJERCICIO_CASILLA] == "2025"
    assert replay_inputs[_M390_TIPO_DECLARACION_CASILLA] == "0"


def test_revision_replay_inputs_do_not_replay_required_manual_defaults() -> None:
    work_unit = _work_unit(modelo="180", filing_year=2024, period_code="0A")
    snapshot = resources().modelos.authority.snapshot("180", filing_year=2024, period="0A")
    manual_required = next(
        casilla
        for casilla in snapshot.revision.casillas
        if casilla.required and casilla.input_kind == InputKind.MANUAL
    )
    revision = _revision(
        work_unit,
        casilla_values={manual_required.id: Decimal("0")},
    )

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert manual_required.id not in replay_inputs


def test_revision_replay_inputs_zero_not_applicable_m100_pagos_relations_for_salaried_profile() -> None:
    work_unit = _work_unit(modelo="100", filing_year=2025, period_code="0A")
    revision = _revision(
        work_unit,
        relation_overrides={"renta-2025-rel-130-pagos-fraccionados": "123.45"},
    )
    profile = TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.TRABAJO}),
        iva_regime=IVARegime.GENERAL,
    )

    replay_inputs = revision_filing_replay_inputs(
        revision=revision,
        work_unit=work_unit,
        workflow_profile=profile,
    )

    assert replay_inputs["renta-2025-rel-130-pagos-fraccionados"] == "123.45"
    assert replay_inputs["renta-2025-rel-131-pagos-fraccionados"] == "0"


def test_revision_replay_inputs_keep_applicable_m100_pagos_relation_unresolved() -> None:
    work_unit = _work_unit(modelo="100", filing_year=2025, period_code="0A")
    revision = _revision(work_unit)
    profile = TaxpayerProfile(
        tax_id="12345678Z",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
    )

    replay_inputs = revision_filing_replay_inputs(
        revision=revision,
        work_unit=work_unit,
        workflow_profile=profile,
    )

    assert "renta-2025-rel-130-pagos-fraccionados" not in replay_inputs
    assert replay_inputs["renta-2025-rel-131-pagos-fraccionados"] == "0"


def test_revision_replay_inputs_strip_m349_country_prefix_from_export_nif_subfield() -> None:
    work_unit = _work_unit(modelo="349", filing_year=2026, period_code="1T")
    revision = _revision(
        work_unit,
        detail_rows=(
            Modelo349OperadorRow(
                codigo_pais="DE",
                nif_comunitario="DE123456789",
                razon_social="ALEMAN GMBH",
                clave_operacion="E",
                importe=Decimal("1500.00"),
            ),
        ),
    )

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert replay_inputs["iva-349-operador-row-codigo-pais"] == {"1": "DE"}
    assert replay_inputs["iva-349-operador-row-nif"] == {"1": "123456789"}
