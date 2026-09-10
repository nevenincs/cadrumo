---
tags:
  - '#audit'
  - '#facts-registry'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:6cf19ac4e9fb7bfa29670913969739956d40af5259bec02bac1b9ce8370804f5'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---



# `facts-registry` audit: `s69 migrated legal parameter gate`

## Scope

Audited S69's cross-slice closure gate for facts replacing the retired legal-parameter provider: Article 101, Article 95 rates and selectors, Articles 109/110 selectors, Article 161 surcharge rates, and Article 31/DT 32 objective-estimation exclusions. The audit reviewed the live fact compiler and resolver path, not the unavailable serialized authority artifact.

## Findings

No CRITICAL, HIGH, MEDIUM, or LOW finding was identified in the S69 gate itself. The gate establishes presence of all migrated identities, filing-period selection, cited source-backed temporal coverage, real change-boundary resolution, and refusal before grounded windows. Its mutation probe detects both deletion of a migrated fact and substitution of a non-filing date axis.

### s69-migrated-legal-parameter-gate | high | The new closure gate is test-only and never reaches registry validation

`migrated_legal_parameter_fact_failures` is declared in `facts/validation.py`, but `governed_fact_catalogue_failures` returns before it is invoked. The staged deletion of `_validate.py` also removes the only registry-validation caller of the general catalogue gate in this worktree; there is no relocated validator calling the new function. Thus an omitted migrated identity, a non-filing axis, a temporal gap, or uncited applicability can pass the production validation path. The focused test calls the new function directly, which proves its local behavior but not enforcement. This contradicts S69's requirement to enforce the invariant and the ADR's fail-closed authority boundary.

### concurrent-relocation-collection-block | medium | General pytest collection cannot currently load the registry fixture graph

The normal combined pytest command fails before test collection because the concurrent compiler relocation removed `registry._source_evidence_fingerprint` while `registry._validate` still imports it. The S69 suite passed under the scoped dev-registry collector, which executes the canonical compiler and resolver but does not load the unrelated registry fixture graph. This is not evidence that the whole repository suite passes.

## Recommendations

Re-run the ordinary focused pytest command after the compiler-relocation import boundary is restored, then conduct the required independent code review before checking S69. Do not relax the gate or introduce a compatibility import to work around the relocation.
