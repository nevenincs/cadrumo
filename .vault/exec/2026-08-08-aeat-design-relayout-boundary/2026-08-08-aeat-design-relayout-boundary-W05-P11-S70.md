---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:4c52f469e38f23f7703189a54acd20674cfd20920f67933f12b4f90dc1033554'
step_id: 'S70'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
  - "[[2026-08-13-aeat-design-relayout-boundary-audit]]"
---

# Record in the campaign audit document that Modelo 200 filing years 2022 and 2023 sit inside the prescripcion window while no registry revision claims them, so they refuse today as a coverage gap rather than as a mis-write, and state that this campaign deliberately does not close that gap because its standing goal is that no filing year is written at wrong offsets rather than that every reachable year is served

## Scope

- `.vault/audit/`

## Description

- Confirmed at HEAD that Modelo 200 carries exactly one revision directory,
  whose `period_selector` starts at ejercicio 2024, leaving ejercicio 2022
  and 2023 unclaimed.
- Ran the production revision-selection path against Modelo 200 for
  ejercicio 2022 and 2023, period `0A`, and captured the refusal verbatim.
- Wrote the finding into the campaign audit document, naming the gap by
  ejercicio rather than by filing year.

## Outcome

Recorded in the campaign audit document under the finding
`modelo-200-ejercicio-gap-2022-2023`: Modelo 200 ejercicios 2022 and 2023
sit inside the prescripcion-reachable window while no registry revision
claims them (the axis is the ejercicio, the fiscal year reported, not the
calendar year of filing). They refuse today through
`ValidatedRegistryAuthority.snapshot` as a coverage gap — no revision
candidate at all — rather than as a mis-write at wrong offsets, which is the
defect class this campaign closes. Verified against HEAD:

    ejercicio 2022: REFUSED -- modelo 200: no revision for year=2022 period='0A' revision=None
    ejercicio 2023: REFUSED -- modelo 200: no revision for year=2023 period='0A' revision=None

This campaign deliberately does not close that gap. Its standing goal is
that no filing year is written at wrong offsets, not that every reachable
year is served, and authoring a Modelo 200 revision for ejercicios 2022–2023
is new registry-authoring work outside this campaign's Waves.

## Notes

None.
