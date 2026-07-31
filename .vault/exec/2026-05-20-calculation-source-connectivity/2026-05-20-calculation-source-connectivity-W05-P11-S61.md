---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:99392296ea08ecc3f8d0713af37857d837c577e75df0ce5d768616506cf4bca2'
step_id: 'S61'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Run hardening pass for silent zero and missing source diagnostics

## Scope

- `src/aeat/domain/calculations/registry`

## Description

- Run the silent-zero / missing-source-diagnostics hardening pass and re-confirm the enrollment gate GREEN on the settled registry.

## Outcome

PASS — 9/9 green on the settled registry with NO `RegistryLoadError`. Every declared binding source is enrolled, explicitly deferred, or manual; no source-backed binding can silently calculate zero (the `no-dormant-source-resolvers` + `no-silent-under-declaration` invariants hold). This is the MANDATORY settle-window re-confirm that closes the campaign honesty-gate — a genuine green on a settled tree, not the churn-contaminated red seen during the concurrent modelo-145 export write. No hardening gap surfaced; no code fix required.

## Notes

The silent-zero hardening is structurally enforced by the enrollment + missing-source gate; this step verified it holds on the settled registry. Closes the calculation-source-connectivity campaign honesty-review.
