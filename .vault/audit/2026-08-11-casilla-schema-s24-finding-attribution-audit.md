---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:1ddcda26b6f6bf179e9216bb03264be553226e25f7bf102eb4fd98a3fb4ba48c'
related:
  - "[[2026-08-10-casilla-schema-plan]]"
---
# `casilla-schema` audit: `S24 finding-to-casilla attribution`

## Scope

Formally reviewed W03.P07.S24 against the accepted read-model ADR, the S23 accepted audit and execution record, the S24 execution record, committed attribution change `3612ed5d74`, and the seven S24 source/test files that subsequently landed in `39a457c7fb`. The review independently censused every production `ModeloVerificationFinding` constructor under `application/modelo`, traced each new attribution to its typed source, adjudicated all remaining record-level omissions including all nine cross-period constructors, checked for duplicate parser or inverse-mapper authority and compatibility surfaces, and reviewed the focused tests against the repository's real-behavior rules.

## Findings

### blocking-predicate-positive-coverage | medium | The new BLOCKING single-casilla attribution branch has no positive regression test

Both the ADVISORY and BLOCKING constructor branches in `_verification_predicates.py` now independently call `_unique_predicate_casilla_id`. The M131 tests positively prove single-casilla attribution only through the ADVISORY branch. The changed BLOCKING test uses a two-casilla expression and correctly asserts record-level `None`, but no test proves that a firing single-casilla BLOCKING predicate carries its canonical id. The BLOCKING constructor could regress to always emit `None` while every S24 focused node remains green. Add a real predicate evaluation test whose one-casilla BLOCKING predicate fires and assert the exact canonical casilla id; retain the existing multi-casilla `None` proof.

### record-level-fixed-point-coverage | medium | Eighteen intentional record-level omissions are narrative-only

The independent AST census confirms the execution record's current fixed point: 33 production constructors across 16 files, 14 with explicit `casilla_id` and 19 omitted. The omitted sites are semantically justified: ledger drift, grouped M210 renta, M303/M349 multi-casilla reconciliation, objective-estimation profile thresholds, transaction-grain cuota/evidence findings, multi-binding OSS evidence, pre-revision snapshot failure, and all nine cross-period dependency/provenance findings lack one canonical target row. However, only the multi-casilla predicate has an explicit `casilla_id is None` assertion. The other 18 adjudications can silently acquire an incorrect target without a red test. Protect the named record-level contracts with real builder behavior tests or a property gate keyed by `(path, enclosing function)` with a written reason and stale-entry failure; do not freeze the total count as a pass condition.

## Recommendations

1. Add a real, firing, one-casilla BLOCKING predicate test that asserts the exact canonical `casilla_id`.
2. Add regression protection for each intentional record-level constructor, using behavior tests where practical and a reasoned, stale-failing `(path, enclosing function)` property gate for the remaining structural cases. Do not gate on the number 19.
3. Retain the implementation boundaries already verified: M100 attribution uses the semantic-role-resolved id; M210 uses the typed unresolved outcome id while scalar-only calls remain record-level; the IVA wallet uses the public canonical compensation casilla constant; predicates reuse the canonical registry parser and attribute only one-casilla expressions; cross-period source casillas are never misrepresented as target review rows; no duplicate parser, inverse mapper, compatibility alias, or wrapper was introduced.

## Verification

- Fresh VaultSpec RAG discovery reached the accepted read-model decision and the production attribution surfaces.
- Independent AST census: 33 production constructors, 14 explicit attributions, 19 intentional omissions; the tally is evidence only, not a test gate.
- Exact focused behavior command: 39 passed in 36.54 seconds on this reviewer's stable rerun.
- A concurrent parent rerun reported 32 passes and 7 registry-fingerprint setup errors while registry files were changing; those setup errors are concurrent-state evidence, not S24 behavioral failures. The executor's earlier stable run also passed all 39 nodes.
- The S24-added assertions contain no fake, stub, mock, patch, monkeypatch, skip, xfail, mirrored business logic, or frozen constructor-count gate.
- Scoped static gates were reported green after formatting normalization.

## Verdict

CHANGES REQUESTED. Production attribution is canonical and single-target wherever assigned, all 19 remaining omissions are presently defensible at record grain, and the implementation introduces no duplicate authority or compatibility surface. S24 should not close until the new BLOCKING single-casilla branch and the intentional record-level fixed point have non-tautological regression coverage.
## Re-review 2026-08-12

### blocking-predicate-positive-coverage-resolution | medium | RESOLVED - a real firing one-casilla BLOCKING predicate now proves attribution

`test_single_casilla_blocking_predicate_attributes_its_canonical_casilla` constructs a valid one-casilla `all_nonzero` `VerificationPredicateDefinition`, sends it through the production `_evaluate_verification_predicates` entry point with a zero value so the BLOCKING branch fires, and asserts blocking kind, blocking severity, and the exact canonical casilla id. The existing two-casilla test continues to prove record-level `None`. The test contains no substitute evaluator, parser, registry mapper, fake, mock, patch, skip, or mirrored business rule.

### record-level-fixed-point-coverage-resolution | medium | RESOLVED - the reasoned ownership gate is structural, stale-failing, and count-free

`test_intentional_record_level_finding_owners_are_reasoned_and_stale_failing` walks the real production AST, derives each constructor's `(relative path, enclosing function)` owner, and observes only whether the constructor supplies the `casilla_id` keyword. The separate human-authored ownership map carries the semantic reason for every deliberate record-level owner. The gate fails on an unexpected omission, a missing or renamed owner, an empty reason, or an expected record-level owner whose constructors gain attribution. It asserts no constructor total, does not encode the number nineteen, and does not reproduce any finding producer's business semantics. The map has eighteen owners because `_missing_evidence_findings` intentionally owns two record-level constructors; this is structural evidence, not a count-based pass condition.

## Re-review verification

- Exact repair nodes: 3 passed in 4.83 seconds.
- Complete `test_s24_precondition_campaign.py`: 7 passed and 1 unrelated locale-authority failure. The failing constructor is `application/calculations/_foreign_asset_redeclaration.py` and the missing catalogue leaf is `application.modelo.findings.foreign_asset_redeclaration` in English; neither belongs to the S24 attribution repair.
- Scoped Ruff check: passed.
- Scoped Ruff format check: 2 files already formatted.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped diff check over the two repair test files: passed.
- Prohibited-test-construct review: no fake, stub, mock, patch, monkeypatch, skip, xfail, mirrored business logic, or exact-count gate was added.

## Final verdict

PASS. Both medium findings are resolved. The positive BLOCKING branch now has real production-path attribution proof, and every intentional record-level ownership decision is protected by a reasoned, stale-failing structural contract without freezing a tally or duplicating business semantics. The remaining full campaign failure is a separately owned English locale-catalogue gap and does not invalidate S24.
