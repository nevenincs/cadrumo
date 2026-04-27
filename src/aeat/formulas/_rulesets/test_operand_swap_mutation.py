"""Operand-swap mutation harness for ``sub_op`` chains.

Wave 60 stream 4 H5 (highest Kent harm): a silent ``sub_op(a, b)`` vs
``sub_op(b, a)`` regression would produce a wrong tax liability that
still "validates" against the user-provided value — because the engine
would re-derive with the swapped operands, and the fixture fed to
``audit_against`` would have been authored against that same wrong
formula during the test.

This harness proves the discrepancy IS detected. For each target
ruleset + target ``sub_op`` formula, we:

1. Build an external-anchored fixture where operands are asymmetric
   (``a > b`` and both non-zero). Swap → sign flip → the audit's
   derived value differs substantially from the fixture's user-value.
2. Construct a mutated ruleset via ``Ruleset.model_copy`` with ONLY
   the target formula's ``sub_op`` operands swapped.
3. Run ``Engine().audit_against`` against the ORIGINAL (correct)
   fixture. Assert a discrepancy IS raised on the target casilla.

Covers the four highest-Kent-harm modelos per the wave 60 reviewer:
130 (autónomo pago fraccionado IRPF), 131 (autónomo módulos), 202
(autónomo cuota IS trimestral), 303 (IVA autoliquidación trimestral).

Per ADR §External-anchoring convention, the asymmetric fixtures
used here are the same ones already shipped in the per-modelo
external-anchored worked-example tests — NOT re-derived from the
ruleset formulas.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

import pytest

from .._engine import Engine
from .._formula import FormulaDefinition, RoundFormula, SubFormula
from .._ruleset import Ruleset
from . import (
    MODELO_100_SUMMARY_2025,
    MODELO_111_2025,
    MODELO_115_2025,
    MODELO_115_2026,
    MODELO_123_2025,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_130_2026,
    MODELO_131_2025,
    MODELO_200_2024,
    MODELO_202_2025,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
    MODELO_390_2025,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_local_state]


def _swap_sub_op(node: object) -> SubFormula:
    """Return a new :class:`SubFormula` with the two operands swapped.

    Raises if ``node`` is not a :class:`SubFormula` — callers must
    target a ``sub_op``-bearing formula.
    """
    if not isinstance(node, SubFormula):
        raise TypeError(f"expected SubFormula, got {type(node).__name__}")
    lhs, rhs = node.operands
    return SubFormula(operands=(rhs, lhs))


def _mutate_outer_sub_op(ruleset: Ruleset, target_casilla_id: str) -> Ruleset:
    """Swap operands of the outermost ``sub_op`` in ``target_casilla_id``'s formula.

    Every ruleset wraps its formula body in a terminal ``RoundFormula``
    (via the ``formula(...)`` helper). So the layout is:

        FormulaDefinition.formula = RoundFormula(operands=(sub_op, ...))

    We unwrap the ``RoundFormula``, assert its operand is a ``SubFormula``,
    swap, and rewrap.
    """
    new_formulas: list[FormulaDefinition] = []
    swapped = False
    for fd in ruleset.formulas:
        if fd.casilla_id != target_casilla_id:
            new_formulas.append(fd)
            continue
        round_node = fd.formula
        if not isinstance(round_node, RoundFormula):
            raise TypeError(f"formula {fd.formula_id} top-level node is {type(round_node).__name__}, not RoundFormula")
        inner = round_node.operands[0]
        mutated_inner = _swap_sub_op(inner)
        new_round = RoundFormula(operands=(mutated_inner,), digits=round_node.digits)
        new_formulas.append(
            FormulaDefinition(
                casilla_id=fd.casilla_id,
                formula_id=fd.formula_id,
                formula=new_round,
            )
        )
        swapped = True
    if not swapped:
        raise LookupError(f"ruleset {ruleset.ruleset_id} has no formula for casilla {target_casilla_id!r}")
    return ruleset.model_copy(update={"formulas": tuple(new_formulas)})


# -- Externally-anchored asymmetric fixtures ----------------------------
#
# Each fixture carries a detectable asymmetry at the targeted sub_op so
# that swapping ``sub_op(a, b)`` to ``sub_op(b, a)`` produces a value
# whose delta from the user-supplied expected value exceeds the 0.01
# audit tolerance. The strongest shape is ``a > b > 0`` (sign-flip on
# swap); two targets — ``modelo_303.2025:45`` and
# ``modelo_202.2025:32`` — have ``b = 0`` on the OUTER sub_op, and
# detection then relies on the large magnitude of ``a`` (sign flip
# still occurs, delta = 2a >> tolerance). Harness authors extending
# this file must verify the delta-after-swap is at least 0.02 for
# every new case.


def _modelo_130_rich_fixture() -> dict[str, Decimal]:
    """Wave 63b: asymmetric fixture exercising EVERY sub_op in Modelo 130.

    Modelo 130 has six sub_op-bearing computed casillas — 03, 07, 11,
    14, 17, 19. Each needs its sub_op operands to be distinct + non-zero
    for an outer-operand swap to produce a detectable discrepancy.

    Formula chain (RIRPF art. 110) with the asymmetric values below:
      - 03 = 01 - 02 = 48000 - 12500 = 35500
      - 04 = 20% * 03 = 7100
      - 07 = sub_op(sub_op(04, 05), 06) = (7100 - 1000) - 500 = 5600
      - 08 = 5000 (agraria ingresos, input)
      - 09 = 2% * 08 = 100
      - 11 = 09 - 10 = 100 - 50 = 50
      - 12 = max(0, 07 + 11) = max(0, 5650) = 5650
      - 14 = 12 - 13 = 5650 - 150 = 5500
      - 17 = sub_op(sub_op(14, 15), 16) = (5500 - 200) - 300 = 5000
      - 19 = 17 - 18 = 5000 - 400 = 4600

    No pair of operands is equal, and every operand in a sub_op is
    non-zero so any outer-operand swap flips the result.
    """
    return {
        "01": Decimal("48000.00"),
        "02": Decimal("12500.00"),
        "03": Decimal("35500.00"),
        "04": Decimal("7100.00"),
        "05": Decimal("1000.00"),
        "06": Decimal("500.00"),
        "07": Decimal("5600.00"),
        "08": Decimal("5000.00"),
        "09": Decimal("100.00"),
        "10": Decimal("50.00"),
        "11": Decimal("50.00"),
        "12": Decimal("5650.00"),
        "13": Decimal("150.00"),
        "14": Decimal("5500.00"),
        "15": Decimal("200.00"),
        "16": Decimal("300.00"),
        "17": Decimal("5000.00"),
        "18": Decimal("400.00"),
        "19": Decimal("4600.00"),
    }


def _modelo_131_rich_fixture() -> dict[str, Decimal]:
    """Wave 63b: asymmetric fixture exercising EVERY sub_op in Modelo 131.

    Modelo 131 has three sub_op-bearing computed casillas — 10, 13, 15.
    Each needs its sub_op operands to be asymmetric + non-zero.

    Formula chain (Orden EHA/672/2007 módulos) with the values below:
      - 04 = 2% * 03 = 2% * 50000 = 1000
      - 06 = 2% * 05 = 2% * 20000 = 400
      - 07 = 02 + 04 + 06 = 2000 + 1000 + 400 = 3400
      - 10 = sub_op(sub_op(07, 08), 09) = (3400 - 500) - 200 = 2700
      - 13 = sub_op(sub_op(10, 11), 12) = (2700 - 300) - 150 = 2250
      - 15 = sub_op(13, 14) = 2250 - 600 = 1650
    """
    return {
        "01": Decimal("0.00"),
        "02": Decimal("2000.00"),
        "03": Decimal("50000.00"),
        "04": Decimal("1000.00"),
        "05": Decimal("20000.00"),
        "06": Decimal("400.00"),
        "07": Decimal("3400.00"),
        "08": Decimal("500.00"),
        "09": Decimal("200.00"),
        "10": Decimal("2700.00"),
        "11": Decimal("300.00"),
        "12": Decimal("150.00"),
        "13": Decimal("2250.00"),
        "14": Decimal("600.00"),
        "15": Decimal("1650.00"),
    }


def _modelo_200_fixture() -> dict[str, Decimal]:
    """Wave 63b H2: Modelo 200 coverage (4-deep sub_op nest in casilla 00611).

    00611 = sub_op(sub_op(sub_op(sub_op(00592, 00599), 00601), 00603), 00605).
    With the asymmetric values below:
      00611 = 125000 - 5000 - 30000 - 25000 - 20000 = 45000.
    A swap of the OUTER sub_op (sub_op(A, 00605) → sub_op(00605, A))
    where A = 65000 yields 00605 - A = 20000 - 65000 = -45000 — a clean
    sign flip that the 0.01 tolerance cannot absorb.
    """
    return {
        "00547": Decimal("0.00"),
        "00550": Decimal("500000.00"),
        "00552": Decimal("500000.00"),
        "00558": Decimal("25.00"),
        "00560": Decimal("125000.00"),
        "00562": Decimal("125000.00"),
        "00582": Decimal("125000.00"),
        "00592": Decimal("125000.00"),
        "00599": Decimal("5000.00"),
        "00601": Decimal("30000.00"),
        "00603": Decimal("25000.00"),
        "00605": Decimal("20000.00"),
        "00615": Decimal("0.00"),
        "00619": Decimal("0.00"),
        "00611": Decimal("45000.00"),
        "00621": Decimal("45000.00"),
    }


def _modelo_202_fixture() -> dict[str, Decimal]:
    """Same scenario as ``test_modelo_202_2025::test_external_worked_example_lis_art_40_3_modalidad``.

    Target: casilla 32 = sub_op(sub_op(sub_op(18, 27), 28), 30).
    The outer-operand swap negates ONLY the outermost subtraction
    (inner structure preserved): correct 32 = 34000 - 12000 - 0 - 0 = 22000;
    after swapping outer operands, 32 = 0 - (34000 - 12000 - 0) = -22000.
    Delta 44000 clears the 0.01 tolerance with margin.
    """
    return {
        "16": Decimal("200000.00"),
        "17": Decimal("17.00"),
        "18": Decimal("34000.00"),
        "27": Decimal("12000.00"),
        "28": Decimal("0.00"),
        "30": Decimal("0.00"),
        "31": Decimal("0.00"),
        "32": Decimal("22000.00"),
        "33": Decimal("20000.00"),
        "34": Decimal("22000.00"),
    }


def _modelo_303_fixture() -> dict[str, Decimal]:
    """Minimal IVA fixture targeting Modelo 303 casilla 69.

    Target: casilla 69 = sub_op(66, 67). With 07=10 000, 65=100, 67=500:
    engine derives 09=2 100, 45=2 100, 64=2 100, 66=2 100; 69 correct=1 600;
    swapped 69 = -1 600. Discrepancy surfaces cleanly on casilla 69.

    Per ``Engine.audit_against`` contract, computed casillas absent from
    ``provided`` are skipped by the discrepancy check — so the fixture
    only asserts the values that matter for this mutation. The rate-
    literal computed casillas (02=4, 05=10, 08=21 per LIVA arts. 90/91)
    are intentionally omitted to keep the fixture focused on the sub_op
    chain under test.
    """
    return {
        "07": Decimal("10000.00"),
        "65": Decimal("100"),
        "67": Decimal("500.00"),
        "09": Decimal("2100.00"),
        "45": Decimal("2100.00"),
        "64": Decimal("2100.00"),
        "66": Decimal("2100.00"),
        "69": Decimal("1600.00"),
        "71": Decimal("1600.00"),
    }


def _modelo_111_fixture() -> dict[str, Decimal]:
    """Wave 75a (issue #314): fixture for Modelo 111 casilla 30.

    Chain: 09=19% * 08; 12=19% * 11; 28=03+06+09+12+15+18;
    30=sub_op(28, 29). Outer swap of 30 yields 29-28=-1652 vs
    correct 1652, delta 3304 >> 0.02.
    """
    return {
        "03": Decimal("1000.00"),
        "06": Decimal("200.00"),
        "08": Decimal("500.00"),
        "09": Decimal("95.00"),
        "11": Decimal("300.00"),
        "12": Decimal("57.00"),
        "15": Decimal("400.00"),
        "18": Decimal("150.00"),
        "28": Decimal("1902.00"),
        "29": Decimal("250.00"),
        "30": Decimal("1652.00"),
    }


def _modelo_115_fixture() -> dict[str, Decimal]:
    """Wave 75a (issue #314): fixture for Modelo 115 casilla 06.

    Chain: 03 = 19% * 02; 06 = sub_op(add_op(03, 04), 05).
    Outer swap of 06 yields 05 - (03+04) = -1830 vs correct 1830,
    delta 3660 >> 0.02.
    """
    return {
        "02": Decimal("10000.00"),
        "03": Decimal("1900.00"),
        "04": Decimal("50.00"),
        "05": Decimal("120.00"),
        "06": Decimal("1830.00"),
    }


def _modelo_123_fixture() -> dict[str, Decimal]:
    """Wave 75a (issue #314): fixture for Modelo 123 casilla 11.

    Chain: 09 = 07 + 08; 11 = sub_op(09, 10). Outer swap of 11
    yields 10-09 = -750 vs correct 750, delta 1500 >> 0.02.
    """
    return {
        "07": Decimal("800.00"),
        "08": Decimal("150.00"),
        "09": Decimal("950.00"),
        "10": Decimal("200.00"),
        "11": Decimal("750.00"),
    }


def _modelo_100_summary_fixture() -> dict[str, Decimal]:
    """Wave 75a (issue #314): fixture for Modelo 100 summary casilla 0720.

    Chain: 0595 = 0550+0551+0560+0561; 0630 = 0620+0622;
    0698 = clamp_pos(0595-0630); 0720 = sub_op(sub_op(0698, 0699), 0700).
    Outer swap of 0720 yields 0700 - (0698-0699) = -9000 vs correct
    9000, delta 18000 >> 0.02.
    """
    return {
        "0550": Decimal("10000.00"),
        "0551": Decimal("2000.00"),
        "0560": Decimal("5000.00"),
        "0561": Decimal("1000.00"),
        "0595": Decimal("18000.00"),
        "0620": Decimal("1500.00"),
        "0622": Decimal("500.00"),
        "0630": Decimal("2000.00"),
        "0698": Decimal("16000.00"),
        "0699": Decimal("4000.00"),
        "0700": Decimal("3000.00"),
        "0720": Decimal("9000.00"),
    }


def _modelo_390_fixture() -> dict[str, Decimal]:
    """Wave 75a (issue #314): fixture for Modelo 390 casilla 105.

    Note: issue #314 body says "casilla 97" but that's an input; the
    only sub_op-bearing computed casilla in Modelo 390 is 105 =
    sub_op(96, 104). Outer swap yields 104-96 = -10000 vs correct
    10000, delta 20000 >> 0.02.
    """
    return {
        "96": Decimal("30000.00"),
        "100": Decimal("18000.00"),
        "101": Decimal("2000.00"),
        "104": Decimal("20000.00"),
        "105": Decimal("10000.00"),
        "108": Decimal("500.00"),
        "109": Decimal("300.00"),
        "190": Decimal("10800.00"),
    }


@pytest.mark.parametrize(
    ("ruleset_factory", "target_casilla", "fixture_factory"),
    [
        # Modelo 130 — every sub_op-bearing casilla (6 chains).
        pytest.param(
            lambda: MODELO_130_2025,
            "03",
            _modelo_130_rich_fixture,
            id="modelo_130.2025:casilla_03_rendimiento_neto",
        ),
        pytest.param(
            lambda: MODELO_130_2025,
            "07",
            _modelo_130_rich_fixture,
            id="modelo_130.2025:casilla_07_resultado_apartado_i",
        ),
        pytest.param(
            lambda: MODELO_130_2025,
            "11",
            _modelo_130_rich_fixture,
            id="modelo_130.2025:casilla_11_resultado_apartado_ii",
        ),
        pytest.param(
            lambda: MODELO_130_2025,
            "14",
            _modelo_130_rich_fixture,
            id="modelo_130.2025:casilla_14_neto_tras_minoracion",
        ),
        pytest.param(
            lambda: MODELO_130_2025,
            "17",
            _modelo_130_rich_fixture,
            id="modelo_130.2025:casilla_17_diferencia",
        ),
        pytest.param(
            lambda: MODELO_130_2025,
            "19",
            _modelo_130_rich_fixture,
            id="modelo_130.2025:casilla_19_resultado_final",
        ),
        # Modelo 131 — every sub_op-bearing casilla (3 chains).
        pytest.param(
            lambda: MODELO_131_2025,
            "10",
            _modelo_131_rich_fixture,
            id="modelo_131.2025:casilla_10_resultado_tras_credits",
        ),
        pytest.param(
            lambda: MODELO_131_2025,
            "13",
            _modelo_131_rich_fixture,
            id="modelo_131.2025:casilla_13_resultado_intermedio",
        ),
        pytest.param(
            lambda: MODELO_131_2025,
            "15",
            _modelo_131_rich_fixture,
            id="modelo_131.2025:casilla_15_resultado_a_ingresar",
        ),
        # Modelo 303 — every sub_op-bearing casilla (2 chains).
        pytest.param(
            lambda: MODELO_303_2025,
            "45",
            _modelo_303_fixture,
            id="modelo_303.2025:casilla_45_resultado_regimen_general",
        ),
        pytest.param(
            lambda: MODELO_303_2025,
            "69",
            _modelo_303_fixture,
            id="modelo_303.2025:casilla_69_resultado",
        ),
        # Modelo 200 — 4-deep sub_op nest (wave 62 H2 closure).
        pytest.param(
            lambda: MODELO_200_2024,
            "00611",
            _modelo_200_fixture,
            id="modelo_200.2024:casilla_00611_cuota_diferencial_deep_nest",
        ),
        # Wave 75a (issue #314) — Modelo 130 2024 clones every sub_op chain.
        pytest.param(
            lambda: MODELO_130_2024,
            "03",
            _modelo_130_rich_fixture,
            id="modelo_130.2024:casilla_03_rendimiento_neto",
        ),
        pytest.param(
            lambda: MODELO_130_2024,
            "07",
            _modelo_130_rich_fixture,
            id="modelo_130.2024:casilla_07_resultado_apartado_i",
        ),
        pytest.param(
            lambda: MODELO_130_2024,
            "11",
            _modelo_130_rich_fixture,
            id="modelo_130.2024:casilla_11_resultado_apartado_ii",
        ),
        pytest.param(
            lambda: MODELO_130_2024,
            "14",
            _modelo_130_rich_fixture,
            id="modelo_130.2024:casilla_14_neto_tras_minoracion",
        ),
        pytest.param(
            lambda: MODELO_130_2024,
            "17",
            _modelo_130_rich_fixture,
            id="modelo_130.2024:casilla_17_diferencia",
        ),
        pytest.param(
            lambda: MODELO_130_2024,
            "19",
            _modelo_130_rich_fixture,
            id="modelo_130.2024:casilla_19_resultado_final",
        ),
        # Issue #321 — Modelo 130 2026 clones every sub_op chain.
        # The 2026 ruleset is a structural clone of 2024 / 2025
        # (RIRPF art. 110 unchanged across all three years), so the
        # rich fixture applies unchanged.
        pytest.param(
            lambda: MODELO_130_2026,
            "03",
            _modelo_130_rich_fixture,
            id="modelo_130.2026:casilla_03_rendimiento_neto",
        ),
        pytest.param(
            lambda: MODELO_130_2026,
            "07",
            _modelo_130_rich_fixture,
            id="modelo_130.2026:casilla_07_resultado_apartado_i",
        ),
        pytest.param(
            lambda: MODELO_130_2026,
            "11",
            _modelo_130_rich_fixture,
            id="modelo_130.2026:casilla_11_resultado_apartado_ii",
        ),
        pytest.param(
            lambda: MODELO_130_2026,
            "14",
            _modelo_130_rich_fixture,
            id="modelo_130.2026:casilla_14_neto_tras_minoracion",
        ),
        pytest.param(
            lambda: MODELO_130_2026,
            "17",
            _modelo_130_rich_fixture,
            id="modelo_130.2026:casilla_17_diferencia",
        ),
        pytest.param(
            lambda: MODELO_130_2026,
            "19",
            _modelo_130_rich_fixture,
            id="modelo_130.2026:casilla_19_resultado_final",
        ),
        # Wave 75a (issue #314) — Modelo 303 2024 clones.
        pytest.param(
            lambda: MODELO_303_2024,
            "45",
            _modelo_303_fixture,
            id="modelo_303.2024:casilla_45_resultado_regimen_general",
        ),
        pytest.param(
            lambda: MODELO_303_2024,
            "69",
            _modelo_303_fixture,
            id="modelo_303.2024:casilla_69_resultado",
        ),
        pytest.param(
            lambda: MODELO_303_2026,
            "45",
            _modelo_303_fixture,
            id="modelo_303.2026:casilla_45_resultado_regimen_general",
        ),
        pytest.param(
            lambda: MODELO_303_2026,
            "69",
            _modelo_303_fixture,
            id="modelo_303.2026:casilla_69_resultado",
        ),
        # Wave 75a (issue #314) — 111 / 115 / 123 / 100_summary / 390.
        pytest.param(
            lambda: MODELO_111_2025,
            "30",
            _modelo_111_fixture,
            id="modelo_111.2025:casilla_30_resultado_a_ingresar",
        ),
        pytest.param(
            lambda: MODELO_115_2025,
            "06",
            _modelo_115_fixture,
            id="modelo_115.2025:casilla_06_resultado_a_ingresar",
        ),
        # Issue #319 — Modelo 115 2026 clones the casilla-06 sub_op chain.
        # The 2026 ruleset re-imports formulas from the 2025 module
        # verbatim (RIRPF art. 100 unchanged across all three years).
        pytest.param(
            lambda: MODELO_115_2026,
            "06",
            _modelo_115_fixture,
            id="modelo_115.2026:casilla_06_resultado_a_ingresar",
        ),
        pytest.param(
            lambda: MODELO_123_2025,
            "11",
            _modelo_123_fixture,
            id="modelo_123.2025:casilla_11_resultado_a_ingresar",
        ),
        pytest.param(
            lambda: MODELO_100_SUMMARY_2025,
            "0720",
            _modelo_100_summary_fixture,
            id="modelo_100_summary.2025:casilla_0720_cuota_resultante",
        ),
        pytest.param(
            lambda: MODELO_390_2025,
            "105",
            _modelo_390_fixture,
            id="modelo_390.2025:casilla_105_resultado_regimen_general",
        ),
    ],
)
def test_sub_op_operand_swap_is_detected(
    ruleset_factory: Callable[[], Ruleset],
    target_casilla: str,
    fixture_factory: Callable[[], dict[str, Decimal]],
) -> None:
    """Mutated ruleset MUST produce a discrepancy on the target casilla.

    Baseline sentinel first: the unmutated ruleset audits cleanly
    against the fixture (confirms the fixture itself is correct). Then
    the mutated ruleset audits and MUST surface ``target_casilla`` in
    the discrepancies list.
    """
    ruleset = ruleset_factory()
    fixture = fixture_factory()
    engine = Engine()

    baseline = engine.audit_against(ruleset=ruleset, provided=fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean(), (
        f"baseline audit must be clean before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )

    mutated = _mutate_outer_sub_op(ruleset, target_casilla)
    report = engine.audit_against(ruleset=mutated, provided=fixture, tolerance=Decimal("0.01"))
    affected = {d.casilla_id for d in report.discrepancies}
    assert target_casilla in affected, (
        f"operand-swap mutation on {ruleset.ruleset_id} casilla {target_casilla} "
        f"was NOT detected — audit returned discrepancies on {affected}"
    )

    # Wave 67e enforcement of the delta-after-swap >= 0.02 invariant
    # documented at the top of this module. A case with delta below
    # the tolerance would still "detect" under audit_against because
    # tolerance=0.01 is strictly less-than, but a future tolerance
    # loosening (or rounding drift) could silently hide it. The
    # explicit threshold here makes the invariant enforceable.
    target_discrepancy = next(d for d in report.discrepancies if d.casilla_id == target_casilla)
    delta_abs = abs(target_discrepancy.delta)
    assert delta_abs >= Decimal("0.02"), (
        f"operand-swap on {ruleset.ruleset_id} casilla {target_casilla} "
        f"produced delta={delta_abs} which is below the 0.02 detection "
        f"floor — the fixture's operand pair is too close to symmetric."
    )


def test_modelo_202_nested_sub_op_swap_is_detected() -> None:
    """Modelo 202 casilla 32's formula has a 4-deep sub_op chain.

    Outer-level swap of ``sub_op(sub_op(sub_op(18, 27), 28), 30)`` to
    ``sub_op(30, sub_op(sub_op(18, 27), 28))`` sign-flips the result
    when the inner chain is non-zero. Fixture provides 18=34000,
    27=12000, 28=0, 30=0 — correct 32 = 22000; swapped 32 = -22000.
    """
    ruleset = MODELO_202_2025
    fixture = _modelo_202_fixture()
    engine = Engine()

    baseline = engine.audit_against(ruleset=ruleset, provided=fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean(), (
        f"baseline audit must be clean before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )

    mutated = _mutate_outer_sub_op(ruleset, "32")
    report = engine.audit_against(ruleset=mutated, provided=fixture, tolerance=Decimal("0.01"))
    affected = {d.casilla_id for d in report.discrepancies}
    assert "32" in affected, f"Modelo 202 casilla 32 outer-sub_op swap not detected; affected={affected}"


def test_mutate_sub_op_helper_rejects_non_sub_formula() -> None:
    """Harness integrity: targeting a non-sub_op casilla raises TypeError.

    Modelo 130 casilla 04 is a ``clamp_pos(percent(...))`` — not a
    ``sub_op``. The helper must refuse to mutate it rather than
    silently succeed.
    """
    with pytest.raises(TypeError):
        _mutate_outer_sub_op(MODELO_130_2025, "04")


def test_mutate_sub_op_helper_rejects_missing_casilla() -> None:
    """Harness integrity: targeting a casilla without a formula raises LookupError."""
    with pytest.raises(LookupError):
        # Casilla "01" on Modelo 130 is an input (ingresos), not computed.
        _mutate_outer_sub_op(MODELO_130_2025, "01")
