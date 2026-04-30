"""Tautology-regression defense for the mutation-harness aggregator (#457).

This module is the structural defense against the failure mode that
issue #457 fixed. The prior aggregator (`test_mutator_kill_rate.py`)
contained a `killed = populated` line that made the kill-rate floor
**vacuous** for any node counted in :data:`EXPECTED_COUNTS` but not
enumerated by a per-class harness. The PR #448 M100 megaproject
exposed the gap (60 mul/div scalar leaves and 213 ``sub_op`` nodes
were silently absent from the per-class harness).

The defense lives in two layers:

- :func:`test_aggregator_catches_uncovered_populated_node` — synthetic
  scenario where ``EXPECTED_COUNTS`` declares a populated count that
  exceeds the empirical coverage AND under-declares the ``_deferred``
  column. Asserts the new
  :func:`test_deferred_count_matches_empirical_coverage_gap`
  invariant raises.

- :func:`test_old_killed_equals_populated_pattern_is_unreachable` —
  spelling guard that fails if the prior tautology source line
  reappears in the aggregator module.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from . import test_mutator_kill_rate as kill_rate_module

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def test_aggregator_catches_uncovered_populated_node(monkeypatch: pytest.MonkeyPatch) -> None:
    """A populated bump without matching deferred bump must fail the gap invariant.

    Patches :data:`EXPECTED_COUNTS` to include a synthetic ruleset
    with a non-zero ``mul_div_scalar`` populated count and a
    ``mul_div_scalar_deferred`` count of 0 — i.e. claiming full
    coverage for a node the empirical coverage map does not reach.
    The new
    :func:`test_deferred_count_matches_empirical_coverage_gap`
    invariant must raise ``AssertionError`` with the descriptive
    "extend the per-class harness or update the deferred catalogue"
    message.
    """
    fake_counts = dict(kill_rate_module.EXPECTED_COUNTS)
    fake_counts["synthetic.tautology.regression"] = {
        "sub_op": 0,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        # 1 populated node, but the empirical coverage map (which
        # cannot include this synthetic ruleset_id) reports 0
        # covered. Declared deferred is 0 — i.e. claiming the node
        # is covered. The invariant must fail.
        "mul_div_scalar": 1,
        "mul_div_scalar_deferred": 0,
    }
    monkeypatch.setattr(kill_rate_module, "EXPECTED_COUNTS", fake_counts)

    with pytest.raises(AssertionError) as exc_info:
        kill_rate_module.test_deferred_count_matches_empirical_coverage_gap()
    message = str(exc_info.value)
    assert "synthetic.tautology.regression" in message
    assert "mul_div_scalar" in message
    assert "extend the per-class harness" in message or "update the deferred catalogue" in message, (
        f"expected the descriptive remediation hint in the failure; got: {message!r}"
    )


def test_aggregator_catches_inflated_deferred_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """A deferred over-claim (``deferred > populated - empirical``) must also fail.

    Symmetric to the under-claim case — the invariant is an equality,
    not just a lower-bound. A future PR that lowers per-class
    coverage but doesn't bump the deferred count must fail; so must a
    PR that bumps deferred without a corresponding empirical
    decrease.
    """
    fake_counts = dict(kill_rate_module.EXPECTED_COUNTS)
    fake_counts["synthetic.tautology.regression"] = {
        "sub_op": 0,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "mul_div_scalar": 0,
        # populated == 0 but deferred == 1 → gap is -1, mismatched.
        "mul_div_scalar_deferred": 1,
    }
    monkeypatch.setattr(kill_rate_module, "EXPECTED_COUNTS", fake_counts)
    with pytest.raises(AssertionError):
        kill_rate_module.test_deferred_count_matches_empirical_coverage_gap()


def test_aggregator_passes_when_deferred_matches_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity check: a row with matched populated / empirical / deferred passes.

    This is the positive case — the synthetic ruleset declares
    ``mul_div_scalar=1`` and ``mul_div_scalar_deferred=1`` (the one
    node is deferred). The invariant must pass under that
    declaration.
    """
    fake_counts = dict(kill_rate_module.EXPECTED_COUNTS)
    fake_counts["synthetic.tautology.regression"] = {
        "sub_op": 0,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "mul_div_scalar": 1,
        "mul_div_scalar_deferred": 1,
    }
    monkeypatch.setattr(kill_rate_module, "EXPECTED_COUNTS", fake_counts)
    # Should not raise.
    kill_rate_module.test_deferred_count_matches_empirical_coverage_gap()


def test_old_killed_equals_populated_pattern_is_unreachable() -> None:
    """AST guard: the prior tautology assignment must not reappear in source.

    Parses :mod:`test_mutator_kill_rate` and walks every
    :class:`ast.Assign` node looking for a single-target assignment of
    the literal name ``populated`` to the literal name ``killed``.
    The aggregator now derives ``killed`` empirically from the
    per-class harness coverage generators; reintroducing the literal
    assignment would re-enable the failure mode that issue #457
    fixed. AST-based detection ignores docstrings and comments so the
    guard only fires on actual code.
    """
    source_path = Path(kill_rate_module.__file__)
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    offending: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not (isinstance(target, ast.Name) and target.id == "killed"):
            continue
        value = node.value
        if isinstance(value, ast.Name) and value.id == "populated":
            offending.append(node.lineno)
    assert not offending, (
        f"{source_path} contains the issue-#457 tautology assignment "
        f"`killed = populated` at line(s) {offending}. The aggregator "
        f"must derive ``killed`` empirically from the per-class harness "
        f"coverage generators."
    )
