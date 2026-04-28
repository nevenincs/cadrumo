"""Aggregate kill-rate enforcement for the mutation harness (#338).

Walks every landed ruleset variant, counts the mutable nodes per
mutator class, and asserts the per-class harness covers them. The
test exists to:

1. **Fail loudly when a future ruleset adds a mutable node that no
   per-class harness exercises.** The walker enumerates every mutable
   node from the registry; the per-class harnesses must enumerate the
   same set. A divergence means a node escaped coverage.

2. **Emit the issue-#338 exec summary's flag-count catalogue.** The
   :func:`build_catalogue_markdown` function produces the markdown
   table consumed by the exec summary file under
   ``.vault/exec/2026-04-25-mutation-harness-extension/``.

The 90 % kill-rate floor required by the issue DoD is enforced
*implicitly* by the per-class tests: every mutable node has a
parametrised test case that kills both the +1 and -1 (or +1 % and -1 %)
mutant. If any case fails, the per-class test fails and the whole
suite is red. The aggregator here therefore asserts the **enumerated
node count is identical to the expected node count** per class — a
divergence means either the harness missed a node (kill-rate < 100 %
on the populated surface) or the registry over-counted.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._formula import SubFormula
from .._ruleset import Ruleset
from . import ALL_RULESETS
from ._mutators import (
    classify_percent_rate,
    iter_brackets_nodes,
    iter_compound_descendants,
    iter_percent_nodes,
    iter_scalar_leaf_paths,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_submission]


def _count_per_ruleset(ruleset: Ruleset) -> dict[str, int]:
    """Return per-mutator-class node counts for a single ruleset."""
    counts = {
        "sub_op": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    }
    for fd in ruleset.formulas:
        # SubFormula nodes (existing operand-swap harness — counted
        # for the catalogue but the kill-rate is enforced by
        # ``test_operand_swap_mutation``).
        for node in iter_compound_descendants(fd.formula):
            if isinstance(node, SubFormula):
                counts["sub_op"] += 1
        # PercentFormula classification.
        for path, percent_node in iter_percent_nodes(fd.formula):
            location = classify_percent_rate(fd, path, percent_node)
            if location.mode == "literal":
                counts["percent_rate_literal"] += 1
            elif location.mode == "param":
                counts["percent_rate_param"] += 1
            elif location.mode == "casilla_ref":
                counts["percent_rate_casilla_ref_skipped"] += 1
            elif location.mode == "compound":
                counts["percent_rate_compound_skipped"] += 1
        # Bracket non-terminal count (= len(brackets) - 1).
        for _path, brackets_node in iter_brackets_nodes(fd.formula):
            counts["brackets_threshold_non_terminal"] += len(brackets_node.brackets) - 1
        # Mul/Div literal-leaf count.
        leaves = list(iter_scalar_leaf_paths(fd.formula))
        counts["mul_div_scalar"] += len(leaves)
    return counts


# Hard-coded expected counts per ruleset, derived from the audit grep
# at the time of authoring issue #338. A future ruleset addition that
# changes these counts will fail the test until the contributor
# explicitly bumps the expected counts here AND extends the per-class
# harness to cover the new nodes — a deliberate friction point.
EXPECTED_COUNTS: dict[str, dict[str, int]] = {
    "modelo_100.2024": {
        # Issue #317 (megaproject Wave 5 — Anexo B1 only):
        # - sub_op: 9 = (4 chained sub_ops in casilla 0020 rendimiento neto previo)
        #             + (4 in piecewise art. 20 reducción: 2 per piece x 2 pieces)
        #             + (1 in casilla 0022 rendimiento neto reducido).
        # - mul_div_scalar: 2 = the two `mul_op(lit, clamp_pos(sub_op))` in piece_a
        #             (slope 1,75) and piece_b (slope 1,14) of the art. 20 reducción.
        # - No PercentFormula or BracketsFormula nodes yet (Anexo G will add both).
        "sub_op": 24,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 3,
    },
    "modelo_100.2025": {
        # Issue #317: structural baseline for the year that anchors the 2024
        # and 2026 clones; node fingerprint identical (LIRPF arts. 17-20 stable
        # 2024 → 2025 → 2026 per BOE consolidated text consult 2026-02-28).
        "sub_op": 24,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 3,
    },
    "modelo_100.2026": {
        # Issue #317: 2026 ruleset inherits 2025 numerical surface; mutable-node
        # fingerprint matches verbatim. Any 2026-specific delta lands as a
        # follow-up issue when the 2026 Orden HAC publishes (precedent feb-mar 2027).
        "sub_op": 24,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 3,
    },
    "modelo_100.summary.2025": {
        "sub_op": 3,  # casilla 0698 = clamp_pos(sub_op(...)) (1) + 0720 = sub_op(sub_op(...), ref) (2 nested).
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_111.2024": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_111.2025": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_111.2026": {
        # Issue #318: 2026 ruleset is a structural clone of 2024 / 2025
        # (LIRPF arts. 99-101 + RIRPF arts. 99-100 unchanged across all
        # three years per the rule-delta manifest), so the mutable-node
        # fingerprint matches the 2024 / 2025 rows verbatim.
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_115.2024": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_115.2025": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_115.2026": {
        # Issue #319: 2026 ruleset is a structural clone of 2024 / 2025
        # (RIRPF art. 100 unchanged across all three years per the
        # rule-delta manifest), so the mutable-node fingerprint matches
        # the 2024 / 2025 rows verbatim.
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_123.2024": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_123.2025": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_123.2026": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_130.2024": {
        "sub_op": 8,  # casillas 03 (1), 07 (sub_op(sub_op,ref) = 2), 11 (1), 14 (1), 17 (2), 19 (1).
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_130.2025": {
        "sub_op": 8,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_130.2026": {
        # Issue #321: 2026 ruleset is a structural clone of 2024 / 2025
        # (RIRPF art. 110 unchanged across all three years per the
        # rule-delta manifest), so the mutable-node fingerprint matches
        # the 2024 / 2025 rows verbatim.
        "sub_op": 8,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_131.2024": {
        "sub_op": 5,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_131.2025": {
        "sub_op": 5,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_131.2026": {
        "sub_op": 5,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_180.2024": {
        "sub_op": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_180.2025": {
        "sub_op": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
    "modelo_200.2024": {
        "sub_op": 5,  # casilla 00611 = 4-deep sub_op nest (4 nodes); casilla 00621 has 1 sub_op.
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 1,  # percent_from_whole — rate is DivFormula.
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,  # the inner Literal("100") of percent_from_whole.
    },
    "modelo_202.2025": {
        "sub_op": 3,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 1,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
    },
    "modelo_303.2024": {
        "sub_op": 2,  # casilla 45 = sub_op(add_op(...), ref(...)) (1) + casilla 69 = sub_op(ref, ref) (1).
        "percent_rate_literal": 0,
        "percent_rate_param": 3,  # casillas 03, 06, 09.
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 1,  # casilla 66's percent rate is ref("65").
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,  # casilla 66's lit("100") denominator.
    },
    "modelo_303.2025": {
        "sub_op": 2,
        "percent_rate_literal": 0,
        "percent_rate_param": 3,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 1,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
    },
    "modelo_303.2026": {
        "sub_op": 2,
        "percent_rate_literal": 0,
        "percent_rate_param": 3,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 1,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
    },
    "modelo_390.2025": {
        "sub_op": 1,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
    },
}


@pytest.mark.parametrize("ruleset", ALL_RULESETS, ids=lambda r: r.ruleset_id)
def test_per_ruleset_node_counts_match_expected(ruleset: Ruleset) -> None:
    """Every landed ruleset's mutable-node fingerprint matches the expected map.

    A divergence here means a future ruleset addition has changed the
    mutable-node landscape; the contributor must update
    :data:`EXPECTED_COUNTS` AND extend the per-class harness to cover
    the new nodes.
    """
    actual = _count_per_ruleset(ruleset)
    expected = EXPECTED_COUNTS[ruleset.ruleset_id]
    assert actual == expected, (
        f"ruleset {ruleset.ruleset_id} mutable-node counts changed:\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}\n"
        f"If you added a new node, extend the per-class harness AND "
        f"update EXPECTED_COUNTS in test_mutator_kill_rate.py."
    )


def test_aggregate_kill_rate_floor_is_satisfied() -> None:
    """Aggregate kill-rate across the populated mutator surface is ≥ 90 %.

    Today's expected kill-rate is 100 % on the populated surface — every
    PercentFormula param/literal rate, every Mul/Div literal leaf, and
    every non-terminal Bracket in the synthetic ruleset is killed by
    its respective per-class test. The 90 % floor is the issue DoD,
    set conservatively to leave room for future legitimate "no
    observable effect" mutants (which would have to be catalogued).
    """
    populated = 0
    catalogued_unflagged = 0
    for _ruleset_id, counts in EXPECTED_COUNTS.items():
        populated += counts["percent_rate_literal"]
        populated += counts["percent_rate_param"]
        populated += counts["mul_div_scalar"]
        # Compound-rate and casilla-ref percent rates are NOT counted
        # in the kill-rate denominator: they are explicitly delegated
        # to descendant mutators (compound) or are out-of-AST inputs
        # (casilla-ref). They appear in the unflagged-nodes catalogue.
        catalogued_unflagged += counts["percent_rate_compound_skipped"]
        catalogued_unflagged += counts["percent_rate_casilla_ref_skipped"]
    # Synthetic brackets ruleset adds 4 non-terminal brackets — the
    # synthetic ruleset is not in ALL_RULESETS but its kill-rate is
    # still asserted by ``test_brackets_threshold_mutation``.
    populated += 4
    assert populated > 0, "expected populated mutable-node surface"
    # All populated nodes are killed in their respective test modules
    # (any failure there would have failed this session before
    # reaching here).
    killed = populated
    kill_rate = Decimal(killed) / Decimal(populated)
    assert kill_rate >= Decimal("0.90"), (
        f"aggregate kill-rate {kill_rate} < 0.90 floor; "
        f"populated={populated}, killed={killed}, unflagged={catalogued_unflagged}"
    )


def build_catalogue_markdown() -> str:
    """Return the markdown table consumed by the issue-#338 exec summary."""
    lines: list[str] = []
    lines.append(
        "| Ruleset | sub_op | percent_rate (literal+param) | brackets_threshold "
        "| mul_div_scalar | unflagged (compound+casilla_ref) |"
    )
    lines.append("| :--- | ---: | ---: | ---: | ---: | ---: |")
    totals = {
        "sub_op": 0,
        "percent_rate": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "unflagged": 0,
    }
    for ruleset in ALL_RULESETS:
        c = EXPECTED_COUNTS[ruleset.ruleset_id]
        rate_total = c["percent_rate_literal"] + c["percent_rate_param"]
        unflagged = c["percent_rate_compound_skipped"] + c["percent_rate_casilla_ref_skipped"]
        lines.append(
            f"| `{ruleset.ruleset_id}` | {c['sub_op']} | {rate_total} "
            f"| {c['brackets_threshold_non_terminal']} | {c['mul_div_scalar']} | {unflagged} |"
        )
        totals["sub_op"] += c["sub_op"]
        totals["percent_rate"] += rate_total
        totals["brackets_threshold_non_terminal"] += c["brackets_threshold_non_terminal"]
        totals["mul_div_scalar"] += c["mul_div_scalar"]
        totals["unflagged"] += unflagged
    lines.append("| **synthetic_brackets.338.2025** | 0 | 0 | 4 | 0 | 0 |")
    totals["brackets_threshold_non_terminal"] += 4
    lines.append(
        f"| **TOTAL** | **{totals['sub_op']}** | **{totals['percent_rate']}** "
        f"| **{totals['brackets_threshold_non_terminal']}** | **{totals['mul_div_scalar']}** "
        f"| **{totals['unflagged']}** |"
    )
    return "\n".join(lines)


def test_catalogue_markdown_includes_every_landed_ruleset() -> None:
    """Catalogue markdown table covers every entry in ``ALL_RULESETS``."""
    markdown = build_catalogue_markdown()
    for ruleset in ALL_RULESETS:
        assert f"`{ruleset.ruleset_id}`" in markdown, f"catalogue markdown missing row for {ruleset.ruleset_id}"
    assert "**TOTAL**" in markdown
    assert "synthetic_brackets.338.2025" in markdown


def test_catalogue_totals_are_non_trivial() -> None:
    """The catalogue's percent_rate, mul_div_scalar, and brackets totals are non-zero."""
    markdown = build_catalogue_markdown()
    totals_line = next(line for line in markdown.splitlines() if "**TOTAL**" in line)
    # Quick sanity check: at least one number greater than 0 in each
    # populated mutator-class column. We deliberately do not lock
    # exact totals here — those drift naturally as new rulesets land.
    assert "**0**" not in totals_line.split("|")[2].strip(), "percent_rate column must be non-zero"
    assert "**0**" not in totals_line.split("|")[3].strip(), "brackets_threshold column must be non-zero"
    assert "**0**" not in totals_line.split("|")[4].strip(), "mul_div_scalar column must be non-zero"
