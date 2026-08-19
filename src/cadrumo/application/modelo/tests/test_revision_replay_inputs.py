from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....application.filing import ModeloOperatorProfile, build_draft, build_runtime_schema_provider
from ....core import CasillaId, Period, validated_casilla_id
from ....domain.calculations.registry import InputKind, select_revision
from ....domain.deadlines import EntityType, IrpfEstimationRegime, IrpfIncomeCategory, IVARegime, TaxpayerProfile
from ....domain.modelos import (
    CalculationRevision,
    CalculationRevisionState,
    Modelo232VinculadaRow,
    Modelo349OperadorRow,
    Modelo349RectificacionRow,
    ModeloCode,
    ModeloDetailRow,
    WorkUnit,
    derive_calculation_revision_id,
    derive_work_unit_id,
)
from ....tests.registry_observations import registry_grounded_observations
from ....tests.registry_tree import bundled_registry_tree
from .._revision_replay_inputs import revision_filing_replay_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CLOCK = datetime(2026, 6, 27, 12, 45, tzinfo=UTC)
_BUCKET_ID = "e6d780ee-3271-4087-a705-7cc7e97010c9"  # was 'revision-replay-inputs'
_M390_EJERCICIO_CASILLA: CasillaId = validated_casilla_id(
    "decl.ejercicio",
    surface="_M390_EJERCICIO_CASILLA",
)
_M390_TIPO_DECLARACION_CASILLA: CasillaId = validated_casilla_id(
    "decl.tipo-declaracion",
    surface="_M390_TIPO_DECLARACION_CASILLA",
)
_M100_RETENCIONES_TRABAJO_CASILLA: CasillaId = validated_casilla_id(
    "0596",
    surface="_M100_RETENCIONES_TRABAJO_CASILLA",
)
_M100_SALARY_CERT_RETENCIONES_BINDING = "renta-2024-certificado-trabajo-retenciones"
_M100_M111_RETENCIONES_BINDING = "renta-2024-modelo-111-retenciones-periodicas"


def _resolved_revision(*, modelo: str, filing_year: int, period_code: str):
    modelos, _catalogues = bundled_registry_tree()
    modelo_definition = next(candidate for candidate in modelos if candidate.id == modelo)
    return select_revision(modelo_definition, filing_year=filing_year, period=period_code)


def _work_unit(*, modelo: str, filing_year: int, period_code: str) -> WorkUnit:
    period = Period.from_year_and_code(filing_year, period_code)
    revision = _resolved_revision(modelo=modelo, filing_year=filing_year, period_code=period_code)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=_BUCKET_ID,
            modelo=modelo,
            filing_year=filing_year,
            period=period,
            revision_id=revision.id,
        ),
        bucket_id=_BUCKET_ID,
        modelo=ModeloCode(modelo),
        filing_year=filing_year,
        period=period,
        revision_id=revision.id,
        name=f"{modelo}-{filing_year}-{period_code}",
        created_at=_CLOCK,
        updated_at=_CLOCK,
    )


def _revision(
    work_unit: WorkUnit,
    *,
    state: CalculationRevisionState = CalculationRevisionState.BORRADOR,
    input_values_by_casilla_id: dict[CasillaId, str] | None = None,
    binding_overrides: dict[str, str] | None = None,
    row_binding_values: dict[str, dict[str, str]] | None = None,
    relation_overrides: dict[str, str] | None = None,
    casilla_values: dict[CasillaId, Decimal] | None = None,
    detail_rows: tuple[ModeloDetailRow, ...] = (),
) -> CalculationRevision:
    inputs = input_values_by_casilla_id or {}
    bindings = binding_overrides or {}
    row_bindings = row_binding_values or {}
    relations = relation_overrides or {}
    values = casilla_values or {}
    return CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit.work_unit_id,
            input_values_by_casilla_id=inputs,
            binding_overrides=bindings,
            row_binding_values=row_bindings,
            relation_overrides=relations,
            casilla_values=values,
            detail_rows=detail_rows,
            filing_instance_evidence=None,
        ),
        work_unit_id=work_unit.work_unit_id,
        state=state,
        input_values_by_casilla_id=inputs,
        binding_overrides=bindings,
        row_binding_values=row_bindings,
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
        verified_at=_CLOCK if state is not CalculationRevisionState.BORRADOR else None,
        verified_by="operator" if state is not CalculationRevisionState.BORRADOR else None,
        filing_instance_evidence=None,
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
    revision = _resolved_revision(modelo="180", filing_year=2024, period_code="0A")
    manual_required = next(
        casilla for casilla in revision.casillas if casilla.required and casilla.input_kind == InputKind.MANUAL
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


def test_revision_replay_inputs_recover_salary_certificate_binding_for_m100_2024_0596() -> None:
    work_unit = _work_unit(modelo="100", filing_year=2024, period_code="0A")
    revision = _revision(
        work_unit,
        input_values_by_casilla_id={_M100_RETENCIONES_TRABAJO_CASILLA: "4500"},
        casilla_values={_M100_RETENCIONES_TRABAJO_CASILLA: Decimal("4500")},
    )

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert replay_inputs[_M100_SALARY_CERT_RETENCIONES_BINDING] == "4500"
    assert _M100_RETENCIONES_TRABAJO_CASILLA not in replay_inputs
    assert _M100_M111_RETENCIONES_BINDING not in replay_inputs


def test_revision_replay_inputs_recover_m100_2024_0596_from_verified_revision_values() -> None:
    work_unit = _work_unit(modelo="100", filing_year=2024, period_code="0A")
    revision = _revision(
        work_unit,
        state=CalculationRevisionState.VERIFICADO_COMPLETO,
        relation_overrides={
            "renta-2024-rel-130-pagos-fraccionados": "1520.00",
            "renta-2024-rel-131-pagos-fraccionados": "0",
        },
        casilla_values={
            _M100_RETENCIONES_TRABAJO_CASILLA: Decimal("4500.00"),
            "0604": Decimal("1520.00"),
            "0609": Decimal("6020.00"),
        },
    )

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert replay_inputs[_M100_SALARY_CERT_RETENCIONES_BINDING] == "4500"
    assert replay_inputs["renta-2024-rel-130-pagos-fraccionados"] == "1520.00"
    assert _M100_RETENCIONES_TRABAJO_CASILLA not in replay_inputs
    assert _M100_M111_RETENCIONES_BINDING not in replay_inputs


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


def test_revision_replay_inputs_project_m349_rectification_row_bindings() -> None:
    work_unit = _work_unit(modelo="349", filing_year=2026, period_code="1T")
    revision = _revision(
        work_unit,
        detail_rows=(
            Modelo349RectificacionRow(
                codigo_pais="DE",
                nif_comunitario="DE123456789",
                razon_social="ALEMAN GMBH",
                clave_operacion="E",
                ejercicio="2025",
                periodo="2T",
                base_rectificada=Decimal("1100.00"),
                base_anterior=Decimal("1000.00"),
            ),
        ),
    )

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert replay_inputs["iva-349-rectificacion-row-codigo-pais"] == {"1": "DE"}
    assert replay_inputs["iva-349-rectificacion-row-nif"] == {"1": "123456789"}
    assert replay_inputs["iva-349-rectificacion-row-apellidos"] == {"1": "ALEMAN GMBH"}
    assert replay_inputs["iva-349-rectificacion-row-clave"] == {"1": "E"}
    assert replay_inputs["iva-349-rectificacion-row-ejercicio"] == {"1": "2025"}
    assert replay_inputs["iva-349-rectificacion-row-periodo"] == {"1": "2T"}
    assert replay_inputs["iva-349-rectificacion-row-base-rectificada"] == {"1": Decimal("1100.00")}
    assert replay_inputs["iva-349-rectificacion-row-base-anterior"] == {"1": Decimal("1000.00")}


def test_revision_replay_inputs_project_m720_row_binding_values_into_draft_rows() -> None:
    work_unit = _work_unit(modelo="720", filing_year=2025, period_code="0A")
    row_binding_values = {
        "modelo-720-asset-row-class": {"1": "C"},
        "modelo-720-asset-row-country": {"1": "AD"},
        "modelo-720-asset-row-currency": {"1": "EUR"},
        "modelo-720-asset-row-identifier": {"1": "AD-ACCOUNT-001"},
        "modelo-720-asset-row-acquisition-date": {"1": "2020-01-15"},
        "modelo-720-asset-row-valuation": {"1": "40000"},
    }
    revision = _revision(work_unit, row_binding_values=row_binding_values)

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)
    draft = build_draft(
        modelo="720",
        period=work_unit.period,
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="TEST DECLARANTE"),
        inputs=replay_inputs,
        schema_provider=build_runtime_schema_provider(
            modelos=("720",),
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        ),
    )

    assert revision.binding_overrides == {}
    assert revision.row_binding_values == row_binding_values
    assert replay_inputs["modelo-720-asset-row-class"] == {"1": "C"}
    assert "modelo-720-asset-row-class:1" not in replay_inputs
    draft_rows = {
        (value.binding_id, value.row_index): value.value
        for value in draft.binding_values
        if value.binding_id.startswith("modelo-720-asset-row-")
    }
    assert draft_rows[("modelo-720-asset-row-class", 1)] == "C"
    assert draft_rows[("modelo-720-asset-row-country", 1)] == "AD"
    assert draft_rows[("modelo-720-asset-row-currency", 1)] == "EUR"
    assert draft_rows[("modelo-720-asset-row-identifier", 1)] == "AD-ACCOUNT-001"
    assert draft_rows[("modelo-720-asset-row-acquisition-date", 1)] == "2020-01-15"
    assert draft_rows[("modelo-720-asset-row-valuation", 1)] == Decimal("40000")


def _m232_row(index: int) -> Modelo232VinculadaRow:
    return Modelo232VinculadaRow(
        nif=f"A1234567{index}",
        nombre=f"Vinculada {index}",
        pais="ES",
        tipo_vinculacion="A",
        tipo_operacion="01",
        metodo="1A",
        importe=Decimal(f"{index}25000"),
    )


def test_persisted_m232_rows_produce_no_replay_inputs_when_absent() -> None:
    """An M232 revision with no related-party rows contributes no vinculada keys.

    The empty case the finding asks for: without it the one-row assertion below
    could pass on a projection that emitted the slots unconditionally.
    """
    work_unit = _work_unit(modelo="232", filing_year=2025, period_code="0A")
    revision = _revision(work_unit)

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert not [key for key in replay_inputs if str(key).startswith("vinculada-")]


def test_persisted_m232_row_reaches_filing_replay() -> None:
    """A persisted related-party row is projected into its positional casillas.

    A valid M232 revision could retain operator-supplied rows in encrypted
    storage while replay produced nothing for them, silently losing the rows
    during export or filing reconstruction.
    """
    work_unit = _work_unit(modelo="232", filing_year=2025, period_code="0A")
    row = _m232_row(1)
    revision = _revision(work_unit, detail_rows=(row,))

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    assert replay_inputs["vinculada-1-nif"] == row.nif
    assert replay_inputs["vinculada-1-tipo-vinculacion"] == row.tipo_vinculacion
    assert replay_inputs["vinculada-1-tipo-operacion"] == row.tipo_operacion
    assert replay_inputs["vinculada-1-metodo-valoracion"] == row.metodo
    assert replay_inputs["vinculada-1-importe"] == "125000"


def test_persisted_m232_rows_fill_every_declared_row_slot() -> None:
    """Five rows populate all five slots, each in its own positional casilla.

    Row order is the slot order, so a projection that collapsed rows onto one
    slot or dropped the tail would surface here rather than in an export diff.
    """
    work_unit = _work_unit(modelo="232", filing_year=2025, period_code="0A")
    rows = tuple(_m232_row(index) for index in range(1, 6))
    revision = _revision(work_unit, detail_rows=rows)

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    for index, row in enumerate(rows, start=1):
        assert replay_inputs[f"vinculada-{index}-nif"] == row.nif
        assert replay_inputs[f"vinculada-{index}-importe"] == str(row.importe)
    assert len([key for key in replay_inputs if str(key).endswith("-nif") and str(key).startswith("vinculada-")]) == 5


def test_m232_replay_keys_are_declared_casillas_of_the_resolved_revision() -> None:
    """Every projected key names a casilla the law-resolved revision declares.

    Guards against the projection inventing coordinates: an id that no casilla
    declares would be dropped downstream exactly as silently as no id at all.
    """
    work_unit = _work_unit(modelo="232", filing_year=2025, period_code="0A")
    revision = _revision(work_unit, detail_rows=(_m232_row(1),))
    resolved_revision = _resolved_revision(modelo="232", filing_year=2025, period_code="0A")
    declared = {casilla.id for casilla in resolved_revision.casillas}

    replay_inputs = revision_filing_replay_inputs(revision=revision, work_unit=work_unit)

    projected = {key for key in replay_inputs if str(key).startswith("vinculada-")}
    assert projected
    assert projected <= declared
