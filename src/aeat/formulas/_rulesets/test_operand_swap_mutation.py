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
from . import MODELO_130_2025, MODELO_131_2025, MODELO_202_2025, MODELO_303_2025

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
# Each fixture carries ``a > b > 0`` at the targeted sub_op, so swapping
# ``sub_op(a, b)`` to ``sub_op(b, a)`` produces a sign-flipped value
# that CANNOT match the original fixture within any reasonable tolerance.


def _modelo_130_rirpf_fixture() -> dict[str, Decimal]:
    """Same scenario as ``test_modelo_130_2025::test_external_worked_example_rirpf_art_110``.

    Target: casilla 03 = sub_op(01, 02). ``01=48000``, ``02=12500``;
    correct 03 = 35500, swapped 03 = -35500.
    """
    return {
        "01": Decimal("48000.00"),
        "02": Decimal("12500.00"),
        "03": Decimal("35500.00"),
        "04": Decimal("7100.00"),
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "07": Decimal("7100.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "10": Decimal("0.00"),
        "11": Decimal("0.00"),
        "12": Decimal("7100.00"),
        "13": Decimal("0.00"),
        "14": Decimal("7100.00"),
        "15": Decimal("2500.00"),
        "16": Decimal("450.00"),
        "17": Decimal("4150.00"),
        "18": Decimal("0.00"),
        "19": Decimal("4150.00"),
    }


def _modelo_131_fixture() -> dict[str, Decimal]:
    """Asymmetric autónomo módulos fixture for Modelo 131.

    Target: casilla 15 = sub_op(13, 14) (resultado_a_ingresar).
    13 = 3 000,00; 14 = 800,00; correct 15 = 2 200,00; swapped 15 = -2 200,00.
    """
    return {
        "01": Decimal("0.00"),
        "02": Decimal("2000.00"),
        "03": Decimal("50000.00"),
        "04": Decimal("1000.00"),
        "05": Decimal("0.00"),
        "06": Decimal("0.00"),
        "07": Decimal("3000.00"),
        "08": Decimal("0.00"),
        "09": Decimal("0.00"),
        "10": Decimal("3000.00"),
        "11": Decimal("0.00"),
        "12": Decimal("0.00"),
        "13": Decimal("3000.00"),
        "14": Decimal("800.00"),
        "15": Decimal("2200.00"),
    }


def _modelo_202_fixture() -> dict[str, Decimal]:
    """Same scenario as ``test_modelo_202_2025::test_external_worked_example_lis_art_40_3_modalidad``.

    Target: casilla 32 = sub_op(sub_op(sub_op(18, 27), 28), 30).
    The outer sub_op swap is ``sub_op(30, sub_op(...))`` - a sign flip of
    the innermost chain. With the fixture values, the correct 32 is
    34000 - 12000 - 0 - 0 = 22000; a swap of the outermost sub_op
    yields 0 - (34000 - 12000 - 0) = -22000.
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


@pytest.mark.parametrize(
    ("ruleset_factory", "target_casilla", "fixture_factory"),
    [
        pytest.param(
            lambda: MODELO_130_2025,
            "03",
            _modelo_130_rirpf_fixture,
            id="modelo_130.2025:casilla_03_rendimiento_neto",
        ),
        pytest.param(
            lambda: MODELO_131_2025,
            "15",
            _modelo_131_fixture,
            id="modelo_131.2025:casilla_15_resultado_a_ingresar",
        ),
        pytest.param(
            lambda: MODELO_303_2025,
            "69",
            _modelo_303_fixture,
            id="modelo_303.2025:casilla_69_resultado",
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
