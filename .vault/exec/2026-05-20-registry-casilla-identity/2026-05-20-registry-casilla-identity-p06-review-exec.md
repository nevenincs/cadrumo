---
tags:
  - '#exec'
  - '#registry-casilla-identity'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - '[[2026-05-20-registry-casilla-identity-plan]]'
  - '[[2026-05-20-registry-casilla-identity-adr]]'
  - '[[2026-05-20-registry-casilla-identity-research]]'
---

# `registry-casilla-identity` P06 Code Review

Holistic safety, intent, and quality audit of Phase P06 — the
calculation-completeness gate refocus — covering Steps S26 through S30
across `_validate.py`, `_schema.py`, `_record_design.py`,
`test_referential_integrity.py`, and `test_record_design.py`.

## Status: PASS

No CRITICAL or HIGH findings. One MEDIUM finding (dead local in the
calculation-closure helper) was identified during review and fixed in a
follow-up commit before sign-off. The phase is safe to merge.

## Scope

Audited commits: the P06.S26-S30 commits plus the review follow-up.
Concurrent non-`#476` commits in the shared worktree were excluded from
scope. The audit verified the implementation against the ADR amendment
of 2026-05-20, which is the authority for the gate refocus.

## Safety Domain

- **No crash paths introduced.** `_emit_completeness_gate_failures`
  short-circuits on a null manifest, then iterates a validated tuple;
  dict `.get` returns `None` for an absent identity and is handled
  explicitly. `calculation_closure_numbers` walks only validated typed
  collections and guards every selector access with `isinstance`.
- **No import cycle.** `_record_design.py` now imports `_runtime_graph`
  and `ModeloRevision`; the intra-package import graph remains a DAG
  (`_record_design` -> `{_runtime_graph, _schema, _errors}`,
  `_runtime_graph` -> `_schema`). Verified by AST inspection.
- **No resource leaks.** The off-load-path derivations reuse the
  existing cached `extract_record_design` reader; no new handles.
- **Rollout safety holds.** Every P06 code path is dormant when a
  revision carries no `completeness_manifest`: the gate returns early,
  and the derivations are off-load-path. All 26 modelos load valid
  (confirmed by `test_modelo_parity_coverage` green after every Step).

## Intent Domain

- **S26 gate semantics correct.** `_emit_completeness_gate_failures`
  implements `manifest-required ⊆ declared`: it iterates
  `manifest.casillas`, keys declared casillas by `(segmento, number)`,
  emits a missing-casilla failure when no casilla sits at the manifest
  identity, and emits grounding failures when the declared casilla has
  empty `legal_refs` / `source_refs`. The `declared == manifest`
  extra-casilla branch is removed — a declared casilla absent from the
  manifest no longer fails, exactly as the amendment requires.
- **S27 schema rename correct.** `DisenoCompletenessManifest` /
  `DisenoCompletenessCasilla` renamed to `CalculationCompleteness*`;
  shape unchanged; docstrings and validator-error strings rewritten to
  the calculation-completeness contract. No stale `DisenoCompleteness`
  references remain anywhere in `src/aeat/`.
- **S28 closure derivation complete.** `calculation_closure_numbers`
  covers all four ADR-amendment surfaces: formula targets, formula-
  expression casilla references (via the runtime-graph walker), binding
  and relation endpoint casillas, and verification-expectation operands.
  Computed/bound casilla endpoints are additionally included. Reference
  tokens are normalised to bare numbers; an undeclared token is kept
  verbatim so the Modelo 200 missing-casilla defect class still
  surfaces. The full-Diseño extraction is retained as
  `derive_diseno_coverage_casillas`, the advisory coverage-report
  producer.
- **S29 / S30 tests match the refocused semantics.** The gate tests
  assert subset-plus-identity-plus-grounding behaviour, including the
  inverted extra-accounting-casilla pass test, the mis-segmented fail
  test, and the ungrounded fail test. The drift test re-derives
  calculation-completeness manifests; the coverage test exercises the
  full-Diseño extraction as an advisory inventory; a new test proves the
  calculation closure is a strict, non-empty subset of full-Diseño
  coverage.
- **No plan drift.** No feature beyond the five planned Steps was added.

## Quality Domain

### CLOSURE-001 | MEDIUM | Dead `number_set` local in calculation-closure helper

`calculation_closure_numbers` computed a `number_set` local that was
never read — it was bound and then `del`-eted, with a comment falsely
claiming callers consult it. Dead code violates the source-hygiene rule.
**Resolved during review:** the local and the misleading comment were
removed and `_as_number` simplified to a single `dict.get`; no
behaviour change, closure and coverage tests stayed green.

### Observations (no action required)

- Spanish-stem terminology is respected: the identity field and derived
  rows use `segmento`; `multi_segment` is an infrastructure boolean
  parameter, ADR-conformant.
- The S29 ungrounded-casilla test constructs a `CasillaDefinition` via
  `model_construct` to bypass the schema's non-empty-refs validator and
  reach the gate's defensive grounding branch. This is a legitimate
  real-object technique, not a test escape: `model_construct` yields a
  genuine pydantic instance and the gate's real grounding code executes
  against it. Without it the branch would be untestable, because the
  schema otherwise guarantees non-empty refs. The test is non-tauto-
  logical — it would fail if the grounding branch were removed.
- The gate's `legal_refs` / `source_refs` grounding check is defensive
  for a validly-constructed `CasillaDefinition` (the schema enforces
  `min_length=1`). Retaining it is correct: it is cheap, it enforces the
  ADR-amendment provenance requirement independently of the field
  constraint, and it guards against a future schema relaxation.
- No mocks, skips, xfail markers, or tautological assertions in the P06
  test changes.

## Verification

- `pytest test_modelo_parity_coverage.py test_referential_integrity.py
  test_record_design.py` — 85 tests pass; all 26 modelos load valid;
  the completeness gate stays dormant (no manifests authored yet).
- `ruff check` clean on every touched file.
