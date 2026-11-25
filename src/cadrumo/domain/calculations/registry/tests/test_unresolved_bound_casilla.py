"""A bound casilla whose resolver left its binding unresolved has no value.

The registry engine seeds a bound casilla fed through the input channel from
the caller's inputs. When the source resolver ran and could not settle the
binding, the casilla must stay absent and every formula reading it must stay
unresolved, rather than folding the gap into a zero that is indistinguishable
from a proven one. A binding nobody reported unresolved keeps the unsupplied
input reading, as does one whose source answered off the scalar channel
(declared inapplicable to the filer, or delivered as rows), and absent-by-design
observation-backed slots keep their
structural zero.

Each case runs the published Modelo 303 or 390 revision through
:func:`calculate_registry_snapshot` or :func:`initial_values`; the expected
figures are plain sums of the supplied amounts, independent of the engine.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingSourceKind
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..authority import PinnedAuthorityOperation
from ..binding_targets import bound_casilla_binding_ids, revision_bindings_by_id
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..formula_initial_values import initial_values
from ..formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ..ids import BindingId
from ..schema import RegistrySnapshot
from ..schema_input_kind import InputKind
from .authored_editions import filing_grade_exercises

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# Modelo 390 is the narrower of the two subjects, so the exercise is its newest filing-grade edition.
_YEAR = filing_grade_exercises("390")[-1]
_PRORRATA_44_BINDING: BindingId = "modelo-303-prorrata-regularizacion-casilla-44"
_SOPORTADO_INTERIORES_BINDING: BindingId = "modelo-303-iva-soportado-interiores-cuota"
_STATE_RATIO_BINDING: BindingId = "modelo-303-profile-state-attribution-ratio"
_COMPENSACION_ANTERIOR_BINDING: BindingId = "modelo-303-compensacion-pendiente-anteriores"
_INPUT_CHANNEL_SOURCES = frozenset(
    {
        BindingSourceKind.LEDGER_IVA_AGGREGATION,
        BindingSourceKind.PRORRATA_REGULARIZACION,
        BindingSourceKind.BIENES_INVERSION_REGULARIZACION,
    }
)

_CASILLA_44: CasillaId = validated_casilla_id("44")
_CASILLA_45: CasillaId = validated_casilla_id("45")
_SOPORTADO_INTERIORES: CasillaId = validated_casilla_id("iva.soportado.interiores")
_DEDUCIBLE_TOTAL: CasillaId = validated_casilla_id("iva.cuota-deducible-total")
_DEVENGADA_TOTAL: CasillaId = validated_casilla_id("iva.cuota-devengada-total")
_RESULTADO_REGIMEN_GENERAL: CasillaId = validated_casilla_id("iva.resultado-regimen-general")
_DEDUCTION_CHAIN = (_DEDUCIBLE_TOTAL, _CASILLA_45, _RESULTADO_REGIMEN_GENERAL)


def _m303_settlement_snapshot(operation: PinnedAuthorityOperation) -> RegistrySnapshot:
    return operation.snapshot("303", filing_year=_YEAR, period="4T")


def _calculate_m303(
    snapshot: RegistrySnapshot,
    *,
    source_values: dict[BindingId, Decimal],
    unresolved: tuple[BindingId, ...] = (),
    settled: tuple[BindingId, ...] = (),
    operator_inputs: dict[CasillaId, Decimal] | None = None,
) -> RegistryCalculationResult:
    """Run the published 303 formulas with the given input-channel source values.

    Every input-channel binding the case does not name carries zero, as a
    resolver that found nothing to declare reports it; a binding listed as
    unresolved carries nothing at all.
    """
    revision = snapshot.revision
    bindings = revision_bindings_by_id(revision)
    input_channel = {
        binding_id: Decimal("0.00")
        for binding_id, binding in bindings.items()
        if binding.source in _INPUT_CHANNEL_SOURCES and binding_id not in unresolved
    }
    input_channel.update(source_values)
    others: dict[BindingId, Decimal] = {
        binding_id: Decimal("0")
        for binding_id, binding in bindings.items()
        if binding.source not in _INPUT_CHANNEL_SOURCES and binding_id not in unresolved
    }
    others[_STATE_RATIO_BINDING] = Decimal("100")
    return calculate_registry_snapshot(
        snapshot,
        inputs={**resolve_available_bound_inputs_by_casilla_id(revision, input_channel), **(operator_inputs or {})},
        binding_values=others,
        unresolved_binding_ids=unresolved,
        settled_binding_ids=settled,
        date_context={"filing_period": date(_YEAR + 1, 1, 30)},
    )


def _observed_ids(result: RegistryCalculationResult) -> frozenset[CasillaId]:
    return frozenset(observation.casilla_id for observation in result.observations)


def test_the_published_settlement_chain_reads_the_casillas_this_module_names(
    *, operation: PinnedAuthorityOperation
) -> None:
    """Fix the premise: 44 and the interior cuota are input-channel bound casillas."""
    revision = _m303_settlement_snapshot(operation).revision
    bindings = revision_bindings_by_id(revision)
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    for casilla_id, binding_id in (
        (_CASILLA_44, _PRORRATA_44_BINDING),
        (_SOPORTADO_INTERIORES, _SOPORTADO_INTERIORES_BINDING),
    ):
        assert casillas[casilla_id].input_kind is InputKind.BOUND
        assert bound_casilla_binding_ids(casillas[casilla_id]) == (binding_id,)
        assert bindings[binding_id].source in _INPUT_CHANNEL_SOURCES
    assert {_DEVENGADA_TOTAL, *_DEDUCTION_CHAIN} <= casillas.keys()


def test_resolved_regularisation_feeds_the_deduction_total(*, operation: PinnedAuthorityOperation) -> None:
    """With 44 settled, the deduction total and result carry it as an ordinary value."""
    result = _calculate_m303(
        _m303_settlement_snapshot(operation),
        source_values={
            _PRORRATA_44_BINDING: Decimal("-217.60"),
            _SOPORTADO_INTERIORES_BINDING: Decimal("89.60"),
        },
    )

    values = result.values
    assert values[_CASILLA_44] == Decimal("-217.60")
    # [45] is the sum of [29] .. [44]; only the two named amounts are non-zero.
    assert values[_DEDUCIBLE_TOTAL] == Decimal("-128.00")
    assert values[_CASILLA_45] == Decimal("-128.00")
    assert values[_RESULTADO_REGIMEN_GENERAL] == values[_DEVENGADA_TOTAL] - Decimal("-128.00")


def test_unresolved_prorrata_regularisation_leaves_44_and_its_dependants_absent(
    *, operation: PinnedAuthorityOperation
) -> None:
    """An unresolved 44 is no observation at all, and nothing summing it is either."""
    result = _calculate_m303(
        _m303_settlement_snapshot(operation),
        source_values={_SOPORTADO_INTERIORES_BINDING: Decimal("89.60")},
        unresolved=(_PRORRATA_44_BINDING,),
    )

    observed = _observed_ids(result)
    assert _CASILLA_44 not in observed
    assert observed.isdisjoint(_DEDUCTION_CHAIN)
    assert _CASILLA_44 not in result.values
    # What does not read 44 is still worked out.
    assert result.values[_SOPORTADO_INTERIORES] == Decimal("89.60")
    assert _DEVENGADA_TOTAL in observed


def test_unresolved_ledger_binding_leaves_its_casilla_and_dependants_absent(
    *, operation: PinnedAuthorityOperation
) -> None:
    """A ledger-sourced bound casilla the ledger resolver could not settle behaves the same way."""
    result = _calculate_m303(
        _m303_settlement_snapshot(operation),
        source_values={_PRORRATA_44_BINDING: Decimal("-217.60")},
        unresolved=(_SOPORTADO_INTERIORES_BINDING,),
    )

    observed = _observed_ids(result)
    assert _SOPORTADO_INTERIORES not in observed
    assert observed.isdisjoint(_DEDUCTION_CHAIN)
    assert result.values[_CASILLA_44] == Decimal("-217.60")


def test_a_settled_binding_keeps_the_unsupplied_input_reading(*, operation: PinnedAuthorityOperation) -> None:
    """A source that answered off the scalar channel (inapplicable, or rows) is not a failed source."""
    result = _calculate_m303(
        _m303_settlement_snapshot(operation),
        source_values={_SOPORTADO_INTERIORES_BINDING: Decimal("89.60")},
        unresolved=(_PRORRATA_44_BINDING,),
        settled=(_PRORRATA_44_BINDING,),
    )

    assert result.values[_CASILLA_44] == Decimal("0")
    assert result.values[_DEDUCIBLE_TOTAL] == Decimal("89.60")


def test_a_supplied_value_wins_over_an_unresolved_report(*, operation: PinnedAuthorityOperation) -> None:
    """An operator value for the box is kept even when the resolver reported the binding unresolved."""
    result = _calculate_m303(
        _m303_settlement_snapshot(operation),
        source_values={},
        unresolved=(_PRORRATA_44_BINDING,),
        operator_inputs={_CASILLA_44: Decimal("-50.00")},
    )

    assert result.values[_CASILLA_44] == Decimal("-50.00")
    assert result.values[_DEDUCIBLE_TOTAL] == Decimal("-50.00")


def test_a_binding_nobody_reported_unresolved_keeps_the_unsupplied_input_reading(
    *, operation: PinnedAuthorityOperation
) -> None:
    """Without an unresolved report an unsupplied bound input still evaluates as zero."""
    snapshot = _m303_settlement_snapshot(operation)
    seeded = initial_values(
        snapshot.revision,
        {},
        binding_values={_COMPENSACION_ANTERIOR_BINDING: Decimal("0")},
        target_period=snapshot.period,
    )

    assert seeded.values[_CASILLA_44] == Decimal("0")
    assert _CASILLA_44 not in seeded.absent_by_design_casilla_ids
    assert seeded.unresolved_casilla_ids == frozenset()


def test_absent_by_design_relation_prefill_keeps_its_structural_zero(*, operation: PinnedAuthorityOperation) -> None:
    """A relation-prefill slot is observation-backed: even reported unresolved it stays absent by design."""
    snapshot = operation.snapshot("390", filing_year=_YEAR, period="0A")
    bindings = revision_bindings_by_id(snapshot.revision)
    relation_casillas = {
        casilla.id: bound_casilla_binding_ids(casilla)
        for casilla in snapshot.revision.casillas
        if casilla.input_kind is InputKind.BOUND
        and any(
            bindings[binding_id].source is BindingSourceKind.RELATION_PREFILL
            for binding_id in bound_casilla_binding_ids(casilla)
        )
    }
    assert relation_casillas

    seeded = initial_values(
        snapshot.revision,
        {},
        binding_values={},
        target_period=snapshot.period,
        unresolved_binding_ids=frozenset(binding_id for ids in relation_casillas.values() for binding_id in ids),
    )

    for casilla_id in relation_casillas:
        assert seeded.values[casilla_id] == Decimal("0")
        assert casilla_id in seeded.absent_by_design_casilla_ids
    assert seeded.unresolved_casilla_ids == frozenset()
