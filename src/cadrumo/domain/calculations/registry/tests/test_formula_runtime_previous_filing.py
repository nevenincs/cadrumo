"""Previous-filing and relation-fold formula runtime tests."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....tests.registry_observations import registry_grounded_modelo_observation
from ..bindings_previous_filing import (
    previous_filing_observation_requirements,
    previous_filing_source_reference,
    resolve_previous_filing_binding_values,
)
from ..errors import RegistryValidationError
from ..relations import (
    RegistryFoldRequirement,
    relation_source_requirements,
    resolve_relation_values_from_observations,
)
from ..schema import RegistrySnapshot
from ._formula_runtime_support import (
    _M100_PAGOS_FRACCIONADOS_CASILLA,
    _M100_RENDIMIENTO_NETO_ACTIVIDADES_CASILLA,
    _M100_RESULTADO_AUTOLIQUIDACION_CASILLA,
    _M100_RETENCIONES_PAGOS_CUENTA_CASILLA,
    _M115_BASE_CASILLA,
    _M115_PERCEPTORES_CASILLA,
    _M115_RETENCIONES_CASILLA,
    _M130_SALDO_NEGATIVO_CASILLA,
    _PREVIOUS_YEAR_NET_INCOME_BINDING,
    _previous_year_net_income_binding,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_previous_filing_binding_resolves_from_observed_irpf_casillas(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    source_reference = previous_filing_source_reference(binding)
    source_casilla_ids = source_reference.source_casilla_ids
    observed_values = {casilla_id: Decimal(index + 1) for index, casilla_id in enumerate(source_casilla_ids)}

    result = resolve_previous_filing_binding_values(
        committed_modelo_130_snapshot.revision,
        (
            registry_grounded_modelo_observation(
                modelo=source_reference.source_modelo,
                filing_year=2025,
                period=source_reference.required_periods[0],
                casilla_values=observed_values,
                grade=RegistryAuthorityGrade.CALCULATION,
            ),
        ),
        filing_year=2026,
        period="1T",
    )

    assert _PREVIOUS_YEAR_NET_INCOME_BINDING in result
    assert isinstance(result[_PREVIOUS_YEAR_NET_INCOME_BINDING], Decimal)


def test_previous_filing_requirements_are_declared_from_registry_binding_selector(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    source_reference = previous_filing_source_reference(binding)

    requirements = previous_filing_observation_requirements(
        committed_modelo_130_snapshot.revision,
        filing_year=2026,
        period="1T",
    )

    assert len(requirements) == 1
    requirement = requirements[0]
    assert requirement.source_modelo == source_reference.source_modelo
    assert requirement.filing_year == 2025
    assert requirement.periods == (source_reference.required_periods[0],)
    assert requirement.binding_ids == (_PREVIOUS_YEAR_NET_INCOME_BINDING,)
    assert requirement.source_casilla_ids == tuple(sorted(source_reference.source_casilla_ids))
    assert requirement.required_source_casilla_ids == ()
    assert requirement.source_presence_groups == (tuple(source_reference.source_casilla_ids),)
    assert requirement.legal_refs == tuple(sorted(binding.legal_refs))
    assert requirement.source_refs == tuple(sorted(binding.source_refs))


def test_relation_requirements_cover_all_source_periods_for_annual_summary(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    # M180 ← M115 is canonically a RELATION fold-in (aggregation-taxonomy
    # ruling 2): the slot bindings declare source = "relation_prefill" and the
    # requirement set is produced by the relation requirement resolver, not the
    # previous-filing one (which now skips relation_prefill slots by design).
    requirements = relation_source_requirements(
        committed_modelo_180_snapshot.revision,
        filing_year=2026,
        period="0A",
    )

    # The two monetary 180 annual_summary relations share one source quadruple
    # (115/2026/[1T-4T]) grouped per source_casilla_id; assert the periods cover all
    # four quarters and the relation source modelo/year are correct. The perceptor
    # count is a retenciones_aggregation binding, not a relation.
    assert {requirement.source_modelo for requirement in requirements} == {"115"}
    assert {requirement.filing_year for requirement in requirements} == {2026}
    assert all(tuple(requirement.periods) == ("1T", "2T", "3T", "4T") for requirement in requirements)
    target_bindings = {tb for requirement in requirements for tb in requirement.target_bindings}
    assert target_bindings == {
        "modelo-180-115-base-anual",
        "modelo-180-115-retenciones-anual",
    }
    assert {
        source_casilla_id for requirement in requirements for source_casilla_id in requirement.source_casilla_ids
    } == {
        _M115_BASE_CASILLA,
        _M115_RETENCIONES_CASILLA,
    }
    relations_by_id = {relation.id: relation for relation in committed_modelo_180_snapshot.revision.relations}
    for requirement in requirements:
        assert requirement.legal_refs == tuple(
            sorted({ref for relation_id in requirement.relation_ids for ref in relations_by_id[relation_id].legal_refs})
        )
        assert requirement.source_refs == tuple(
            sorted(
                {ref for relation_id in requirement.relation_ids for ref in relations_by_id[relation_id].source_refs}
            )
        )


def test_relation_resolves_annual_summary_from_all_source_periods(
    committed_modelo_180_snapshot: RegistrySnapshot,
) -> None:
    # Per .claude/rules/aeat-quality-gates.md, we do not assert
    # base-anual / retenciones-anual equal the author's hand-summation of the
    # synthetic inputs; the runtime's `op = "sum"` aggregator and the author
    # would share the same arithmetic. Instead this test asserts the canonical
    # RELATION resolver (now live) produces:
    #   1. graph-wiring: the two expected monetary relation ids appear in result;
    #   2. type: the summed relations are Decimal-valued, sign-preserving.
    observations = tuple(
        registry_grounded_modelo_observation(
            modelo="115",
            filing_year=2026,
            period=period,
            casilla_values={
                _M115_PERCEPTORES_CASILLA: Decimal("1"),
                _M115_BASE_CASILLA: base,
                _M115_RETENCIONES_CASILLA: retention,
            },
            grade=RegistryAuthorityGrade.CALCULATION,
        )
        for period, base, retention in (
            ("1T", Decimal("100.00"), Decimal("19.00")),
            ("2T", Decimal("200.00"), Decimal("38.00")),
            ("3T", Decimal("300.00"), Decimal("57.00")),
            ("4T", Decimal("-50.00"), Decimal("0.00")),
        )
    )

    result = resolve_relation_values_from_observations(
        committed_modelo_180_snapshot.revision,
        observations,
        filing_year=2026,
        period="0A",
    )

    assert set(result.keys()) == {
        "modelo-180-rel-115-base-anual",
        "modelo-180-rel-115-retenciones-anual",
    }
    assert isinstance(result["modelo-180-rel-115-base-anual"], Decimal)
    assert isinstance(result["modelo-180-rel-115-retenciones-anual"], Decimal)


def test_previous_filing_binding_resolves_from_any_registry_declared_applicable_casilla(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    source_reference = previous_filing_source_reference(binding)
    source_casilla_ids = source_reference.source_casilla_ids

    resolved = resolve_previous_filing_binding_values(
        committed_modelo_130_snapshot.revision,
        (
            registry_grounded_modelo_observation(
                modelo=source_reference.source_modelo,
                filing_year=2025,
                period=source_reference.required_periods[0],
                casilla_values={source_casilla_ids[0]: Decimal("1")},
                grade=RegistryAuthorityGrade.CALCULATION,
            ),
        ),
        filing_year=2026,
        period="1T",
    )

    assert resolved[binding.id] == Decimal("1")


def test_previous_filing_requirements_max_year_delta_unset_preserves_unbounded_anchors(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    assert _previous_filing_offset_year_periods(committed_modelo_130_snapshot, target_period="1T") == ((2025, ("4T",)),)
    assert _previous_filing_offset_year_periods(committed_modelo_130_snapshot, target_period="2T") == ((2026, ("1T",)),)


def test_previous_filing_requirements_max_year_delta_zero_drops_cross_ejercicio_offset_anchor(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    assert (
        _previous_filing_offset_year_periods(
            committed_modelo_130_snapshot,
            target_period="1T",
            max_year_delta=0,
        )
        == ()
    )


def test_previous_filing_requirements_max_year_delta_zero_admits_same_ejercicio_offset_anchors(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    assert _previous_filing_offset_year_periods(
        committed_modelo_130_snapshot,
        target_period="2T",
        max_year_delta=0,
    ) == ((2026, ("1T",)),)
    assert _previous_filing_offset_year_periods(
        committed_modelo_130_snapshot,
        target_period="3T",
        max_year_delta=0,
    ) == ((2026, ("2T",)),)
    assert _previous_filing_offset_year_periods(
        committed_modelo_130_snapshot,
        target_period="4T",
        max_year_delta=0,
    ) == ((2026, ("3T",)),)


def test_previous_filing_requirements_max_year_delta_one_admits_one_year_cross_ejercicio_anchor(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    assert _previous_filing_offset_year_periods(
        committed_modelo_130_snapshot,
        target_period="1T",
        max_year_delta=1,
    ) == ((2025, ("4T",)),)
    assert _previous_filing_offset_year_periods(
        committed_modelo_130_snapshot,
        target_period="2T",
        max_year_delta=1,
    ) == ((2026, ("1T",)),)


def test_previous_filing_requirements_max_year_delta_rejects_negative_values(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    with pytest.raises(RegistryValidationError, match="max_year_delta must be non-negative"):
        _previous_filing_offset_year_periods(
            committed_modelo_130_snapshot,
            target_period="1T",
            max_year_delta=-1,
        )


def _previous_filing_offset_year_periods(
    snapshot: RegistrySnapshot,
    *,
    target_period: str,
    max_year_delta: int | None = None,
) -> tuple[tuple[int, tuple[str, ...]], ...]:
    requirements = _previous_filing_offset_requirements(
        snapshot,
        target_period=target_period,
        max_year_delta=max_year_delta,
    )
    return tuple((requirement.filing_year, requirement.periods) for requirement in requirements)


def _previous_filing_offset_requirements(
    snapshot: RegistrySnapshot,
    *,
    target_period: str,
    max_year_delta: int | None,
) -> tuple[RegistryFoldRequirement, ...]:
    selector: dict[str, object] = {
        "source": "previous_filing",
        "source_modelo": "130",
        "source_casilla_id": _M130_SALDO_NEGATIVO_CASILLA,
        "source_period_offset_from_target": -1,
    }
    if max_year_delta is not None:
        selector["max_year_delta"] = max_year_delta
    binding = _previous_year_net_income_binding(snapshot).model_copy(
        update={
            "id": "test-previous-filing-offset-requirements",
            "selector": selector,
            "aggregation": BindingAggregation(op=BindingAggregationOp.COPY),
        },
    )
    revision = snapshot.revision.model_copy(update={"bindings": (binding,)})
    return previous_filing_observation_requirements(revision, filing_year=2026, period=target_period)


def test_previous_filing_requirements_walker_skips_cap_suppressed_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    base_binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    capped_binding = base_binding.model_copy(
        update={
            "id": "test-cap-suppressed-binding",
            "selector": {
                "source": "previous_filing",
                "source_modelo": "130",
                "source_casilla_id": _M130_SALDO_NEGATIVO_CASILLA,
                "source_period_offset_from_target": -1,
                "max_year_delta": 0,
            },
            "aggregation": BindingAggregation(op=BindingAggregationOp.COPY),
        },
    )
    extended_revision = committed_modelo_130_snapshot.revision.model_copy(
        update={"bindings": (*committed_modelo_130_snapshot.revision.bindings, capped_binding)},
    )

    requirements_first_period = previous_filing_observation_requirements(
        extended_revision,
        filing_year=2026,
        period="1T",
    )
    assert all(
        "test-cap-suppressed-binding" not in requirement.binding_ids for requirement in requirements_first_period
    )

    requirements_second_period = previous_filing_observation_requirements(
        extended_revision,
        filing_year=2026,
        period="2T",
    )
    matching = [
        requirement
        for requirement in requirements_second_period
        if "test-cap-suppressed-binding" in requirement.binding_ids
    ]
    assert len(matching) == 1
    assert matching[0].source_modelo == "130"
    assert matching[0].filing_year == 2026
    assert matching[0].periods == ("1T",)


def test_previous_filing_resolver_skips_cap_suppressed_binding(
    committed_modelo_130_snapshot: RegistrySnapshot,
) -> None:
    base_binding = _previous_year_net_income_binding(committed_modelo_130_snapshot)
    capped_binding = base_binding.model_copy(
        update={
            "id": "test-cap-suppressed-binding-resolve",
            "selector": {
                "source": "previous_filing",
                "source_modelo": "130",
                "source_casilla_id": _M130_SALDO_NEGATIVO_CASILLA,
                "source_period_offset_from_target": -1,
                "max_year_delta": 0,
            },
            "aggregation": BindingAggregation(op=BindingAggregationOp.COPY),
        },
    )
    extended_revision = committed_modelo_130_snapshot.revision.model_copy(
        update={"bindings": (*committed_modelo_130_snapshot.revision.bindings, capped_binding)},
    )

    m100_observation = registry_grounded_modelo_observation(
        modelo="100",
        filing_year=2025,
        period="0A",
        casilla_values={
            _M100_RENDIMIENTO_NETO_ACTIVIDADES_CASILLA: Decimal("1"),
            _M100_RETENCIONES_PAGOS_CUENTA_CASILLA: Decimal("1"),
            _M100_PAGOS_FRACCIONADOS_CASILLA: Decimal("1"),
            _M100_RESULTADO_AUTOLIQUIDACION_CASILLA: Decimal("1"),
        },
        grade=RegistryAuthorityGrade.CALCULATION,
    )

    resolved = resolve_previous_filing_binding_values(
        extended_revision,
        observations=(m100_observation,),
        filing_year=2026,
        period="1T",
    )

    assert "test-cap-suppressed-binding-resolve" not in resolved
    assert _PREVIOUS_YEAR_NET_INCOME_BINDING in resolved
