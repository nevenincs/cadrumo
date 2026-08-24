---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f78708eed7b89d65e5f206382fcd864486c7d626748fba819ca6db05928e2049'
step_id: 'S72'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Make filing-export participation grade-scoped per the accepted ADR, revise closure eligibility so below-filing revisions are not filing refusals, prove a genuinely complete real composed below-grade row when canonical temporal and source evidence support it, and add durable mutation-bite evidence for complete, refused, stale-evidence, below-filing-grade, and cross-limb-disagreement guards

## Scope

- `src/cadrumo/application/registry/`
- `dev/registry/conformance/`

## Description

- Replace below-filing export refusals with an explicit, filing-only `not_applicable` limb state.
- Enforce temporal-grade and filing-participation agreement in the joined closure row model.
- Keep source-connectivity `unmeasured` fail-closed and prove the real Modelo 036 row is blocked only by that canonical evidence gap.
- Add durable real-row mutations proving below-grade participation and filing-grade non-participation are both rejected.
- Scan the live canonical report for a below-filing row whose temporal and source limbs both satisfy before evaluating the named complete outcome.

## Outcome

The bounded grade-scoping implementation is delivered. Below-filing revisions remain visible in the temporal denominator but do not claim filing capability and no longer receive a filing refusal. A `not_applicable` limb is valid only for filing export, carries neither evidence nor refusal, and is accepted by a joined row only when its temporal declaration is below filing grade. The inverse mutation is also refused: filing-grade temporal coverage cannot carry a non-participating filing limb.

The real bundled Modelo 036 revision `2025-02-03-y-siguientes` now composes with validated temporal coverage and `filing_export=not_applicable`. Its canonical source-connectivity limb remains `unmeasured`, so its only row refusal is the source-evidence gap and release remains blocked. Focused Ruff and 20 focused tests passed; the real-row guard test revalidates mutated M036 and M100 payloads and proves both grade/participation contradictions bite.

S72 remains unchecked. The live canonical census scan found zero below-filing revisions with both validated temporal coverage and a satisfied source-connectivity limb. Therefore no genuinely complete real composed below-grade row exists in the current corpus, and this record does not relabel absence as success or substitute a constructed limb.

## Notes

Live scan evidence: load the report through `canonical_live_registry_closure_authorities`, join each row to its declared `RegistryAuthorityGrade`, then select below-`FILING` rows with `temporal_coverage.status == "validated"` and `source_connectivity.outcome == "satisfied"`; the result is `[]`. The missing owner is the canonical source-connectivity census campaign: it must enroll current exact-revision evidence or an ADR-authorized participation rule before S72 can prove the named complete outcome. The existing stale-evidence and cross-limb-disagreement real regressions remain green, but their presence does not close the absent complete outcome. No source-unmeasured behavior was weakened, no fake proof authority or limb was introduced, and S11 remains open for independent reconciliation.
