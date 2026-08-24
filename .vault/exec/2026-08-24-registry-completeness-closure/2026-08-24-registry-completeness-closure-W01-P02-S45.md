---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:99683d1f0cbe3028dfec95f4f2004968b7463c8872b73b0b22c069527beff437'
step_id: 'S45'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---

# Revalidate connected census claims through live source proof authority at composition time and refuse proof loss or digest mismatch.

## Scope

- `src/cadrumo/application/registry/`

## Description

- Revalidate every connected census row through the live source-connectivity proof authority when composing a closure report.
- Convert a missing, lost, or digest-divergent live proof into an evidence-bearing refused source-connectivity limb.
- Exercise the report boundary against a real encrypted calculation-revision repository, then mutate executable evidence after the initial report.

## Outcome

- Connected claims no longer remain terminal merely because an earlier census load passed live proof validation.
- A changed executable-evidence digest changes the affected source limb from satisfied to refused with an actionable owner disposition.
- Passed focused Ruff, five unit coverage tests, and the real integration digest-drift regression.

## Notes

- The default focused test command selects unit tests and intentionally deselects the real integration proof; the integration test was run explicitly with the integration marker.
