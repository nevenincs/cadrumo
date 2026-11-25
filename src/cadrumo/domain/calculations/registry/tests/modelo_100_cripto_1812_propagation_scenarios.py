"""Scenario bodies for test_modelo_100_cripto_1812_propagation, called by its authored-source and published-authority tests."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..formula_runtime import calculate_registry_snapshot
from ..relations import relation_prefill_bindings_for_period
from ..schema import RegistrySnapshot
from ..snapshot_globals import SupportedFilingYearsCatalogue


# The horizon exercise carries the newest Modelo 100 revision forward, while that
# revision's dated parameters stop at its own exercise; the chain is proven on every
# supported exercise below the horizon, each of which has its own authored revision.
def authored_years(support: SupportedFilingYearsCatalogue) -> tuple[int, ...]:
    return tuple(year for year in support.years if year < support.horizon)


M100_CRIPTO_TRANSMISION_CASILLA: CasillaId = validated_casilla_id(
    "1804",
    surface="M100_CRIPTO_TRANSMISION_CASILLA",
)

M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA: CasillaId = validated_casilla_id(
    "1811",
    surface="M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA",
)

M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA: CasillaId = validated_casilla_id(
    "1812",
    surface="M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA",
)

M100_CRIPTO_GANANCIA_SUMA_CASILLA: CasillaId = validated_casilla_id(
    "1814",
    surface="M100_CRIPTO_GANANCIA_SUMA_CASILLA",
)


# Each revision's form graph carries its own binding set.  Rather than
# hand-transcribe every binding id (brittle, and orthogonal to the crypto chain
# under test), the runner below enumerates the snapshot's own binding/relation
# set and supplies neutral zero/identity values.  The crypto chain
# (1804 -> 1811 -> 1812 -> 1814) depends only on casilla 1804, so the neutral
# fill isolates the propagation without asserting anything about unrelated
# casillas.


def calculate(snapshot: RegistrySnapshot, valor_1804: Decimal):
    revision = snapshot.revision
    enum_binding_values = {b.id: "madrid" for b in revision.bindings if ("ccaa" in b.id or "residence" in b.id)}
    date_binding_values = {b.id: date(snapshot.filing_year - 50, 6, 15) for b in revision.bindings if "birth" in b.id}
    typed_ids = set(enum_binding_values) | set(date_binding_values)
    binding_values = {b.id: Decimal("0") for b in revision.bindings if b.id not in typed_ids}
    relation_values = {
        binding.id: Decimal("0")
        for binding, _provider in relation_prefill_bindings_for_period(revision, period=snapshot.period)
    }
    return calculate_registry_snapshot(
        snapshot,
        inputs={M100_CRIPTO_TRANSMISION_CASILLA: valor_1804},
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        binding_values=binding_values,
        enum_binding_values=enum_binding_values,
        relation_values=relation_values,
        date_binding_values=date_binding_values,
    )


def snapshot(registry_snapshot: Callable[..., RegistrySnapshot], filing_year: int) -> RegistrySnapshot:
    """1812/1811 identity-copy propagation, a calculation claim, never filing."""
    return registry_snapshot("100", filing_year, "0A", grade=RegistryAuthorityGrade.CALCULATION)


def check_1812_identity_copy_standard_gain_reaches_aggregator(
    filing_year: int,
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    """With 1804 = 8500, 1811 = 8500, 1812 must equal 1811 and reach aggregator 1814.

    Oracle: 1811 = 1804 - 1806 - 1810; with 1806/1810 = 0, 1811 = 1804.
    1812 = copy(1811) = 1811.  Identity is the AEAT default for single-year
    imputación (Art. 14.1 LIRPF; no multi-year deferral).  Before the fix 1812
    was ``input_kind = "manual"`` and defaulted to zero, so 1814 (``suma de las
    casillas [1812]``) silently dropped the crypto gain from base imponible del
    ahorro — a silent under-declaration.
    """
    result = calculate(snapshot(registry_snapshot, filing_year), Decimal("8500"))

    assert result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA] == Decimal("8500.00"), (
        f"{filing_year}: casilla 1811 = {result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r}; expected 8500.00.  "
        "Formula renta-criptomonedas-ganancia-no-exenta should compute "
        "1811 = 1804 - 1806 - 1810 = 8500 - 0 - 0."
    )
    assert (
        result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA] == result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]
    ), (
        f"{filing_year}: casilla 1812 = {result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; "
        f"expected {result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r} (= 1811). "
        "Formula renta-ganancia-cripto-imputable must copy 1811 to 1812."
    )
    assert result.values[M100_CRIPTO_GANANCIA_SUMA_CASILLA] == result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA], (
        f"{filing_year}: casilla 1814 = {result.values[M100_CRIPTO_GANANCIA_SUMA_CASILLA]!r}; "
        f"expected {result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r} (= 1812). "
        "The crypto gain must reach the aggregator, not vanish from base imponible del ahorro."
    )


def check_1812_zero_when_no_crypto_gain(
    filing_year: int,
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    """With 1804 = 0, 1811, 1812 and 1814 must all be zero.

    No spurious propagation: a taxpayer without crypto gain must not see
    a phantom value in 1812 or its aggregator.
    """
    result = calculate(snapshot(registry_snapshot, filing_year), Decimal("0"))

    assert result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA] == Decimal("0.00"), (
        f"{filing_year}: casilla 1811 = {result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r}; "
        "expected 0.00 when no crypto gain."
    )
    assert result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA] == Decimal("0.00"), (
        f"{filing_year}: casilla 1812 = {result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; "
        "expected 0.00 when no crypto gain.  "
        "No spurious value must appear in 1812 when 1811 = 0."
    )
    assert result.values[M100_CRIPTO_GANANCIA_SUMA_CASILLA] == Decimal("0.00"), (
        f"{filing_year}: casilla 1814 = {result.values[M100_CRIPTO_GANANCIA_SUMA_CASILLA]!r}; expected 0.00."
    )


def check_1812_anti_tautology_tracks_input(
    filing_year: int,
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    """Anti-tautology: 1804 = 7000 must produce 1812 = 7000, not 8500.

    This test uses a distinct non-default value to confirm the formula is
    actually wired: if 1812 always equalled a hardcoded constant the test
    would still pass, but a different 1804 input changes 1811 and therefore
    must also change 1812.
    """
    result = calculate(snapshot(registry_snapshot, filing_year), Decimal("7000"))

    assert result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA] == Decimal("7000.00"), (
        f"{filing_year}: casilla 1812 = {result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; "
        "expected 7000.00 — the copy must track the actual 1811 value, not a cached constant."
    )
    assert (
        result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA] == result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]
    ), (
        f"{filing_year}: 1812 ({result.values[M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}) != "
        f"1811 ({result.values[M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r}). "
        "Identity copy must hold for any input."
    )
