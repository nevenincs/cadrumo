"""M100 anualidades por alimentos separate-escala for 2020-2023 (#532 Phase 2).

LIRPF art. 64 (estatal) / art. 75 (autonómica) grant judicial anualidades por
alimentos a favor de los hijos a SEPARATE-escala treatment: the art. 63 escala
is applied separately to the anualidades (casilla 0527) and to the rest of the
base liquidable general (0505 - 0527), and the total is minorada by the escala
applied to the mínimo personal y familiar INCREMENTADO EN 1.980 EUR, floored at
0. Phase 1 (commit 63f9b6125) modelled this for 2024/2025; this module proves
the same régimen for the 2020-2023 revisions, where casilla 0505 is now computed
(max(0, 0500)) rather than a manual input.

Non-tautological grounding: the expected cuota is DERIVED from the LIRPF art. 63
escala general estatal tramos (external BOE authority, bundled ley-35-2006.html;
identical across 2020-2024 in each renta-{year}-escala-estatal-base-general
parameter), applied through the separate-escala ASSEMBLY that art. 64 mandates
(escala(0527) + escala(0505 - 0527) - escala(mínimo + 1.980), floored). The
lookup_bracket primitive is separately tested; what these tests exercise is the
if_then_else régimen assembly. The actual computed 0505 and 0521 are read from
the engine and fed into the derivation, so the tests are robust to the upstream
base-liquidable / mínimo chain and pin the assembly, not those inputs. The
ordering shortcut < separate < no-benefit is the structural anchor: the fix
raises the cuota above the retired subtract-from-base shortcut while keeping the
benefit genuine (below the no-benefit single escala).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import RegistrySnapshot, calculate_registry_snapshot, validated_casilla_id
from .._authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SEPARATE_ESCALA_YEARS = (2020, 2021, 2022, 2023)
_TOLERANCE = Decimal("0.01")

# LIRPF art. 63 escala general estatal — tramos unchanged 2020-2024 (BOE
# consolidated Ley 35/2006 art. 63; verified byte-identical in every
# renta-{year}-escala-estatal-base-general registry parameter).
_ESTATAL_TRAMOS: tuple[tuple[Decimal, Decimal | None, Decimal, Decimal], ...] = (
    (Decimal("0"), Decimal("12450"), Decimal("0"), Decimal("0.095")),
    (Decimal("12450"), Decimal("20200"), Decimal("1182.75"), Decimal("0.12")),
    (Decimal("20200"), Decimal("35200"), Decimal("2112.75"), Decimal("0.15")),
    (Decimal("35200"), Decimal("60000"), Decimal("4362.75"), Decimal("0.185")),
    (Decimal("60000"), Decimal("300000"), Decimal("8950.75"), Decimal("0.225")),
    (Decimal("300000"), None, Decimal("62950.75"), Decimal("0.245")),
)


def _escala(amount: Decimal) -> Decimal:
    """Cuota per the LIRPF art. 63 escala general estatal tramos."""
    for lower, upper, fixed, rate in _ESTATAL_TRAMOS:
        if upper is None or amount <= upper:
            return fixed + (amount - lower) * rate
    raise AssertionError(f"amount {amount!r} outside escala range")


def _c(value: str) -> object:
    return validated_casilla_id(value, surface="test_m100_anualidades_multiyear")


_TRABAJO_INGRESOS = Decimal("16896")
_ANUALIDADES = Decimal("3000")
_ANUALIDADES_ABOVE_BASE = Decimal("25000")


def _anualidades_casilla(year: int) -> object:
    # 2020 carries casilla 0527 as a direct manual input; 2021-2023 compute
    # 0527 from casilla 1741 (renta-{year}-anualidades-alimentos-hijos-suma).
    return _c("0527") if year == 2020 else _c("1741")


def _run(
    snapshot: RegistrySnapshot,
    year: int,
    *,
    anualidades: Decimal | None,
    flag: Decimal = Decimal("1"),
) -> dict[str, Decimal]:
    inputs: dict[object, Decimal] = {_c("0003"): _TRABAJO_INGRESOS}
    if anualidades is not None:
        inputs[_anualidades_casilla(year)] = anualidades
    binding_values = {
        f"renta-{year}-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        f"renta-{year}-modelo-111-retenciones-periodicas": Decimal("0"),
        f"renta-{year}-modelo-123-retenciones-periodicas": Decimal("0"),
        f"renta-{year}-profile-anualidades-sin-minimo-descendientes": flag,
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

    expected_0528 = _escala(c0527) + _escala(c0505 - c0527)
    expected_0530 = _escala(c0521 + Decimal("1980"))
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
    """shortcut < separate < no-benefit for the anualidades filer (#532)."""
    snapshot = _snapshot(registry_authority, year)
    separate = _run(snapshot, year, anualidades=_ANUALIDADES)
    no_benefit = _run(snapshot, year, anualidades=None)

    c0505 = separate[_c("0505")]
    c0521 = separate[_c("0521")]
    c0527 = separate[_c("0527")]

    cuota_separate = separate[_c("0545")]
    cuota_no_benefit = no_benefit[_c("0545")]
    # Retired subtract-from-base shortcut: escala(0505 - 0527) - escala(0521).
    cuota_shortcut = max(Decimal("0"), _escala(c0505 - c0527) - _escala(c0521))
    # No-benefit single escala on the full base: escala(0505) - escala(0521).
    cuota_no_benefit_derived = max(Decimal("0"), _escala(c0505) - _escala(c0521))

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
def test_regime_off_when_anualidades_reach_base(
    registry_authority: ValidatedRegistryAuthority, year: int
) -> None:
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
