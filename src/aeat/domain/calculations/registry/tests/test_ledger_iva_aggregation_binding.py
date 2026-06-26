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

from .....core.aggregation import BindingAggregation, BindingAggregationOp
from .....core.resources import resources
from ....iva import (
    CUOTA_LESS_M303_IVA_CATEGORIES,
    InvoiceKind,
    IvaCategory,
    IvaFlowDirection,
    IvaRateKind,
    derive_flow_for_classification,
)
from .. import (
    CasillaId,
    DataBindingDefinition,
    IvaLedgerObservation,
    ModeloRevision,
    RegistryCalculationResult,
    RegistryModeloObservation,
    RegistryValidationError,
    calculate_registry_snapshot,
    materialize_relation_binding_values,
    resolve_bound_inputs_by_casilla_id,
    resolve_ledger_iva_aggregation_binding_values,
    unsupported_ledger_iva_observations,
    validate_ledger_iva_aggregation_binding_definition,
    validated_casilla_id,
)
from .._relations import resolve_relation_values_from_observations

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]



def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"ledger IVA aggregation fixture casilla key {value!r} is not a CasillaId") from exc


_M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.interior.devengado",
)
_M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.interior.deducible",
)
_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEVENGADO_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.intracomunitaria.devengado",
)
_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEDUCIBLE_CASILLA: CasillaId = _casilla_id(
    "iva.autorepercutido.intracomunitaria.deducible",
)
_M303_SOPORTADO_IMPORTACIONES_CASILLA: CasillaId = _casilla_id("iva.soportado.importaciones")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-devengada-total")
_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-deducible-total")
_M303_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.resultado-regimen-general")
_M303_COMPENSACION_GENERADA_PERIODO_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")
_M390_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.anual.cuota-devengada-total")
_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA: CasillaId = _casilla_id("iva.anual.cuota-deducible-total")
_M390_RESULTADO_REGIMEN_GENERAL_CASILLA: CasillaId = _casilla_id("iva.anual.resultado-regimen-general")
_M390_RECONCILIACION_DEVENGADA_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.devengada-303",
)
_M390_RECONCILIACION_DEDUCIBLE_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.deducible-303",
)
_M390_RECONCILIACION_RESULTADO_303_CASILLA: CasillaId = _casilla_id(
    "iva.anual.reconciliacion.resultado-303",
)
_M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA: CasillaId = _casilla_id(
    "iva.anual.compensacion-ultimo-periodo-97",
)
_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA: CasillaId = _casilla_id(
    "iva.anual.compensacion-generada-ejercicio-no-97",
)
_M303_REPERCUTIDO_GENERAL_BASE_CASILLA: CasillaId = _casilla_id("07")
_M303_SOPORTADO_INTERIORES_BASE_CASILLA: CasillaId = _casilla_id("28")
_M303_REPERCUTIDO_GENERAL_CUOTA_CASILLA: CasillaId = _casilla_id("09")
_M303_SOPORTADO_INTERIORES_CUOTA_CASILLA: CasillaId = _casilla_id("29")
_M303_REPERCUTIDO_SUPER_REDUCIDO_BASE_CASILLA: CasillaId = _casilla_id("01")
_M303_REPERCUTIDO_REDUCIDO_BASE_CASILLA: CasillaId = _casilla_id("04")


@lru_cache(maxsize=1)
def _modelo_303_revision() -> ModeloRevision:
    modelo = resources().modelos.get("303")
    return modelo.revisions["2009-y-siguientes"]


def _binding(binding_id: str = "modelo-303-iva-repercutido-general-cuota") -> DataBindingDefinition:
    return next(item for item in _modelo_303_revision().bindings if item.id == binding_id)


def _with_selector(binding: DataBindingDefinition, **updates: object) -> DataBindingDefinition:
    return binding.model_copy(update={"selector": {**binding.selector, **updates}})


def _with_aggregation(binding: DataBindingDefinition, op: BindingAggregationOp) -> DataBindingDefinition:
    return binding.model_copy(update={"aggregation": BindingAggregation(op=op)})


def _observation(
    *,
    ledger_id: str = "ledger-1",
    txn_date: date = date(2025, 6, 15),
    category: IvaCategory = IvaCategory.DOMESTIC_GENERAL_21,
    rate_kind: IvaRateKind = IvaRateKind.GENERAL,
    flow: IvaFlowDirection = IvaFlowDirection.REPERCUTIDO,
    base: Decimal = Decimal("1000"),
    iva: Decimal = Decimal("210"),
    recargo: Decimal = Decimal("0"),
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=txn_date,
        category=category,
        rate_kind=rate_kind,
        flow_direction=flow,
        base_amount=base,
        iva_amount=iva,
        recargo_amount=recargo,
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
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
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
    m303_observations = tuple(
        RegistryModeloObservation(
            modelo="303",
            filing_year=filing_year,
            period=period,
            observations=result.observations,
        )
        for period, result in quarterly_results.items()
    )
    relation_values = resolve_relation_values_from_observations(
        snapshot.revision,
        m303_observations,
        filing_year=filing_year,
        period="0A",
    )
    relation_binding_values = materialize_relation_binding_values(snapshot.revision, relation_values, period="0A")
    binding_values = {**ledger_binding_values, **relation_binding_values}
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
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
        validate_ledger_iva_aggregation_binding_definition(_with_aggregation(_binding(), BindingAggregationOp.COPY))


def test_validate_rejects_unknown_fact() -> None:
    with pytest.raises(RegistryValidationError, match="malformed"):
        validate_ledger_iva_aggregation_binding_definition(_with_selector(_binding(), fact="bogus"))


def test_validate_rejects_wrong_source_kind() -> None:
    binding = _binding().model_copy(update={"source": "manual_input"})
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
    assert with_reverse_charge.values[_M303_AUTOREPERCUTIDO_INTERIOR_DEVENGADO_CASILLA] == reverse_charge_cuota
    assert with_reverse_charge.values[_M303_AUTOREPERCUTIDO_INTERIOR_DEDUCIBLE_CASILLA] == reverse_charge_cuota
    # The reverse-charge nets to zero: both totals rose by exactly the
    # self-assessed cuota, so the resultado is unchanged versus the
    # domestic-only filing. Each delta is computed by comparison, not by
    # summing literals (no-tautological-calculation-tests).
    assert (
        with_reverse_charge.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        - domestic_only.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        - domestic_only.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        == reverse_charge_cuota
    )
    assert (
        with_reverse_charge.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == domestic_only.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
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
            ),
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

    chain_pairs: tuple[tuple[CasillaId, CasillaId], ...] = (
        (_M390_CUOTA_DEVENGADA_TOTAL_CASILLA, _M390_RECONCILIACION_DEVENGADA_303_CASILLA),
        (_M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA, _M390_RECONCILIACION_DEDUCIBLE_303_CASILLA),
        (_M390_RESULTADO_REGIMEN_GENERAL_CASILLA, _M390_RECONCILIACION_RESULTADO_303_CASILLA),
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
        (values[_M303_COMPENSACION_GENERADA_PERIODO_CASILLA] for values in non_q4_results),
        Decimal("0"),
    )

    assert (
        annual_result.values[_M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA]
        == q4_result[_M303_COMPENSACION_GENERADA_PERIODO_CASILLA]
    )
    assert annual_result.values[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA] == non_q4_generated
    assert annual_result.values[_M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA] > Decimal("0")
    assert annual_result.values[_M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA] > Decimal("0")


def test_resolve_aic_official_box_parity_routes_devengado_and_deducible_net_zero() -> None:
    """AIC official-box parity: boxes 10/11 devengado + 36/37 deducible, net-zero.

    An ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`` observation on the
    ``INVERSION_SUJETO_PASIVO`` flow is consumed by BOTH new official-box parity
    bindings: the devengado parity binding (official boxes 10/11, LIVA art. 13 +
    art. 15 + art. 84.Uno.2) and the deducible parity binding (official boxes
    36/37, + art. 92). Each resolves the same self-assessed cuota, so the pair
    nets to zero — mirroring the autorepercutido-interior pair. A ``SOPORTADO``
    row on the same category must NOT leak in (different flow).
    """
    revision = _revision_with_bindings(
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"),
        _binding("modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota"),
    )
    observations = [
        _observation(
            ledger_id="aic-isp",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            iva=Decimal("84.00"),
        ),
        _observation(
            ledger_id="aic-stray-soportado",
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("99.00"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("84.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("84.00"),
    }
    devengado = result["modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota"]
    deducible = result["modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota"]
    assert devengado - deducible == Decimal("0")


def test_calculate_303_aic_official_box_parity_books_boxes_and_leaves_resultado_unchanged() -> None:
    """End-to-end: an AIC ISP observation books the parity casillas and nets to zero.

    The AIC self-assessed cuota lands on the official-box parity casillas
    (``iva.autorepercutido.intracomunitaria.devengado`` = boxes 10/11,
    ``...deducible`` = boxes 36/37), each echoing the observation's own
    ``iva_amount`` (the binding copies the ledger fact). Because the existing
    ``iva.autorepercutido.intracomunitaria`` semantic casilla already books the
    AIC cuota into the resultado, the parity casillas are NOT in the resultado
    formula — so adding the AIC observation changes the resultado by exactly the
    already-net-zero ISP contribution, i.e. leaves it unchanged versus a filing
    with no AIC. Deltas are computed by comparison, never by summing literals
    (no-tautological-calculation-tests).
    """
    aic_cuota = Decimal("84.00")
    domestic_only = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(_observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),),
    )
    with_aic = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("21.00")),
            _observation(
                ledger_id="aic-isp",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                iva=aic_cuota,
            ),
        ),
    )
    assert with_aic.values[_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEVENGADO_CASILLA] == aic_cuota
    assert with_aic.values[_M303_AUTOREPERCUTIDO_INTRACOMUNITARIA_DEDUCIBLE_CASILLA] == aic_cuota
    # The AIC contribution nets to zero in the resultado (the semantic
    # intracomunitaria casilla feeds both totals equally); the parity casillas
    # are pure official-box exposure, not in the resultado formula.
    assert (
        with_aic.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == domestic_only.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
    )


def test_resolve_import_third_country_routes_deducible_only() -> None:
    """Third-country import deducible routing: box 33, real deduction.

    An ``IMPORT_THIRD_COUNTRY`` observation on the ``SOPORTADO`` flow (the only
    leg that reaches M303 — output IVA is settled at customs/DUA) is consumed by
    the new ``modelo-303-iva-soportado-importaciones-cuota`` binding (official box
    33, LIVA art. 17 hecho imponible + art. 92 cuotas deducibles). Unlike the
    reverse-charge pairs this is NOT net-zero: there is no offsetting devengado
    binding for imports.
    """
    revision = _revision_with_bindings(_binding("modelo-303-iva-soportado-importaciones-cuota"))
    observations = [
        _observation(
            ledger_id="import",
            category=IvaCategory.IMPORT_THIRD_COUNTRY,
            flow=IvaFlowDirection.SOPORTADO,
            iva=Decimal("33.00"),
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {"modelo-303-iva-soportado-importaciones-cuota": Decimal("33.00")}


def test_calculate_303_import_deducible_reduces_resultado_by_its_cuota() -> None:
    """End-to-end: an import deducible observation lowers the resultado by its cuota.

    The import IVA borne at customs is genuinely deductible (LIVA art. 92), so
    booking an ``IMPORT_THIRD_COUNTRY`` SOPORTADO observation raises the
    cuota-deducible-total by the observation's own ``iva_amount`` and lowers the
    resultado régimen general by the same amount versus a filing without the
    import. Both deltas are computed by comparison, not by summing literals.
    """
    import_cuota = Decimal("33.00")
    without_import = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(_observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")),),
    )
    with_import = _calculate_303_from_observations(
        filing_year=2025,
        period="1T",
        observations=(
            _observation(ledger_id="sale", txn_date=date(2025, 2, 15), iva=Decimal("210.00")),
            _observation(
                ledger_id="import",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.IMPORT_THIRD_COUNTRY,
                flow=IvaFlowDirection.SOPORTADO,
                iva=import_cuota,
            ),
        ),
    )
    assert with_import.values[_M303_SOPORTADO_IMPORTACIONES_CASILLA] == import_cuota
    assert (
        with_import.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        - without_import.values[_M303_CUOTA_DEDUCIBLE_TOTAL_CASILLA]
        == import_cuota
    )
    assert (
        without_import.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        - with_import.values[_M303_RESULTADO_REGIMEN_GENERAL_CASILLA]
        == import_cuota
    )


def test_64_advisory_no_longer_fires_on_aic_or_import() -> None:
    """#64 advisory: the routed AIC + import observations are no longer flagged.

    With the AIC official-box parity bindings and the import deducible binding in
    place, an ``INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE`` ISP observation and an
    ``IMPORT_THIRD_COUNTRY`` SOPORTADO observation are both consumed by a binding,
    so neither appears in the unconsumed-declarable advisory's flagged set.
    """
    revision = _modelo_303_revision()
    aic = _observation(
        ledger_id="aic",
        category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
        flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
        iva=Decimal("84.00"),
    )
    import_row = _observation(
        ledger_id="import",
        category=IvaCategory.IMPORT_THIRD_COUNTRY,
        flow=IvaFlowDirection.SOPORTADO,
        iva=Decimal("33.00"),
    )
    assert unsupported_ledger_iva_observations(revision, (aic, import_row)) == ()


def test_64_advisory_residual_flagged_set_is_empty_for_all_declarable_categories() -> None:
    """#64 advisory residual is empty for every realistically-classifiable category.

    For each declarable :class:`IvaCategory` (excluding the cuota-less-by-law set
    and the non-declarable sentinels) projected on the canonical flow the
    application classifier emits for it (via ``derive_flow_for_classification``,
    with the rate kind that matches the category), no observation lands in the
    unconsumed-declarable advisory's flagged set — the M303 routing tail (reverse-charge
    + AIC parity + import deducible routing) leaves no
    cuota-bearing declarable category unrouted.

    The synthesised observation uses the rate kind the category implies
    (reduced/super-reduced map to their tier; all others to general) and the
    invoice direction the operation occurs under (imports are received; supplies
    and sales are issued), so the projection matches what the live classifier
    would emit rather than an impossible combination.
    """
    revision = _modelo_303_revision()
    non_declarable = {
        IvaCategory.RECARGO_EQUIVALENCIA,
        IvaCategory.UNKNOWN,
        IvaCategory.ERRONEOUS_INVOICE,
    }
    rate_for_category = {
        IvaCategory.DOMESTIC_REDUCED_10: IvaRateKind.REDUCED,
        IvaCategory.DOMESTIC_SUPER_REDUCED_4: IvaRateKind.SUPER_REDUCED,
    }
    # Imports are an inbound purchase the operator received; everything else here
    # is an outbound sale/supply the operator issued. This is the realistic
    # invoice direction the live classifier produces per category.
    received_categories = {IvaCategory.IMPORT_THIRD_COUNTRY}

    flagged: list[tuple[str, str]] = []
    for category in IvaCategory:
        if category in non_declarable or category in CUOTA_LESS_M303_IVA_CATEGORIES:
            continue
        invoice_direction = InvoiceKind.RECEIVED if category in received_categories else InvoiceKind.ISSUED
        flow = derive_flow_for_classification(category=category, invoice_direction=invoice_direction)
        observation = _observation(
            ledger_id=f"probe-{category.value}",
            category=category,
            rate_kind=rate_for_category.get(category, IvaRateKind.GENERAL),
            flow=flow,
            iva=Decimal("10.00"),
        )
        if unsupported_ledger_iva_observations(revision, (observation,)):
            flagged.append((category.value, flow.value))

    assert flagged == [], f"#64 advisory residual must be empty; still flagged: {sorted(flagged)}"


def test_box_59_carries_substantive_intra_community_supply_grounding() -> None:
    """Box 59: substantive ground is LIVA art. 25, not the generic art. 88/92.

    Casilla 59 reports the base of exempt intra-community supplies; its
    substantive legal_ref is ``ley-37-1992:art-25`` (exención entregas
    intracomunitarias). The former repercusión/deducción articles 88/92 (which do
    not apply to an exempt entrega) must be gone. Asserted against the loaded
    registry revision, both 2009 and 2023.
    """
    for revision_id in ("2009-y-siguientes", "2023-y-siguientes"):
        revision = resources().modelos.get("303").revisions[revision_id]
        casilla_59 = next(casilla for casilla in revision.casillas if casilla.number == "59")
        refs = tuple(casilla_59.legal_refs)
        assert "ley-37-1992:art-25" in refs, f"{revision_id}: box 59 must cite art-25"
        assert "ley-37-1992:art-88" not in refs, f"{revision_id}: box 59 must drop art-88"
        assert "ley-37-1992:art-92" not in refs, f"{revision_id}: box 59 must drop art-92"


def test_box_60_carries_substantive_export_grounding() -> None:
    """Box 60: substantive grounds are LIVA art. 21 + art. 22.

    Casilla 60 reports the base of exempt exports and operations treated as
    exports; its substantive legal_refs are ``ley-37-1992:art-21`` (exenciones
    exportaciones) and ``ley-37-1992:art-22`` (exenciones asimiladas a las
    exportaciones), the latter matching the casilla label's "operaciones
    asimiladas" leg. Asserted against the loaded registry revision, both 2009
    and 2023.
    """
    for revision_id in ("2009-y-siguientes", "2023-y-siguientes"):
        revision = resources().modelos.get("303").revisions[revision_id]
        casilla_60 = next(casilla for casilla in revision.casillas if casilla.number == "60")
        refs = tuple(casilla_60.legal_refs)
        assert "ley-37-1992:art-21" in refs, f"{revision_id}: box 60 must cite art-21"
        assert "ley-37-1992:art-22" in refs, f"{revision_id}: box 60 must cite art-22"


def test_modelo_303_2024_domestic_base_aggregates_from_ledger() -> None:
    """Regression: casillas 07/28 (base imponible) aggregate the ledger base.

    Before the domestic base bindings landed, casillas 01/04/07/28 were
    ``input_kind = "manual"`` with no binding, so the base imponible stayed 0
    while the cuota (09/29) resolved from the ledger — a structurally
    inconsistent M303 (cuota without base) that nonetheless passed verify. The
    base now aggregates via ``fact = "base_amount_sum"``, mirroring the existing
    59/60 export / intra-community base bindings.

    Expected values are the declared observation base sums (ground truth from the
    inputs, not a re-run of the registry formula), so a regression to the manual
    no-binding state (base -> 0) fails this test loudly.
    """
    repercutido = _observation(
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("6500"),
        iva=Decimal("1365"),
    )
    soportado = _observation(
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.SOPORTADO,
        base=Decimal("300"),
        iva=Decimal("63"),
    )
    result = _calculate_303_from_observations(
        filing_year=2024,
        period="2T",
        observations=(repercutido, soportado),
    )
    # Base imponible boxes now carry the ledger base sum (the regression target).
    assert result.values[_M303_REPERCUTIDO_GENERAL_BASE_CASILLA] == Decimal("6500")
    assert result.values[_M303_SOPORTADO_INTERIORES_BASE_CASILLA] == Decimal("300")
    # Cuota boxes are unchanged — the base binding is independent of the cuota
    # binding (casilla 09 is not base x tipo here, it is its own aggregation).
    assert result.values[_M303_REPERCUTIDO_GENERAL_CUOTA_CASILLA] == Decimal("1365")
    assert result.values[_M303_SOPORTADO_INTERIORES_CUOTA_CASILLA] == Decimal("63")
    # No reduced / super-reduced operations -> those base boxes resolve to zero.
    assert result.values[_M303_REPERCUTIDO_SUPER_REDUCIDO_BASE_CASILLA] == Decimal("0")
    assert result.values[_M303_REPERCUTIDO_REDUCIDO_BASE_CASILLA] == Decimal("0")


def test_modelo_303_2009_revision_domestic_base_aggregates_from_ledger() -> None:
    """#15 regression: the 2009-y-siguientes revision (filing years 2009-2022)
    now aggregates the domestic base imponible from the ledger.

    The 2009 revision (inline-declared) carried the cuota ledger bindings (and the
    compensación carry + verification) but lacked the domestic-base bindings that
    the 2023-y-siguientes revision has, so casillas 01/04/07/28 were
    ``input_kind = "manual"`` and a ledger-driven 2009-2022 M303 left the base at 0
    while the cuota resolved — a "cuota without base" under-declaration. This fixes
    that by back-filling the four base bindings (``fact = "base_amount_sum"``,
    selectors mirroring the 2023 revision). filing_year=2022 resolves to the
    2009-y-siguientes revision; this test fails loudly if the base regresses to the
    unbound manual state (0). Expected values are the seeded observation base sums
    (ground truth from inputs, not a re-run of the registry formula).
    """
    snapshot = resources().modelos.authority.snapshot("303", filing_year=2022, period="2T")
    assert snapshot.revision.id == "2009-y-siguientes"  # filing_year 2022 resolves to the older revision
    observations = (
        _observation(
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.REPERCUTIDO,
            base=Decimal("6500"),
            iva=Decimal("1365"),
        ),
        _observation(
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow=IvaFlowDirection.SOPORTADO,
            base=Decimal("300"),
            iva=Decimal("63"),
        ),
    )
    values = resolve_ledger_iva_aggregation_binding_values(snapshot.revision, observations)
    binding_values = {
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0"),
        **values,
    }
    # The back-filled base bindings now aggregate the ledger base on the 2009
    # revision (the #15 regression target). Before the fix these binding ids did
    # not exist, so the base never resolved and the numbered boxes stayed 0.
    assert values["modelo-303-iva-repercutido-general-base"] == Decimal("6500")
    assert values["modelo-303-iva-soportado-interiores-base"] == Decimal("300")
    assert values["modelo-303-iva-repercutido-super-reducido-base"] == Decimal("0")
    assert values["modelo-303-iva-repercutido-reducido-base"] == Decimal("0")
    # The pre-existing cuota bindings still aggregate — base and cuota coexist, no
    # regression on the 2009 revision's existing capability.
    assert values["modelo-303-iva-repercutido-general-cuota"] == Decimal("1365")
    assert values["modelo-303-iva-soportado-interiores-cuota"] == Decimal("63")
    # The new base bindings map to the numbered base casillas (01/04/07/28).
    inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    assert inputs[_M303_REPERCUTIDO_GENERAL_BASE_CASILLA] == Decimal("6500")
    assert inputs[_M303_SOPORTADO_INTERIORES_BASE_CASILLA] == Decimal("300")


def test_iva_ledger_observation_is_strict_and_frozen() -> None:
    obs = _observation()
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        obs.iva_amount = Decimal("999")


def test_recargo_equivalencia_cuota_aggregates_by_tier_from_recargo_amount() -> None:
    """A supplier's recargo charged on a repercutido sale aggregates into the M303
    recargo cuota casillas by IVA tier (LIVA art. 161), instead of reporting zero.

    Expected values derive from the recargo amounts placed on the observations,
    routed by category to the matching tier binding — not from re-running the sum
    under test. Proves the recargo_amount_sum fact closes the recargo silent zero.
    """
    revision = resources().modelos.get("303").revisions["2023-y-siguientes"]
    general = _observation(
        ledger_id="rec-general",
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("1000"),
        iva=Decimal("210"),
        recargo=Decimal("52.00"),
    )
    reduced = _observation(
        ledger_id="rec-reduced",
        category=IvaCategory.DOMESTIC_REDUCED_10,
        rate_kind=IvaRateKind.REDUCED,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("1000"),
        iva=Decimal("100"),
        recargo=Decimal("14.00"),
    )
    # A normal sale with no recargo contributes zero to the recargo cuota.
    plain = _observation(
        ledger_id="plain-general",
        category=IvaCategory.DOMESTIC_GENERAL_21,
        rate_kind=IvaRateKind.GENERAL,
        flow=IvaFlowDirection.REPERCUTIDO,
        base=Decimal("2000"),
        iva=Decimal("420"),
        recargo=Decimal("0"),
    )

    resolved = resolve_ledger_iva_aggregation_binding_values(revision, (general, reduced, plain))

    assert resolved["modelo-303-recargo-equivalencia-general-cuota"] == Decimal("52.00")
    assert resolved["modelo-303-recargo-equivalencia-reducido-cuota"] == Decimal("14.00")
    assert resolved["modelo-303-recargo-equivalencia-super-reducido-cuota"] == Decimal("0")
