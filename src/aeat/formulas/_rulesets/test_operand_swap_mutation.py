"""Operand-swap mutation harness for ``sub_op`` chains.

A silent ``sub_op(a, b)`` vs ``sub_op(b, a)`` regression would produce
a wrong tax liability that still "validates" against the user-provided
value — because the engine would re-derive with the swapped operands,
and the fixture fed to ``audit_against`` would have been authored
against that same wrong formula during the test.

This harness proves the discrepancy IS detected. For each target
ruleset + target ``sub_op`` formula, we:

1. Build an external-anchored fixture where operands are asymmetric
   (``a > b`` and both non-zero). Swap → sign flip → the audit's
   derived value differs substantially from the fixture's user-value.
2. Construct a mutated ruleset via ``Ruleset.model_copy`` with ONLY
   the target formula's ``sub_op`` operands swapped.
3. Run ``Engine().audit_against`` against the ORIGINAL (correct)
   fixture. Assert a discrepancy IS raised on the target casilla.

Per the external-anchoring ADR, the asymmetric fixtures used here are
the same ones already shipped in the per-modelo external-anchored
worked-example tests — NOT re-derived from the ruleset formulas.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import cast

import pytest

from .._engine import Engine
from .._formula import ClampPositiveFormula, Formula, FormulaDefinition, Operand, RoundFormula, SubFormula
from .._ruleset import Ruleset
from . import (
    MODELO_100_2024,
    MODELO_100_2025,
    MODELO_100_2026,
    MODELO_100_SUMMARY_2025,
    MODELO_111_2024,
    MODELO_111_2025,
    MODELO_111_2026,
    MODELO_115_2024,
    MODELO_115_2025,
    MODELO_115_2026,
    MODELO_123_2024,
    MODELO_123_2025,
    MODELO_123_2026,
    MODELO_130_2024,
    MODELO_130_2025,
    MODELO_130_2026,
    MODELO_131_2024,
    MODELO_131_2025,
    MODELO_131_2026,
    MODELO_200_2024,
    MODELO_200_2025,
    MODELO_200_2026,
    MODELO_202_2025,
    MODELO_303_2024,
    MODELO_303_2025,
    MODELO_303_2026,
    MODELO_390_2024,
    MODELO_390_2025,
    MODELO_390_2026,
)
from ._mutators import _node_at_path, _replace_at_path

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


def _swap_outer_sub_op_in_subtree(node: Operand) -> Operand:
    """Return ``node`` with its outermost reachable ``SubFormula`` swapped.

    Descends through unary wrappers — ``ClampPositiveFormula`` — until a
    ``SubFormula`` is reached, then rebuilds the wrapper chain around
    the swapped node. Required for clamp-wrapped chains like Modelo
    100 casilla 0545 (``clamp_pos(sub_op(sub_op(...), ref))``).
    Raises ``TypeError`` if no ``SubFormula`` is reachable through the
    wrapper chain.
    """
    if isinstance(node, SubFormula):
        return _swap_sub_op(node)
    if isinstance(node, ClampPositiveFormula):
        inner = node.operands[0]
        swapped_inner = _swap_outer_sub_op_in_subtree(inner)
        return ClampPositiveFormula(operands=(swapped_inner,))
    raise TypeError(f"expected SubFormula or ClampPositiveFormula(SubFormula), got {type(node).__name__}")


def _mutate_outer_sub_op(ruleset: Ruleset, target_casilla_id: str) -> Ruleset:
    """Swap operands of the outermost reachable ``sub_op`` in the casilla's formula.

    Every ruleset wraps its formula body in a terminal ``RoundFormula``
    (via the ``formula(...)`` helper). So the layout is:

        FormulaDefinition.formula = RoundFormula(operands=(<chain>, ...))

    where ``<chain>`` is either a direct ``SubFormula`` or a unary
    wrapper sequence — currently ``ClampPositiveFormula`` — wrapping
    one. We descend through the wrappers, swap the underlying
    ``SubFormula`` operands, and rebuild the tree.
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
        mutated_inner = _swap_outer_sub_op_in_subtree(inner)
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


def _mutate_sub_op_at_path(ruleset: Ruleset, target_casilla_id: str, sub_op_path: tuple[int, ...]) -> Ruleset:
    """Swap operands of the :class:`SubFormula` at ``sub_op_path`` inside the casilla's tree.

    Generalisation of :func:`_mutate_outer_sub_op` that targets any
    ``SubFormula`` node — outer or inner. ``sub_op_path`` is the
    operand-index tuple from the casilla's
    :class:`FormulaDefinition.formula` root to the target node.

    Raises:
        LookupError: ``ruleset`` has no formula for ``target_casilla_id``.
        TypeError: the node at ``sub_op_path`` is not a :class:`SubFormula`.
    """
    new_formulas: list[FormulaDefinition] = []
    swapped = False
    for fd in ruleset.formulas:
        if fd.casilla_id != target_casilla_id:
            new_formulas.append(fd)
            continue
        target_node = _node_at_path(fd.formula, sub_op_path)
        if not isinstance(target_node, SubFormula):
            raise TypeError(
                f"expected SubFormula at path {sub_op_path} for ruleset {ruleset.ruleset_id} "
                f"casilla {target_casilla_id}; got {type(target_node).__name__}"
            )
        swapped_node = _swap_sub_op(target_node)
        # ``_replace_at_path`` returns ``object`` for intra-mutator
        # flexibility; casting is safe here because the casilla's
        # formula root is a :class:`Formula` subtype and replacing a
        # :class:`SubFormula` with another :class:`SubFormula` preserves
        # the union membership.
        new_formula = cast(Formula, _replace_at_path(fd.formula, sub_op_path, swapped_node))
        new_formulas.append(
            FormulaDefinition(
                casilla_id=fd.casilla_id,
                formula_id=fd.formula_id,
                formula=new_formula,
            )
        )
        swapped = True
    if not swapped:
        raise LookupError(f"ruleset {ruleset.ruleset_id} has no formula for casilla {target_casilla_id!r}")
    return ruleset.model_copy(update={"formulas": tuple(new_formulas)})


def _walk_sub_op_paths(formula: Formula) -> list[tuple[int, ...]]:
    """Return every path to a :class:`SubFormula` descendant of ``formula``."""
    from .._formula import _compound_operands, _is_compound

    paths: list[tuple[int, ...]] = []

    def _descend(node: object, prefix: tuple[int, ...]) -> None:
        if isinstance(node, SubFormula):
            paths.append(prefix)
        if _is_compound(node):
            for idx, child in enumerate(_compound_operands(node)):
                _descend(child, (*prefix, idx))

    _descend(formula, ())
    return paths


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
    """Asymmetric fixture exercising EVERY sub_op in Modelo 130.

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
    """Asymmetric fixture exercising EVERY sub_op in Modelo 131.

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
    """Modelo 200 coverage (4-deep sub_op nest in casilla 00611).

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
    """Issue #314 fixture for Modelo 111 casilla 30.

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
    """Issue #314 fixture for Modelo 115 casilla 06.

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
    """Issue #314 fixture for Modelo 123 casilla 11.

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
    """Issue #314 fixture for Modelo 100 summary casilla 0720.

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


_M100_BASE_INPUTS_AND_STABLE_COMPUTED: dict[str, Decimal] = {
    # Anexo B1: 0020 = 199 002, 0021 = 0 (clamped, 0020 > 19 747.50),
    # 0022 = 199 002.
    "0001": Decimal("200000.00"),
    "0008": Decimal("200.00"),
    "0009": Decimal("100.00"),
    "0010": Decimal("50.00"),
    "0019": Decimal("648.00"),
    "0020": Decimal("199002.00"),
    "0021": Decimal("0.00"),
    "0022": Decimal("199002.00"),
    # Anexo B2: 0048 = 15 000, 0049 = 13 000.
    "0028": Decimal("10000.00"),
    "0029": Decimal("5000.00"),
    "0030": Decimal("2000.00"),
    "0031": Decimal("1000.00"),
    "0032": Decimal("2000.00"),
    "0035": Decimal("3000.00"),
    "0048": Decimal("15000.00"),
    "0049": Decimal("13000.00"),
    # Anexo C: 0106 = 13 000, 0107 = 12 000.
    "0061": Decimal("20000.00"),
    "0066": Decimal("5000.00"),
    "0072": Decimal("2000.00"),
    "0078": Decimal("1000.00"),
    "0085": Decimal("5000.00"),
    "0106": Decimal("13000.00"),
    "0107": Decimal("12000.00"),
    # Anexo D normal: 0190 = 14 400, 0195 = 65 600, 0205 = 63 600.
    "0140": Decimal("80000.00"),
    "0150": Decimal("10000.00"),
    "0155": Decimal("500.00"),
    "0165": Decimal("2000.00"),
    "0170": Decimal("1500.00"),
    "0173": Decimal("800.00"),
    "0180": Decimal("600.00"),
    "0200": Decimal("2000.00"),
    "0190": Decimal("14400.00"),
    "0195": Decimal("65600.00"),
    "0205": Decimal("63600.00"),
    # Anexo D simplificada: 0220 = 30 000, 0225 = 1 500 (5 % cap
    # active, < 2 000 limit), 0230 = 28 500, 0240 = 27 500.
    "0210": Decimal("35000.00"),
    "0215": Decimal("5000.00"),
    "0235": Decimal("1000.00"),
    "0220": Decimal("30000.00"),
    "0225": Decimal("1500.00"),
    "0230": Decimal("28500.00"),
    "0240": Decimal("27500.00"),
    # Anexo D modulos: 0260 = 13 000.
    "0250": Decimal("15000.00"),
    "0255": Decimal("2000.00"),
    "0260": Decimal("13000.00"),
    # Anexo E: 0405 = 6 000 (saldo neto patrimonial).
    "0306": Decimal("8000.00"),
    "0307": Decimal("2000.00"),
    "0405": Decimal("6000.00"),
    # Anexo F BIG drivers + computed: 0432 = 420 102, 0500 = 380 000,
    # 0545 (BLG) = 383 102 (spans all 6 tarifa brackets).
    "0399": Decimal("100000.00"),
    "0445": Decimal("25000.00"),
    "0455": Decimal("12000.00"),
    # Each component of 0500 (mínimo personal y familiar) is non-zero
    # so the Add-chain at 0500 = (0505+0510)+(0515+0520) carries
    # detectable RHS magnitudes for the arithmetic-op-swap harness.
    # Sum: 378000 + 1000 + 800 + 200 = 380 000 (preserves the 0500
    # baseline used by every downstream calculation).
    "0505": Decimal("378000.00"),
    "0510": Decimal("1000.00"),
    "0515": Decimal("800.00"),
    "0520": Decimal("200.00"),
    "0500": Decimal("380000.00"),
    "0432": Decimal("420102.00"),
    "0545": Decimal("383102.00"),
    # Anexo F BLA: 0400 = 350 000 → 0555 = 363 000.
    "0400": Decimal("350000.00"),
    "0460": Decimal("363000.00"),
    "0555": Decimal("363000.00"),
    # Anexo G stable across years (TARIFA_ESTATAL_GENERAL unchanged
    # 2021-2026): 0540 = 83 310,74, 0542 = 82 550,75, 0550 = 759,99.
    "0540": Decimal("83310.74"),
    "0542": Decimal("82550.75"),
    "0550": Decimal("759.99"),
    # Anexo G autonomic cuotas (caller-supplied): asymmetric.
    "0551": Decimal("1000.00"),
    "0561": Decimal("500.00"),
    # Anexo N: per-CCAA aggregate deductions. 1101 (Andalucía) = 2 000,
    # others 0 → 0622 = 2 000.
    # Per-CCAA aggregate deductions: every entry non-zero so the
    # 15-operand AddFormula at 0622 has a detectable last-operand
    # for the arithmetic-op-swap harness. Decreasing values
    # (1900, 50, 50, ...) preserve the asymmetric design while
    # keeping the sum at 0622 = 2 000.
    "1101": Decimal("1860.00"),
    "1102": Decimal("10.00"),
    "1103": Decimal("10.00"),
    "1104": Decimal("10.00"),
    "1105": Decimal("10.00"),
    "1106": Decimal("10.00"),
    "1107": Decimal("10.00"),
    "1108": Decimal("10.00"),
    "1109": Decimal("10.00"),
    "1110": Decimal("10.00"),
    "1111": Decimal("10.00"),
    "1112": Decimal("10.00"),
    "1113": Decimal("10.00"),
    "1114": Decimal("10.00"),
    "1115": Decimal("10.00"),
    "0622": Decimal("2000.00"),
    # Deducciones estatales + Ceuta/Melilla.
    "0612": Decimal("1000.00"),
    "0620": Decimal("5000.00"),
    "0630": Decimal("7000.00"),
    # Retenciones + pagos fraccionados.
    "0699": Decimal("8000.00"),
    "0700": Decimal("2500.00"),
}


def _modelo_100_full_fixture_2024() -> dict[str, Decimal]:
    """Year-2024 variant of the comprehensive M100 fixture.

    The ahorro top-bracket rate is 0.14 in 2024 (pre-Ley 7/2024); the
    derived 0560 / 0595 / 0698 / 0720 values therefore differ from
    the 2025/2026 fixture.
    """
    return {
        **_M100_BASE_INPUTS_AND_STABLE_COMPUTED,
        # Year-specific computed casillas (TARIFA_ESTATAL_AHORRO 2024
        # top-bracket rate 0.14): 0560 = 44 760, 0595 = 47 019,99,
        # 0698 = 39 019,99, 0720 = 28 519,99.
        "0560": Decimal("44760.00"),
        "0595": Decimal("47019.99"),
        "0698": Decimal("39019.99"),
        "0720": Decimal("28519.99"),
    }


def _modelo_100_full_fixture_post_2025() -> dict[str, Decimal]:
    """Year-2025/2026 variant of the comprehensive M100 fixture.

    Ley 7/2024 raised the ahorro top-bracket rate from 0.14 to 0.15
    effective 1/1/2025, lifting 0560 by 630 € and the dependent
    chain accordingly.
    """
    return {
        **_M100_BASE_INPUTS_AND_STABLE_COMPUTED,
        # Year-specific computed casillas (TARIFA_ESTATAL_AHORRO post-2025
        # top-bracket rate 0.15): 0560 = 45 390, 0595 = 47 649,99,
        # 0698 = 39 649,99, 0720 = 29 149,99.
        "0560": Decimal("45390.00"),
        "0595": Decimal("47649.99"),
        "0698": Decimal("39649.99"),
        "0720": Decimal("29149.99"),
    }


# Note: pre-Wave-5 a backwards-compatible ``_modelo_100_full_fixture()``
# alias resolved to the post-2025 variant unconditionally. The alias
# was removed because applying it against the 2024 ruleset would
# fail baseline-clean audit (the 0560 ahorro top-bracket rate is 0.14
# in 2024 vs 0.15 in 2025/2026). Per-year callers must select the
# correct variant explicitly.


def _modelo_100_art20_piece_a_fixture() -> dict[str, Decimal]:
    """Path-override fixture for casilla 0021 piece_a sub_ops.

    Drives 0020 = 16 000 € so the LIRPF art. 20 piecewise selects
    piece_a (slope 1.75). At this rendimiento level piece_a yields
    5 293 € while piece_b clamps to 0 — the ``max_op`` selects
    piece_a, so any swap inside piece_a's sub_op chain produces a
    detectable change on 0021.

    Trade-off: with 0020 = 16 000 the rest of the M100 chain
    collapses (0432 ≈ 16 000, 0545 ≈ 0 after reducciones) and
    bracket-spanning sub_ops in Anexo G are NOT detectable — but
    this fixture is targeted *only* at piece_a paths via the
    :data:`_SUB_OP_PATH_OVERRIDES` table.
    """
    return {
        "0001": Decimal("16000.00"),
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": Decimal("16000.00"),
        "0021": Decimal("5293.00"),
    }


def _modelo_100_art20_piece_b_fixture() -> dict[str, Decimal]:
    """Path-override fixture for casilla 0021 piece_b sub_ops.

    Drives 0020 = 18 500 € so the LIRPF art. 20 piecewise selects
    piece_b (slope 1.14, max-op winner over piece_a). Same trade-off
    as the piece_a fixture: targeted only at piece_b paths.
    """
    return {
        "0001": Decimal("18500.00"),
        "0008": Decimal("0.00"),
        "0009": Decimal("0.00"),
        "0010": Decimal("0.00"),
        "0019": Decimal("0.00"),
        "0020": Decimal("18500.00"),
        # 0021 = min(0020, max(piece_a=918, piece_b=1422.15)) = 1422.15.
        "0021": Decimal("1422.15"),
    }


# Path-specific fixture overrides for sub_op nodes whose detection
# requires a different operand range than the comprehensive default.
# Issue #457: only the LIRPF art. 20 piecewise reducción in M100
# casilla 0021 needs this — both pieces share a single ``max_op`` so
# only one piece's chain is observable per fixture.
_SUB_OP_PATH_OVERRIDES: dict[
    tuple[str, str, tuple[int, ...]],
    Callable[[], dict[str, Decimal]],
] = {
    # LIRPF art. 20 piece_a outer + inner sub_ops (paths from the
    # walker inspection: ``(0, 1, 0, 0)`` and ``(0, 1, 0, 0, 1, 1, 0)``).
    ("modelo_100.2024", "0021", (0, 1, 0, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2024", "0021", (0, 1, 0, 0, 1, 1, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2025", "0021", (0, 1, 0, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2025", "0021", (0, 1, 0, 0, 1, 1, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2026", "0021", (0, 1, 0, 0)): _modelo_100_art20_piece_a_fixture,
    ("modelo_100.2026", "0021", (0, 1, 0, 0, 1, 1, 0)): _modelo_100_art20_piece_a_fixture,
    # LIRPF art. 20 piece_b outer + inner.
    ("modelo_100.2024", "0021", (0, 1, 1, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2024", "0021", (0, 1, 1, 0, 1, 1, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2025", "0021", (0, 1, 1, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2025", "0021", (0, 1, 1, 0, 1, 1, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2026", "0021", (0, 1, 1, 0)): _modelo_100_art20_piece_b_fixture,
    ("modelo_100.2026", "0021", (0, 1, 1, 0, 1, 1, 0)): _modelo_100_art20_piece_b_fixture,
}


def _modelo_390_fixture() -> dict[str, Decimal]:
    """Asymmetric fixture for Modelo 390 sub_op chains.

    Three sub_op-bearing computed casillas live in the Modelo 390
    ruleset (issue #327): casilla 105 = sub_op(96, 104), casilla 191 =
    sub_op(190, 662), casilla 193 = clamp_pos(sub_op(0, 191)). The
    fixture sets each LHS strictly larger than its RHS so an operand
    swap on any of them flips the sign and produces a delta well
    above the 0.01 tolerance.
    """
    return {
        "95": Decimal("100000.00"),
        "96": Decimal("30000.00"),
        "100": Decimal("18000.00"),
        "101": Decimal("2000.00"),
        "104": Decimal("20000.00"),
        "105": Decimal("10000.00"),
        "108": Decimal("500.00"),
        "109": Decimal("300.00"),
        "190": Decimal("10800.00"),
        "191": Decimal("9800.00"),  # 190 - 662 = 10800 - 1000
        "192": Decimal("9800.00"),
        "193": Decimal("0.00"),
        "662": Decimal("1000.00"),
    }


# Comprehensive sub_op coverage table — the single source of truth for
# the operand-swap parametrize block AND the kill-rate aggregator. Each
# entry maps a (ruleset, casilla) pair to its asymmetric fixture
# factory; the parametrize generator walks every ``SubFormula``
# descendant of the casilla's formula tree and emits one case per
# ``(ruleset_id, casilla_id, sub_op_path)`` triple. The
# :data:`SUB_OP_COVERAGE` constant is derived from the same walk and
# imported by :mod:`test_mutator_kill_rate` for the deferred-gap
# invariant.
_SUB_OP_COVERAGE_DATA: tuple[
    tuple[Callable[[], Ruleset], str, Callable[[], dict[str, Decimal]]],
    ...,
] = (
    # Modelo 130 — every sub_op-bearing casilla x 3 years.
    (lambda: MODELO_130_2024, "03", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2024, "07", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2024, "11", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2024, "14", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2024, "17", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2024, "19", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2025, "03", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2025, "07", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2025, "11", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2025, "14", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2025, "17", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2025, "19", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2026, "03", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2026, "07", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2026, "11", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2026, "14", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2026, "17", _modelo_130_rich_fixture),
    (lambda: MODELO_130_2026, "19", _modelo_130_rich_fixture),
    # Modelo 131 — every sub_op-bearing casilla x 3 years.
    (lambda: MODELO_131_2024, "10", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2024, "13", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2024, "15", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2025, "10", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2025, "13", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2025, "15", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2026, "10", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2026, "13", _modelo_131_rich_fixture),
    (lambda: MODELO_131_2026, "15", _modelo_131_rich_fixture),
    # Modelo 303 — every sub_op-bearing casilla x 3 years.
    (lambda: MODELO_303_2024, "45", _modelo_303_fixture),
    (lambda: MODELO_303_2024, "69", _modelo_303_fixture),
    (lambda: MODELO_303_2025, "45", _modelo_303_fixture),
    (lambda: MODELO_303_2025, "69", _modelo_303_fixture),
    (lambda: MODELO_303_2026, "45", _modelo_303_fixture),
    (lambda: MODELO_303_2026, "69", _modelo_303_fixture),
    # Modelo 200 — casillas 00611 (4-deep nest) + 00621 (1 sub_op) x 3 years.
    (lambda: MODELO_200_2024, "00611", _modelo_200_fixture),
    (lambda: MODELO_200_2024, "00621", _modelo_200_fixture),
    (lambda: MODELO_200_2025, "00611", _modelo_200_fixture),
    (lambda: MODELO_200_2025, "00621", _modelo_200_fixture),
    (lambda: MODELO_200_2026, "00611", _modelo_200_fixture),
    (lambda: MODELO_200_2026, "00621", _modelo_200_fixture),
    # Modelo 202 — casilla 32 (3-deep nest).
    (lambda: MODELO_202_2025, "32", _modelo_202_fixture),
    # Modelo 111 / 115 — outer sub_ops x 3 years.
    (lambda: MODELO_111_2024, "30", _modelo_111_fixture),
    (lambda: MODELO_111_2025, "30", _modelo_111_fixture),
    (lambda: MODELO_111_2026, "30", _modelo_111_fixture),
    (lambda: MODELO_115_2024, "06", _modelo_115_fixture),
    (lambda: MODELO_115_2025, "06", _modelo_115_fixture),
    (lambda: MODELO_115_2026, "06", _modelo_115_fixture),
    # Modelo 123 — 1 chain x 3 years.
    (lambda: MODELO_123_2024, "11", _modelo_123_fixture),
    (lambda: MODELO_123_2025, "11", _modelo_123_fixture),
    (lambda: MODELO_123_2026, "11", _modelo_123_fixture),
    # Modelo 100 summary 2025 — casillas 0698 + 0720 (3 sub_ops total).
    (lambda: MODELO_100_SUMMARY_2025, "0698", _modelo_100_summary_fixture),
    (lambda: MODELO_100_SUMMARY_2025, "0720", _modelo_100_summary_fixture),
    # Modelo 390 — 3 sub_op-bearing casillas (105 / 191 / 193) x 3 years.
    (lambda: MODELO_390_2024, "105", _modelo_390_fixture),
    (lambda: MODELO_390_2024, "191", _modelo_390_fixture),
    (lambda: MODELO_390_2024, "193", _modelo_390_fixture),
    (lambda: MODELO_390_2025, "105", _modelo_390_fixture),
    (lambda: MODELO_390_2025, "191", _modelo_390_fixture),
    (lambda: MODELO_390_2025, "193", _modelo_390_fixture),
    (lambda: MODELO_390_2026, "105", _modelo_390_fixture),
    (lambda: MODELO_390_2026, "191", _modelo_390_fixture),
    (lambda: MODELO_390_2026, "193", _modelo_390_fixture),
    # Modelo 100 full-form — every sub_op-bearing casilla x 3 years.
    # Issue #457 closure: the M100 megaproject's full per-anexo coverage.
    (lambda: MODELO_100_2024, "0020", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0021", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0022", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0048", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0049", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0106", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0107", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0190", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0195", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0205", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0220", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0230", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0240", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0260", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0405", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0540", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0542", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0545", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0550", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0560", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0698", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2024, "0720", _modelo_100_full_fixture_2024),
    (lambda: MODELO_100_2025, "0020", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0021", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0022", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0048", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0049", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0106", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0107", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0190", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0195", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0205", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0220", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0230", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0240", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0260", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0405", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0540", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0542", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0545", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0550", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0560", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0698", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2025, "0720", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0020", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0021", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0022", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0048", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0049", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0106", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0107", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0190", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0195", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0205", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0220", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0230", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0240", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0260", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0405", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0540", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0542", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0545", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0550", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0560", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0698", _modelo_100_full_fixture_post_2025),
    (lambda: MODELO_100_2026, "0720", _modelo_100_full_fixture_post_2025),
)


def _build_sub_op_test_params() -> list:
    """Generate one pytest.param per (ruleset, casilla, sub_op_path).

    For each entry in :data:`_SUB_OP_COVERAGE_DATA` the casilla's
    formula tree is walked for every :class:`SubFormula` descendant
    and one parametrize entry is emitted per ``(ruleset, casilla,
    sub_op_path)`` triple. Path-suffixed test ids let a failing case
    point directly at the offending node. A ``(ruleset_id, casilla,
    path)`` entry in :data:`_SUB_OP_PATH_OVERRIDES` selects a
    targeted fixture for paths the default fixture cannot activate
    (e.g. M100 art. 20 piece_a vs piece_b — both pieces share a
    ``max_op`` so only one is observable per fixture).
    """
    params: list = []
    for ruleset_factory, casilla_id, fixture_factory in _SUB_OP_COVERAGE_DATA:
        ruleset = ruleset_factory()
        fd = ruleset.formula_for(casilla_id)
        assert fd is not None, f"ruleset {ruleset.ruleset_id} has no formula for casilla {casilla_id}"
        sub_op_paths = _walk_sub_op_paths(fd.formula)
        if not sub_op_paths:
            raise AssertionError(
                f"_SUB_OP_COVERAGE_DATA registers {ruleset.ruleset_id}:{casilla_id} "
                f"but its formula has no SubFormula descendants"
            )
        for path in sub_op_paths:
            override = _SUB_OP_PATH_OVERRIDES.get((ruleset.ruleset_id, casilla_id, path))
            effective_fixture = override if override is not None else fixture_factory
            path_id = "outer" if not path else "_".join(str(p) for p in path)
            params.append(
                pytest.param(
                    ruleset_factory,
                    casilla_id,
                    path,
                    effective_fixture,
                    id=f"{ruleset.ruleset_id}:casilla_{casilla_id}:path_{path_id}",
                )
            )
    return params


def _build_sub_op_coverage() -> tuple[tuple[str, str, tuple[int, ...]], ...]:
    """Derive :data:`SUB_OP_COVERAGE` from :data:`_SUB_OP_COVERAGE_DATA` + walker."""
    coverage: list[tuple[str, str, tuple[int, ...]]] = []
    seen: set[tuple[str, str, tuple[int, ...]]] = set()
    for ruleset_factory, casilla_id, _fixture_factory in _SUB_OP_COVERAGE_DATA:
        ruleset = ruleset_factory()
        fd = ruleset.formula_for(casilla_id)
        if fd is None:
            continue
        for path in _walk_sub_op_paths(fd.formula):
            key = (ruleset.ruleset_id, casilla_id, path)
            if key in seen:
                continue
            seen.add(key)
            coverage.append(key)
    return tuple(coverage)


SUB_OP_COVERAGE: tuple[tuple[str, str, tuple[int, ...]], ...] = _build_sub_op_coverage()


@pytest.mark.parametrize(
    ("ruleset_factory", "target_casilla", "sub_op_path", "fixture_factory"),
    _build_sub_op_test_params(),
)
def test_sub_op_operand_swap_at_path_is_detected(
    ruleset_factory: Callable[[], Ruleset],
    target_casilla: str,
    sub_op_path: tuple[int, ...],
    fixture_factory: Callable[[], dict[str, Decimal]],
) -> None:
    """Mutated ruleset MUST produce a discrepancy on the target casilla.

    Generalisation of the historic outer-only swap test: the path
    argument selects ANY :class:`SubFormula` descendant in the
    casilla's formula tree, so inner sub_ops are mutated alongside
    outer ones. Baseline-clean sentinel first; then the mutated
    ruleset MUST surface a discrepancy on ``target_casilla`` with
    ``|delta| >= 0.02 €``. A test failure points directly at the
    ``(ruleset, casilla, path)`` triple via the parametrize id.
    """
    ruleset = ruleset_factory()
    fixture = fixture_factory()
    engine = Engine()

    baseline = engine.audit_against(ruleset=ruleset, provided=fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean(), (
        f"baseline audit must be clean before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )

    mutated = _mutate_sub_op_at_path(ruleset, target_casilla, sub_op_path)
    report = engine.audit_against(ruleset=mutated, provided=fixture, tolerance=Decimal("0.01"))
    affected = {d.casilla_id for d in report.discrepancies}
    assert target_casilla in affected, (
        f"sub_op swap on {ruleset.ruleset_id} casilla {target_casilla} at path "
        f"{sub_op_path} was NOT detected — audit returned discrepancies on {affected}"
    )

    target_discrepancy = next(d for d in report.discrepancies if d.casilla_id == target_casilla)
    delta_abs = abs(target_discrepancy.delta)
    assert delta_abs >= Decimal("0.02"), (
        f"sub_op swap on {ruleset.ruleset_id} casilla {target_casilla} at path {sub_op_path} "
        f"produced delta={delta_abs} which is below the 0.02 detection floor — the fixture's "
        f"operand pair at that path is too close to symmetric (or a guard like clamp_pos pruned the change)."
    )


def test_mutate_outer_sub_op_descends_through_clamp_pos() -> None:
    """Issue #457: the helper descends through ``ClampPositiveFormula`` wrappers.

    M100 casilla 0545 (base liquidable general) wraps its outer
    ``sub_op`` chain in a ``clamp_pos``. Without the descent step
    introduced for #457, ``_mutate_outer_sub_op`` would raise
    ``TypeError`` on the wrapper. This test asserts the helper
    successfully swaps the underlying ``SubFormula`` and the audit
    surfaces the resulting discrepancy on casilla 0545.
    """
    fixture = _modelo_100_full_fixture_2024()
    engine = Engine()
    baseline = engine.audit_against(ruleset=MODELO_100_2024, provided=fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean(), (
        f"M100 fixture must audit cleanly before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )
    mutated = _mutate_outer_sub_op(MODELO_100_2024, "0545")
    report = engine.audit_against(ruleset=mutated, provided=fixture, tolerance=Decimal("0.01"))
    assert any(d.casilla_id == "0545" for d in report.discrepancies)


def test_mutate_outer_sub_op_rejects_nonsubop_inside_clamp_pos() -> None:
    """The descent stops at the first non-wrapper node; non-``SubFormula`` raises ``TypeError``.

    Modelo 130 casilla 04 is ``clamp_pos(percent(...))`` — descending
    through the clamp_pos reaches a ``PercentFormula``, not a
    ``SubFormula``. The helper must refuse rather than silently
    succeed.
    """
    with pytest.raises(TypeError):
        _mutate_outer_sub_op(MODELO_130_2025, "04")


def test_sub_op_path_overrides_point_at_real_subformula_nodes() -> None:
    """Issue #457 strict-audit defense: every override key resolves to a live ``SubFormula``.

    :data:`_SUB_OP_PATH_OVERRIDES` is keyed by hand-typed path tuples;
    a future M100 ruleset refactor that changes the AST shape would
    silently leave the overrides pointing at the wrong nodes (or
    nothing). This test re-walks each override key against the live
    ruleset and asserts the path still terminates at a
    :class:`SubFormula`. A drift fails loudly with the offending
    triple in the message.
    """
    rulesets_by_id: dict[str, Ruleset] = {
        MODELO_100_2024.ruleset_id: MODELO_100_2024,
        MODELO_100_2025.ruleset_id: MODELO_100_2025,
        MODELO_100_2026.ruleset_id: MODELO_100_2026,
    }
    for (ruleset_id, casilla_id, path), _fixture in _SUB_OP_PATH_OVERRIDES.items():
        ruleset = rulesets_by_id.get(ruleset_id)
        assert ruleset is not None, f"_SUB_OP_PATH_OVERRIDES references unknown ruleset {ruleset_id!r}"
        fd = ruleset.formula_for(casilla_id)
        assert fd is not None, (
            f"_SUB_OP_PATH_OVERRIDES[{ruleset_id, casilla_id, path}] points at "
            f"a casilla that does not exist on {ruleset_id}"
        )
        node = _node_at_path(fd.formula, path)
        assert isinstance(node, SubFormula), (
            f"_SUB_OP_PATH_OVERRIDES[{ruleset_id, casilla_id, path}] points at "
            f"{type(node).__name__}, not SubFormula — the M100 AST shape may have "
            f"changed; refresh the override paths from `iter_compound_descendants`."
        )


def test_mutate_sub_op_at_path_rejects_non_sub_formula_node() -> None:
    """Path-based helper raises ``TypeError`` if the path does not point at a ``SubFormula``.

    Modelo 130 casilla 04's body is ``RoundFormula(ClampPositiveFormula(PercentFormula(...)))`` —
    the top of the wrapper chain at path ``(0,)`` is a
    :class:`ClampPositiveFormula`, not a :class:`SubFormula`. The
    path-based helper must refuse rather than silently succeed.
    """
    with pytest.raises(TypeError):
        _mutate_sub_op_at_path(MODELO_130_2025, "04", (0,))


def test_mutate_sub_op_at_path_rejects_missing_casilla() -> None:
    """Path-based helper raises ``LookupError`` for an unknown casilla."""
    with pytest.raises(LookupError):
        _mutate_sub_op_at_path(MODELO_130_2025, "01", ())


def test_walk_sub_op_paths_yields_every_subformula_descendant() -> None:
    """Walker enumerates every :class:`SubFormula` descendant in operand-index order.

    Modelo 130 casilla 07 is ``RoundFormula(SubFormula(SubFormula(ref, ref), ref))``;
    the walker must yield two paths — the outer ``(0,)`` and the
    inner ``(0, 0)``.
    """
    fd = MODELO_130_2025.formula_for("07")
    assert fd is not None
    paths = _walk_sub_op_paths(fd.formula)
    assert paths == [(0,), (0, 0)]
