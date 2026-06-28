---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: 2026-05-28
modified: '2026-05-28'
step_id: S398
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-05-27-dsl-conditional-predicate-adr]]"
---

# `cross-domain-continuity` `W04.P19.S398`

Dual-narrative learning record: the S398 M131 `implies_nonzero` predicate landed against a misunderstood formula DAG and was rolled back end-to-end after architect-2's BLOCKER verdict. Both the authoring commit and the rollback commit are documented here so future readers do not re-author the same flawed predicate.

Commits:
- `31b332ed0` — initial authoring (later rolled back)
- `c159966df` — full rollback after BLOCKER verdict

- Modified (initial then reverted): `src/aeat/_data/registry/aeat/modelos/131/revisions/{2019-2023,2024,2025,2026}/verification_expectations/0002-verification_predicates.toml`
- Modified (initial then reverted): predicate-level anti-tautology test suite

## What landed in 31b332ed0

The initial authoring added an `implies_nonzero(["01", "07"])` verification predicate to each of the four M131 revision verification_expectations TOML fragments, with the stated intent of capturing the AEAT cuota-mínima rule "cuando C01 sea positivo, C07 debe ser distinta de cero". Each revision's predicate carried `finding_kind = "BLOCKING_RULE"` and the LIRPF / RD 439/2007 legal anchor; two anti-tautology tests were authored alongside to exercise the antecedent-positive / consequent-zero violation path and a happy-path satisfaction case.

## What the architect-2 review caught

The structural claim "C01 positive implies C07 non-zero" is wrong for M131. The M131 formula DAG defines `C07 = add(C02, C04, C06)` — C01 is NOT a summand of C07. A legitimate Khalid-shape EO contribuyente with `C01 = 50000` and the C02 / C04 / C06 feeders all zero produces `C07 = 0` lawfully. Under the authored predicate this filer would have hit a BLOCKING_RULE finding and been refused calculate, despite filing correctly.

The architect-2 BLOCKER verdict required the predicate AND its anti-tautology tests be removed from all four revisions; the cap_le_when_positive(["11","10"]) predicate (P08.S47/S48) is unrelated and stayed intact.

## What c159966df rolled back

Removed the four predicate rows (one per revision) plus the two anti-tautology tests. Verified by inspection of the current M131 verification_expectations TOMLs: only the cap_le_when_positive entry remains across all four revisions.

The S376/S377/S378 infrastructure (operator name registered on `KNOWN_VERIFICATION_PREDICATE_OPERATORS`, runtime branch + regex in `_evaluate_predicate_expression`, five-test anti-tautology suite on `test_verification_substance.py`) STAYED intact. The operator is still a valid DSL primitive; the M131 binding was the wrong application of it.

## Lessons captured

1. **DAG-correctness must precede predicate authoring.** The author of the M131 predicate read the regulatory text ("cuando C01 sea positivo") and bound a predicate without verifying the actual M131 formula DAG. The two are not equivalent: the regulatory rule is about base imponible being positive, while the formula DAG models cuota-mínima as a sum of specific feeders. The predicate's `implies_nonzero(["01","07"])` shape conflates the two.

2. **Predicate-route silent-refusal failure mode.** When the predicate fires it surfaces a BLOCKING_RULE finding with no per-row context. The operator sees "predicate failed" without diagnostic information about which row or which casilla state triggered the rule. This is the load-bearing argument in the classifier-vs-predicate research memo (`2026-05-28-source-jurisdiction-axis-research.md`): for high legal-blast-radius gates, the classifier shape's loud per-row failure mode is preferable to the predicate's silent aggregate refusal.

3. **Architecture review catches what authoring discipline misses.** The architect-2 review identified the DAG misread via formula inspection; the predicate's own diagnostics gave the same BLOCKING_RULE finding regardless of whether the rule was right or wrong. Future predicate authors should ground every binding against the formula DAG before authoring, not only against the regulatory text.

## Why this record exists

The S398 cycle ran from authoring through review through full rollback in a single short window. Without a documented record, a future reader inspecting the c159966df rollback might (a) not understand why the predicate was removed, (b) attempt to re-author the same flawed shape against the same regulatory text, or (c) miss the architect-2 verdict reasoning. This record exists so the lesson is durable.

Task tracking: #57 (M131 implies_nonzero) was closed at S398 ship and reopened at the rollback.

## Gate evidence

- G1 no naked env reads: unchanged across both commits.
- G2 typed pydantic at boundary: predicate TOML rows are schema-validated authoring data; no untyped boundary introduced or removed.
- G3 user messages via tr(): N/A; verification predicate authoring is registry data.
- G4 no locale yml hand-edits: unchanged.
- G5 no shims: rollback was a clean reversal, no compatibility scaffolding left behind.
- G6 no tautological tests: the anti-tautology tests were removed alongside the predicate; the underlying operator's S376/S377/S378 anti-tautology suite remains and is unaffected.

## References

- ADR: dsl-conditional-predicate-adr (defines the operator semantics that the M131 binding misapplied)
- Sibling Steps: S376 (operator register), S377 (runtime branch), S378 (operator anti-tautology tests) — all intact.
- Related research memo: source-jurisdiction-axis research (uses this rollback as the canonical example of the predicate-route silent-refusal failure mode).
- Authoring commit: `31b332ed0`. Rollback commit: `c159966df`.
- Verified state: current M131 verification_expectations TOMLs across 2019-2023 / 2024 / 2025 / 2026 revisions carry only the `cap_le_when_positive(["11","10"])` predicate (S398 rows are absent).
