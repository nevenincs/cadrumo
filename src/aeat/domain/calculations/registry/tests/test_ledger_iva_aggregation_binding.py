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

from .....core.resources import resources
from ....iva import (
    IvaCategory,
    IvaFlowDirection,
    IvaRateKind,
)
from .. import (
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
    unsupported_ledger_iva_observations,
    validate_ledger_iva_aggregation_binding_definition,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
        # No promotor-autoconsumo (Art. 84 ISP property-developer self-supply)
        # in this reconciliation fixture; supply the neutral zero base.
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
        # Common-territory taxpayer: 100 % of IVA attributable to the state.
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
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


def test_resolve_routes_domestic_reverse_charge_to_devengado_and_deducible_net_zero() -> None:
    """Domestic inversión del sujeto pasivo (LIVA art. 84.Uno.2) books both sides.

    A ``DOMESTIC_REVERSE_CHARGE`` observation on the ``INVERSION_SUJETO_PASIVO``
    flow (as the application classifier now emits via
    ``derive_flow_for_classification``) is consumed by BOTH new bindings:
    ``modelo-303-iva-autorepercutido-interior-devengado-cuota`` (official box 13)
    and ``modelo-303-iva-autorepercutido-interior-deducible-cuota`` (official box
    37). Each resolves the same self-assessed cuota, so the pair nets to zero in
    the resultado. The ``SOPORTADO`` reverse-charge observation must NOT leak in
    (it is a different flow and the application gate would never emit it).
    """
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-autorepercutido-interior-devengado-cuota"),
        _binding("modelo-303-iva-autorepercutido-interior-deducible-cuota"),
    )
    observations = [
        _observation(
            ledger_id="domestic-rc",
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("42.00"),
        ),
        # A stray SOPORTADO reverse-charge row must not be selected by the
        # inversion_sujeto_pasivo-flow bindings.
        _observation(
            ledger_id="stray-soportado",
            category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("99.00"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("42.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("42.00"),
    }
    devengado = result["modelo-303-iva-autorepercutido-interior-devengado-cuota"]
    deducible = result["modelo-303-iva-autorepercutido-interior-deducible-cuota"]
    assert devengado - deducible == Decimal("0")


def test_resolve_intracomunitaria_binding_consumes_inversion_sujeto_pasivo_flow() -> None:
    """The intracomunitaria binding resolves the ISP-flow observation.

    Pre-flow-fix the application classifier left intra-community-acquisition
    reverse-charge observations on a direction-only ``SOPORTADO`` flow, so this
    ``inversion_sujeto_pasivo``-flow binding was effectively unreachable from the
    ledger path. With the classifier now routing reverse-charge categories to
    ``INVERSION_SUJETO_PASIVO``, the binding consumes the observation; a
    ``SOPORTADO`` row on the same category must NOT match.
    """
    revision = _revision_with_bindings(_binding("modelo-303-iva-autorepercutido-intracomunitaria-cuota"))
    observations = [
        _observation(
            ledger_id="ica-isp",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("63.00"),
        ),
        _observation(
            ledger_id="ica-soportado",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("77.00"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("63.00")}


def test_calculate_303_domestic_reverse_charge_books_boxes_13_and_37_with_zero_net_impact() -> None:
    """End-to-end: a reverse-charge ISP observation books box 13 + 37 and nets to zero.

    Calculates the M303 snapshot from a domestic sale plus a domestic
    reverse-charge ISP observation whose self-assessed cuota the autorepercutido
    interior bindings echo verbatim. Box 13 (devengado) and box 37 (deducible)
    must each equal the observation's own ``iva_amount`` (the binding copies the
    ledger fact; no hand-computed aggregate is asserted). Because the same cuota
    lands on BOTH the cuota-devengada-total and the cuota-deducible-total (LIVA
    art. 84.Uno.2 + art. 92 deduction), the reverse-charge contribution to the
    resultado is exactly zero — the resultado and both totals' *deltas* versus the
    domestic-only filing are derived by comparison, never by literal addition.
    """
    reverse_charge_cuota = Decimal("63.00")
    domestic_only = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(_observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),),
    )
    with_reverse_charge = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),
            _observation(
                ledger_id="domestic-rc",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=reverse_charge_cuota,
            ),
        ),
    )
    # Box 13 (devengado) and box 37 (deducible) both echo the self-assessed cuota
    # the observation carried — the binding copies the ledger fact verbatim.
    assert with_reverse_charge.values["iva.autorepercutido.interior.devengado"] == reverse_charge_cuota
    assert with_reverse_charge.values["iva.autorepercutido.interior.deducible"] == reverse_charge_cuota
    # The reverse-charge nets to zero: both totals rose by exactly the
    # self-assessed cuota, so the resultado is unchanged versus the
    # domestic-only filing. Each delta is computed by comparison, not by
    # summing literals (no-tautological-calculation-tests).
    assert (
        with_reverse_charge.values["iva.cuota-devengada-total"]
        - domestic_only.values["iva.cuota-devengada-total"]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values["iva.cuota-deducible-total"]
        - domestic_only.values["iva.cuota-deducible-total"]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values["iva.resultado-regimen-general"]
        == domestic_only.values["iva.resultado-regimen-general"]
    )


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


def test_unsupported_ledger_iva_observations_identifies_unbound_regimes() -> None:
    revision = _revision_with_bindings(_binding())
    supported = _observation(ledger_id="ordinary-output")
    unsupported = _observation(
        ledger_id="recargo-row",
        category=IvaCategory.RECARGO_EQUIVALENCIA,
        flow=IvaFlowDirection.SOPORTADO,
        iva=Decimal("5.20"),
    )

    assert unsupported_ledger_iva_observations(revision, (supported, unsupported)) == (unsupported,)


def test_unsupported_excludes_cuota_less_by_law_categories() -> None:
    """#64 refinement: cuota-less-by-law categories must not be flagged as unsupported.

    An ``INTRA_COMMUNITY_SUPPLY`` repercutido observation (entrega
    intracomunitaria exenta, Ley 37/1992 art. 25) bears zero M303 cuota and
    correctly matches no cuota binding; it must be excluded from the unsupported
    set, whereas a ``DOMESTIC_REVERSE_CHARGE`` observation that genuinely bears a
    cuota but is routed by no binding yet must still be flagged.
    """
    revision = _revision_with_bindings(_binding())
    exempt_supply = _observation(
        ledger_id="intra-community-supply",
        category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        flow=IvaFlowDirection.REPERCUTIDO,
        iva=Decimal("0"),
    )
    reverse_charge = _observation(
        ledger_id="domestic-reverse-charge",
        category=IvaCategory.DOMESTIC_REVERSE_CHARGE,
        flow=IvaFlowDirection.SOPORTADO,
        iva=Decimal("42.00"),
    )

    assert unsupported_ledger_iva_observations(revision, (exempt_supply, reverse_charge)) == (reverse_charge,)


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


def test_modelo_390_annual_iva_pipeline_resolves_binding_chain_from_four_303_filings() -> None:
    """The 390 annual snapshot resolves its 303-sourced bindings and produces the expected casillas.

    This test asserts binding-resolution wiring: the annual 390 engine must
    produce the annual ledger-derived totals, the four-period 303
    reconciliation totals, and the annual compensation casillas 97/662.
    Expected compensation values are read from the generated quarterly 303
    observations, so the test does not mirror the 390 binding aggregation
    formulas.
    """
    quarterly_observations = {
        "1T": (
            _observation(ledger_id="q1-output", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),
            _observation(
                ledger_id="q1-input",
                txn_date=date(2025, 3, 1),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("42.00"),
            ),
        ),
        "2T": (
            _observation(ledger_id="q2-output", txn_date=date(2025, 5, 10), iva=Decimal("10.00")),
            _observation(
                ledger_id="q2-input",
                txn_date=date(2025, 6, 20),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("30.00"),
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
                ledger_id="q4-output",
                txn_date=date(2025, 11, 4),
                iva=Decimal("15.00"),
            ),
            _observation(
                ledger_id="q4-input",
                txn_date=date(2025, 12, 12),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("45.00"),
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
        ("iva.anual.cuota-devengada-total", "iva.anual.reconciliacion.devengada-303"),
        ("iva.anual.cuota-deducible-total", "iva.anual.reconciliacion.deducible-303"),
        ("iva.anual.resultado-regimen-general", "iva.anual.reconciliacion.resultado-303"),
    )
    for annual_casilla, reconciliation_casilla in chain_pairs:
        assert annual_casilla in annual_result.values, f"{annual_casilla!r} missing from 390 result"
        assert reconciliation_casilla in annual_result.values, f"{reconciliation_casilla!r} missing from 390 result"
        assert annual_result.values[annual_casilla] == annual_result.values[reconciliation_casilla], (
            f"{annual_casilla!r} and {reconciliation_casilla!r} must be equal "
            "between annual ledger totals and 303 reconciliation totals"
        )

    q4_result = quarterly_results["4T"].values
    non_q4_results = tuple(result.values for period, result in quarterly_results.items() if period != "4T")
    non_q4_generated = sum(
        (values["iva.compensacion-generada-periodo"] for values in non_q4_results),
        Decimal("0"),
    )

    assert (
        annual_result.values["iva.anual.compensacion-ultimo-periodo-97"]
        == q4_result["iva.compensacion-generada-periodo"]
    )
    assert annual_result.values["iva.anual.compensacion-generada-ejercicio-no-97"] == non_q4_generated
    assert annual_result.values["iva.anual.compensacion-ultimo-periodo-97"] > Decimal("0")
    assert annual_result.values["iva.anual.compensacion-generada-ejercicio-no-97"] > Decimal("0")


def test_iva_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        obs.iva_amount = Decimal("999")
