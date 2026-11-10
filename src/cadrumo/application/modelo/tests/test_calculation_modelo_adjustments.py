"""Canonical binding-to-casilla use in Modelo-specific calculation adjustments."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from functools import cache
from typing import Literal, get_args

import pytest

from ....core.aggregation import OBSERVATION_BACKED_BINDING_SOURCE_KINDS
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.binding_targets import bound_casilla_binding_ids, revision_bindings_by_id
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.calculations.registry.tests.authored_editions import filing_grade_exercises, filing_year_envelope
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.modelos.codes import ModeloCode
from ....domain.modelos.row_models import Modelo349OperadorRow, ModeloDetailRow
from ....domain.modelos.work_unit import WorkUnit, derive_work_unit_id
from ..action_errors import ModeloAggregationBindingError, ModeloCrossPeriodCleanStateError
from ..calculation_modelo_adjustments import (
    detail_row_binding_values_for_calculation,
    raise_if_m390_303_reconciliation_would_save_silent_zero,
    reconciliation_relation_targets,
    union_detail_rows_by_identity,
)
from ..m303_regimen_simplificado_scope import m303_general_regime_claimed

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_TARGET_BINDING = "modelo-390-prev-303-cuota-devengada-total"
_OTHER_BINDING = "modelo-390-prev-303-cuota-deducible-total"
_TARGET_CASILLA = "iva.anual.reconciliacion.devengada-303"
_RELATION = "modelo-390-prev-303-cuota-devengada-total"
_DEVENGADA_TOTAL = validated_casilla_id("iva.anual.cuota-devengada-total")
_DEDUCIBLE_TOTAL = validated_casilla_id("iva.anual.cuota-deducible-total")
_REPERCUTIDO_21_CUOTA = validated_casilla_id("iva.anual.repercutido.tipo-21.cuota")
_MODIFICACION_CUOTA = validated_casilla_id("iva.anual.modificacion.bases-cuotas.cuota")
_COMPENSACIONES_REAGP_CUOTA = validated_casilla_id("iva.anual.deducible.compensaciones-reagp.cuota")
_COMPENSACIONES_REAGP_BINDING: BindingId = "modelo-390-prev-303-compensaciones-reagp"


def test_m390_reconciliation_target_reaches_a_binding_declared_only_as_an_alternate() -> None:
    """The adjustment consumes the canonical reverse join, including alternates."""
    snapshot = published_snapshot(Modelo("390").value, filing_year=filing_grade_exercises("390")[-1], period="0A")
    revised_casillas = tuple(
        CasillaDefinition.model_validate(
            {
                **casilla.model_dump(),
                "localization_keys": casilla.localization_keys,
                "binding": _OTHER_BINDING,
                "alternate_bindings": (_TARGET_BINDING,),
            },
        )
        if casilla.id == _TARGET_CASILLA
        else casilla
        for casilla in snapshot.revision.casillas
    )
    revised_snapshot = snapshot.model_copy(
        update={"revision": snapshot.revision.model_copy(update={"casillas": revised_casillas})},
    )

    relation_targets = reconciliation_relation_targets(revised_snapshot)
    target = next(row for row in relation_targets if row[0] == _RELATION)

    assert target[1] == _TARGET_BINDING
    assert target[2] == (_TARGET_CASILLA,)


def _work_unit(modelo: Modelo, *, filing_year: int = filing_year_envelope().horizon) -> WorkUnit:
    bucket_id = "calculation-modelo-adjustments-bucket"
    period = Period.from_year_and_code(filing_year, "0A")
    revision_id = "r" + "0" * 63
    code = ModeloCode(modelo.value)
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id=bucket_id,
            modelo=code,
            filing_year=filing_year,
            period=period,
            revision_id=revision_id,
        ),
        bucket_id=bucket_id,
        modelo=code,
        filing_year=filing_year,
        period=period,
        revision_id=revision_id,
        name=f"{code}-{filing_year}",
        created_at=datetime(1980, 1, 1, tzinfo=UTC),
        updated_at=datetime(1980, 1, 1, tzinfo=UTC),
    )


def _m349_operador(
    *,
    nif_comunitario: str,
    clave_operacion: Literal["E", "M", "H", "A", "T", "S", "I", "R", "D", "C"],
    importe: Decimal,
) -> Modelo349OperadorRow:
    return Modelo349OperadorRow(
        codigo_pais="DE",
        nif_comunitario=nif_comunitario,
        razon_social="Deutschland GmbH",
        clave_operacion=clave_operacion,
        importe=importe,
    )


def test_union_keeps_disjoint_rows_from_both_supply_paths() -> None:
    """Two supply paths naming DIFFERENT counterparties both survive the union."""
    from decimal import Decimal

    resolver_row = _m349_operador(nif_comunitario="DE111111111", clave_operacion="E", importe=Decimal("1000.00"))
    caller_row = _m349_operador(nif_comunitario="FR222222222", clave_operacion="E", importe=Decimal("500.00"))

    unioned = union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    assert set(unioned) == {resolver_row, caller_row}


def test_union_collapses_an_identical_row_named_by_both_paths_to_one() -> None:
    """The bite proof this test exists for: without the union, this pair double-counts.

    An invoice-sourced operador row the operator ALSO enters manually for the
    SAME (nif_comunitario, clave_operacion) must count once, not twice, in
    every downstream declarant-summary total.
    """
    from decimal import Decimal

    resolver_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("1000.00"))
    caller_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("1000.00"))

    unioned = union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    assert len(unioned) == 1
    values = detail_row_binding_values_for_calculation(
        work_unit=_work_unit(Modelo("349")),
        # Modelo 349 declares only monthly and quarterly periods.
        revision=published_snapshot(
            Modelo("349").value, filing_year=filing_year_envelope().horizon, period="4T"
        ).revision,
        detail_rows=unioned,
    )
    assert values["iva-349-declarante-numero-operadores"] == Decimal("1")
    assert values["iva-349-declarante-importe-operaciones"] == Decimal("1000.00")


def test_union_refuses_a_divergent_amount_for_the_same_identity_naming_the_field() -> None:
    """Two supply paths disagreeing on a declarable figure refuse, rather than pick a side."""
    from decimal import Decimal

    resolver_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("1000.00"))
    caller_row = _m349_operador(nif_comunitario="DE123456789", clave_operacion="E", importe=Decimal("2500.00"))

    with pytest.raises(ModeloAggregationBindingError) as excinfo:
        union_detail_rows_by_identity(resolver_rows=(resolver_row,), caller_rows=(caller_row,))

    context = excinfo.value.context
    assert context is not None
    assert context["reason"] == "detail_row_identity_conflict"
    assert context["identity"] == ["DE123456789", "E"]
    assert context["divergent_fields"] == ["importe"]


def test_union_is_a_no_op_for_a_modelo_whose_rows_come_from_one_source_alone() -> None:
    """M184/M232 have no resolver-produced rows today: prove byte-identical output.

    Establishing this generically (empty resolver side) rather than special-
    casing each modelo, since the union function itself has no
    modelo-specific branch -- it is the ABSENCE of a resolver contribution
    that must leave caller-supplied rows untouched, for any row kind.
    """
    from decimal import Decimal

    from ....domain.modelos.row_models import Modelo184MemberRow, Modelo232VinculadaRow

    caller_rows = (
        Modelo184MemberRow(nif="12345678A", porcentaje=Decimal("50.00"), importe=Decimal("100.00"), clave="D"),
        Modelo232VinculadaRow(pais="ES", nif="87654321B", importe=Decimal("200.00")),
    )

    unioned = union_detail_rows_by_identity(resolver_rows=(), caller_rows=caller_rows)

    assert unioned == caller_rows


def test_every_detail_row_kind_has_an_identity_table_entry() -> None:
    """Gate: a row kind added to the union without an identity entry regresses the double-count fix silently."""
    from .. import calculation_modelo_adjustments

    assert set(get_args(ModeloDetailRow)) == set(calculation_modelo_adjustments.ROW_IDENTITY_FIELDS)


def test_the_coverage_gate_bites_on_a_kind_missing_from_the_identity_table() -> None:
    """Prove the gate is real: removing one real kind from the table is detected."""
    from ....domain.modelos.row_models import Modelo184MemberRow
    from .. import calculation_modelo_adjustments

    row_kinds = set(get_args(ModeloDetailRow))
    real_table = set(calculation_modelo_adjustments.ROW_IDENTITY_FIELDS)
    incomplete_table = real_table - {Modelo184MemberRow}

    assert row_kinds - incomplete_table == {Modelo184MemberRow}
    # The real table stays fully covered -- this test does not mutate it.
    assert row_kinds - real_table == set()


@dataclass(frozen=True, slots=True)
class _M390Calculation:
    """One real engine run over an M390 snapshot plus what the sources supplied to it."""

    snapshot: RegistrySnapshot
    result: RegistryCalculationResult
    supplied_casilla_ids: frozenset[CasillaId]
    answered_binding_ids: frozenset[BindingId]


@cache
def _filing_grade_m390_snapshot() -> RegistrySnapshot:
    """Select the latest supported year whose Modelo 390 revision is filing grade."""
    support = published_supported_filing_years()
    assert support is not None
    for filing_year in reversed(support.years):
        try:
            return published_snapshot(Modelo("390").value, filing_year=filing_year, period="0A")
        except RegistryValidationError:
            continue
    raise AssertionError("no supported filing year selects a filing-grade Modelo 390 revision")


def _calculate_m390(
    *,
    inputs: dict[CasillaId, Decimal] | None = None,
    binding_values: dict[BindingId, Decimal] | None = None,
    settled_binding_ids: tuple[BindingId, ...] = (),
) -> _M390Calculation:
    snapshot = _filing_grade_m390_snapshot()
    supplied_inputs = inputs or {}
    supplied_bindings = binding_values or {}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=supplied_inputs,
        date_context={},
        binding_values=supplied_bindings or None,
        unresolved_binding_ids=settled_binding_ids,
        settled_binding_ids=settled_binding_ids,
    )
    return _M390Calculation(
        snapshot=snapshot,
        result=result,
        supplied_casilla_ids=frozenset(supplied_inputs),
        answered_binding_ids=frozenset((*supplied_bindings, *settled_binding_ids)),
    )


def _guard(
    calculation: _M390Calculation,
    *,
    casilla_values: dict[CasillaId, Decimal] | None = None,
    general_regime_claimed: bool = True,
    resolved_binding_values: dict[BindingId, Decimal] | None = None,
) -> None:
    raise_if_m390_303_reconciliation_would_save_silent_zero(
        work_unit=_work_unit(Modelo("390"), filing_year=calculation.snapshot.filing_year),
        snapshot=calculation.snapshot,
        casilla_values=dict(calculation.result.values) if casilla_values is None else casilla_values,
        resolved_binding_values=resolved_binding_values or {},
        general_regime_claimed=general_regime_claimed,
        observations=calculation.result.observations,
        supplied_casilla_ids=calculation.supplied_casilla_ids,
        answered_binding_ids=calculation.answered_binding_ids,
    )


def _refused_annuals(
    calculation: _M390Calculation,
    *,
    casilla_values: dict[CasillaId, Decimal] | None = None,
    general_regime_claimed: bool = True,
    resolved_binding_values: dict[BindingId, Decimal] | None = None,
) -> tuple[CasillaId, ...]:
    with pytest.raises(ModeloCrossPeriodCleanStateError) as raised:
        _guard(
            calculation,
            casilla_values=casilla_values,
            general_regime_claimed=general_regime_claimed,
            resolved_binding_values=resolved_binding_values,
        )
    context = raised.value.context
    assert context is not None
    assert context["reason"] == "missing_clean_cross_period_303_filings_or_observations"
    refused = context["annual_casillas_not_proven_zero"]
    assert isinstance(refused, tuple)
    return tuple(validated_casilla_id(str(casilla_id)) for casilla_id in refused)


def _annual_casillas() -> tuple[CasillaId, ...]:
    return tuple(row[4] for row in reconciliation_relation_targets(_filing_grade_m390_snapshot()))


def _annuals_except(excluded: CasillaId) -> tuple[CasillaId, ...]:
    return tuple(annual for annual in _annual_casillas() if annual != excluded)


def _explicit_zero_entries() -> tuple[dict[CasillaId, Decimal], dict[BindingId, Decimal]]:
    """Return an operator zero for every box the annual totals are folded from.

    A relation-fed box is answered through its binding, as the engine requires;
    every other box takes a casilla input.
    """
    snapshot = _filing_grade_m390_snapshot()
    observations = {observation.casilla_id: observation for observation in _calculate_m390().result.observations}
    casillas = {casilla.id: casilla for casilla in snapshot.revision.casillas}
    bindings_by_id = revision_bindings_by_id(snapshot.revision)
    inputs: dict[CasillaId, Decimal] = {}
    bindings: dict[BindingId, Decimal] = {}
    pending = list(_annual_casillas())
    seen: set[CasillaId] = set()
    while pending:
        casilla_id = pending.pop()
        if casilla_id in seen:
            continue
        seen.add(casilla_id)
        observation = observations[casilla_id]
        if observation.formula_id is not None:
            pending.extend(observation.operand_casilla_refs)
            continue
        relation_fed = tuple(
            binding_id
            for binding_id in bound_casilla_binding_ids(casillas[casilla_id])
            if bindings_by_id[binding_id].source in OBSERVATION_BACKED_BINDING_SOURCE_KINDS
        )
        if relation_fed:
            bindings[relation_fed[0]] = Decimal("0.00")
        else:
            inputs[casilla_id] = Decimal("0.00")
    return inputs, bindings


def test_m390_annual_zero_folded_from_nothing_supplied_is_not_proof() -> None:
    calculation = _calculate_m390()
    annuals = _annual_casillas()
    # The engine reads every unsupplied input as zero, so each annual total is a
    # calculated zero although no source and no operator stated any figure.
    assert all(calculation.result.values[annual] == Decimal("0") for annual in annuals)

    assert _refused_annuals(calculation) == annuals


def test_m390_annual_zero_from_explicit_operator_zeros_is_proof() -> None:
    inputs, bindings = _explicit_zero_entries()
    calculation = _calculate_m390(inputs=inputs, binding_values=bindings)
    assert all(calculation.result.values[annual] == Decimal("0") for annual in _annual_casillas())

    _guard(calculation)


def test_m390_operator_values_on_the_reconciliation_slots_ground_them() -> None:
    slots = {row[1]: Decimal("0.00") for row in reconciliation_relation_targets(_filing_grade_m390_snapshot())}

    _guard(_calculate_m390(), resolved_binding_values=slots)


def test_m390_resolved_sources_netting_to_zero_prove_the_annual_zero() -> None:
    inputs, bindings = _explicit_zero_entries()
    charged = Decimal("210.00")
    corrected = Decimal("-210.00")
    inputs[_REPERCUTIDO_21_CUOTA] = charged
    inputs[_MODIFICACION_CUOTA] = corrected
    calculation = _calculate_m390(inputs=inputs, binding_values=bindings)
    assert calculation.result.values[_DEVENGADA_TOTAL] == charged + corrected

    _guard(calculation)


def test_m390_one_unsupplied_box_leaves_the_totals_it_feeds_unknown() -> None:
    inputs, bindings = _explicit_zero_entries()
    del inputs[_MODIFICACION_CUOTA]

    refused = _refused_annuals(_calculate_m390(inputs=inputs, binding_values=bindings))

    # Box 65 is box 47 less box 64, so an unknown output-IVA box reaches 47 and
    # 65 but not the deductions total.
    assert refused == _annuals_except(_DEDUCIBLE_TOTAL)


def test_m390_structural_zero_seeded_for_an_unfolded_relation_box_is_not_proof() -> None:
    inputs, bindings = _explicit_zero_entries()
    del bindings[_COMPENSACIONES_REAGP_BINDING]
    calculation = _calculate_m390(inputs=inputs, binding_values=bindings)
    seeded = next(
        observation
        for observation in calculation.result.observations
        if observation.casilla_id == _COMPENSACIONES_REAGP_CUOTA
    )
    assert seeded.absent_by_design
    assert seeded.value == Decimal("0")

    refused = _refused_annuals(calculation)

    # The REAGP compensations are a deduction (box 64), which box 65 subtracts.
    assert refused == _annuals_except(_DEVENGADA_TOTAL)


def test_m390_a_settled_binding_answers_its_box() -> None:
    inputs, bindings = _explicit_zero_entries()
    del inputs[_REPERCUTIDO_21_CUOTA]
    casilla = next(
        casilla for casilla in _filing_grade_m390_snapshot().revision.casillas if casilla.id == _REPERCUTIDO_21_CUOTA
    )
    assert casilla.binding is not None

    _guard(_calculate_m390(inputs=inputs, binding_values=bindings, settled_binding_ids=(casilla.binding,)))
    assert _refused_annuals(_calculate_m390(inputs=inputs, binding_values=bindings)) == _annuals_except(
        _DEDUCIBLE_TOTAL
    )


def test_m390_silent_zero_guard_refuses_an_annual_box_that_was_never_calculated() -> None:
    assert _refused_annuals(_calculate_m390(), casilla_values={}) == _annual_casillas()


def test_m390_silent_zero_guard_refuses_a_nonzero_annual_box_without_303_evidence() -> None:
    inputs, bindings = _explicit_zero_entries()
    inputs[_REPERCUTIDO_21_CUOTA] = Decimal("125.50")

    refused = _refused_annuals(_calculate_m390(inputs=inputs, binding_values=bindings))

    assert refused == _annuals_except(_DEDUCIBLE_TOTAL)


def test_m390_silent_zero_guard_skips_absent_boxes_only_for_a_filer_with_no_general_regime() -> None:
    _guard(_calculate_m390(), casilla_values={}, general_regime_claimed=False)


def test_m390_unknown_zero_boxes_are_exempt_for_a_filer_with_no_general_regime() -> None:
    _guard(_calculate_m390(), general_regime_claimed=False)


def test_m390_a_non_zero_figure_makes_unknown_zero_boxes_unknown_again_without_general_regime() -> None:
    calculation = _calculate_m390(inputs={_REPERCUTIDO_21_CUOTA: Decimal("125.50")})

    assert _refused_annuals(calculation, general_regime_claimed=False) == _annual_casillas()


def test_m390_silent_zero_guard_reads_absent_boxes_as_unknown_beside_a_non_zero_annual_figure() -> None:
    annuals = _annual_casillas()

    refused = _refused_annuals(
        _calculate_m390(), casilla_values={annuals[0]: Decimal("125.50")}, general_regime_claimed=False
    )

    assert refused == annuals


def test_m390_silent_zero_guard_reads_absent_boxes_as_unknown_beside_a_non_zero_resolved_fold() -> None:
    targets = reconciliation_relation_targets(_filing_grade_m390_snapshot())
    first_binding = targets[0][1]

    refused = _refused_annuals(
        _calculate_m390(),
        casilla_values={},
        general_regime_claimed=False,
        resolved_binding_values={first_binding: Decimal("40.00")},
    )

    assert refused == tuple(row[4] for row in targets[1:])


def test_a_general_regime_is_claimed_unless_the_composition_is_simplified_only() -> None:
    assert m303_general_regime_claimed("general")
    assert m303_general_regime_claimed("mixed")
    assert m303_general_regime_claimed(None)
    assert not m303_general_regime_claimed("simplified")
