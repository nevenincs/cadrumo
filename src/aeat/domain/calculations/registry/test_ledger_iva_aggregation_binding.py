"""Tests for the ledger_iva_aggregation binding source kind.

Generic counterpart to ledger_oss_aggregation for the standard IVA
modelos (303, 322, 353, 309, 390). Aggregates ledger lines by the
canonical IVA classification triple (IvaCategory, IvaRateKind,
IvaFlowDirection).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

import pytest
from pydantic import ValidationError

from aeat.core.resources import resources
from aeat.domain.calculations.registry import (
    CasillaObservation,
    DataBindingDefinition,
    IvaLedgerObservation,
    ModeloRevision,
    RegistryCalculationResult,
    RegistryModeloObservation,
    RegistryValidationError,
    calculate_registry_snapshot,
    resolve_bound_casilla_inputs,
    resolve_ledger_iva_aggregation_binding_values,
    resolve_previous_filing_binding_values,
    validate_ledger_iva_aggregation_binding_definition,
)
from aeat.domain.iva import (
    IvaFlowDirection,
    IvaCategory,
    IvaRateKind,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@lru_cache(maxsize=1)
def _modelo_303_revision() -> ModeloRevision:
    modelo = resources().modelos.get("303")
    return modelo.revisions["2009-y-siguientes"]


def _binding(binding_id: str = "modelo-303-iva-repercutido-general-cuota") -> DataBindingDefinition:
    return next(item for item in _modelo_303_revision().bindings if item.id == binding_id)


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**binding.selector, **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: str) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": {"op": op}})


def _observation(
    *,
    ledger_id: str = "ledger-1",
    txn_date: date = date(2025, 6, 15),
    category: IvaCategory = IvaCategory.DOMESTIC_GENERAL_21,
    rate_kind: IvaRateKind = IvaRateKind.GENERAL,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    base: Decimal = Decimal("1000"),
    iva: Decimal = Decimal("210"),
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow,
        base_amount=base,
        iva_amount=iva,
    )


def _revision_with_bindings(*bindings: DataBindingDefinition) -> ModeloRevision:
    return _modelo_303_revision().model_copy(update={"bindings": bindings})


def _calculate_303_from_observations(
    *,
    filing_year: int,
    period: str,
    observations: tuple[IvaLedgerObservation, ...],
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot("303", filing_year=filing_year, period=period)
    binding_values = {
        # Cold-start scenario: no prior 303 compensation balance carried
        # in. Real chained-quarter flows would inject this from the
        # previous quarter's calculation; the reconciliation fixture
        # exercises each quarter in isolation.
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        **resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations),
    }
    inputs = resolve_bound_casilla_inputs(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": observations[-1].transaction_date},
    )


def _calculate_390_from_observations_and_303_filings(
    *,
    filing_year: int,
    observations: tuple[IvaLedgerObservation, ...],
    quarterly_results: dict[str, RegistryCalculationResult],
) -> RegistryCalculationResult:
    snapshot = resources().modelos.authority.snapshot("390", filing_year=filing_year, period="0A")
    ledger_binding_values = resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations)
    previous_filing_values = resolve_previous_filing_binding_values(
        snapshot.revision,
        (
            RegistryModeloObservation(
                modelo="303",
                filing_year=filing_year,
                period=period,
                observations=tuple(CasillaObservation(casilla_id=cid, value=val) for cid, val in result.values.items()),
            )
            for period, result in quarterly_results.items()
        ),
        filing_year=filing_year,
        period="0A",
    )
    binding_values = {**ledger_binding_values, **previous_filing_values}
    inputs = resolve_bound_casilla_inputs(snapshot.revision, binding_values)
    return calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(filing_year, 12, 31)},
    )


def test_validate_accepts_canonical_iva_repercutido_binding() -> None:
    binding = _binding()
    assert binding.id == "modelo-303-iva-repercutido-general-cuota"
    assert binding.selector, "binding must declare a selector for validation to be meaningful"
    result = validate_ledger_iva_aggregation_binding_definition(binding)
    assert result is None


def test_validate_rejects_unknown_category() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), categories=("bogus",)))


def test_validate_rejects_unknown_rate_kind() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), rate_kinds=("medium",)))


def test_validate_rejects_unknown_flow_direction() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), flow_direction="unknown"))


def test_validate_rejects_empty_categories() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), categories=()))


def test_validate_rejects_empty_rate_kinds() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), rate_kinds=()))


def test_validate_rejects_non_sum_aggregation() -> None:
    with pytest.raises(RegistryValidationError, match="aggregation op 'sum'"):
        validate_ledger_iva_aggregation_binding_definition(_with_aggregation(_binding(), "max"))


def test_validate_rejects_unknown_fact() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), fact="bogus"))


def test_validate_rejects_wrong_source_kind() -> None:
    binding = _binding().model_copy(update={"source": "invoice"})
    with pytest.raises(RegistryValidationError, match="not a ledger_iva_aggregation"):
        validate_ledger_iva_aggregation_binding_definition(binding)


def test_resolve_filters_by_flow_direction_repercutido() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [
        _observation(flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
        _observation(flow=IvaFlowDirection.SOPORTADO, iva=Decimal("105")),
        _observation(flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO, iva=Decimal("90")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("210")}


def test_resolve_filters_by_flow_direction_soportado() -> None:
    revision = _revision_with_bindings(_binding("modelo-303-iva-soportado-interiores-cuota"))
    observations = [
        _observation(flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
        _observation(flow=IvaFlowDirection.SOPORTADO, iva=Decimal("105")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-soportado-interiores-cuota": Decimal("105")}


def test_resolve_filters_by_flow_direction_autorepercutido() -> None:
    revision = _revision_with_bindings(_binding("modelo-303-iva-autorepercutido-intracomunitaria-cuota"))
    observations = [
        _observation(
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("42"),
        ),
        _observation(
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("99"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("42")}


def test_resolve_filters_by_category_set() -> None:
    """The selector's categories tuple is interpreted as a SET match —
    observations whose category is in the tuple count, others don't."""
    observations = [
        _observation(
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("210"),
        ),
        _observation(
            category=IvaCategory.DOMESTIC_REDUCED_10,
            rate_kind=IvaRateKind.REDUCED,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("100"),
        ),
        _observation(
            category=IvaCategory.RECARGO_EQUIVALENCIA,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("999"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(
        _revision_with_bindings(
            _binding(
                "modelo-303-iva-soportado-interiores-cuota",
            )
        ),
        observations,
    )
    # Filter contract verification: the binding's category set excludes
    # RECARGO_EQUIVALENCIA. The aggregator must (1) NOT leak the 999
    # EUR recargo observation into the result and (2) include both
    # DOMESTIC_GENERAL_21 and DOMESTIC_REDUCED_10 observations. This
    # bounds the result between the largest single matching observation
    # and the upper bound that would include the excluded category.
    cuota = result["modelo-303-iva-soportado-interiores-cuota"]
    # Upper bound: the recargo's 999 EUR observation must not leak in.
    assert cuota < Decimal("999"), f"recargo observation leaked into result; got {cuota}"
    # Lower bound: both matching observations must contribute; the
    # result must exceed the largest single matching observation.
    assert cuota > Decimal("210"), f"only one matching observation aggregated; got {cuota}"


def test_resolve_supports_base_amount_sum_fact() -> None:
    revision = _revision_with_bindings(_with_selector(_binding(), fact="base_amount_sum"))
    observations = [
        _observation(base=Decimal("1000"), iva=Decimal("210")),
        _observation(base=Decimal("500"), iva=Decimal("105")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("1500")}


def test_resolve_returns_zero_when_no_observation_matches() -> None:
    revision = _revision_with_bindings(_binding())
    observations = [_observation(category=IvaCategory.RECARGO_EQUIVALENCIA, iva=Decimal("999"))]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-repercutido-general-cuota": Decimal("0")}


def test_resolve_handles_multiple_bindings_independently() -> None:
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-repercutido-general-cuota"),
        _binding("modelo-303-iva-soportado-interiores-cuota"),
    )
    observations = [
        _observation(flow=IvaFlowDirection.REPERCUTIDO, iva=Decimal("210")),
        _observation(flow=IvaFlowDirection.SOPORTADO, iva=Decimal("63")),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-repercutido-general-cuota": Decimal("210"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("63"),
    }


def test_modelo_390_annual_iva_totals_reconcile_with_four_registry_calculated_modelo_303_filings() -> None:
    quarterly_observations = {
        "1T": (
            _observation(ledger_id="q1-output", txn_date=date(2025, 2, 15), iva=Decimal("210.00")),
            _observation(
                ledger_id="q1-input",
                txn_date=date(2025, 3, 1),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("42.00"),
            ),
        ),
        "2T": (
            _observation(ledger_id="q2-output", txn_date=date(2025, 5, 10), iva=Decimal("105.00")),
            _observation(
                ledger_id="q2-input",
                txn_date=date(2025, 6, 20),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("21.00"),
            ),
        ),
        "3T": (
            _observation(
                ledger_id="q3-output-reduced",
                txn_date=date(2025, 8, 12),
                category=IvaCategory.DOMESTIC_REDUCED_10,
                rate_kind=IvaRateKind.REDUCED,
                iva=Decimal("50.00"),
            ),
        ),
        "4T": (
            _observation(
                ledger_id="q4-output-reverse-charge",
                txn_date=date(2025, 11, 4),
                category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=Decimal("84.00"),
            ),
        ),
    }
    quarterly_results = {
        period: _calculate_303_from_observations(
            filing_year=2025,
            period=period,
            observations=observations,
        )
        for period, observations in quarterly_observations.items()
    }
    annual_result = _calculate_390_from_observations_and_303_filings(
        filing_year=2025,
        observations=tuple(row for rows in quarterly_observations.values() for row in rows),
        quarterly_results=quarterly_results,
    )

    chain_pairs = (
        ("iva.cuota-devengada-total", "iva.anual.cuota-devengada-total", "iva.anual.reconciliacion.devengada-303"),
        ("iva.cuota-deducible-total", "iva.anual.cuota-deducible-total", "iva.anual.reconciliacion.deducible-303"),
        (
            "iva.resultado-regimen-general",
            "iva.anual.resultado-regimen-general",
            "iva.anual.reconciliacion.resultado-303",
        ),
    )
    for periodic_casilla, annual_casilla, reconciliation_casilla in chain_pairs:
        periodic_total = sum((result.values[periodic_casilla] for result in quarterly_results.values()), Decimal("0"))
        assert annual_result.values[annual_casilla] == periodic_total
        assert annual_result.values[reconciliation_casilla] == periodic_total


def test_iva_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        setattr(obs, "iva_amount", Decimal("999"))  # noqa: B010 — exercise frozen-model __setattr__
