"""E2E continuity: Modelo 151 Beckham impatriado cuota escala across 2 renta years.

Modelo 151 is the annual IRPF declaration for taxpayers under the régimen
especial de trabajadores desplazados (impatriados, "Ley Beckham", Ley 35/2006
art. 93). Its load-bearing calculation is the cuota íntegra general: the flat
two-band escala of art. 93.2.e).1.º — 24 % on the base liquidable general up to
600.000 euros and 47 % on the excess — computed via ``lookup_bracket`` over the
``modelo-151.escala-cuota-integra-general`` bracket table.

This module is the multi-year-renta authorization enrollment for Modelo 151. It
drives the REAL registry calculation engine (real authority + the real
lookup_bracket runtime — no mocks) across two distinct renta years (2024, 2025),
records each through the :class:`EnrollmentRecorder`, and cross-checks the
recorded year-set against the authorization manifest via
:func:`assert_enrollment_matches_manifest`.

The régimen runs for the change-of-residence year + the five following years
(art. 93 chapeau, "el período impositivo en que se efectúe el cambio de
residencia y durante los cinco períodos impositivos siguientes") — a 6-year
eligibility window. That window is the cross-renta continuity: the régimen (and
its escala) persists year-over-year within the window, so the same cuota rule
applies to two consecutive in-window ejercicios. The two enrolled years (2024,
2025) sit inside one taxpayer's window.

Grounding (non-tautological — A5 / aeat-quality-gates):
the expected cuota is derived from the BOE escala arithmetic (art. 93.2.e.1º),
NOT by re-running the registry formula. For a base liquidable general of
700.000 €: cuota = 600.000 × 0,24 + (700.000 − 600.000) × 0,47 = 144.000 +
47.000 = 191.000,00 €. For 900.000 €: 144.000 + 300.000 × 0,47 = 285.000,00 €.
These are computed by hand from the law's two rates/threshold (the external
authority) and asserted against the engine output — the test fails if the
registry escala drifts from the BOE rates. The art. 93.2.f withholding (24 % /
47 % over 600.000 € on work income) is a pago a cuenta, distinct from this
cuota — subtracted, not part of the escala.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.formula_runtime import RegistryCalculationResult, calculate_registry_snapshot
from ....tests.secure_sql import isolated_runtime_profile
from ..multi_year import EnrollmentRecorder, assert_enrollment_matches_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: Modelo id this module enrolls into the multi-year-renta authorization gate.
_MODELO = "151"

#: The two distinct renta years enrolled — both inside one taxpayer's 6-year
#: Beckham window (e.g. change-of-residence year 2022 → window 2022..2027).
_RENTA_YEARS = (2024, 2025)

#: The art. 93.2.e.1º escala threshold and rates (BOE, ley-35-2006:art-93).
_THRESHOLD = Decimal("600000")
_RATE_LOW = Decimal("0.24")
_RATE_HIGH = Decimal("0.47")
_BASE_LIQUIDABLE_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "impatriado.base-liquidable-general",
    surface="_BASE_LIQUIDABLE_GENERAL_CASILLA",
)
_RETENCIONES_CASILLA: CasillaId = validated_casilla_id(
    "impatriado.retenciones",
    surface="_RETENCIONES_CASILLA",
)
_CUOTA_INTEGRA_GENERAL_CASILLA: CasillaId = validated_casilla_id(
    "impatriado.cuota-integra-general",
    surface="_CUOTA_INTEGRA_GENERAL_CASILLA",
)
_CUOTA_DIFERENCIAL_CASILLA: CasillaId = validated_casilla_id(
    "impatriado.cuota-diferencial",
    surface="_CUOTA_DIFERENCIAL_CASILLA",
)


def _expected_cuota_from_boe_escala(base_liquidable: Decimal) -> Decimal:
    """Derive the expected cuota from the BOE art.93.2.e.1º rates — NOT the registry.

    This is the external-authority oracle: 24 % up to 600.000 € + 47 % on the
    excess, computed by hand from the law's published rates/threshold. The test
    fails if the registry escala drifts from these BOE values.
    """
    if base_liquidable <= _THRESHOLD:
        return (base_liquidable * _RATE_LOW).quantize(Decimal("0.01"))
    low = _THRESHOLD * _RATE_LOW
    high = (base_liquidable - _THRESHOLD) * _RATE_HIGH
    return (low + high).quantize(Decimal("0.01"))


#: Per-year base liquidable general (both above the €600.000 threshold so the
#: two-band escala is genuinely exercised; distinct per year).
_BASE_BY_YEAR: dict[int, Decimal] = {
    2024: Decimal("700000.00"),  # expected cuota 191.000,00
    2025: Decimal("900000.00"),  # expected cuota 285.000,00
}
_RETENCIONES_BY_YEAR: dict[int, Decimal] = {
    2024: Decimal("50000.00"),
    2025: Decimal("70000.00"),
}


def _calculate_151(*, filing_year: int) -> tuple[RegistryCalculationResult, int]:
    """Run the REAL registry 151 cuota calculation for one renta year."""
    snapshot = bundled_authority().snapshot(_MODELO, filing_year=filing_year, period="0A")
    result = calculate_registry_snapshot(
        snapshot,
        inputs={
            _BASE_LIQUIDABLE_GENERAL_CASILLA: _BASE_BY_YEAR[filing_year],
            _RETENCIONES_CASILLA: _RETENCIONES_BY_YEAR[filing_year],
        },
        binding_values={},
        date_context={"filing_period": date(filing_year, 12, 31)},
    )
    return result, len(result.values)


def test_cuota_matches_boe_escala_at_threshold_crossing(tmp_path: Path) -> None:
    """The 151 engine cuota equals the BOE art.93.2.e.1º escala for a threshold-crossing base.

    Base 700.000 € crosses the €600.000 boundary, so both the 24 % and 47 %
    tramos are exercised. The expected cuota (191.000,00) is hand-derived from
    the BOE rates, not the registry formula — non-tautological.
    """
    with isolated_runtime_profile(tmp_path=tmp_path):
        result, produced = _calculate_151(filing_year=2024)

    assert produced > 0
    expected = _expected_cuota_from_boe_escala(_BASE_BY_YEAR[2024])
    assert expected == Decimal("191000.00")
    assert result.values[_CUOTA_INTEGRA_GENERAL_CASILLA] == expected
    # cuota diferencial = cuota − retenciones (art.93.2.f withholding is a pago a cuenta).
    assert result.values[_CUOTA_DIFERENCIAL_CASILLA] == expected - _RETENCIONES_BY_YEAR[2024]


def test_modelo_151_beckham_enrolls_two_renta_years(tmp_path: Path) -> None:
    """End-to-end enrollment: 151 cuota escala across two in-window renta years.

    Drives the REAL 151 engine for 2024 and 2025 (both inside one taxpayer's
    6-year Beckham window — the régimen and its escala persist year-over-year,
    the cross-renta continuity), asserts each year's cuota against the
    hand-derived BOE-escala oracle, records each through the EnrollmentRecorder,
    and cross-checks the year-set against the manifest. A single-year or stub run
    would raise, turning the gate RED.
    """
    recorder = EnrollmentRecorder(_MODELO)
    with isolated_runtime_profile(tmp_path=tmp_path):
        for filing_year in _RENTA_YEARS:
            result, produced = _calculate_151(filing_year=filing_year)
            expected = _expected_cuota_from_boe_escala(_BASE_BY_YEAR[filing_year])
            assert result.values[_CUOTA_INTEGRA_GENERAL_CASILLA] == expected, (
                f"151 cuota for {filing_year} drifted from the BOE art.93.2.e.1º escala"
            )
            recorder.record_calculation_year(filing_year=filing_year, produced_value_count=produced)

    # Independent oracle check: the two years' expected cuotas are the BOE values.
    assert _expected_cuota_from_boe_escala(_BASE_BY_YEAR[2025]) == Decimal("285000.00")

    evidence = recorder.evidence()
    assert evidence.distinct_renta_years == _RENTA_YEARS
    assert_enrollment_matches_manifest(evidence)
