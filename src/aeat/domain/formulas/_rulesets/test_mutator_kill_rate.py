"""Aggregate kill-rate enforcement for the mutation harness (#338, #457).

Walks every landed ruleset variant, counts the mutable nodes per
mutator class, and asserts the per-class harness covers them. The
test exists to:

1. **Fail loudly when a future ruleset adds a mutable node that no
   per-class harness exercises.** The walker enumerates every mutable
   node from the registry; the per-class harnesses must enumerate the
   same set. A divergence means a node escaped coverage.

2. **Compute the kill-rate floor empirically.** Issue #457 surfaced
   a structural tautology in the prior ``killed = populated`` line:
   nodes that lived in :data:`EXPECTED_COUNTS` but were not
   enumerated by any per-class harness sailed past every assertion.
   The aggregator now imports the per-class harness coverage
   generators (``_iter_scalar_targets``, ``_iter_percent_targets``)
   and counts unique mutated targets. The 90 % kill-rate floor is
   computed against the **claimed-covered surface** — populated minus
   the deliberately-deferred subset — so a future ruleset PR that
   bumps populated counts without extending the per-class harness
   AND without bumping the matching ``_deferred`` column fails
   loudly. See [[2026-04-29-mutation-harness-fix-adr]].

3. **Emit the catalogue markdown table.** :func:`build_catalogue_markdown`
   produces the markdown table consumed by the exec summary, now
   surfacing the deferred columns explicitly so readers see the
   coverage gap rather than seeing inflated 100 % numbers.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from .._formula import SubFormula
from .._ruleset import Ruleset
from . import ALL_RULESETS
from ._mutators import (
    classify_percent_rate,
    is_additive_identity_literal,
    iter_arithmetic_op_paths,
    iter_brackets_nodes,
    iter_casilla_ref_paths,
    iter_compound_descendants,
    iter_percent_nodes,
    iter_scalar_leaf_paths,
    iter_threshold_literal_paths,
)
from .test_arithmetic_op_mutation import (
    _TEST_PARAMS_CACHE as _ARITHMETIC_OP_TEST_PARAMS,
)
from .test_casilla_ref_topology_mutation import (
    _TEST_PARAMS_CACHE as _CASILLA_REF_TEST_PARAMS,
)
from .test_operand_swap_mutation import SUB_OP_COVERAGE
from .test_percent_rate_mutation import _iter_percent_targets
from .test_scalar_mutation import _iter_scalar_targets
from .test_threshold_literal_mutation import (
    _iter_covered_threshold_targets,
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
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "arithmetic_op_swap_covered": 0,
        "casilla_ref_topology_covered": 0,
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
        # Threshold-literal positions (issue #457 closure).
        # Split into "covered by harness" (ε-shift detectable) vs
        # "identity-excluded" (additive/multiplicative identity:
        # Max(0, X) / Min(0, X)).
        for _path, literal, parent_op in iter_threshold_literal_paths(fd.formula):
            if is_additive_identity_literal(parent_op, literal.value):
                counts["threshold_literal_identity_excluded"] += 1
            else:
                counts["threshold_literal_covered"] += 1
        # Arithmetic-op-swap positions ( — operator-class typos).
        # Walker enumerates every Add/Sub position; the per-class
        # harness's runtime probe filters fixture-masked entries
        # (catalogued in ``_FIXTURE_MASKED_OP_POSITIONS_RATIONALES``).
        for _ in iter_arithmetic_op_paths(fd.formula):
            counts["arithmetic_op_swap_covered"] += 1
        for _ in iter_casilla_ref_paths(fd.formula):
            counts["casilla_ref_topology_covered"] += 1
    return counts


# Hard-coded expected counts per ruleset, derived from the audit grep
# at the time of authoring issue #338. A future ruleset addition that
# changes these counts will fail the test until the contributor
# explicitly bumps the expected counts here AND extends the per-class
# harness to cover the new nodes — a deliberate friction point.
# Per-mutator-class deferred-coverage convention (issue #457):
#
# Each ruleset row carries a ``<class>_deferred`` column for every
# mutator class whose populated surface has nodes whose per-class
# harness coverage has been **deliberately deferred** to a follow-up
# issue. The aggregator subtracts ``<class>_deferred`` from the
# populated count when computing the kill-rate floor, so the floor is
# evaluated on the **claimed-covered surface only**. The
# :func:`test_deferred_count_matches_empirical_coverage_gap` invariant
# asserts ``populated - empirical_coverage == declared_deferred`` per
# (ruleset, mutator class) — a future PR that bumps populated counts
# without either extending the per-class harness or bumping the
# matching deferred count fails loudly.
#
# A ``<class>_deferred`` value of 0 means the per-class harness fully
# covers that class for that ruleset (or the populated count is 0).
EXPECTED_COUNTS: dict[str, dict[str, int]] = {
    "modelo_100.2024": {
        # Issue #317 (M100 megaproject — Anexos B1, B2, C, D normal/
        # simplificada/modulos, E, F, G, N composed):
        # - sub_op: 71 — fanout across all anexo chains: 4 in B1 rendimiento
        #   previo chain + 4 in B1 art. 20 piecewise + 1 in B1 reducido + 2
        #   in B2 + 1 in B2 reducido + 3 in C + 9 in D normal + 4 in D
        #   simplificada + 1 in D modulos + 1 in E saldo neto + 2 in F BLG +
        #   38 in G (3 progressive_tarifa applications x 6 brackets +
        #   estatal-minimo + cuota chain + cuota liquida + cuota diferencial).
        # - mul_div_scalar: 20 — 2 in B1 (slopes 1.75 + 1.14 in art. 20
        #   piecewise) + 1 in D simplificada (0.05 in 5% cap) + 17 in G
        #   (rate literals across 3 progressive_tarifa applications).
        # No PercentFormula or BracketsFormula nodes yet — the per-CCAA
        # tarifa autonomica progressive scales for Madrid / Cataluna /
        # Andalucia / Comunitat Valenciana / Castilla y Leon are deferred
        # to a follow-up issue.
        # Issue #457: 2 sub_op chains covered (0720 cuota_diferencial +
        # 0545 base_liquidable_general clamp-wrapped) → 69 deferred.
        # 3 mul_div_scalar archetypes covered (0540 bracket-5 / 0560
        # bracket-5 / 0021 art. 20 slope) → 17 deferred.
        "sub_op": 71,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 20,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 33,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 96,
        "arithmetic_op_swap_deferred": 3,
        "casilla_ref_topology_covered": 131,
        "casilla_ref_topology_deferred": 3,
    },
    "modelo_100.2025": {
        # Issue #317: structural baseline for the year that anchors the 2024
        # and 2026 clones; node fingerprint identical (LIRPF arts. 17-20 stable
        # 2024 → 2025 → 2026 per BOE consolidated text consult 2026-02-28).
        "sub_op": 71,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 20,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 33,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 96,
        "arithmetic_op_swap_deferred": 3,
        "casilla_ref_topology_covered": 131,
        "casilla_ref_topology_deferred": 3,
    },
    "modelo_100.2026": {
        # Issue #317: 2026 ruleset inherits 2025 numerical surface; mutable-node
        # fingerprint matches verbatim. Any 2026-specific delta lands as a
        # follow-up issue when the 2026 Orden HAC publishes (precedent feb-mar 2027).
        "sub_op": 71,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 20,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 33,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 96,
        "arithmetic_op_swap_deferred": 3,
        "casilla_ref_topology_covered": 131,
        "casilla_ref_topology_deferred": 3,
    },
    "modelo_100.summary.2025": {
        # 1 sub_op covered (0720 outer); 0698 outer + the inner
        # sub_op of 0720 are not covered (the operand-swap harness
        # mutates only the outermost SubFormula).
        "sub_op": 3,  # casilla 0698 = clamp_pos(sub_op(...)) (1) + 0720 = sub_op(sub_op(...), ref) (2 nested).
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 7,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 11,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_111.2024": {
        # Issue #457: M111 2024 has 1 sub_op (casilla 30); the
        # operand-swap harness only imports M111 2025 / 2026 → 1
        # deferred. Pre-existing pre-#457 behaviour, surfaced honestly.
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 2,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 10,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_111.2025": {
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 2,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 10,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_111.2026": {
        # Issue #318: 2026 ruleset is a structural clone of 2024 / 2025
        # (LIRPF arts. 99-101 + RIRPF arts. 99-100 unchanged across all
        # three years per the rule-delta manifest), so the mutable-node
        # fingerprint matches the 2024 / 2025 rows verbatim.
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 2,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 10,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_115.2024": {
        # Issue #457: M115 2024 sub_op (casilla 06) not covered by
        # operand-swap harness (only 2025 / 2026 imported) → 1 deferred.
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 2,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 4,
        "casilla_ref_topology_deferred": 1,
    },
    "modelo_115.2025": {
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 2,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 4,
        "casilla_ref_topology_deferred": 1,
    },
    "modelo_115.2026": {
        # Issue #319: 2026 ruleset is a structural clone of 2024 / 2025
        # (RIRPF art. 100 unchanged across all three years per the
        # rule-delta manifest), so the mutable-node fingerprint matches
        # the 2024 / 2025 rows verbatim.
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 2,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 4,
        "casilla_ref_topology_deferred": 1,
    },
    "modelo_123.2024": {
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 4,
        "arithmetic_op_swap_deferred": 2,
        "casilla_ref_topology_covered": 8,
        "casilla_ref_topology_deferred": 4,
    },
    "modelo_123.2025": {
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 4,
        "arithmetic_op_swap_deferred": 2,
        "casilla_ref_topology_covered": 8,
        "casilla_ref_topology_deferred": 4,
    },
    "modelo_123.2026": {
        "sub_op": 1,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 4,
        "arithmetic_op_swap_deferred": 2,
        "casilla_ref_topology_covered": 8,
        "casilla_ref_topology_deferred": 4,
    },
    "modelo_130.2024": {
        # M130 has 8 SubFormula descendants per year — 6 outer (one per
        # sub_op-bearing casilla 03/07/11/14/17/19) plus 2 inner sub_ops
        # nested inside casillas 07 and 17. The operand-swap harness
        # mutates only outer sub_ops → 2 inner are deferred.
        "sub_op": 8,  # casillas 03 (1), 07 (sub_op(sub_op,ref) = 2), 11 (1), 14 (1), 17 (2), 19 (1).
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 1,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 9,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 18,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_130.2025": {
        "sub_op": 8,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 1,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 9,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 18,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_130.2026": {
        # Issue #321: 2026 ruleset is a structural clone of 2024 / 2025
        # (RIRPF art. 110 unchanged across all three years per the
        # rule-delta manifest), so the mutable-node fingerprint matches
        # the 2024 / 2025 rows verbatim.
        "sub_op": 8,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 1,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 9,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 18,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_131.2024": {
        # Issue #457: M131 2024 not imported by operand-swap harness
        # (only 2025 / 2026 are) → all 5 deferred.
        "sub_op": 5,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 13,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_131.2025": {
        # 3 outer sub_ops covered (10, 13, 15); 2 inner sub_ops nested
        # inside 10 and 13 are deferred (outer-only harness limitation).
        "sub_op": 5,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 13,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_131.2026": {
        "sub_op": 5,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 2,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 13,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_180.2024": {
        "sub_op": 0,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 0,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 1,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_180.2025": {
        "sub_op": 0,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 0,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 1,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_180.2026": {
        "sub_op": 0,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 1,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 0,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 1,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_200.2024": {
        # 1 outer sub_op covered (00611); 4 inner sub_ops in the 4-deep
        # nest are deferred. Casilla 00621's outer sub_op is also not
        # covered.
        "sub_op": 5,  # casilla 00611 = 4-deep sub_op nest (4 nodes); casilla 00621 has 1 sub_op.
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 1,  # percent_from_whole — rate is DivFormula.
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,  # the inner Literal("100") of percent_from_whole.
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 2,
        "casilla_ref_topology_covered": 10,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_200.2025": {
        "sub_op": 5,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 1,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 2,
        "casilla_ref_topology_covered": 10,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_200.2026": {
        "sub_op": 5,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 1,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 2,
        "casilla_ref_topology_covered": 10,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_202.2025": {
        # 1 outer sub_op covered (32); 2 inner sub_ops in the chain are
        # deferred (outer-only harness limitation).
        "sub_op": 3,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 1,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 3,
        "arithmetic_op_swap_deferred": 2,
        "casilla_ref_topology_covered": 8,
        "casilla_ref_topology_deferred": 0,
    },
    "modelo_303.2024": {
        "sub_op": 2,  # casilla 45 = sub_op(add_op(...), ref(...)) (1) + casilla 69 = sub_op(ref, ref) (1).
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 3,  # casillas 03, 06, 09.
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 1,  # casilla 66's percent rate is ref("65").
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,  # casilla 66's lit("100") denominator.
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 5,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 4,
        "casilla_ref_topology_covered": 23,
        "casilla_ref_topology_deferred": 15,
    },
    "modelo_303.2025": {
        "sub_op": 2,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 3,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 1,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 5,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 4,
        "casilla_ref_topology_covered": 23,
        "casilla_ref_topology_deferred": 15,
    },
    "modelo_303.2026": {
        "sub_op": 2,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 3,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 1,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 1,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 5,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 6,
        "arithmetic_op_swap_deferred": 4,
        "casilla_ref_topology_covered": 23,
        "casilla_ref_topology_deferred": 15,
    },
    "modelo_390.2024": {
        # 2 outer sub_ops covered (105, 191); casilla 193 (clamp-wrapped
        # sub_op(0, 191)) is deferred — newly mutable post-#457 helper
        # generalisation, fixture follow-up tracked separately.
        "sub_op": 3,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 1,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 5,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 11,
        "casilla_ref_topology_deferred": 1,
    },
    "modelo_390.2025": {
        "sub_op": 3,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 1,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 5,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 11,
        "casilla_ref_topology_deferred": 1,
    },
    "modelo_390.2026": {
        "sub_op": 3,
        "sub_op_deferred": 0,
        "percent_rate_literal": 0,
        "percent_rate_param": 0,
        "percent_rate_compound_skipped": 0,
        "percent_rate_casilla_ref_skipped": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 1,
        "threshold_literal_identity_excluded": 0,
        "threshold_literal_deferred": 0,
        "arithmetic_op_swap_covered": 5,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 11,
        "casilla_ref_topology_deferred": 1,
    },
}


_POPULATED_KEYS = frozenset(
    {
        "sub_op",
        "percent_rate_literal",
        "percent_rate_param",
        "percent_rate_compound_skipped",
        "percent_rate_casilla_ref_skipped",
        "brackets_threshold_non_terminal",
        "mul_div_scalar",
        "threshold_literal_covered",
        "threshold_literal_identity_excluded",
        "arithmetic_op_swap_covered",
        "casilla_ref_topology_covered",
    }
)
_DEFERRED_KEYS = frozenset(
    {
        "sub_op_deferred",
        "mul_div_scalar_deferred",
        "threshold_literal_deferred",
        "arithmetic_op_swap_deferred",
        "casilla_ref_topology_deferred",
    }
)
_NUMERIC_BRACKETS_SYNTHETIC = 4  # synthetic_brackets.338.2025 contributes 4 non-terminal brackets.


def _empirical_scalar_coverage() -> dict[str, int]:
    """Return per-ruleset count of unique mul/div scalar targets exercised.

    Imported from :mod:`test_scalar_mutation`; dictionary keys are
    ruleset IDs, values are the count of unique
    ``(casilla_id, leaf_path)`` pairs the scalar harness mutates for
    that ruleset.
    """
    coverage: dict[str, int] = {ruleset.ruleset_id: 0 for ruleset in ALL_RULESETS}
    for ruleset_id, _casilla_id, _leaf_path in _iter_scalar_targets():
        coverage[ruleset_id] = coverage.get(ruleset_id, 0) + 1
    return coverage


def _empirical_percent_coverage() -> dict[str, int]:
    """Return per-ruleset count of unique percent-rate targets exercised."""
    coverage: dict[str, int] = {ruleset.ruleset_id: 0 for ruleset in ALL_RULESETS}
    for ruleset_id, _casilla_id, _signature in _iter_percent_targets():
        coverage[ruleset_id] = coverage.get(ruleset_id, 0) + 1
    return coverage


@pytest.mark.parametrize("ruleset", ALL_RULESETS, ids=lambda r: r.ruleset_id)
def test_per_ruleset_node_counts_match_expected(ruleset: Ruleset) -> None:
    """Every landed ruleset's mutable-node fingerprint matches the expected map.

    A divergence here means a future ruleset addition has changed the
    mutable-node landscape; the contributor must update
    :data:`EXPECTED_COUNTS` AND extend the per-class harness to cover
    the new nodes.
    """
    actual = _count_per_ruleset(ruleset)
    expected_full = EXPECTED_COUNTS[ruleset.ruleset_id]
    expected_populated = {k: v for k, v in expected_full.items() if k in _POPULATED_KEYS}
    assert actual == expected_populated, (
        f"ruleset {ruleset.ruleset_id} mutable-node counts changed:\n"
        f"  expected: {expected_populated}\n"
        f"  actual:   {actual}\n"
        f"If you added a new node, extend the per-class harness AND "
        f"update EXPECTED_COUNTS in test_mutator_kill_rate.py."
    )


def test_expected_counts_rows_carry_required_columns() -> None:
    """Every ``EXPECTED_COUNTS`` row carries the populated and deferred keys.

    Issue #457: the deferred catalogue is the regression-defense
    mechanism; a row missing a ``_deferred`` column would silently
    skip the gap-equality invariant in
    :func:`test_deferred_count_matches_empirical_coverage_gap`.
    """
    required = _POPULATED_KEYS | _DEFERRED_KEYS
    for ruleset_id, counts in EXPECTED_COUNTS.items():
        missing = required - set(counts)
        assert not missing, f"EXPECTED_COUNTS[{ruleset_id!r}] missing required keys: {missing!r}"
        unexpected = set(counts) - required
        assert not unexpected, (
            f"EXPECTED_COUNTS[{ruleset_id!r}] has unexpected keys: {unexpected!r}; "
            f"add them to _POPULATED_KEYS / _DEFERRED_KEYS or remove."
        )


def test_deferred_count_matches_empirical_coverage_gap() -> None:
    """Issue #457 regression defense: ``populated - empirical == declared_deferred``.

    For every (ruleset, mutator class) the declared ``<class>_deferred``
    column must equal the gap between the walker-reported populated
    count and the per-class harness's empirical coverage. If a future
    PR bumps a populated count without either extending the per-class
    harness OR bumping the matching deferred count, this assertion
    fails — exactly the failure mode the prior ``killed = populated``
    tautology hid.
    """
    scalar_coverage = _empirical_scalar_coverage()
    # The sub_op surface is not yet plumbed via a per-class harness
    # generator (the operand-swap harness uses an explicit literal
    # parametrize block rather than a builder function). The deferred
    # gap for sub_op is therefore validated against a dedicated
    # operand-swap target inventory derived from the ``EXPECTED_COUNTS``
    # walker minus the operand-swap harness's covered set.
    sub_op_coverage = _empirical_sub_op_coverage()
    threshold_coverage = _empirical_threshold_literal_coverage()

    for ruleset_id, counts in EXPECTED_COUNTS.items():
        scalar_gap = counts["mul_div_scalar"] - scalar_coverage.get(ruleset_id, 0)
        assert scalar_gap >= 0, (
            f"{ruleset_id}: empirical mul_div_scalar coverage "
            f"{scalar_coverage.get(ruleset_id, 0)} exceeds populated "
            f"{counts['mul_div_scalar']} — the per-class harness mutates a node "
            f"the walker did not enumerate."
        )
        assert scalar_gap == counts["mul_div_scalar_deferred"], (
            f"{ruleset_id}: mul_div_scalar gap {scalar_gap} (populated "
            f"{counts['mul_div_scalar']} - empirical {scalar_coverage.get(ruleset_id, 0)}) "
            f"does not match declared mul_div_scalar_deferred "
            f"{counts['mul_div_scalar_deferred']}. Either extend the "
            f"per-class harness or update the deferred catalogue."
        )

        sub_op_gap = counts["sub_op"] - sub_op_coverage.get(ruleset_id, 0)
        assert sub_op_gap >= 0, (
            f"{ruleset_id}: empirical sub_op coverage "
            f"{sub_op_coverage.get(ruleset_id, 0)} exceeds populated "
            f"{counts['sub_op']}."
        )
        assert sub_op_gap == counts["sub_op_deferred"], (
            f"{ruleset_id}: sub_op gap {sub_op_gap} (populated {counts['sub_op']} - "
            f"empirical {sub_op_coverage.get(ruleset_id, 0)}) does not match "
            f"declared sub_op_deferred {counts['sub_op_deferred']}. Either "
            f"extend the operand-swap harness or update the deferred catalogue."
        )

        threshold_gap = counts["threshold_literal_covered"] - threshold_coverage.get(ruleset_id, 0)
        assert threshold_gap >= 0, (
            f"{ruleset_id}: empirical threshold_literal coverage "
            f"{threshold_coverage.get(ruleset_id, 0)} exceeds populated "
            f"{counts['threshold_literal_covered']}."
        )
        assert threshold_gap == counts["threshold_literal_deferred"], (
            f"{ruleset_id}: threshold_literal gap {threshold_gap} "
            f"(populated {counts['threshold_literal_covered']} - empirical "
            f"{threshold_coverage.get(ruleset_id, 0)}) does not match declared "
            f"threshold_literal_deferred {counts['threshold_literal_deferred']}. "
            f"Either extend the harness or update the deferred catalogue "
            f"(e.g. _CLAMP_MASKED_IDENTITY_POSITIONS in test_threshold_literal_mutation)."
        )

    arithmetic_coverage = _empirical_arithmetic_op_coverage()
    for ruleset_id, counts in EXPECTED_COUNTS.items():
        arithmetic_gap = counts["arithmetic_op_swap_covered"] - arithmetic_coverage.get(ruleset_id, 0)
        assert arithmetic_gap >= 0, (
            f"{ruleset_id}: empirical arithmetic_op_swap coverage "
            f"{arithmetic_coverage.get(ruleset_id, 0)} exceeds populated "
            f"{counts['arithmetic_op_swap_covered']}."
        )
        assert arithmetic_gap == counts["arithmetic_op_swap_deferred"], (
            f"{ruleset_id}: arithmetic_op_swap gap {arithmetic_gap} "
            f"(populated {counts['arithmetic_op_swap_covered']} - empirical "
            f"{arithmetic_coverage.get(ruleset_id, 0)}) does not match declared "
            f"arithmetic_op_swap_deferred {counts['arithmetic_op_swap_deferred']}. "
            f"Each masked position is documented in "
            f"``_FIXTURE_MASKED_OP_POSITIONS_RATIONALES``; bump the deferred "
            f"count or remove the position via fixture redesign to close the gap."
        )

    casilla_ref_coverage = _empirical_casilla_ref_coverage()
    for ruleset_id, counts in EXPECTED_COUNTS.items():
        ref_gap = counts["casilla_ref_topology_covered"] - casilla_ref_coverage.get(ruleset_id, 0)
        assert ref_gap >= 0, (
            f"{ruleset_id}: empirical casilla_ref_topology coverage "
            f"{casilla_ref_coverage.get(ruleset_id, 0)} exceeds populated "
            f"{counts['casilla_ref_topology_covered']}."
        )
        assert ref_gap == counts["casilla_ref_topology_deferred"], (
            f"{ruleset_id}: casilla_ref_topology gap {ref_gap} "
            f"(populated {counts['casilla_ref_topology_covered']} - empirical "
            f"{casilla_ref_coverage.get(ruleset_id, 0)}) does not match declared "
            f"casilla_ref_topology_deferred {counts['casilla_ref_topology_deferred']}. "
            f"Each masked position is documented in "
            f"``_FIXTURE_MASKED_REF_POSITIONS_RATIONALES``; bump the deferred "
            f"count or extend the fixture so a substitute target exists."
        )


def _empirical_casilla_ref_coverage() -> dict[str, int]:
    """Return per-ruleset count of unique casilla-ref topology targets exercised."""
    coverage: dict[str, int] = {ruleset.ruleset_id: 0 for ruleset in ALL_RULESETS}
    seen: set[tuple[str, str, tuple[int, ...]]] = set()
    for param in _CASILLA_REF_TEST_PARAMS:
        case = param.values[0]
        key = (case.ruleset.ruleset_id, case.casilla_id, case.ref_path)
        if key in seen:
            continue
        seen.add(key)
        coverage[case.ruleset.ruleset_id] = coverage.get(case.ruleset.ruleset_id, 0) + 1
    return coverage


def _empirical_arithmetic_op_coverage() -> dict[str, int]:
    """Return per-ruleset count of unique arithmetic-op (Add/Sub) targets exercised.

    Reads :data:`_ARITHMETIC_OP_TEST_PARAMS` from the per-class
    harness — the parametrize cache built at import time, populated
    by walking every Add/Sub position and probing each via the
    runtime fixture-mask filter. Counts unique
    ``(ruleset_id, casilla_id, op_path)`` triples.
    """
    coverage: dict[str, int] = {ruleset.ruleset_id: 0 for ruleset in ALL_RULESETS}
    seen: set[tuple[str, str, tuple[int, ...]]] = set()
    for param in _ARITHMETIC_OP_TEST_PARAMS:
        case = param.values[0]
        key = (case.ruleset.ruleset_id, case.casilla_id, case.op_path)
        if key in seen:
            continue
        seen.add(key)
        coverage[case.ruleset.ruleset_id] = coverage.get(case.ruleset.ruleset_id, 0) + 1
    return coverage


def _empirical_threshold_literal_coverage() -> dict[str, int]:
    """Return per-ruleset count of unique threshold-literal targets exercised.

    Reads the per-class harness's
    :func:`_iter_covered_threshold_targets` enumeration and counts
    unique ``(ruleset_id, casilla_id, leaf_path)`` triples — the +1 €
    / -1 € directions count as a single covered target.
    """
    coverage: dict[str, int] = {ruleset.ruleset_id: 0 for ruleset in ALL_RULESETS}
    seen: set[tuple[str, str, tuple[int, ...]]] = set()
    for ruleset, casilla_id, leaf_path, _parent_op, _value in _iter_covered_threshold_targets():
        key = (ruleset.ruleset_id, casilla_id, leaf_path)
        if key in seen:
            continue
        seen.add(key)
        coverage[ruleset.ruleset_id] = coverage.get(ruleset.ruleset_id, 0) + 1
    return coverage


def _empirical_sub_op_coverage() -> dict[str, int]:
    """Return per-ruleset count of unique sub_op nodes the operand-swap harness exercises.

    Reads :data:`SUB_OP_COVERAGE` from :mod:`test_operand_swap_mutation`
    — a flat tuple of every ``(ruleset_id, casilla_id, sub_op_path)``
    triple the path-based harness covers. The tuple is derived
    programmatically from ``_SUB_OP_COVERAGE_DATA`` plus the
    walker, so coverage is comprehensive (outer + inner sub_ops) and
    the constant cannot drift from the parametrize block (both come
    from the same source of truth).
    """
    coverage: dict[str, int] = {ruleset.ruleset_id: 0 for ruleset in ALL_RULESETS}
    seen: set[tuple[str, str, tuple[int, ...]]] = set()
    for ruleset_id, casilla_id, sub_op_path in SUB_OP_COVERAGE:
        key = (ruleset_id, casilla_id, sub_op_path)
        if key in seen:
            continue
        seen.add(key)
        coverage[ruleset_id] = coverage.get(ruleset_id, 0) + 1
    return coverage


def test_aggregate_kill_rate_floor_is_satisfied() -> None:
    """Aggregate kill-rate across the **claimed-covered** mutator surface is ≥ 90 %.

    Issue #457 replaces the prior ``killed = populated`` tautology
    with empirical coverage computed from the per-class harness
    parameter generators. The floor is evaluated against
    ``populated - declared_deferred`` so it reflects the surface the
    per-class harnesses actually claim to cover. The
    :func:`test_deferred_count_matches_empirical_coverage_gap`
    assertion above guarantees that the deferred declaration is in
    sync with the per-class harness empirical coverage.

    **Co-enforcement note** (re: gemini-code-assist review on PR #459):
    this 90 % floor is intentionally the looser of two layered
    checks. The strict-equality invariant in
    :func:`test_aggregator_killed_equals_populated_under_test` (next)
    is the authoritative gate; the floor is preserved as the
    historical issue-#338 DoD anchor and as a soft fallback if a
    future PR relaxes the equality (e.g. to admit a documented
    "no-observable-effect mutant" set). Removing the floor would
    erase that traceability without adding behavioral safety.
    """
    populated = 0
    deferred = 0
    catalogued_unflagged = 0
    catalogued_identity_excluded = 0
    for _ruleset_id, counts in EXPECTED_COUNTS.items():
        populated += counts["percent_rate_literal"]
        populated += counts["percent_rate_param"]
        populated += counts["mul_div_scalar"]
        populated += counts["threshold_literal_covered"]
        populated += counts["arithmetic_op_swap_covered"]
        populated += counts["casilla_ref_topology_covered"]
        deferred += counts["mul_div_scalar_deferred"]
        deferred += counts["threshold_literal_deferred"]
        deferred += counts["arithmetic_op_swap_deferred"]
        deferred += counts["casilla_ref_topology_deferred"]
        # Compound-rate and casilla-ref percent rates are NOT counted
        # in the kill-rate denominator: they are explicitly delegated
        # to descendant mutators (compound) or are out-of-AST inputs
        # (casilla-ref). They appear in the unflagged-nodes catalogue.
        catalogued_unflagged += counts["percent_rate_compound_skipped"]
        catalogued_unflagged += counts["percent_rate_casilla_ref_skipped"]
        # Architectural identities (Max(0, X) / Min(0, X)) are
        # documented in NOT_MUTABLE_NODE_TYPES rationale and excluded
        # from the kill-rate denominator with rationale.
        catalogued_identity_excluded += counts["threshold_literal_identity_excluded"]
    # Synthetic brackets ruleset adds 4 non-terminal brackets — the
    # synthetic ruleset is not in ALL_RULESETS but its kill-rate is
    # still asserted by ``test_brackets_threshold_mutation``. No
    # deferred coverage on the synthetic ruleset.
    populated += _NUMERIC_BRACKETS_SYNTHETIC
    populated_under_test = populated - deferred
    assert populated_under_test > 0, "expected non-empty claimed-covered surface"

    scalar_coverage = sum(_empirical_scalar_coverage().values())
    percent_coverage = sum(_empirical_percent_coverage().values())
    threshold_coverage = sum(_empirical_threshold_literal_coverage().values())
    arithmetic_coverage = sum(_empirical_arithmetic_op_coverage().values())
    casilla_ref_coverage = sum(_empirical_casilla_ref_coverage().values())
    brackets_coverage = _NUMERIC_BRACKETS_SYNTHETIC
    killed = (
        scalar_coverage
        + percent_coverage
        + threshold_coverage
        + arithmetic_coverage
        + casilla_ref_coverage
        + brackets_coverage
    )

    kill_rate = Decimal(killed) / Decimal(populated_under_test)
    assert kill_rate >= Decimal("0.90"), (
        f"aggregate kill-rate {kill_rate} < 0.90 floor; "
        f"populated={populated}, deferred={deferred}, "
        f"populated_under_test={populated_under_test}, killed={killed}, "
        f"unflagged={catalogued_unflagged}, "
        f"identity_excluded={catalogued_identity_excluded}"
    )


def test_aggregator_killed_equals_populated_under_test() -> None:
    """The empirical killed count matches the claimed-covered surface.

    Per-class harnesses fail-fast on every parametrised case, so when
    the suite reaches this aggregator every claimed-covered node has
    already been killed. The assertion enforces that the empirical
    coverage matches ``populated - deferred`` exactly — a future
    addition that introduces a per-class case but forgets to lower the
    deferred count fails here.
    """
    populated_under_test = 0
    for counts in EXPECTED_COUNTS.values():
        populated_under_test += counts["percent_rate_literal"]
        populated_under_test += counts["percent_rate_param"]
        populated_under_test += counts["mul_div_scalar"]
        populated_under_test -= counts["mul_div_scalar_deferred"]
        populated_under_test += counts["threshold_literal_covered"]
        populated_under_test -= counts["threshold_literal_deferred"]
        populated_under_test += counts["arithmetic_op_swap_covered"]
        populated_under_test -= counts["arithmetic_op_swap_deferred"]
        populated_under_test += counts["casilla_ref_topology_covered"]
        populated_under_test -= counts["casilla_ref_topology_deferred"]
    populated_under_test += _NUMERIC_BRACKETS_SYNTHETIC

    killed = (
        sum(_empirical_scalar_coverage().values())
        + sum(_empirical_percent_coverage().values())
        + sum(_empirical_threshold_literal_coverage().values())
        + sum(_empirical_arithmetic_op_coverage().values())
        + sum(_empirical_casilla_ref_coverage().values())
        + _NUMERIC_BRACKETS_SYNTHETIC
    )
    assert killed == populated_under_test, (
        f"empirical killed count {killed} != populated_under_test {populated_under_test}; "
        f"either a per-class harness covers more than the deferred catalogue declares "
        f"or the catalogue claims coverage that the harness does not provide."
    )


def build_catalogue_markdown() -> str:
    """Return the markdown table consumed by the issue-#338 / #457 exec summary.

    Columns: ``sub_op`` populated, ``sub_op_deferred``, ``percent_rate``
    populated (literal+param), ``brackets_threshold``, ``mul_div_scalar``
    populated, ``mul_div_scalar_deferred``, ``threshold_literal``
    covered, ``threshold_literal_deferred``,
    ``threshold_literal_identity`` (architectural identity, excluded
    with rationale), ``unflagged`` (compound+casilla_ref).
    """
    lines: list[str] = []
    lines.append(
        "| Ruleset | sub_op | sub_op_def | rate (lit+param) | brackets | "
        "mul_div_scalar | mul_div_def | thr_lit | thr_lit_def | thr_lit_id "
        "| arith_op | arith_op_def | ref_topo | ref_topo_def | unflagged |"
    )
    lines.append(
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"
    )
    totals = {
        "sub_op": 0,
        "sub_op_deferred": 0,
        "percent_rate": 0,
        "brackets_threshold_non_terminal": 0,
        "mul_div_scalar": 0,
        "mul_div_scalar_deferred": 0,
        "threshold_literal_covered": 0,
        "threshold_literal_deferred": 0,
        "threshold_literal_identity_excluded": 0,
        "arithmetic_op_swap_covered": 0,
        "arithmetic_op_swap_deferred": 0,
        "casilla_ref_topology_covered": 0,
        "casilla_ref_topology_deferred": 0,
        "unflagged": 0,
    }
    for ruleset in ALL_RULESETS:
        c = EXPECTED_COUNTS[ruleset.ruleset_id]
        rate_total = c["percent_rate_literal"] + c["percent_rate_param"]
        unflagged = c["percent_rate_compound_skipped"] + c["percent_rate_casilla_ref_skipped"]
        lines.append(
            f"| `{ruleset.ruleset_id}` | {c['sub_op']} | {c['sub_op_deferred']} "
            f"| {rate_total} | {c['brackets_threshold_non_terminal']} "
            f"| {c['mul_div_scalar']} | {c['mul_div_scalar_deferred']} "
            f"| {c['threshold_literal_covered']} | {c['threshold_literal_deferred']} "
            f"| {c['threshold_literal_identity_excluded']} "
            f"| {c['arithmetic_op_swap_covered']} | {c['arithmetic_op_swap_deferred']} "
            f"| {c['casilla_ref_topology_covered']} | {c['casilla_ref_topology_deferred']} "
            f"| {unflagged} |"
        )
        totals["sub_op"] += c["sub_op"]
        totals["sub_op_deferred"] += c["sub_op_deferred"]
        totals["percent_rate"] += rate_total
        totals["brackets_threshold_non_terminal"] += c["brackets_threshold_non_terminal"]
        totals["mul_div_scalar"] += c["mul_div_scalar"]
        totals["mul_div_scalar_deferred"] += c["mul_div_scalar_deferred"]
        totals["threshold_literal_covered"] += c["threshold_literal_covered"]
        totals["threshold_literal_deferred"] += c["threshold_literal_deferred"]
        totals["threshold_literal_identity_excluded"] += c["threshold_literal_identity_excluded"]
        totals["arithmetic_op_swap_covered"] += c["arithmetic_op_swap_covered"]
        totals["arithmetic_op_swap_deferred"] += c["arithmetic_op_swap_deferred"]
        totals["casilla_ref_topology_covered"] += c["casilla_ref_topology_covered"]
        totals["casilla_ref_topology_deferred"] += c["casilla_ref_topology_deferred"]
        totals["unflagged"] += unflagged
    lines.append("| **synthetic_brackets.338.2025** | 0 | 0 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
    totals["brackets_threshold_non_terminal"] += _NUMERIC_BRACKETS_SYNTHETIC
    lines.append(
        f"| **TOTAL** | **{totals['sub_op']}** | **{totals['sub_op_deferred']}** "
        f"| **{totals['percent_rate']}** | **{totals['brackets_threshold_non_terminal']}** "
        f"| **{totals['mul_div_scalar']}** | **{totals['mul_div_scalar_deferred']}** "
        f"| **{totals['threshold_literal_covered']}** "
        f"| **{totals['threshold_literal_deferred']}** "
        f"| **{totals['threshold_literal_identity_excluded']}** "
        f"| **{totals['arithmetic_op_swap_covered']}** "
        f"| **{totals['arithmetic_op_swap_deferred']}** "
        f"| **{totals['casilla_ref_topology_covered']}** "
        f"| **{totals['casilla_ref_topology_deferred']}** "
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
    # Column layout per ``build_catalogue_markdown`` (post-):
    #   [0] empty (leading "|")
    #   [1] **TOTAL**
    #   [2] sub_op
    #   [3] sub_op_def
    #   [4] rate (lit+param)
    #   [5] brackets
    #   [6] mul_div_scalar
    #   [7] mul_div_def
    #   [8] thr_lit
    #   [9] thr_lit_def
    #  [10] thr_lit_id (architectural identity)
    #  [11] arith_op
    #  [12] arith_op_def (fixture-masked architectural-identity Adds/Subs)
    #  [13] unflagged
    #  [14] empty (trailing "|")
    cells = totals_line.split("|")
    assert "**0**" not in cells[2].strip(), "sub_op column must be non-zero"
    assert "**0**" not in cells[4].strip(), "percent_rate column must be non-zero"
    assert "**0**" not in cells[5].strip(), "brackets_threshold column must be non-zero"
    assert "**0**" not in cells[6].strip(), "mul_div_scalar column must be non-zero"
    assert "**0**" not in cells[8].strip(), "threshold_literal column must be non-zero"
    assert "**0**" not in cells[11].strip(), "arithmetic_op_swap column must be non-zero"
    # Closeable ``_deferred`` totals are 0; arith_op_def is non-zero
    # only because of architectural-identity ``Add(x, 0)`` masking
    # (catalogued in ``_FIXTURE_MASKED_OP_POSITIONS_RATIONALES``).
    assert cells[3].strip() == "**0**", f"sub_op_deferred total must be 0; got {cells[3].strip()!r}"
    assert cells[7].strip() == "**0**", f"mul_div_scalar_deferred total must be 0; got {cells[7].strip()!r}"
    assert cells[9].strip() == "**0**", f"threshold_literal_deferred total must be 0; got {cells[9].strip()!r}"
