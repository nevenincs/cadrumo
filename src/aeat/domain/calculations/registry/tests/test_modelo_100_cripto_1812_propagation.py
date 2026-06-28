"""Regression tests for M100 casilla 1812 auto-propagation from 1811 (contract).

Casilla 1812 (Ganancia no exenta imputable al ejercicio) previously had
``input_kind = "manual"``.  Without an explicit ``--casilla "1812=<value>"``
the aggregators 1813/1814 received zero and the entire crypto gain disappeared
from base imponible del ahorro.

After contract, 1812 is ``input_kind = "computed"`` with formula
``renta-2024-ganancia-cripto-imputable`` (identity copy from 1811).  The AEAT
form default is: 1812 equals 1811 unless the taxpayer defers under Art. 14.2.d
LIRPF (multi-year deferral); that override path is out of scope here.

Oracle authority
----------------
The expected values are structural identities — 1812 must equal 1811 exactly
because the formula is ``op = "copy"``.  The oracle is the TOML formula
declaration itself, verified against the AEAT 2024 form (boe-modelo-100-2024-form)
which shows 1812 pre-populated from 1811 for the standard single-year case.

Both 2024 and 2025 revisions are covered; the same gap existed in both.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .. import BindingId, CasillaId, RegistrySnapshot, RelationId, calculate_registry_snapshot, validated_casilla_id
from .._authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_M100_CRIPTO_TRANSMISION_CASILLA: CasillaId = validated_casilla_id(
    "1804",
    surface="_M100_CRIPTO_TRANSMISION_CASILLA",
)
_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA: CasillaId = validated_casilla_id(
    "1811",
    surface="_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA",
)
_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA: CasillaId = validated_casilla_id(
    "1812",
    surface="_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def m100_2024_snapshot(registry_authority: ValidatedRegistryAuthority):
    return registry_authority.snapshot("100", filing_year=2024, period="0A")


@pytest.fixture
def m100_2025_snapshot(registry_authority: ValidatedRegistryAuthority):
    return registry_authority.snapshot("100", filing_year=2025, period="0A")


def _binding_values_2024() -> dict[BindingId, Decimal]:
    return {
        "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
        "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
        # declaration_type = 1 (individual) → 0461 computed = 0
        "renta-2024-profile-declaration-type": Decimal("1"),
        "renta-2024-profile-family-minor-children-in-unit": Decimal("0"),
        # Art. 81 bis LIRPF guarderia bindings (b7ad3a993): zero in non-guarderia scenarios.
        "renta-2024-profile-guarderia-gastos-reales": Decimal("0"),
        "renta-2024-profile-cotizaciones-ss-madre": Decimal("0"),
        "renta-2024-profile-descendientes-menores-3": Decimal("0"),
        # matrimonio-sobrevenido bindings (81feae7b0): zero = marriage pre-dates filing year.
        "renta-2024-profile-marriage-full-year": Decimal("0"),
        "renta-2024-profile-marriage-month-start": Decimal("0"),
        "renta-2024-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline.
        "renta-2024-base-liquidable-negativa-general-anterior": Decimal("0"),
    }


_RELATION_VALUES_2024: dict[RelationId, Decimal] = {
    "renta-2024-rel-111-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-111-retenciones-mensuales": Decimal("0"),
    "renta-2024-rel-115-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-123-retenciones-trimestrales": Decimal("0"),
    "renta-2024-rel-193-retenciones-anuales": Decimal("0"),
    "renta-2024-rel-130-pagos-fraccionados": Decimal("0"),
    "renta-2024-rel-131-pagos-fraccionados": Decimal("0"),
}


def _enum_binding_values_2024() -> dict[BindingId, str]:
    return {"renta-2024-profile-tax-residence-ccaa": "madrid"}


def _date_binding_values_2024() -> dict[BindingId, date]:
    return {"renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15)}


def _run_2024(snapshot: RegistrySnapshot, valor_1804: Decimal):
    return calculate_registry_snapshot(
        snapshot,
        inputs={_M100_CRIPTO_TRANSMISION_CASILLA: valor_1804},
        date_context={"filing_period": date(2024, 12, 31)},
        binding_values=_binding_values_2024(),
        relation_values=_RELATION_VALUES_2024,
        enum_binding_values=_enum_binding_values_2024(),
        date_binding_values=_date_binding_values_2024(),
    )


# ---------------------------------------------------------------------------
# 2024 revision
# ---------------------------------------------------------------------------


def test_2024_1812_identity_copy_standard_gain(m100_2024_snapshot: RegistrySnapshot) -> None:
    """With 1804 = 8500, 1811 = 8500 and 1812 must equal 1811.

    Oracle: 1811 = 1804 - 1806 - 1810; with 1806/1810 = 0, 1811 = 1804.
    1812 = copy(1811) = 1811.  Identity is the AEAT default for single-year
    imputación (Art. 14.1 LIRPF; no multi-year deferral).
    """
    result = _run_2024(m100_2024_snapshot, Decimal("8500"))

    assert result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA] == Decimal("8500.00"), (
        f"casilla 1811 = {result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r}; expected 8500.00.  "
        "Formula renta-2024-criptomonedas-ganancia-no-exenta should compute "
        "1811 = 1804 - 1806 - 1810 = 8500 - 0 - 0."
    )
    assert (
        result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]
        == result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]
    ), (
        f"casilla 1812 = {result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; "
        f"expected {result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r}. "
        "Formula renta-2024-ganancia-cripto-imputable must copy 1811 to 1812 "
        "(S371 regression: before the fix 1812 stayed at 0)."
    )


def test_2024_1812_zero_when_no_crypto_gain(m100_2024_snapshot: RegistrySnapshot) -> None:
    """With 1804 = 0, both 1811 and 1812 must be zero.

    No spurious propagation: a taxpayer without crypto gain must not see
    a phantom value in 1812.
    """
    result = _run_2024(m100_2024_snapshot, Decimal("0"))

    assert result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA] == Decimal("0.00"), (
        f"casilla 1811 = {result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r}; "
        "expected 0.00 when no crypto gain."
    )
    assert result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA] == Decimal("0.00"), (
        f"casilla 1812 = {result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; "
        "expected 0.00 when no crypto gain.  "
        "No spurious value must appear in 1812 when 1811 = 0."
    )


def test_2024_1812_anti_tautology_different_gain(m100_2024_snapshot: RegistrySnapshot) -> None:
    """Anti-tautology: 1804 = 7000 must produce 1812 = 7000, not 8500.

    This test uses a distinct non-default value to confirm the formula is
    actually wired: if 1812 always equalled a hardcoded constant the test
    would still pass, but a different 1804 input changes 1811 and therefore
    must also change 1812.
    """
    result = _run_2024(m100_2024_snapshot, Decimal("7000"))

    assert result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA] == Decimal("7000.00"), (
        f"casilla 1812 = {result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; expected 7000.00. "
        "Formula must propagate the actual 1811 value, not a cached constant."
    )
    assert (
        result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]
        == result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]
    ), (
        f"1812 ({result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}) != "
        f"1811 ({result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r}). "
        "Identity copy must hold for any input."
    )


# ---------------------------------------------------------------------------
# 2025 revision
# ---------------------------------------------------------------------------


def _binding_values_2025() -> dict[BindingId, Decimal]:
    # 2025 retenciones/pagos are carried via relation_values not binding_values.
    # Only scalar bindings that lack a relation source are passed here.
    return {
        "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
        # declaration_type = 1 (individual) → 0461 computed = 0
        "renta-2025-profile-declaration-type": Decimal("1"),
        "renta-2025-profile-family-minor-children-in-unit": Decimal("0"),
        # matrimonio-sobrevenido bindings (81feae7b0): zero = marriage pre-dates filing year.
        "renta-2025-profile-marriage-full-year": Decimal("0"),
        "renta-2025-profile-marriage-month-start": Decimal("0"),
        "renta-2025-profile-marriage-month-end": Decimal("0"),
        # BIN-pendiente fresh-filer baseline (2025 binding).
        "renta-2025-base-liquidable-negativa-general-anterior": Decimal("0"),
    }


def _relation_values_2025() -> dict[RelationId, Decimal]:
    # All retenciones/pagos relations zero — no retenciones scenario.
    return {
        "renta-2025-rel-111-retenciones-trimestrales": Decimal("0"),
        "renta-2025-rel-111-retenciones-mensuales": Decimal("0"),
        "renta-2025-rel-115-retenciones-trimestrales": Decimal("0"),
        "renta-2025-rel-123-retenciones-trimestrales": Decimal("0"),
        "renta-2025-rel-130-pagos-fraccionados": Decimal("0"),
        "renta-2025-rel-131-pagos-fraccionados": Decimal("0"),
        "renta-2025-rel-180-retenciones-anuales": Decimal("0"),
        "renta-2025-rel-184-atribucion-actividades-economicas": Decimal("0"),
        "renta-2025-rel-190-retenciones-anuales": Decimal("0"),
        "renta-2025-rel-193-retenciones-anuales": Decimal("0"),
    }


def _enum_binding_values_2025() -> dict[BindingId, str]:
    return {"renta-2025-profile-tax-residence-ccaa": "madrid"}


def _date_binding_values_2025() -> dict[BindingId, date]:
    return {"renta-2025-profile-taxpayer-birth-date": date(1975, 6, 15)}


def _run_2025(snapshot: RegistrySnapshot, valor_1804: Decimal):
    return calculate_registry_snapshot(
        snapshot,
        inputs={_M100_CRIPTO_TRANSMISION_CASILLA: valor_1804},
        date_context={"filing_period": date(2025, 12, 31)},
        binding_values=_binding_values_2025(),
        relation_values=_relation_values_2025(),
        enum_binding_values=_enum_binding_values_2025(),
        date_binding_values=_date_binding_values_2025(),
    )


def test_2025_1812_identity_copy_standard_gain(m100_2025_snapshot: RegistrySnapshot) -> None:
    """2025 revision: 1812 must equal 1811 when 1804 = 8500."""
    result = _run_2025(m100_2025_snapshot, Decimal("8500"))

    assert (
        result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]
        == result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]
    ), (
        f"2025: casilla 1812 = {result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; "
        f"expected {result.values[_M100_CRIPTO_GANANCIA_NO_EXENTA_CASILLA]!r} (= 1811).  "
        "Formula renta-2025-ganancia-cripto-imputable must copy 1811 to 1812."
    )


def test_2025_1812_zero_when_no_crypto_gain(m100_2025_snapshot: RegistrySnapshot) -> None:
    """2025 revision: no spurious 1812 when 1804 = 0."""
    result = _run_2025(m100_2025_snapshot, Decimal("0"))

    assert result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA] == Decimal("0.00"), (
        f"2025: casilla 1812 = {result.values[_M100_CRIPTO_GANANCIA_IMPUTABLE_CASILLA]!r}; expected 0.00."
    )
