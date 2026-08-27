"""AEAT-grounded verification of the LIVA art. 104.Tres denominator exclusion.

The oracle figures are the AEAT Manual practico IVA 2025 prorrata-general example
(pages 137-138), bundled in
`corpus/manual_oracles/modelo-303-2025-prorrata-general-regularizacion.json`: the
current-year operations are viviendas 20.000 EUR (exempt, sin derecho) and
locales 25.000 EUR (con derecho), giving an annual con-derecho volume of
25.000 EUR, an annual total volume of 45.000 EUR, and a definitive prorrata of
55,5555% rounded up to 56% (LIVA art. 102.Dos). No value below is derived from
the registry formula under test - every expected number is read from the bundled
manual oracle.

The manual example does not itself carry an art. 104.Tres excluded operation, so
it is augmented with one to exercise the exclusion: a one-off sale of a
non-habitual inmueble (art. 104.Tres 4.º) that would otherwise inflate the
con-derecho volume. Because the law removes it from BOTH terms of the ratio, the
exclusion-filtered ledger rollup must reproduce the manual's 25.000 / 45.000
volumes and hence the manual's 56% - and the anti-tautology companion proves the
exclusion is load-bearing (without it the percentage is not 56%).
"""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core import Period
from ....core.resources import bundled_path
from ....domain.calculations.registry.ledger_bindings import IvaLedgerObservation
from ....domain.iva import (
    IvaCategory,
    IvaExemptionArticle,
    IvaFlowDirection,
    IvaLedgerObservationRole,
    IvaRateKind,
    ProrrataInputs,
    compute_prorrata_definitiva_anual,
)
from .._prorrata_regularizacion import build_prorrata_declared_volume_divergence_advisory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_ORACLE_PATH = Path(
    bundled_path("corpus", "manual_oracles", "modelo-303-2025-prorrata-general-regularizacion.json"),
)

# The augmenting excluded operation: a one-off non-habitual inmueble sale that
# would otherwise be con-derecho output volume (LIVA art. 104.Tres 4.º).
_EXCLUDED_NON_HABITUAL_INMUEBLE_SALE = Decimal("33000.00")

# The manual's current-year 'n' operations: locales 25.000 EUR con derecho and
# viviendas 20.000 EUR exentas sin derecho, annual total 45.000 EUR. These are
# the scenario's GIVENS (input_kind=manual casillas), so they are named
# constants quoting the manual rather than entries in the payload's
# `expected_by_casilla_id`, which is reserved for casillas the registry engine
# computes and a verification expectation reconciles.
_MANUAL_CURRENT_YEAR_CON_DERECHO = Decimal("25000.00")
_MANUAL_CURRENT_YEAR_TOTAL = Decimal("45000.00")


def _oracle_payload() -> dict[str, Any]:
    return json.loads(_ORACLE_PATH.read_text(encoding="utf-8"))


def _oracle_decimal(payload: dict[str, Any], casilla_id: str) -> Decimal:
    return Decimal(str(payload["expected_by_casilla_id"][casilla_id]))


def _periods_2025() -> tuple[Period, ...]:
    return tuple(Period.from_year_and_code(2025, code) for code in ("1T", "2T", "3T", "4T"))


def _con_derecho_locales(con_derecho_volume: Decimal) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="manual-locales-con-derecho",
        transaction_date=date(2025, 3, 10),
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=con_derecho_volume,
        iva_amount=Decimal("0.00"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _sin_derecho_viviendas(sin_derecho_volume: Decimal) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="manual-viviendas-sin-derecho",
        transaction_date=date(2025, 6, 5),
        category=IvaCategory.DOMESTIC_EXEMPT,
        exemption_article=IvaExemptionArticle.ART_20_UNO_8,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=sin_derecho_volume,
        iva_amount=Decimal("0.00"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _excluded_non_habitual_inmueble() -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id="non-habitual-inmueble-sale",
        transaction_date=date(2025, 9, 20),
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.REPERCUTIDO,
        base_amount=_EXCLUDED_NON_HABITUAL_INMUEBLE_SALE,
        iva_amount=Decimal("0.00"),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def test_art_104_tres_exclusion_reproduces_aeat_manual_prorrata_percentage() -> None:
    """Excluding the non-habitual inmueble sale reproduces the manual's 56% definitiva.

    The excluded operation is removed from both terms of the ratio, so the
    exclusion-filtered ledger volumes equal the manual's declared 25.000 /
    45.000 and the definitive percentage equals the manual's 56%.
    """
    payload = _oracle_payload()
    manual_con_derecho = _MANUAL_CURRENT_YEAR_CON_DERECHO
    manual_total = _MANUAL_CURRENT_YEAR_TOTAL
    manual_percentage = _oracle_decimal(payload, "iva.prorrata-porcentaje")
    manual_sin_derecho = manual_total - manual_con_derecho

    observations = (
        _con_derecho_locales(manual_con_derecho),
        _sin_derecho_viviendas(manual_sin_derecho),
        _excluded_non_habitual_inmueble(),
    )

    rollup, _diagnostic = build_prorrata_declared_volume_divergence_advisory(
        declared_volume_total=manual_total,
        declared_volume_con_derecho=manual_con_derecho,
        ledger_observations=observations,
        ejercicio_periods=_periods_2025(),
        regularizacion_year=2025,
        art_104_tres_excluded_ledger_ids=("non-habitual-inmueble-sale",),
    )

    # The excluded operation is removed from both terms: the ledger rollup
    # equals the manual's declared volumes.
    assert rollup.ledger_volume_con_derecho == manual_con_derecho
    assert rollup.ledger_volume_total == manual_total
    assert rollup.art_104_tres_excluded_ledger_ids == ("non-habitual-inmueble-sale",)

    definitiva = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=rollup.ledger_volume_con_derecho,
            operaciones_sin_derecho_deduccion=rollup.ledger_volume_sin_derecho,
        ),
        year=2025,
    )
    assert definitiva.percentage == manual_percentage


def test_without_art_104_tres_exclusion_the_manual_percentage_is_not_reproduced() -> None:
    """Anti-tautology: omitting the exclusion inflates the con-derecho volume off the manual figure.

    If the non-habitual inmueble sale were counted, the con-derecho volume would
    rise above the manual's 25.000 and the definitive percentage would exceed the
    manual's 56%, proving the exclusion is load-bearing rather than a no-op.
    """
    payload = _oracle_payload()
    manual_con_derecho = _MANUAL_CURRENT_YEAR_CON_DERECHO
    manual_total = _MANUAL_CURRENT_YEAR_TOTAL
    manual_percentage = _oracle_decimal(payload, "iva.prorrata-porcentaje")
    manual_sin_derecho = manual_total - manual_con_derecho

    observations = (
        _con_derecho_locales(manual_con_derecho),
        _sin_derecho_viviendas(manual_sin_derecho),
        _excluded_non_habitual_inmueble(),
    )

    rollup, _diagnostic = build_prorrata_declared_volume_divergence_advisory(
        declared_volume_total=manual_total,
        declared_volume_con_derecho=manual_con_derecho,
        ledger_observations=observations,
        ejercicio_periods=_periods_2025(),
        regularizacion_year=2025,
        art_104_tres_excluded_ledger_ids=(),
    )

    assert rollup.ledger_volume_con_derecho == manual_con_derecho + _EXCLUDED_NON_HABITUAL_INMUEBLE_SALE
    unfiltered = compute_prorrata_definitiva_anual(
        ProrrataInputs(
            operaciones_con_derecho_deduccion=rollup.ledger_volume_con_derecho,
            operaciones_sin_derecho_deduccion=rollup.ledger_volume_sin_derecho,
        ),
        year=2025,
    )
    assert unfiltered.percentage != manual_percentage
