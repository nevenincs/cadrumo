---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:c8aaa1ff43e86230202cac6aab0e8b1aab4d5fb2b7e3f823db88750895bd564c'
step_id: 'S279'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
---

# Decide and record which canonical public producer answers each Workspace capability and what disposition each admission yields, since the governing record rules that a capability answer is copied from its canonical producer and that absence of a producer or measurement is unmeasured rather than available, without naming the capability-to-producer mapping; rule explicitly whether an admission that structurally excludes a contributor yields not-applicable or unmeasured, amend the governing registry-api-gate decision record in the same change, and prove no capability is inferred from schema population, layout presence, lifecycle state or a neighbouring capability

## Scope

- `the amended 2026-08-24-tui-registry-api-gate-adr`
- `src/cadrumo/application/modelo/workspace.py capability projection`
- `and focused per-admission capability disposition tests`

## Changes

- `M` `.vault/adr/2026-08-24-tui-registry-api-gate-adr.md`
- `M` `src/cadrumo/application/modelo/workspace.py`
- `M` `src/cadrumo/application/modelo/tests/test_workspace.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_workspace.py -m integration -q` -> `pass` (13 passed)
- `verify:` `uv run --no-sync ty check src/cadrumo/application/modelo/workspace.py src/cadrumo/application/modelo/tests/test_workspace.py` -> `pass`

## Notes

Derived the capability-to-producer mapping from the ADR's own existing text
rather than name-matching the capability enum: "static inspection captures
exactly registry, work, locale_catalogue, and field_manifest; it does not
read bounded_review, calculation, readiness, or closure" gives four excluded
contributors against the four non-schema capabilities by elimination.
`calculation_materialization` and the closure report's named `filing-export`
limb are exact string/name matches, needing no inference at all;
`verification_readiness` -> `bounded_review` and `filing_draft_readiness` ->
`readiness` are grounded in each contributor's own described role
(`ModeloWorkReview` as the verification-tracking projection;
`ProjectionModeloReadiness`'s axes as the pre-filing-draft preflight gate).
`schema_inspection` -> `field_manifest` is declared but its disposition stays
provisional on the separate, still-open `W03.P20.S278` question.

Reopened and corrected this Step's own earlier-accepted disposition:
`a3db12320e` (this same Step's prior partial) had `STATIC_INSPECTION`'s four
excluded capabilities as `NOT_APPLICABLE`, reasoned from
`RegistryRevisionInspection`'s docstring ("cannot calculate, render, or file
anything"). That reasoning answers "can this admission ever produce the
fact," not what the disposition enum encodes ("did this read's canonical
producer answer"). The ADR's own rule -- absence of a producer or measurement
is `unmeasured`, never available -- covers an admission that structurally
never invokes a contributor exactly as it covers a graded producer that ran
and declined; the ADR amendment states this explicitly and reserves
`not_applicable` for the latter, narrower case (a producer that ran and
declared the target-specific fact inapplicable).

Added a direct anti-inference test: `static_inspection_modelo_workspace_capabilities`
returns byte-identical capability rows whether or not a work unit exists,
proving no disposition leaks from `work_state`, `review_status`, or a
neighbouring capability, per the Step's own proof requirement.

GRADED_SNAPSHOT's runtime disposition computation (reading each producer's
real verdict into `available`/`refused`/`not_applicable`) is deliberately
untouched -- this Step decides the mapping and the disposition-category rule,
both admission-agnostic; computing an actual graded verdict is
GRADED_SNAPSHOT assembly work, tracked separately, not part of this Step's
scope.
