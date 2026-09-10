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

The gate establishes presence of all migrated identities, filing-period selection, cited source-backed temporal coverage, real change-boundary resolution, and refusal before grounded windows. Its mutation probes detect deletion of a migrated fact, substitution of a non-filing date axis, and an internal temporal gap.

### canonical-validator-wiring | high | Initial S69 wiring did not survive the compiler relocation

The initial S69 implementation called the gate through the retiring source-tree validator, which was being relocated. Remediated: `dev.registry.compiler.validator.RegistryValidator` now invokes the gate in its catalogue-validation branch, and a real compiler test supplies compiled facts with one retired-slice identity removed and receives the exact missing-fact diagnostic through that branch. No legacy source-validator import or compatibility path was restored.

### s69-migrated-legal-parameter-gate | high | The new closure gate is test-only and never reaches registry validation

`migrated_legal_parameter_fact_failures` is declared in `facts/validation.py`, but `governed_fact_catalogue_failures` returns before it is invoked. The staged deletion of `_validate.py` also removes the only registry-validation caller of the general catalogue gate in this worktree; there is no relocated validator calling the new function. Thus an omitted migrated identity, a non-filing axis, a temporal gap, or uncited applicability can pass the production validation path. The focused test calls the new function directly, which proves its local behavior but not enforcement. This contradicts S69's requirement to enforce the invariant and the ADR's fail-closed authority boundary.

### concurrent-relocation-collection-block | medium | General pytest collection cannot currently load the registry fixture graph

The normal public `RegistryValidator.validate_registry()` path reaches the S69 catalogue-validation branch but cannot complete its downstream registry-scope pass because the concurrent compiler relocation leaves `registry_scope` importing missing `dev.registry.compiler.bindings`. The S69 suite passed under the scoped dev-registry collector, exercising the canonical compiler, resolver, and validator catalogue branch. This is not evidence that the whole repository suite passes.

## Recommendations

Repair the relocated `registry_scope` binding import, then run the public validator path and conduct the required independent code review before checking S69. Do not relax the gate or introduce a compatibility import to work around the relocation.
