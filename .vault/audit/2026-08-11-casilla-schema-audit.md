---
tags:
  - '#audit'
  - '#casilla-schema'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:d15526c1b060a1db2436860a58485accb98ddaa0ddee0527956c9435e416e00d'
related: []
---
# `casilla-schema` audit: `S09 canonical binding reverse join`

## Scope

Reviewed W02.P03.S09 against the accepted canonical-derivations decision, the campaign plan, research, registry-authority, binding, quality, worktree-safety, and no-legacy rules. The reviewed implementation surface was `casillas_by_binding`, its package-facade export, the rate-box partition and unscreened consumers, and the three direct test modules. The required behavior is an ordered, de-duplicated reverse join whose membership is defined only by `bound_casilla_binding_ids`, including alternate bindings, excluding non-BOUND declarations, and replacing the former private rate-box mapper without introducing another authority.

## Findings

### s09-canonical-binding-reverse-join | medium | S09 was absorbed into unrelated broad commits instead of one atomic step commit

The code is correct, but the delivery history does not satisfy the plan's one-Step-one-atomic-commit rule. The canonical production function, facade export, rate-box retarget, and original tests landed inside `c0fbbb0456`, a 41-file registry/M303 commit containing substantial unrelated work. During this review, the stronger-schema test reconciliation and `_bindings` prose were then absorbed into `174f5acaf4`, whose stated purpose is factoring general-regime IVA profile axes and which also changes eight unrelated application, core, and CLI test files. The current tree is behaviorally sound, but S09 cannot truthfully be represented as one atomic relocation commit and the peer-WIP boundary was crossed.

No code finding was identified. `casillas_by_binding` directly iterates `bound_casilla_binding_ids`; it does not redeclare the BOUND predicate or alternate-binding rule. Its facade object is identical to the canonical implementation. Both rate-box consumers import the canonical function and the former private mapper is absent. The remaining last-write-wins application mapper is explicitly owned by the next planned step, W02.P03.S10, and is not an undeclared S09 duplicate.

The changed tests use real Pydantic schema construction, the bundled registry authority, and production derivations. The BOUND-without-binding and primary-as-alternate cases now truthfully stop at the stronger `CasillaDefinition` boundary rather than manufacturing impossible model instances. Alternate bindings and non-BOUND behavior are exercised directly. The corpus transpose uses the production forward primitive as the canonical oracle; it does not restate the BOUND predicate or binding selection business logic. No fake, stub, mock, patch, monkeypatch, skip, or expected-failure construct appears.

## Verification

- Direct S09 and rate-box modules: 20 passed.
- Facade identity: `registry.casillas_by_binding is _bindings.casillas_by_binding` is true.
- Real corpus probe: 10 ledger-IVA revisions, zero binding-declaring non-BOUND casillas in that consumer population, and five alternate-binding pairs reached by the reverse join.
- Scoped Ruff: passed.
- Scoped BasedPyright: 0 errors, 0 warnings, 0 notes.
- Scoped `git diff --check`: passed.
- Prohibited test-construct scan: no hits.
- Exact-symbol sweep: one production definition, one facade import/export, and canonical consumption in both rate-box paths; the separately planned S10 application mapper remains visible.

## Recommendations

Before lifecycle closure, record the two actual landing commits and the shared-tree absorption explicitly in the S09 execution record or append a formally owned carry-forward through the plan's lifecycle mechanism. Do not rewrite shared history or create a cosmetic compatibility surface. Future step commits must use path-scoped, ownership-verified delivery so the plan can make its atomicity claim honestly.

Verdict: **CHANGES REQUESTED** on delivery integrity. The S09 code and tests pass formal review; lifecycle closure is blocked only by the unrecorded violation of the step's atomic-commit and peer-WIP boundary.

## Finding resolution

### s09-canonical-binding-reverse-join | resolved | delivery violation formally carried forward

The MEDIUM delivery-integrity finding is resolved for lifecycle purposes. The S09 execution record explicitly identifies `c0fbbb0456` as the production/facade/rate-box/original-test landing and `174f5acaf4` as the stronger-schema prose/test reconciliation landing. It admits that this history violates the one-Step-one-atomic-commit convention, explains that rewriting shared history is forbidden, creates no cosmetic replacement commit or compatibility surface, and binds subsequent steps to ownership-verified path-scoped delivery.

The plan marks W02.P03.S09 checked, and `vaultspec-core status casilla-schema` independently resolves it to `2026-08-10-casilla-schema-W02-P03-S09` with `exec_missing = 0`. Both named commit objects and their recorded subjects exist, and scoped `git diff --check` over the plan, execution record, and audit is clean.

This resolution does not revise the historical finding or claim that the commits were atomic. It supplies the formal, auditable carry-forward requested by the recommendation while preserving shared history and the verified current code state.

Final verdict: **PASS.** The S09 implementation, tests, and lifecycle accounting now satisfy the review requirements; no open finding remains.

