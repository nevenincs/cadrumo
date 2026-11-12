"""Regression tests for the M100 base imponible del ahorro chain (casilla 0460).

Defect #181 (quadruple-confirmed): the formula ``renta-{year}-base-imponible-del-ahorro``
was missing casilla 0041 (suma de rendimientos reducidos del capital mobiliario) as a
summand.  The registry fix adds ``{ casilla = "0041" }`` as the first arg of the sum
expression in every M100 revision currently shipped by the registry (2020-2025); this
module keeps live calculation coverage for 2024 and 2025, while
``test_modelo_100_registry`` pins the all-revision structural invariant.

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

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregationOp
from .....core.authority_grade import RegistryAuthorityGrade
from .....core.casilla_id import CasillaId, validated_casilla_id
from ..binding_aggregation import binding_aggregation_op
from ..formula_runtime import calculate_registry_snapshot
from ..relations import relation_prefill_bindings_for_period
from ..schema import RegistrySnapshot
from .authored_editions import newest_authored_edition
from .modelo_100_registry_support import M100_NO_DESCENDANT_MATERNIDAD_BINDINGS
from .relation_fixture import resolve_relation_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


# ── shared date contexts ──────────────────────────────────────────────────────
# The newest Modelo 100 edition the registry authors.
_REVIEWED_EDITION = newest_authored_edition("100")
_DATE_REVIEWED_EDITION = {"filing_period": date(_REVIEWED_EDITION, 12, 31)}

# ── minimal binding_values required by M100 2024/2025 bound casillas ─────────
_BINDINGS: dict[str, Decimal] = {
    "renta-profile-has-economic-activity": Decimal("1"),
    "renta-profile-estimacion-directa": Decimal("1"),
    "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
    # declaration_type = 1 (individual) → 0461 computed = 0
    "renta-profile-declaration-type": Decimal("1"),
    "renta-profile-family-minor-children-in-unit": Decimal("0"),
    # Art. 81.2 LIRPF guarderia bindings (b7ad3a993): zero default for
    # scenarios that do not exercise the maternidad-guarderia chain.
    "renta-profile-incremento-guarderia": Decimal("0"),
    **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
    "renta-profile-minimo-descendientes-estatal": Decimal("0"),
    "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
    # matrimonio-sobrevenido bindings (81feae7b0): zero = marriage pre-dates filing year.
    "renta-profile-marriage-full-year": Decimal("0"),
    "renta-profile-marriage-month-start": Decimal("0"),
    "renta-profile-marriage-month-end": Decimal("0"),
    # BIN-pendiente fresh-filer baseline: previous_filing binding for
    # casilla 1388 (LIRPF Art. 48) resolves to zero with no prior filing.
    "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
    "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
    "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
}

_ENUM_BINDINGS = {"renta-profile-tax-residence-ccaa": "madrid"}

# RD 439/2007 Art. 110 pagos-fraccionados relations; zero in scenarios that
# do not exercise M130/M131 cross-model integration.
_RELATION_VALUES: dict[str, Decimal] = {
    "renta-modelo-130-pagos-fraccionados": Decimal("0"),
    "renta-modelo-131-pagos-fraccionados": Decimal("0"),
}


def _zero_relation_output(op: BindingAggregationOp) -> Decimal | tuple[Decimal, ...] | tuple[tuple[Decimal, ...], ...]:
    """Return a zero external output shaped for ``op``'s relation fold."""
    if op is BindingAggregationOp.COPY:
        return Decimal("0")
    if op is BindingAggregationOp.PAGOS_FRACCIONADOS_INGRESADOS:
        return ((Decimal("0"), Decimal("0")),)
    return (Decimal("0"),)


_CAPITAL_MOBILIARIO_INTERESES_CASILLA: CasillaId = validated_casilla_id(
    "0027", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: CasillaId = validated_casilla_id(
    "0029", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_CAPITAL_MOBILIARIO_TOTAL_INGRESOS_CASILLA: CasillaId = validated_casilla_id(
    "0036", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_CAPITAL_MOBILIARIO_RENDIMIENTOS_REDUCIDOS_CASILLA: CasillaId = validated_casilla_id(
    "0041", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_BASE_IMPONIBLE_AHORRO_CASILLA: CasillaId = validated_casilla_id(
    "0460", surface="test_modelo_100_ahorro_base_chain.casilla"
)

# ── helper ────────────────────────────────────────────────────────────────────


def _run_second_newest(snapshot: RegistrySnapshot, inputs: dict[CasillaId, Decimal]) -> dict[CasillaId, Decimal]:
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context={"filing_period": date(snapshot.filing_year, 12, 31)},
        enum_binding_values=_ENUM_BINDINGS,
        binding_values=_BINDINGS,
        relation_values=_RELATION_VALUES,
        # Supply a representative birth date so that any age_at_year_end
        # formula in the mínimo personal chain can resolve.  The exact
        # birth date does not affect the capital-mobiliario / base-ahorro
        # computation chain under test.
        date_binding_values={"renta-profile-taxpayer-birth-date": date(1975, 6, 15)},
    )
    return dict(result.values)


# ── Sergio shape: 0029 = 20 000 EUR dividends ─────────────────────────────────


def test_sergio_0029_dividends_20000_populates_0460(m100_second_newest_snapshot: RegistrySnapshot) -> None:
    """Sergio shape: casilla 0029 (dividendos) = 20 000 EUR.

    Oracle (Art. 49.1.a LIRPF): with no offsetting losses or prior-period
    compensations the base imponible del ahorro equals the net rendimiento del
    capital mobiliario, which equals 0029 when 0037 and 0039 are zero.

    Chain: 0029→0036→0038→0040→0041→0460.
    """
    values = _run_second_newest(m100_second_newest_snapshot, {_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("20000")})

    # The chain must propagate through: 0036=20000, 0038=20000, 0040=20000, 0041=20000.
    assert values[_CAPITAL_MOBILIARIO_TOTAL_INGRESOS_CASILLA] == Decimal("20000"), (
        f"0036 (total ingresos) = {values[_CAPITAL_MOBILIARIO_TOTAL_INGRESOS_CASILLA]!r}; "
        "expected 20000.  Chain 0029→0036 is broken."
    )
    assert values[_CAPITAL_MOBILIARIO_RENDIMIENTOS_REDUCIDOS_CASILLA] == Decimal("20000"), (
        "0041 (suma rendimientos reducidos) = "
        f"{values[_CAPITAL_MOBILIARIO_RENDIMIENTOS_REDUCIDOS_CASILLA]!r}; expected 20000.  "
        "Chain 0036→0038→0040→0041 is broken."
    )
    # Primary regression guard: before the fix, 0460 = 0 even when 0041 = 20 000.
    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] >= Decimal("20000"), (
        f"casilla 0460 (base imponible del ahorro) = {values[_BASE_IMPONIBLE_AHORRO_CASILLA]!r}; "
        "expected ≥ 20 000.  Defect #181 regression: 0041 is not included in "
        "formula renta-base-imponible-del-ahorro.  "
        "Fix: add { casilla = '0041' } to the expression in "
        "2024/formulas/0145-renta-base-imponible-del-ahorro.toml."
    )


def test_sergio_0460_equals_0029_when_no_losses_or_gp(m100_second_newest_snapshot: RegistrySnapshot) -> None:
    """Art. 49.1 oracle: 0460 = 0041 when ganancias patrimoniales saldo = 0.

    With no ganancias-patrimoniales inputs (0422=0, 0423=0) the only base-ahorro
    component is 0041 (capital mobiliario).  Art. 49.1.a → 0460 = net rendimiento
    del capital mobiliario = 0029 (when 0037 and 0039 are zero).
    """
    values = _run_second_newest(m100_second_newest_snapshot, {_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("20000")})

    expected = Decimal("20000")
    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] == expected, (
        f"casilla 0460 = {values[_BASE_IMPONIBLE_AHORRO_CASILLA]!r}; expected {expected}.  "
        "Art. 49.1.a LIRPF: 0460 must equal the net capital-mobiliario rendimiento "
        "when no ganancias or compensations apply."
    )


# ── Carla shape: 0027 = 1 200 EUR cuenta-corriente interest ──────────────────


def test_carla_0027_intereses_1200_propagates_to_0460(m100_second_newest_snapshot: RegistrySnapshot) -> None:
    """Carla shape: casilla 0027 (intereses cuenta corriente) = 1 200 EUR.

    Oracle (Art. 49.1.a LIRPF): 0460 = 1 200 EUR when 0037 and 0039 are zero.

    Chain: 0027→0036→0038→0040→0041→0460.
    """
    values = _run_second_newest(m100_second_newest_snapshot, {_CAPITAL_MOBILIARIO_INTERESES_CASILLA: Decimal("1200")})

    assert values[_CAPITAL_MOBILIARIO_RENDIMIENTOS_REDUCIDOS_CASILLA] == Decimal("1200"), (
        f"0041 = {values[_CAPITAL_MOBILIARIO_RENDIMIENTOS_REDUCIDOS_CASILLA]!r}; "
        "expected 1200.  Chain 0027→…→0041 broken."
    )
    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] == Decimal("1200"), (
        f"casilla 0460 = {values[_BASE_IMPONIBLE_AHORRO_CASILLA]!r}; expected 1200.  "
        "Art. 49.1.a LIRPF oracle: net capital-mobiliario = 1200 → 0460 = 1200.  "
        "Check 2024/formulas/0145-renta-base-imponible-del-ahorro.toml "
        "— 0041 must be included."
    )


# ── Aitor shape: 0029 = 6 000 EUR dividends SAL ───────────────────────────────


def test_aitor_0029_dividends_6000_populates_0460(m100_second_newest_snapshot: RegistrySnapshot) -> None:
    """Aitor shape: casilla 0029 (dividendos SAL) = 6 000 EUR.

    Oracle (Art. 49.1.a LIRPF): 0460 = 6 000 EUR.
    """
    values = _run_second_newest(m100_second_newest_snapshot, {_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("6000")})

    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] == Decimal("6000"), (
        f"casilla 0460 = {values[_BASE_IMPONIBLE_AHORRO_CASILLA]!r}; expected 6000.  "
        "Art. 49.1.a LIRPF oracle: dividends 6000 → 0460 = 6000."
    )


# ── Anti-tautology: proportional scaling ─────────────────────────────────────


def test_0460_scales_proportionally_with_capital_mobiliario_input(
    m100_second_newest_snapshot: RegistrySnapshot,
) -> None:
    """Anti-tautology: doubling the dividends input must double 0460.

    This test cannot pass against a formula that always returns 0 or any
    constant — it verifies that 0460 is strictly coupled to 0029.
    """
    v_small = _run_second_newest(m100_second_newest_snapshot, {_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("5000")})
    v_large = _run_second_newest(
        m100_second_newest_snapshot, {_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("10000")}
    )

    small = v_small[_BASE_IMPONIBLE_AHORRO_CASILLA]
    large = v_large[_BASE_IMPONIBLE_AHORRO_CASILLA]

    assert large == small * 2, (
        f"0460 at 10000 input = {large!r}; at 5000 = {small!r}.  "
        "Doubling the capital-mobiliario income must double the base imponible "
        "del ahorro (Art. 49.1.a LIRPF, no other summands active)."
    )


# ── reviewed edition: same defect must also be fixed ──────────────────────────


def _run_reviewed_edition(
    registry_snapshot: Callable[..., RegistrySnapshot], inputs: dict[CasillaId, Decimal]
) -> dict[CasillaId, Decimal]:
    snapshot = registry_snapshot("100", _REVIEWED_EDITION, "0A", grade=RegistryAuthorityGrade.CALCULATION)
    bindings: dict[str, Decimal] = {
        # The production profile resolver supplies this predicate as 1/0 from
        # taxpayer_type.irpf_income_categories; the scenario models a directa filer.
        "renta-profile-has-economic-activity": Decimal("1"),
        "renta-profile-estimacion-directa": Decimal("1"),
        "renta-modelo-100-estimacion-directa-es-normal": Decimal("1"),
        # declaration_type = 1 (individual) → 0461 computed = 0
        "renta-profile-declaration-type": Decimal("1"),
        "renta-profile-family-minor-children-in-unit": Decimal("0"),
        "renta-profile-incremento-guarderia": Decimal("0"),
        # matrimonio-sobrevenido bindings (81feae7b0): zero = marriage pre-dates filing year.
        "renta-profile-marriage-full-year": Decimal("0"),
        "renta-profile-marriage-month-start": Decimal("0"),
        "renta-profile-marriage-month-end": Decimal("0"),
        "renta-base-liquidable-negativa-general-anterior": Decimal("0"),
        "renta-base-liquidable-negativa-general-em4-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em2-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-gyp-ahorro-em1-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em3-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em2-pendiente-inicio": Decimal("0"),
        "renta-saldo-negativo-rcm-ahorro-em1-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em3-pendiente-inicio": Decimal("0"),
        "renta-base-liquidable-negativa-general-em2-pendiente-inicio": Decimal("0"),
        "renta-retencion-soportada-arrendamiento-actividad": Decimal("0"),
        # Madrid nacimiento/adopción deducción (casilla 1039) profile-derived
        # facts; neutral zero when the chain under test is unrelated.
        "renta-profile-madrid-nacimiento-adopcion-eligible-count": Decimal("0"),
        "renta-profile-unidad-familiar-otros-miembros-base": Decimal("0"),
        "renta-profile-minimo-descendientes-estatal": Decimal("0"),
        "renta-profile-minimo-descendientes-autonomico": Decimal("0"),
        # Art. 75 Ley 19/1994 maritime-worker exemption operands; neutral zero
        # when the chain under test is unrelated (path itself is false).
        "renta-maritime-gross-navigation-income": Decimal("0"),
        "renta-maritime-annual-salary": Decimal("0"),
        "renta-maritime-qualifying-days": Decimal("0"),
        # The Art. 81.1 maternidad deducción of an edition that computes casilla 0611;
        # neutral zero for a scenario with no descendants.
        **M100_NO_DESCENDANT_MATERNIDAD_BINDINGS,
    }
    # The reviewed edition requires all cross-model relation values; supply zeros for
    # all relations so the ahorro chain can be exercised in isolation.
    relation_values = resolve_relation_values(
        snapshot.revision,
        {
            binding.id: _zero_relation_output(binding_aggregation_op(binding))
            for binding, _ in relation_prefill_bindings_for_period(snapshot.revision, period="0A")
        },
        period="0A",
    )
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        date_context=_DATE_REVIEWED_EDITION,
        enum_binding_values={"renta-profile-tax-residence-ccaa": "madrid"},
        binding_values=bindings,
        relation_values=relation_values,
        date_binding_values={"renta-profile-taxpayer-birth-date": date(_REVIEWED_EDITION - 50, 6, 15)},
        # Art. 75 Ley 19/1994 maritime-worker exemption path; neutral false
        # when the chain under test is unrelated.
        boolean_binding_values={"renta-maritime-path-rebeca": False},
    )
    return dict(result.values)


def test_reviewed_edition_0029_dividends_20000_populates_0460(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    """The reviewed edition: same Art. 49.1.a chain must hold.

    Every shipped M100 revision had the same missing-0041 defect.
    """
    values = _run_reviewed_edition(registry_snapshot, {_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("20000")})

    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] >= Decimal("20000"), (
        f"{_REVIEWED_EDITION}: casilla 0460 = {values[_BASE_IMPONIBLE_AHORRO_CASILLA]!r}; expected ≥ 20000.  "
        f"Defect #181 also affects the {_REVIEWED_EDITION} revision.  "
        "Check its renta-base-imponible-del-ahorro formula."
    )


# ── saldo neto del capital mobiliario (casillas 0429 / 0430) ──────────────────
# Art. 49.1.a LIRPF integrates the net movable-capital yield of the year. The
# official BIAHOH expression is 0460 = 0424 - 0436 - ... + 0429 - 0446 - ...
# (no 0041 term); 0429 carries the positive net yield, 0430 the magnitude of
# the negative one, and the negative one is compensated against 0424 within the
# 25 per cent cap (0436) before it reaches 0460.

_GASTOS_DEDUCIBLES_CASILLA: CasillaId = validated_casilla_id(
    "0037", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_SALDO_POSITIVO_CAPITAL_MOBILIARIO_CASILLA: CasillaId = validated_casilla_id(
    "0429", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_SALDO_NEGATIVO_CAPITAL_MOBILIARIO_CASILLA: CasillaId = validated_casilla_id(
    "0430", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_GANANCIAS_BASE_AHORRO_CASILLA: CasillaId = validated_casilla_id(
    "0392", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_PERDIDAS_BASE_AHORRO_CASILLA: CasillaId = validated_casilla_id(
    "0395", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_SALDO_POSITIVO_GYP_AHORRO_CASILLA: CasillaId = validated_casilla_id(
    "0424", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_SALDO_NEGATIVO_GYP_AHORRO_CASILLA: CasillaId = validated_casilla_id(
    "0425", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_COMPENSACION_RCM_CAP_CASILLA: CasillaId = validated_casilla_id(
    "0436", surface="test_modelo_100_ahorro_base_chain.casilla"
)
_COMPENSACION_GYP_CAP_CASILLA: CasillaId = validated_casilla_id(
    "0446", surface="test_modelo_100_ahorro_base_chain.casilla"
)


def test_positive_net_capital_mobiliario_is_0429_and_0430_is_zero(
    m100_second_newest_snapshot: RegistrySnapshot,
) -> None:
    values = _run_second_newest(m100_second_newest_snapshot, {_CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("20000")})

    assert values[_SALDO_POSITIVO_CAPITAL_MOBILIARIO_CASILLA] == Decimal("20000")
    assert values[_SALDO_NEGATIVO_CAPITAL_MOBILIARIO_CASILLA] == Decimal("0")
    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] == Decimal("20000")


def test_negative_net_capital_mobiliario_is_a_positive_0430_magnitude_and_does_not_reduce_0460(
    m100_second_newest_snapshot: RegistrySnapshot,
) -> None:
    """A 800 EUR loss (income 1 000, deductible expenses 1 800) is carried as 0430 = 800."""
    values = _run_second_newest(
        m100_second_newest_snapshot,
        {
            _CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("1000"),
            _GASTOS_DEDUCIBLES_CASILLA: Decimal("1800"),
        },
    )

    assert values[_CAPITAL_MOBILIARIO_RENDIMIENTOS_REDUCIDOS_CASILLA] == Decimal("-800")
    assert values[_SALDO_POSITIVO_CAPITAL_MOBILIARIO_CASILLA] == Decimal("0")
    assert values[_SALDO_NEGATIVO_CAPITAL_MOBILIARIO_CASILLA] == Decimal("800")
    # With no positive gains to offset against, nothing is compensated and the
    # negative yield cannot push the savings base below zero.
    assert values[_COMPENSACION_RCM_CAP_CASILLA] == Decimal("0")
    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] == Decimal("0")


def test_0446_cap_is_a_quarter_of_positive_0429_when_losses_exist(
    m100_second_newest_snapshot: RegistrySnapshot,
) -> None:
    """Art. 49.1.b: pérdidas del año (0425) offset positive 0429 up to 25 per cent."""
    values = _run_second_newest(
        m100_second_newest_snapshot,
        {
            _CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("4000"),
            _PERDIDAS_BASE_AHORRO_CASILLA: Decimal("3000"),
        },
    )

    assert values[_SALDO_NEGATIVO_GYP_AHORRO_CASILLA] == Decimal("3000")
    assert values[_COMPENSACION_GYP_CAP_CASILLA] == Decimal("1000")
    # 4 000 positive yield - 1 000 offset; the 2 000 balance of the loss stays unapplied.
    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] == Decimal("3000")


def test_manual_renta_2025_savings_base_integration_current_year_part(
    registry_snapshot: Callable[..., RegistrySnapshot],
) -> None:
    """Manual práctico Renta 2025, ahorro: gains 5 600, losses 1 600, RCM -800.

    Independent oracle: net gains 4 000; the negative movable-capital yield of
    800 is within the 25 per cent cap (1 000), so every balance before prior-year
    carries is compensated: base del ahorro = 4 000 - 800 = 3 200 (the manual
    then applies 3 000 of prior-year carries, which are zero here).
    """
    values = _run_reviewed_edition(
        registry_snapshot,
        {
            _GANANCIAS_BASE_AHORRO_CASILLA: Decimal("5600"),
            _PERDIDAS_BASE_AHORRO_CASILLA: Decimal("1600"),
            _CAPITAL_MOBILIARIO_DIVIDENDOS_CASILLA: Decimal("1000"),
            _GASTOS_DEDUCIBLES_CASILLA: Decimal("1800"),
        },
    )

    assert values[_SALDO_POSITIVO_GYP_AHORRO_CASILLA] == Decimal("4000")
    assert values[_SALDO_POSITIVO_CAPITAL_MOBILIARIO_CASILLA] == Decimal("0")
    assert values[_SALDO_NEGATIVO_CAPITAL_MOBILIARIO_CASILLA] == Decimal("800")
    assert values[_COMPENSACION_RCM_CAP_CASILLA] == Decimal("800")
    assert values[_BASE_IMPONIBLE_AHORRO_CASILLA] == Decimal("3200")
