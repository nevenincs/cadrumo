"""M100 anualidades por alimentos separate-escala for 2020-2023.

LIRPF art. 64 (estatal) / art. 75 (autonómica) grant judicial anualidades por
alimentos a favor de los hijos a SEPARATE-escala treatment: the art. 63 escala
is applied separately to the anualidades (casilla 0527) and to the rest of the
base liquidable general (0505 - 0527), and the total is minorada by the escala
applied to the mínimo personal y familiar INCREMENTADO EN 1.980 EUR, floored at
0. This module proves this régimen for the 2020-2023 revisions in addition to
2024/2025, where casilla 0505 is now computed (max(0, 0500)) rather than a
manual input.

Casilla 0527 input surface differs by year, verified against the bundled AEAT
Diseño de Registros for each revision. 2020 and 2021 both carry 0527 (IMPALIM)
as a single scalar `tipo_ImpPositivo` field (2021 XSD: `maxOccurs="1"`) with no
per-child structure, so it is a direct manual input in both years. 2022 and
2023 introduce a 5-child "Hijo/Hija N: Importe de las anualidades por alimentos
satisfechas" repeating block (casillas 1741/1744/1747.../1759) and 0527 is
computed as their sum (the 2021 revision's now-deleted
`renta-2021-anualidades-alimentos-hijos-suma` formula wrongly summed casillas
1741/1744/1749/1754/1759, which in 2021 are unrelated Anexo C
aportaciones/contribuciones a sistemas de previsión social fields, not the
per-child anualidades block that only exists from 2022 onward).

Non-tautological grounding: the expected cuota is DERIVED from the LIRPF art. 63
escala general estatal tramos (external BOE authority, bundled ley-35-2006.html;
verified per-year against each renta-{year}-escala-estatal-base-general registry
parameter — 2020 carries 5 tramos with no 300.000 € split, since that split
arrived via Ley 11/2020 effective 2021; 2021-2024 carry 6 tramos), applied
through the separate-escala ASSEMBLY that art. 64 mandates (escala(0527) +
escala(0505 - 0527) - escala(mínimo + 1.980), floored). The lookup_bracket
primitive is separately tested; what these tests exercise is the if_then_else
régimen assembly. The actual computed 0505 and 0521 are read from the engine
and fed into the derivation, so the tests are robust to the upstream
base-liquidable / mínimo chain and pin the assembly, not those inputs. The
ordering shortcut < separate < no-benefit is the structural anchor: the fix
raises the cuota above the retired subtract-from-base shortcut while keeping the
benefit genuine (below the no-benefit single escala).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core import CasillaId, validated_casilla_id
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ..authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEPARATE_ESCALA_YEARS = (2020, 2021, 2022, 2023)
_TOLERANCE = Decimal("0.01")

# LIRPF art. 63 escala general estatal tramos, per year (BOE consolidated Ley
# 35/2006 art. 63; verified byte-identical against each
# renta-{year}-escala-estatal-base-general registry parameter). 2020 carries
# 5 tramos with no 300.000 EUR split (the 22,5% marginal top bracket has no
# upper bound); the split into a 300.000 EUR / 24,5% top bracket arrived via
# Ley 11/2020 effective filing year 2021, so 2021-2023 carry 6 tramos.
_ESTATAL_TRAMOS_2020: tuple[tuple[Decimal, Decimal | None, Decimal, Decimal], ...] = (
    (Decimal("0"), Decimal("12450"), Decimal("0"), Decimal("0.095")),
    (Decimal("12450"), Decimal("20200"), Decimal("1182.75"), Decimal("0.12")),
    (Decimal("20200"), Decimal("35200"), Decimal("2112.75"), Decimal("0.15")),
    (Decimal("35200"), Decimal("60000"), Decimal("4362.75"), Decimal("0.185")),
    (Decimal("60000"), None, Decimal("8950.75"), Decimal("0.225")),
)
_ESTATAL_TRAMOS_2021_2023: tuple[tuple[Decimal, Decimal | None, Decimal, Decimal], ...] = (
    (Decimal("0"), Decimal("12450"), Decimal("0"), Decimal("0.095")),
    (Decimal("12450"), Decimal("20200"), Decimal("1182.75"), Decimal("0.12")),
    (Decimal("20200"), Decimal("35200"), Decimal("2112.75"), Decimal("0.15")),
    (Decimal("35200"), Decimal("60000"), Decimal("4362.75"), Decimal("0.185")),
    (Decimal("60000"), Decimal("300000"), Decimal("8950.75"), Decimal("0.225")),
    (Decimal("300000"), None, Decimal("62950.75"), Decimal("0.245")),
)


def _tramos_for_year(year: int) -> tuple[tuple[Decimal, Decimal | None, Decimal, Decimal], ...]:
    return _ESTATAL_TRAMOS_2020 if year == 2020 else _ESTATAL_TRAMOS_2021_2023


def _escala(amount: Decimal, year: int) -> Decimal:
    """Cuota per the LIRPF art. 63 escala general estatal tramos for `year`."""
    for lower, upper, fixed, rate in _tramos_for_year(year):
        if upper is None or amount <= upper:
            return fixed + (amount - lower) * rate
    raise AssertionError(f"amount {amount!r} outside escala range for {year}")


def _c(value: str) -> CasillaId:
    return validated_casilla_id(value, surface="test_m100_anualidades_multiyear")


_TRABAJO_INGRESOS = Decimal("16896")
_ANUALIDADES = Decimal("3000")
_ANUALIDADES_ABOVE_BASE = Decimal("25000")


def _anualidades_casilla(year: int) -> CasillaId:
    # 2020 and 2021 carry casilla 0527 (IMPALIM) as a direct manual input — the
    # bundled 2021 AEAT XSD declares it `maxOccurs="1"`, a plain scalar, with
    # no per-child structure. 2022-2023 introduce the
    # per-child "Hijo/Hija N: Importe de las anualidades..." block and compute
    # 0527 from casilla 1741 (renta-{year}-anualidades-alimentos-hijos-suma).
    return _c("0527") if year in (2020, 2021) else _c("1741")


def _run(
    snapshot: RegistrySnapshot,
    year: int,
    *,
    anualidades: Decimal | None,
    flag: Decimal = Decimal("1"),
) -> dict[CasillaId, Decimal]:
    inputs: dict[CasillaId, Decimal] = {_c("0003"): _TRABAJO_INGRESOS}
    if anualidades is not None:
        inputs[_anualidades_casilla(year)] = anualidades
    binding_values = {
        f"renta-{year}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        f"renta-{year}-modelo-111-retenciones-periodicas": Decimal("0"),
        f"renta-{year}-modelo-123-retenciones-periodicas": Decimal("0"),
        f"renta-{year}-profile-anualidades-sin-minimo-descendientes": flag,
        f"renta-{year}-profile-minimo-descendientes-estatal": Decimal("0"),
        f"renta-{year}-profile-minimo-descendientes-autonomico": Decimal("0"),
    }
    relation_values = {
        f"renta-{year}-rel-130-pagos-fraccionados": Decimal("0"),
        f"renta-{year}-rel-131-pagos-fraccionados": Decimal("0"),
    }
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(year, 12, 31)},
        enum_binding_values={f"renta-{year}-profile-tax-residence-ccaa": "cataluna"},
        binding_values=binding_values,
        relation_values=relation_values,
    )
    return {_c(k): result.values[_c(k)] for k in ("0505", "0521", "0527", "0528", "0530", "0532", "0545")}


def _snapshot(authority: ValidatedRegistryAuthority, year: int) -> RegistrySnapshot:
    return authority.snapshot("100", filing_year=year, period="0A")


@pytest.mark.parametrize("year", _SEPARATE_ESCALA_YEARS)
def test_separate_escala_estatal_assembly_matches_lirpf_tramos(
    registry_authority: ValidatedRegistryAuthority, year: int
) -> None:
    """Casilla 0528/0530/0532 implement the art. 64 separate-escala assembly."""
    snapshot = _snapshot(registry_authority, year)
    values = _run(snapshot, year, anualidades=_ANUALIDADES)

    c0505 = values[_c("0505")]
    c0521 = values[_c("0521")]
    c0527 = values[_c("0527")]
    assert c0527 == _ANUALIDADES, f"{year}: 0527 = {c0527!r}; expected {_ANUALIDADES!r}"
    assert c0527 < c0505, f"{year}: régimen requires anualidades ({c0527!r}) < base ({c0505!r})"

    expected_0528 = _escala(c0527, year) + _escala(c0505 - c0527, year)
    expected_0530 = _escala(c0521 + Decimal("1980"), year)
    expected_0532 = max(Decimal("0"), expected_0528 - expected_0530)

    assert abs(values[_c("0528")] - expected_0528) <= _TOLERANCE, (
        f"{year}: 0528 (escala s/ base, separate) = {values[_c('0528')]!r}; "
        f"expected escala({c0527}) + escala({c0505 - c0527}) = {expected_0528!r} per LIRPF art. 64."
    )
    assert abs(values[_c("0530")] - expected_0530) <= _TOLERANCE, (
        f"{year}: 0530 (escala s/ mínimo + 1.980) = {values[_c('0530')]!r}; "
        f"expected escala({c0521 + Decimal('1980')}) = {expected_0530!r} per LIRPF art. 64."
    )
    assert abs(values[_c("0532")] - expected_0532) <= _TOLERANCE, (
        f"{year}: 0532 (cuota base liq. general estatal, floored) = {values[_c('0532')]!r}; "
        f"expected max(0, {expected_0528!r} - {expected_0530!r}) = {expected_0532!r}."
    )


@pytest.mark.parametrize("year", _SEPARATE_ESCALA_YEARS)
def test_separate_escala_ordering_shortcut_below_separate_below_no_benefit(
    registry_authority: ValidatedRegistryAuthority, year: int
) -> None:
    """shortcut < separate < no-benefit for the anualidades filer."""
    snapshot = _snapshot(registry_authority, year)
    separate = _run(snapshot, year, anualidades=_ANUALIDADES)
    no_benefit = _run(snapshot, year, anualidades=None)

    c0505 = separate[_c("0505")]
    c0521 = separate[_c("0521")]
    c0527 = separate[_c("0527")]

    cuota_separate = separate[_c("0545")]
    cuota_no_benefit = no_benefit[_c("0545")]
    # Retired subtract-from-base shortcut: escala(0505 - 0527) - escala(0521).
    cuota_shortcut = max(Decimal("0"), _escala(c0505 - c0527, year) - _escala(c0521, year))
    # No-benefit single escala on the full base: escala(0505) - escala(0521).
    cuota_no_benefit_derived = max(Decimal("0"), _escala(c0505, year) - _escala(c0521, year))

    assert abs(cuota_no_benefit - cuota_no_benefit_derived) <= _TOLERANCE, (
        f"{year}: no-benefit cuota {cuota_no_benefit!r} != derived {cuota_no_benefit_derived!r}"
    )
    assert cuota_shortcut < cuota_separate < cuota_no_benefit, (
        f"{year}: ordering shortcut ({cuota_shortcut!r}) < separate ({cuota_separate!r}) "
        f"< no-benefit ({cuota_no_benefit!r}) violated; the separate-escala régimen is "
        f"mis-wired or the benefit is not genuine."
    )


@pytest.mark.parametrize("year", _SEPARATE_ESCALA_YEARS)
def test_regime_off_shared_custody_reduces_to_single_escala(
    registry_authority: ValidatedRegistryAuthority, year: int
) -> None:
    """Flag off (custodia compartida) collapses to the ordinary single escala."""
    snapshot = _snapshot(registry_authority, year)
    off = _run(snapshot, year, anualidades=_ANUALIDADES, flag=Decimal("0"))
    no_benefit = _run(snapshot, year, anualidades=None)

    assert off[_c("0505")] == no_benefit[_c("0505")], (
        f"{year}: 0505 must be the full base regardless of the régimen flag"
    )
    assert abs(off[_c("0545")] - no_benefit[_c("0545")]) <= _TOLERANCE, (
        f"{year}: flag-off cuota {off[_c('0545')]!r} must equal the single-escala "
        f"no-benefit cuota {no_benefit[_c('0545')]!r} (LIRPF art. 64 denies the régimen "
        f"to a payer who retains the mínimo por descendientes)."
    )


@pytest.mark.parametrize("year", _SEPARATE_ESCALA_YEARS)
def test_regime_off_when_anualidades_reach_base(registry_authority: ValidatedRegistryAuthority, year: int) -> None:
    """Anualidades >= base liquidable general → régimen off (art. 64 condition)."""
    snapshot = _snapshot(registry_authority, year)
    over = _run(snapshot, year, anualidades=_ANUALIDADES_ABOVE_BASE)
    no_benefit = _run(snapshot, year, anualidades=None)

    assert over[_c("0527")] >= over[_c("0505")], (
        f"{year}: scenario requires anualidades ({over[_c('0527')]!r}) >= base ({over[_c('0505')]!r})"
    )
    assert abs(over[_c("0545")] - no_benefit[_c("0545")]) <= _TOLERANCE, (
        f"{year}: anualidades>=base cuota {over[_c('0545')]!r} must equal the single-escala "
        f"no-benefit cuota {no_benefit[_c('0545')]!r} (art. 64 applies only when anualidades "
        f"< base liquidable general)."
    )


def test_2021_casilla_0527_is_manual_and_not_derived_from_anexo_c_pension_fields(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """2021 regression: 0527 must not derive from the Anexo C pension fields.

    In the 2021 revision, casillas 1741/1744/1749/1754/1759 are Anexo C
    aportaciones/contribuciones a sistemas de previsión social fields (a
    contribuyente-reduccion-derecho text flag plus per-exercise pension
    pending-application amounts) — NOT the per-child anualidades por alimentos
    block that only exists from 2022 onward. Casilla 0527 (IMPALIM) is a
    single scalar manual input per the bundled 2021 AEAT XSD
    (`maxOccurs="1"`, no repeating child structure). Seeding the Anexo C
    fields as a scalar (the pre-fix defect) must NOT populate 0527, and must
    NOT trigger the art. 64 separate-escala régimen; only a real entry on
    0527 itself may do so.
    """
    snapshot = _snapshot(registry_authority, 2021)

    # Seed the Anexo C pension-contribution fields the retired 2021 sum
    # formula wrongly summed into 0527. They must have zero effect on 0527
    # or on the separate-escala régimen gate (0527 > 0 AND 0527 < 0505).
    stray_inputs: dict[object, Decimal] = {
        _c("0003"): _TRABAJO_INGRESOS,
        _c("1744"): Decimal("500"),
        _c("1749"): Decimal("600"),
        _c("1754"): Decimal("700"),
        _c("1759"): Decimal("800"),
    }
    binding_values = {
        "renta-2021-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2021-modelo-111-retenciones-periodicas": Decimal("0"),
        "renta-2021-modelo-123-retenciones-periodicas": Decimal("0"),
        "renta-2021-profile-anualidades-sin-minimo-descendientes": Decimal("1"),
        "renta-2021-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-2021-profile-minimo-descendientes-autonomico": Decimal("0"),
    }
    relation_values = {
        "renta-2021-rel-130-pagos-fraccionados": Decimal("0"),
        "renta-2021-rel-131-pagos-fraccionados": Decimal("0"),
    }
    stray_result = calculate_registry_snapshot(
        snapshot,
        inputs=stray_inputs,
        date_context={"filing_period": date(2021, 12, 31)},
        enum_binding_values={"renta-2021-profile-tax-residence-ccaa": "cataluna"},
        binding_values=binding_values,
        relation_values=relation_values,
    )
    assert stray_result.values[_c("0527")] == Decimal("0"), (
        f"2021: casilla 0527 = {stray_result.values[_c('0527')]!r}; expected 0 — the Anexo C "
        "pension-contribution fields (1744/1749/1754/1759) must not populate the anualidades "
        "casilla by being wrongly summed into it."
    )

    # A real entry directly on 0527 (the correct 2021 manual-input surface)
    # activates the separate-escala régimen exactly as in 2020.
    real_result = _run(snapshot, 2021, anualidades=_ANUALIDADES)
    assert real_result[_c("0527")] == _ANUALIDADES, (
        f"2021: real manual entry on 0527 = {real_result[_c('0527')]!r}; expected {_ANUALIDADES!r}"
    )
