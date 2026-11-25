"""Annual ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.core.casilla_id import CasillaId
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope

from .ledger_iva_aggregation_support import (
    M303_COMPENSACION_GENERADA_PERIODO_CASILLA,
    M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA,
    M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA,
    M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    M390_CUOTA_DEVENGADA_TOTAL_CASILLA,
    M390_RECONCILIACION_DEDUCIBLE_303_CASILLA,
    M390_RECONCILIACION_DEVENGADA_303_CASILLA,
    M390_RECONCILIACION_RESULTADO_303_CASILLA,
    M390_RESULTADO_REGIMEN_GENERAL_CASILLA,
    calculate_303_from_observations,
    calculate_390_from_observations_and_303_filings,
    deduction_kind,
    ledger_iva_aggregation_category,
    ledger_iva_aggregation_flow,
    ledger_iva_aggregation_observation,
    ledger_iva_aggregation_rate_kind,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


def _newest_year_both_returns_calculate() -> int:
    """Return the newest supported year in which every 303 quarter and the annual 390 reach calculation grade.

    The pipeline drives the quarterly returns into the annual one, so it needs a year
    whose editions are authored deeply enough for the engine to calculate both. A year
    whose annual edition is only applicability-grade is refused by the snapshot builder,
    which is the registry saying so, not a defect of the pipeline.
    """
    ladder = tuple(RegistryAuthorityGrade)
    coordinates = (("303", "1T"), ("303", "2T"), ("303", "3T"), ("303", "4T"), ("390", "0A"))
    with bundled_indexed_authority().operation() as operation:
        for year in reversed(filing_year_envelope().years):
            if all(
                ladder.index(operation.reachable_authority_grade(modelo, filing_year=year, period=period))
                >= ladder.index(RegistryAuthorityGrade.CALCULATION)
                for modelo, period in coordinates
            ):
                return year
    raise LookupError("no supported year reaches calculation grade for every quarterly 303 and the annual 390")


_YEAR = _newest_year_both_returns_calculate()


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
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="q1-output", txn_date=date(_YEAR, 2, 15), iva=Decimal("21.00")
            ),
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q1-input",
                txn_date=date(_YEAR, 3, 1),
                flow=ledger_iva_aggregation_flow("soportado"),
                iva=Decimal("42.00"),
                deduction_fact_kind=deduction_kind("domestic_current"),
            ),
        ),
        "2T": (
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="q2-output", txn_date=date(_YEAR, 5, 10), iva=Decimal("10.00")
            ),
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q2-input",
                txn_date=date(_YEAR, 6, 20),
                flow=ledger_iva_aggregation_flow("soportado"),
                iva=Decimal("30.00"),
                deduction_fact_kind=deduction_kind("domestic_current"),
            ),
        ),
        "3T": (
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.10"),
                ledger_id="q3-output-reduced",
                txn_date=date(_YEAR, 8, 12),
                category=ledger_iva_aggregation_category("domestic_reduced"),
                rate_kind=ledger_iva_aggregation_rate_kind("reduced"),
                iva=Decimal("50.00"),
            ),
        ),
        "4T": (
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q4-output",
                txn_date=date(_YEAR, 11, 4),
                iva=Decimal("15.00"),
            ),
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q4-input",
                txn_date=date(_YEAR, 12, 12),
                flow=ledger_iva_aggregation_flow("soportado"),
                iva=Decimal("45.00"),
                deduction_fact_kind=deduction_kind("domestic_current"),
            ),
        ),
    }
    quarterly_results = {
        period: calculate_303_from_observations(
            filing_year=_YEAR,
            period=period,
            observations=observations,
        )
        for period, observations in quarterly_observations.items()
    }
    annual_result = calculate_390_from_observations_and_303_filings(
        filing_year=_YEAR,
        observations=tuple(row for rows in quarterly_observations.values() for row in rows),
        quarterly_results=quarterly_results,
    )

    chain_pairs: tuple[tuple[CasillaId, CasillaId], ...] = (
        (M390_CUOTA_DEVENGADA_TOTAL_CASILLA, M390_RECONCILIACION_DEVENGADA_303_CASILLA),
        (M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA, M390_RECONCILIACION_DEDUCIBLE_303_CASILLA),
        (M390_RESULTADO_REGIMEN_GENERAL_CASILLA, M390_RECONCILIACION_RESULTADO_303_CASILLA),
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
        (values[M303_COMPENSACION_GENERADA_PERIODO_CASILLA] for values in non_q4_results),
        Decimal("0"),
    )

    assert (
        annual_result.values[M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA]
        == q4_result[M303_COMPENSACION_GENERADA_PERIODO_CASILLA]
    )
    assert annual_result.values[M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA] == non_q4_generated
    assert annual_result.values[M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA] > Decimal("0")
    assert annual_result.values[M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA] > Decimal("0")


def test_m390_annual_intracom_matches_303_quarters_for_an_eu_services_acquisition() -> None:
    """An EU services acquisition reaches the annual return, not only the quarters.

    Modelo 390 reconciles its annual devengada against the sum of the four
    Modelo 303 quarters, so any category the quarterly line consumes and the
    annual line does not produces a divergence that is either a blocked filing
    or a silently under-declared annual return. Both lines therefore have to
    select the same intra-community acquisition categories.

    The goods and services legs rest on different articles — arts. 13/15 for
    goods, art. 69.Uno.1 read subject to art. 70 for services, with art.
    84.Uno.2.a) making the recipient the sujeto pasivo on either — but AEAT
    reports them on one line, so both legs are booked on both surfaces. The
    expectation is derived by comparing the annual figure against the summed
    quarterly figures, never from a literal.
    """
    services_cuota = Decimal("21.00")
    goods_cuota = Decimal("63.00")
    quarterly_observations = {
        "1T": (
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-1t", txn_date=date(_YEAR, 2, 15), iva=Decimal("210.00")
            ),
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"),
                ledger_id="eu-goods",
                txn_date=date(_YEAR, 3, 1),
                category=ledger_iva_aggregation_category("intra_community_acquisition_reverse_charge"),
                flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo"),
                rate_kind=ledger_iva_aggregation_rate_kind("general"),
                iva=goods_cuota,
                deduction_fact_kind=deduction_kind("intra_eu_current"),
            ),
        ),
        "2T": (
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-2t", txn_date=date(_YEAR, 5, 15), iva=Decimal("105.00")
            ),
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"),
                ledger_id="eu-service",
                txn_date=date(_YEAR, 6, 1),
                category=ledger_iva_aggregation_category("intra_community_service_acquisition_reverse_charge"),
                flow=ledger_iva_aggregation_flow("inversion_sujeto_pasivo"),
                rate_kind=ledger_iva_aggregation_rate_kind("general"),
                iva=services_cuota,
                deduction_fact_kind=deduction_kind("intra_eu_current"),
            ),
        ),
        "3T": (
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-3t", txn_date=date(_YEAR, 8, 15), iva=Decimal("105.00")
            ),
        ),
        "4T": (
            ledger_iva_aggregation_observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-4t", txn_date=date(_YEAR, 11, 15), iva=Decimal("105.00")
            ),
        ),
    }
    quarterly_results = {
        period: calculate_303_from_observations(filing_year=_YEAR, period=period, observations=observations)
        for period, observations in quarterly_observations.items()
    }
    all_observations = tuple(row for rows in quarterly_observations.values() for row in rows)
    annual_result = calculate_390_from_observations_and_303_filings(
        filing_year=_YEAR,
        observations=all_observations,
        quarterly_results=quarterly_results,
    )

    # The annual devengada total must equal the summed quarterly devengada
    # totals. Dropping the services leg from the annual line breaks this by
    # exactly the services cuota.
    summed_quarterly_devengada = sum(
        (result.values[M303_CUOTA_DEVENGADA_TOTAL_CASILLA] for result in quarterly_results.values()),
        Decimal("0"),
    )
    assert annual_result.values[M390_CUOTA_DEVENGADA_TOTAL_CASILLA] == summed_quarterly_devengada
    # And the reconciliation casilla the blocking rule reads must agree with it.
    assert (
        annual_result.values[M390_CUOTA_DEVENGADA_TOTAL_CASILLA]
        == annual_result.values[M390_RECONCILIACION_DEVENGADA_303_CASILLA]
    )
