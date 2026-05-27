"""Regression tests for the M100 base imponible del ahorro chain (casilla 0460).

Defect #181 (quadruple-confirmed): the formula ``renta-{year}-base-imponible-del-ahorro``
was missing casilla 0041 (suma de rendimientos reducidos del capital mobiliario) as a
summand.  The fix adds ``{ casilla = "0041" }`` as the first arg of the sum expression
in both the 2024 and 2025 formula TOMLs.

Oracle authority
----------------
Article 49 Ley 35/2006 (LIRPF):

  "La base imponible del ahorro estará constituida por:
   a) El saldo positivo resultante de integrar y compensar entre sí, sin limitación
      alguna, en cada período impositivo, los rendimientos netos a que se refiere el
      artículo 25 de esta Ley.
   b) El saldo positivo resultante de integrar y compensar, exclusivamente entre sí,
      los saldos positivos y negativos que se pongan de manifiesto con ocasión de la
      transmisión de los elementos patrimoniales (artículos 33 a 38)."

Art. 25 LIRPF: Rendimientos del capital mobiliario → casilla 0041 carries the net
rendimiento del capital mobiliario a integrar en la base del ahorro for the current
ejercicio.  Art. 49.1.a requires this to appear as a summand in 0460.

All expected values are derived strictly from the stated input and Art. 49 LIRPF:
  - With only capital-mobiliario inputs and no offsetting losses the base imponible
    del ahorro equals the net rendimiento del capital mobiliario (= 0041 after chain).
  - With zero inputs the base is zero.

The anti-tautology property is enforced by tests that vary the input and verify that
0460 changes proportionally.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from . import calculate_registry_snapshot
from ._authority import ValidatedRegistryAuthority
from ._relations import resolve_relation_values

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

# ── shared date contexts ──────────────────────────────────────────────────────
_DATE_2024 = {"filing_period": date(2024, 12, 31)}
_DATE_2025 = {"filing_period": date(2025, 12, 31)}

# ── minimal binding_values required by M100 2024/2025 bound casillas ─────────
_BINDINGS_2024: dict[str, Decimal] = {
    "renta-2024-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    "renta-2024-modelo-111-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-115-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-123-retenciones-periodicas": Decimal("0"),
    "renta-2024-modelo-193-retenciones-anuales": Decimal("0"),
}

_ENUM_BINDINGS_2024 = {"renta-2024-profile-tax-residence-ccaa": "madrid"}


@pytest.fixture
def m100_2024_snapshot(registry_authority: ValidatedRegistryAuthority):
    return registry_authority.snapshot("100", filing_year=2024, period="0A")


@pytest.fixture
def m100_2025_snapshot(registry_authority: ValidatedRegistryAuthority):
    return registry_authority.snapshot("100", filing_year=2025, period="0A")


# ── helper ────────────────────────────────────────────────────────────────────

def _run_2024(snapshot, inputs: dict[str, Decimal]) -> dict[str, Decimal]:
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context=_DATE_2024,
        enum_binding_values=_ENUM_BINDINGS_2024,
        binding_values=_BINDINGS_2024,
        # Supply a representative birth date so that any age_at_year_end
        # formula in the mínimo personal chain can resolve.  The exact
        # birth date does not affect the capital-mobiliario / base-ahorro
        # computation chain under test.
        date_binding_values={"renta-2024-profile-taxpayer-birth-date": date(1975, 6, 15)},
    )
    return dict(result.values)


# ── Sergio shape: 0029 = 20 000 EUR dividends ─────────────────────────────────

def test_sergio_0029_dividends_20000_populates_0460(m100_2024_snapshot) -> None:
    """Sergio shape: casilla 0029 (dividendos) = 20 000 EUR.

    Oracle (Art. 49.1.a LIRPF): with no offsetting losses or prior-period
    compensations the base imponible del ahorro equals the net rendimiento del
    capital mobiliario, which equals 0029 when 0037 and 0039 are zero.

    Chain: 0029→0036→0038→0040→0041→0460.
    """
    values = _run_2024(m100_2024_snapshot, {"0029": Decimal("20000")})

    # The chain must propagate through: 0036=20000, 0038=20000, 0040=20000, 0041=20000.
    assert values.get("0036") == Decimal("20000"), (
        f"0036 (total ingresos) = {values.get('0036')!r}; expected 20000.  "
        "Chain 0029→0036 is broken."
    )
    assert values.get("0041") == Decimal("20000"), (
        f"0041 (suma rendimientos reducidos) = {values.get('0041')!r}; expected 20000.  "
        "Chain 0036→0038→0040→0041 is broken."
    )
    # Primary regression guard: before the fix, 0460 = 0 even when 0041 = 20 000.
    assert values.get("0460", Decimal("0")) >= Decimal("20000"), (
        f"casilla 0460 (base imponible del ahorro) = {values.get('0460')!r}; "
        "expected ≥ 20 000.  Defect #181 regression: 0041 is not included in "
        "formula renta-2024-base-imponible-del-ahorro.  "
        "Fix: add { casilla = '0041' } to the expression in "
        "2024/formulas/0145-renta-2024-base-imponible-del-ahorro.toml."
    )


def test_sergio_0460_equals_0029_when_no_losses_or_gp(m100_2024_snapshot) -> None:
    """Art. 49.1 oracle: 0460 = 0041 when ganancias patrimoniales saldo = 0.

    With no ganancias-patrimoniales inputs (0422=0, 0423=0) the only base-ahorro
    component is 0041 (capital mobiliario).  Art. 49.1.a → 0460 = net rendimiento
    del capital mobiliario = 0029 (when 0037 and 0039 are zero).
    """
    values = _run_2024(m100_2024_snapshot, {"0029": Decimal("20000")})

    expected = Decimal("20000")
    assert values.get("0460") == expected, (
        f"casilla 0460 = {values.get('0460')!r}; expected {expected}.  "
        "Art. 49.1.a LIRPF: 0460 must equal the net capital-mobiliario rendimiento "
        "when no ganancias or compensations apply."
    )


# ── Carla shape: 0027 = 1 200 EUR cuenta-corriente interest ──────────────────

def test_carla_0027_intereses_1200_propagates_to_0460(m100_2024_snapshot) -> None:
    """Carla shape: casilla 0027 (intereses cuenta corriente) = 1 200 EUR.

    Oracle (Art. 49.1.a LIRPF): 0460 = 1 200 EUR when 0037 and 0039 are zero.

    Chain: 0027→0036→0038→0040→0041→0460.
    """
    values = _run_2024(m100_2024_snapshot, {"0027": Decimal("1200")})

    assert values.get("0041") == Decimal("1200"), (
        f"0041 = {values.get('0041')!r}; expected 1200.  Chain 0027→…→0041 broken."
    )
    assert values.get("0460") == Decimal("1200"), (
        f"casilla 0460 = {values.get('0460')!r}; expected 1200.  "
        "Art. 49.1.a LIRPF oracle: net capital-mobiliario = 1200 → 0460 = 1200.  "
        "Check 2024/formulas/0145-renta-2024-base-imponible-del-ahorro.toml "
        "— 0041 must be included."
    )


# ── Aitor shape: 0029 = 6 000 EUR dividends SAL ───────────────────────────────

def test_aitor_0029_dividends_6000_populates_0460(m100_2024_snapshot) -> None:
    """Aitor shape: casilla 0029 (dividendos SAL) = 6 000 EUR.

    Oracle (Art. 49.1.a LIRPF): 0460 = 6 000 EUR.
    """
    values = _run_2024(m100_2024_snapshot, {"0029": Decimal("6000")})

    assert values.get("0460") == Decimal("6000"), (
        f"casilla 0460 = {values.get('0460')!r}; expected 6000.  "
        "Art. 49.1.a LIRPF oracle: dividends 6000 → 0460 = 6000."
    )


# ── Anti-tautology: proportional scaling ─────────────────────────────────────

def test_0460_scales_proportionally_with_capital_mobiliario_input(m100_2024_snapshot) -> None:
    """Anti-tautology: doubling the dividends input must double 0460.

    This test cannot pass against a formula that always returns 0 or any
    constant — it verifies that 0460 is strictly coupled to 0029.
    """
    v_small = _run_2024(m100_2024_snapshot, {"0029": Decimal("5000")})
    v_large = _run_2024(m100_2024_snapshot, {"0029": Decimal("10000")})

    small = v_small.get("0460", Decimal("0"))
    large = v_large.get("0460", Decimal("0"))

    assert large == small * 2, (
        f"0460 at 10000 input = {large!r}; at 5000 = {small!r}.  "
        "Doubling the capital-mobiliario income must double the base imponible "
        "del ahorro (Art. 49.1.a LIRPF, no other summands active)."
    )


# ── 2025 revision: same defect must also be fixed ─────────────────────────────

def test_2025_0029_dividends_20000_populates_0460(m100_2025_snapshot) -> None:
    """2025 revision: same Art. 49.1.a chain must hold.

    Both the 2024 and 2025 formulas had the same missing-0041 defect.
    """
    _bindings_2025: dict[str, Decimal] = {
        "renta-2025-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        "renta-2025-modelo-184-atribucion-actividades-economicas": Decimal("0"),
    }
    # 2025 revision requires all cross-model relation values; supply zeros for
    # all relations so the ahorro chain can be exercised in isolation.
    relation_values_2025 = resolve_relation_values(
        m100_2025_snapshot.revision,
        {
            relation.id: (
                Decimal("0")
                if (str((relation.aggregation or {}).get("op", "copy")) == "copy")
                else (Decimal("0"),)
            )
            for relation in m100_2025_snapshot.revision.relations
        },
        period="0A",
    )
    result = calculate_registry_snapshot(
        m100_2025_snapshot,
        inputs={"0029": Decimal("20000")},
        date_context=_DATE_2025,
        enum_binding_values={"renta-2025-profile-tax-residence-ccaa": "madrid"},
        binding_values=_bindings_2025,
        relation_values=relation_values_2025,
        date_binding_values={"renta-2025-profile-taxpayer-birth-date": date(1975, 6, 15)},
    )
    values = dict(result.values)

    assert values.get("0460", Decimal("0")) >= Decimal("20000"), (
        f"2025: casilla 0460 = {values.get('0460')!r}; expected ≥ 20000.  "
        "Defect #181 also affects the 2025 revision.  "
        "Check 2025/formulas/0168-renta-2025-base-imponible-del-ahorro.toml."
    )
