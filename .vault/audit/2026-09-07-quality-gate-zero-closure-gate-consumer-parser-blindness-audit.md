---
tags:
  - '#audit'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:1844bee0149bd63c2268f1d34aaf7d99df4a690b000b67d4df8216a250b0a089'
related:
  - "[[2026-09-07-quality-gate-zero-closure-blind-green-gates-adr]]"
  - "[[2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr]]"
---

# `quality-gate-zero-closure` audit: `gate consumer parser blindness`

## Scope

Reviewed three live gate-integrity defects found while driving an unrelated rename campaign
through the six mandatory static gates on 2026-09-07, and tested each against
`2026-09-07-quality-gate-zero-closure-blind-green-gates-adr`. The question is whether the
blind-green family, as adjudicated, reaches every surface where a gate can be green without
being able to fail -- or only the assertion surface its four detector classes describe.

It does not reach every surface. One defect names a class the accepted decision does not
cover, and it was found in the reporting layer of the gate system itself.

## Findings

### consumer-parser-cannot-represent-valid-output | high | A gate's reporting layer was blind to nine of twelve contracts

`dev/audit/report.py` classified import-linter contract verdicts with `endswith("KEPT")`.
A contract carrying ignored imports prints `KEPT (3 ignored imports)`, which fails that test.
Nine of twelve contracts print that form, so the layer could not see them, and reported a
healthy gate as "the run aborted / rotted gate configuration".

The dimension exists precisely to detect "the gate did not run". It had been misreporting for
months, and nothing failed: `just check-imports` exited zero throughout, because the defect
was in the layer that *reads* the gate, not the gate.

This is the blind-green property applied one layer out. The accepted decision defines the
family over assertions -- "an assertion is tautological when its truth value is fixed before
any operand is understood" -- and its four detector classes (subsuming disjunction,
self-echoing token, locale-bound absence, never-emitted literal) all sweep `assert`
statements. A verdict parser is not an assertion and would not be swept by any of them.

It is nonetheless mechanically decidable, and by the same means: the defect is a
**containment test against structured output whose real grammar has a suffix**. The parser
treats a token-with-parenthetical as a bare token. That is decidable from the AST wherever a
known gate's output grammar is known -- the same shape as the never-emitted-literal detector,
joined against the gate's real output rather than against the corpus.

Fixed by reading the verdict as the last word before the optional parenthetical, with a
bare-word guard. The class is unowned.

### mock-asserted-the-call-not-the-effect | medium | A banned-mock test proved a call happened, not that anything followed

`dev/registry/newmodelo/tests/test_manager.py` spied on `reset_conformance_cache` through
`mock.patch` and asserted `spy.assert_called_once_with()`. That verdict is fixed by the call
happening; it is true whether or not the cache is dropped, which is the property the test
names. The repository's own rule, surfaced by `TID251`, reads "Mocks are banned. Exercise real
objects and explicit production seams."

The repair used the idiom already present in four other modules: the memoised loader returns
the same object until something clears it, so identity across two public
`load_locale_coverage_index()` calls is the cache state. No stub, no private access, and it
fails when the production call is removed -- demonstrated by removing it. 14 tests pass;
reverting the production call fails the one that should fail.

This sits inside the adjudicated family (an assertion whose claim is weaker than its subject)
but in a form none of the four detectors reaches, because the weakening is the *choice of
instrument*, not the shape of the expression.

### declared-census-fails-both-drift-directions | high | A declaration with no drift tests, contradicting the sanctioned pattern

`src/cadrumo/tests/test_deferred_cross_layer_imports.py:173` carries `_DECLARED`, a
hand-maintained census of function-local cross-layer imports. Measured against the live tree
it holds **26 stale rows** whose edges no longer exist (`application/bucket_maintenance/
service.py` alone accounts for 7) and **8 undeclared live edges**. Proven pre-existing: the
two failures reproduce identically against the original `.importlinter`.

The accepted decision sanctions exactly one declaration pattern -- "a hand-authored,
site-specific claim whose docstring states why this particular site is correct, checked by a
conformance gate against AST-discovered reality, in both drift directions -- a stale
declaration and an undeclared site both fail" -- and names `PINNED_TAXONOMY_LITERALS` with its
two drift tests as the template. `_DECLARED` has neither drift test, which is why both
populations accumulated unnoticed.

The decision also settles the disposition question that was open before it was read: this is
not a choice between tidying the rows and deleting the table. A declaration either gains both
drift tests, or it is an exemption list and is forbidden. The table's own message already
states the per-row rule -- a deferral breaking a genuine import cycle is declared
`UNADJUDICATED`; one existing only to quiet a layer contract is removed from the code.

### commit-time-remedy-was-already-adjudicated | none | Recorded to prevent re-proposal

`just check-style` was red at HEAD three separate times in three hours (9 errors, then 2, then
2), each from a different committed change, including the banned `unittest.mock` above. Every
instance cost a 35-minute gated cycle downstream.

The obvious remedy -- run the mechanical gates at commit time -- is rejected and binding under
`2026-09-02-gate-integrity-adjudication-commit-time-mechanical-gates-adr`, including in
verify-only form, because the pre-commit runner's stash-and-restore step destroyed uncommitted
work in this repository. This audit proposed it before reading that record and withdraws it.
The observation stands as evidence of cost; the remedy is closed.

## Evidence

- `dev/audit/report.py` verdict parsing, before and after; live `lint-imports` output showing
  `KEPT (N ignored imports)` on 9 of 12 contracts; `just audit-health-report` layering
  dimension moving to GREEN "all 12 of 12 contract(s) kept" once the parser could see them.
- `dev/registry/newmodelo/tests/test_manager.py`, mock removal and identity-based repair;
  teeth proven by neutering `reset_conformance_cache()` in production (1 failed, 3 passed) and
  restoring (14 passed, `git diff` empty).
- `_DECLARED` populations measured against the live tree; both failures reproduced against the
  original `.importlinter` to establish pre-existence.
- `just check-style` red at HEAD at 10:22 (9 errors: 7 `I001`, 2 `TID251`, 1 `E501`), 10:39
  (`I001`, `SIM300`), 12:15 (2 `RUF043`).

## Recommendations

Extend the family's stated scope from assertions to **verdicts**: any code that converts a
gate's output into a pass/fail claim is in scope, whether it is an `assert` or a parser. The
accepted decision's own reasoning supports this -- it warns against generalising from a list
of forms to a claim about the family, which is the error the tautology scanner's boundary
claim made and measurement refuted.

Add the decidable class this finding names: a containment or suffix test against a gate output
grammar that admits a suffix. Hold it to the decision's three-part standard -- sweeps the real
tree, ships a positive control, ships an anti-vacuity floor -- like every other detector.

Bring `_DECLARED` to the sanctioned declaration pattern or remove it, using the two drift
tests as the acceptance condition. This is `W08.P26.S118`'s mechanism applied to a second
census, and that step's shape can be reused rather than re-derived.
