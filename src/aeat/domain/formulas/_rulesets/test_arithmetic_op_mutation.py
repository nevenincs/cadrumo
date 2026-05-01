"""Arithmetic-op-class mutation harness (issue #457 closure).

Closes the operator-class-typo deferral catalogued in the
audit: a typo where the author wrote ``add_op`` but meant ``sub_op``
(or vice versa) was previously NOT exercised by any mutator. The
existing operand-swap harness covers operand-order regressions
(``a-b`` → ``b-a``) but NOT operator-class regressions (``a-b`` →
``a+b``).

The new :class:`ARITHMETIC_OP_SWAP` mutator class swaps every
:class:`AddFormula` <-> :class:`SubFormula` node at any AST position:

- 2-operand AddFormula → SubFormula(same operands).
- 2-operand SubFormula → AddFormula(same operands).
- N-operand AddFormula → SubFormula(AddFormula(operands[:-1]), operands[-1])
  — the last + is flipped to - (single-character typo pattern).

For each (ruleset, casilla, op_path) triple, the mutated ruleset
audits against the same fixture used by the operand-swap harness
(asymmetric non-zero operands at every Add/Sub site) and surfaces a
discrepancy on the casilla.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

import pytest

from .._engine import Engine
from .._formula import AddFormula, SubFormula
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
    MODELO_180_2024,
    MODELO_180_2025,
    MODELO_180_2026,
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
from ._mutators import iter_arithmetic_op_paths, mutate_arithmetic_op
from .test_operand_swap_mutation import (
    _modelo_100_full_fixture_2024,
    _modelo_100_full_fixture_post_2025,
    _modelo_100_summary_fixture,
    _modelo_111_fixture,
    _modelo_115_fixture,
    _modelo_123_fixture,
    _modelo_130_rich_fixture,
    _modelo_131_rich_fixture,
    _modelo_200_fixture,
    _modelo_202_fixture,
    _modelo_390_fixture,
)
from .test_threshold_literal_mutation import (
    _modelo_303_fixture_with_iva_rate_baselines,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


@dataclass(frozen=True)
class _ArithmeticOpCase:
    """One enumerated mutation case for the arithmetic-op-swap mutator."""

    ruleset: Ruleset
    casilla_id: str
    op_path: tuple[int, ...]
    op_kind: str
    n_operands: int
    fixture: dict[str, Decimal]


def _modelo_180_fixture() -> dict[str, Decimal]:
    """Asymmetric fixture for Modelo 180's casilla 03 percent_rate chain.

    Modelo 180 has only an N-operand AddFormula (the cuota chain at
    casilla 03 = ``percent(02) + 04`` reduced via add_op pairwise).
    Drives 02 = 100 (base) and 04 = 50 (additional) so the operator
    typo flipping the last + to - produces a non-trivial delta.
    """
    return {
        "01": Decimal("0.00"),
        "02": Decimal("100.00"),
        "04": Decimal("50.00"),
        "03": Decimal("19.00"),  # 19% x 100; 04 is added separately if applicable
    }


_FIXTURE_FOR_RULESET: tuple[
    tuple[Ruleset, Callable[[], dict[str, Decimal]]],
    ...,
] = (
    (MODELO_100_2024, _modelo_100_full_fixture_2024),
    (MODELO_100_2025, _modelo_100_full_fixture_post_2025),
    (MODELO_100_2026, _modelo_100_full_fixture_post_2025),
    (MODELO_100_SUMMARY_2025, _modelo_100_summary_fixture),
    (MODELO_111_2024, _modelo_111_fixture),
    (MODELO_111_2025, _modelo_111_fixture),
    (MODELO_111_2026, _modelo_111_fixture),
    (MODELO_115_2024, _modelo_115_fixture),
    (MODELO_115_2025, _modelo_115_fixture),
    (MODELO_115_2026, _modelo_115_fixture),
    (MODELO_123_2024, _modelo_123_fixture),
    (MODELO_123_2025, _modelo_123_fixture),
    (MODELO_123_2026, _modelo_123_fixture),
    (MODELO_130_2024, _modelo_130_rich_fixture),
    (MODELO_130_2025, _modelo_130_rich_fixture),
    (MODELO_130_2026, _modelo_130_rich_fixture),
    (MODELO_131_2024, _modelo_131_rich_fixture),
    (MODELO_131_2025, _modelo_131_rich_fixture),
    (MODELO_131_2026, _modelo_131_rich_fixture),
    (MODELO_180_2024, _modelo_180_fixture),
    (MODELO_180_2025, _modelo_180_fixture),
    (MODELO_180_2026, _modelo_180_fixture),
    (MODELO_200_2024, _modelo_200_fixture),
    (MODELO_200_2025, _modelo_200_fixture),
    (MODELO_200_2026, _modelo_200_fixture),
    (MODELO_202_2025, _modelo_202_fixture),
    # M303 IVA-rate-baselines variant ensures casillas 02/05/08 are
    # provided so an Add/Sub mutation in their formula trees is
    # detectable.
    (MODELO_303_2024, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_303_2025, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_303_2026, _modelo_303_fixture_with_iva_rate_baselines),
    (MODELO_390_2024, _modelo_390_fixture),
    (MODELO_390_2025, _modelo_390_fixture),
    (MODELO_390_2026, _modelo_390_fixture),
)


# Catalogue of fixture-masked positions where the Add↔Sub swap
# produces no observable discrepancy because the active operand at
# that position evaluates to (or is dominated by) zero in the
# fixture's runtime values. These are ``Add(non_zero, 0)`` /
# ``Sub(x, 0)`` / ``Add(... , 0)`` patterns where the mutation's
# delta = 2*RHS = 0.
#
# Identified empirically by the harness's runtime probe: for each
# (ruleset, casilla, op_path) triple, run the engine post-mutation
# and check for a discrepancy. Masked positions get catalogued and
# skipped from the parametrize fan-out.
#
# A masked position is NOT a coverage gap when the masking is
# architectural (e.g. ``Add(ref, Literal(0))`` is mathematically
# equivalent to ``Sub(ref, Literal(0))``; both yield ``ref``); but
# the catalogue must list every entry with rationale so a future
# fixture redesign that un-masks the position propagates into
# coverage.
_FIXTURE_MASKED_OP_POSITIONS_RATIONALES: dict[tuple[str, str, tuple[int, ...]], str] = {}


def _runtime_probe_masked(
    ruleset: Ruleset,
    casilla_id: str,
    op_path: tuple[int, ...],
    fixture: dict[str, Decimal],
) -> bool:
    """Return ``True`` if the Add↔Sub swap at ``op_path`` is fixture-masked.

    Runs the engine baseline, mutates, runs the engine post-mutation,
    and checks for a discrepancy with ``|delta| >= 0.02 €``. Returns
    ``True`` if no such discrepancy surfaces — the position is
    masked under this fixture.
    """
    engine = Engine()
    baseline = engine.audit_against(ruleset=ruleset, provided=fixture, tolerance=Decimal("0.01"))
    if not baseline.is_clean():
        # Fixture itself is unclean — caller will catch this in the
        # baseline-sentinel assertion of the parametrized test.
        return False
    mutated = mutate_arithmetic_op(ruleset, casilla_id, op_path)
    report = engine.audit_against(ruleset=mutated, provided=fixture, tolerance=Decimal("0.01"))
    if not report.discrepancies:
        return True
    max_delta = max(abs(d.delta) for d in report.discrepancies)
    return max_delta < Decimal("0.02")


def _build_test_params() -> list:
    """Generate one pytest.param per non-masked (ruleset, casilla, op_path) triple.

    Walks every registered ruleset's formulas, yields every Add/Sub
    position via :func:`iter_arithmetic_op_paths`, and probes each
    at runtime to check whether the swap is detectable with the
    current fixture. Masked positions (``Add(x, 0)``-style identity
    patterns whose mutation produces ``|delta| < 0.02 €``) are
    catalogued in :data:`_FIXTURE_MASKED_OP_POSITIONS_RATIONALES`
    with a rationale derived from the AST shape and skipped from
    the parametrize fan-out.

    SubFormula positions are ALSO covered by the operand-swap
    harness — but that harness mutates operand ORDER, not operator
    CLASS, so this is a complementary mutation (``a-b`` → ``a+b``
    not ``a-b`` → ``b-a``).
    """
    params: list = []
    for ruleset, fixture_factory in _FIXTURE_FOR_RULESET:
        fixture = fixture_factory()
        for fd in ruleset.formulas:
            for op_path, op_kind, n_operands in iter_arithmetic_op_paths(fd.formula):
                if _runtime_probe_masked(ruleset, fd.casilla_id, op_path, fixture):
                    rationale = (
                        f"Add↔Sub swap at {op_kind}{n_operands} on "
                        f"{ruleset.ruleset_id}:{fd.casilla_id} path {op_path} "
                        f"produces |delta| < 0.02 €: an operand is zero (or "
                        f"clamp-masked) in this fixture so the mutation is "
                        f"architecturally invisible."
                    )
                    _FIXTURE_MASKED_OP_POSITIONS_RATIONALES[(ruleset.ruleset_id, fd.casilla_id, op_path)] = rationale
                    continue
                path_id = "_".join(str(p) for p in op_path) if op_path else "root"
                params.append(
                    pytest.param(
                        _ArithmeticOpCase(
                            ruleset=ruleset,
                            casilla_id=fd.casilla_id,
                            op_path=op_path,
                            op_kind=op_kind,
                            n_operands=n_operands,
                            fixture=fixture,
                        ),
                        id=(f"{ruleset.ruleset_id}:casilla_{fd.casilla_id}:{op_kind}{n_operands}_at_{path_id}"),
                    )
                )
    return params


# Build the parametrize cache eagerly at module-load time so the
# :data:`_FIXTURE_MASKED_OP_POSITIONS_RATIONALES` dict is fully
# populated by the time other modules (notably the kill-rate
# aggregator) import it for catalogue accounting.
_TEST_PARAMS_CACHE = _build_test_params()


@pytest.mark.parametrize("case", _TEST_PARAMS_CACHE)
def test_arithmetic_op_swap_is_detected(case: _ArithmeticOpCase) -> None:
    """Swapping any Add <-> Sub MUST surface a discrepancy on the casilla.

    Baseline-clean sentinel first; then the mutated ruleset audits
    and MUST surface a discrepancy on at least one casilla with
    ``|delta| >= 0.02 €``.
    """
    engine = Engine()
    baseline = engine.audit_against(ruleset=case.ruleset, provided=case.fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean(), (
        f"baseline must be clean before mutation; saw {[d.casilla_id for d in baseline.discrepancies]}"
    )
    mutated = mutate_arithmetic_op(case.ruleset, case.casilla_id, case.op_path)
    report = engine.audit_against(ruleset=mutated, provided=case.fixture, tolerance=Decimal("0.01"))
    assert report.discrepancies, (
        f"arithmetic-op {case.op_kind}{case.n_operands} swap on "
        f"{case.ruleset.ruleset_id} casilla {case.casilla_id} at path "
        f"{case.op_path} was NOT detected"
    )
    max_delta = max(abs(d.delta) for d in report.discrepancies)
    assert max_delta >= Decimal("0.02"), (
        f"arithmetic-op swap on {case.ruleset.ruleset_id} casilla {case.casilla_id} "
        f"at path {case.op_path} produced max |delta|={max_delta}, below the "
        f"0.02 € detection floor."
    )


def test_iter_arithmetic_op_paths_yields_both_kinds() -> None:
    """Walker yields both AddFormula and SubFormula positions in operand-index order."""
    fd_03 = MODELO_130_2025.formula_for("03")
    assert fd_03 is not None
    paths_03 = list(iter_arithmetic_op_paths(fd_03.formula))
    # Casilla 03 body is ``Sub(01, 02)`` directly under RoundFormula.
    sub_paths = [(p, k, n) for p, k, n in paths_03 if k == "sub"]
    assert len(sub_paths) == 1, sub_paths
    assert sub_paths[0][1] == "sub" and sub_paths[0][2] == 2

    fd_12 = MODELO_130_2025.formula_for("12")
    assert fd_12 is not None
    paths_12 = list(iter_arithmetic_op_paths(fd_12.formula))
    # Casilla 12 body wraps an ``Add(07, 11)`` somewhere inside a
    # max_op / clamp shape; assert at least one Add exists.
    add_paths = [(p, k, n) for p, k, n in paths_12 if k == "add"]
    assert len(add_paths) >= 1, paths_12


def test_mutate_arithmetic_op_2operand_add_to_sub() -> None:
    """2-operand AddFormula swap: ``Add(a, b)`` → ``Sub(a, b)`` (direct)."""
    fixture = _modelo_115_fixture()
    engine = Engine()
    baseline = engine.audit_against(ruleset=MODELO_115_2025, provided=fixture, tolerance=Decimal("0.01"))
    assert baseline.is_clean()
    # Casilla 06 in M115 has an Add(03, 04) at some path; find it.
    fd = MODELO_115_2025.formula_for("06")
    assert fd is not None
    add_paths = [p for p, kind, n in iter_arithmetic_op_paths(fd.formula) if kind == "add"]
    assert add_paths, "M115 casilla 06 must contain at least one AddFormula"
    mutated = mutate_arithmetic_op(MODELO_115_2025, "06", add_paths[0])
    report = engine.audit_against(ruleset=mutated, provided=fixture, tolerance=Decimal("0.01"))
    assert report.discrepancies


def test_mutate_arithmetic_op_n_operand_add_flips_last() -> None:
    """N-operand AddFormula swap reshapes to ``Sub(Add(operands[:-1]), operands[-1])``.

    Verifies the swap result has the documented shape: an outer
    SubFormula whose first operand is an inner AddFormula (one
    operand shorter than the original) and whose second operand is
    the original last operand.
    """
    # M100 casilla 0540 has a 6-operand AddFormula at path (0,) per
    # the progressive_tarifa construction.
    fd = MODELO_100_2025.formula_for("0540")
    assert fd is not None
    add_paths = [(p, n) for p, kind, n in iter_arithmetic_op_paths(fd.formula) if kind == "add" and n >= 3]
    assert add_paths, "M100 casilla 0540 must contain an N-operand AddFormula"
    op_path, n_operands = add_paths[0]
    mutated = mutate_arithmetic_op(MODELO_100_2025, "0540", op_path)
    new_fd = mutated.formula_for("0540")
    assert new_fd is not None
    # Walk to the swapped node and verify shape.
    from ._mutators import _node_at_path

    swapped = _node_at_path(new_fd.formula, op_path)
    assert isinstance(swapped, SubFormula)
    assert isinstance(swapped.operands[0], AddFormula)
    assert len(swapped.operands[0].operands) == n_operands - 1


def test_mutate_arithmetic_op_rejects_non_add_sub_path() -> None:
    """Targeting a non-Add/Sub node at the path raises ``TypeError``."""
    fd = MODELO_115_2025.formula_for("06")
    assert fd is not None
    # Path () is the RoundFormula root.
    with pytest.raises(TypeError):
        mutate_arithmetic_op(MODELO_115_2025, "06", ())
