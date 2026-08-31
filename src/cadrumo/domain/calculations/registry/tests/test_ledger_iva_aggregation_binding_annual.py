"""Annual ledger IVA aggregation binding tests."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.casilla_id import CasillaId
from .....core.iva_deduction_fact import IvaDeductionFactKind
from ....iva.flow import IvaFlowDirection
from ....iva.schema import IvaCategory, IvaRateKind
from ._ledger_iva_aggregation_support import (
    _M303_COMPENSACION_GENERADA_PERIODO_CASILLA,
    _M303_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M390_COMPENSACION_GENERADA_EJERCICIO_NO_97_CASILLA,
    _M390_COMPENSACION_ULTIMO_PERIODO_97_CASILLA,
    _M390_CUOTA_DEDUCIBLE_TOTAL_CASILLA,
    _M390_CUOTA_DEVENGADA_TOTAL_CASILLA,
    _M390_RECONCILIACION_DEDUCIBLE_303_CASILLA,
    _M390_RECONCILIACION_DEVENGADA_303_CASILLA,
    _M390_RECONCILIACION_RESULTADO_303_CASILLA,
    _M390_RESULTADO_REGIMEN_GENERAL_CASILLA,
    _calculate_303_from_observations,
    _calculate_390_from_observations_and_303_filings,
    _observation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


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
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="q1-output", txn_date=date(2025, 2, 15), iva=Decimal("21.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q1-input",
                txn_date=date(2025, 3, 1),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("42.00"),
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            ),
        ),
        "2T": (
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="q2-output", txn_date=date(2025, 5, 10), iva=Decimal("10.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q2-input",
                txn_date=date(2025, 6, 20),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("30.00"),
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            ),
        ),
        "3T": (
            _observation(
                applied_rate=Decimal("0.10"),
                ledger_id="q3-output-reduced",
                txn_date=date(2025, 8, 12),
                category=IvaCategory.DOMESTIC_REDUCED,
                rate_kind=IvaRateKind.REDUCED,
                iva=Decimal("50.00"),
            ),
        ),
        "4T": (
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q4-output",
                txn_date=date(2025, 11, 4),
                iva=Decimal("15.00"),
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="q4-input",
                txn_date=date(2025, 12, 12),
                flow=IvaFlowDirection.SOPORTADO,
                iva=Decimal("45.00"),
                deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
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
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-1t", txn_date=date(2025, 2, 15), iva=Decimal("210.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="eu-goods",
                txn_date=date(2025, 3, 1),
                category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                rate_kind=IvaRateKind.GENERAL,
                iva=goods_cuota,
                deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            ),
        ),
        "2T": (
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-2t", txn_date=date(2025, 5, 15), iva=Decimal("105.00")
            ),
            _observation(
                applied_rate=Decimal("0.21"),
                ledger_id="eu-service",
                txn_date=date(2025, 6, 1),
                category=IvaCategory.INTRA_COMMUNITY_SERVICE_ACQUISITION_REVERSE_CHARGE,
                flow=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
                rate_kind=IvaRateKind.GENERAL,
                iva=services_cuota,
                deduction_fact_kind=IvaDeductionFactKind.INTRA_EU_CURRENT,
            ),
        ),
        "3T": (
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-3t", txn_date=date(2025, 8, 15), iva=Decimal("105.00")
            ),
        ),
        "4T": (
            _observation(
                applied_rate=Decimal("0.21"), ledger_id="sale-4t", txn_date=date(2025, 11, 15), iva=Decimal("105.00")
            ),
        ),
    }
    quarterly_results = {
        period: _calculate_303_from_observations(filing_year=2025, period=period, observations=observations)
        for period, observations in quarterly_observations.items()
    }
    all_observations = tuple(row for rows in quarterly_observations.values() for row in rows)
    annual_result = _calculate_390_from_observations_and_303_filings(
        filing_year=2025,
        observations=all_observations,
        quarterly_results=quarterly_results,
    )

    # The annual devengada total must equal the summed quarterly devengada
    # totals. Dropping the services leg from the annual line breaks this by
    # exactly the services cuota.
    summed_quarterly_devengada = sum(
        (result.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA] for result in quarterly_results.values()),
        Decimal("0"),
    )
    assert annual_result.values[_M390_CUOTA_DEVENGADA_TOTAL_CASILLA] == summed_quarterly_devengada
    # And the reconciliation casilla the blocking rule reads must agree with it.
    assert (
        annual_result.values[_M390_CUOTA_DEVENGADA_TOTAL_CASILLA]
        == annual_result.values[_M390_RECONCILIACION_DEVENGADA_303_CASILLA]
    )
