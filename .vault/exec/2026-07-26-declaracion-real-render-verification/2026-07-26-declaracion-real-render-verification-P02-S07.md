---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
step_id: 'S07'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
---

# Sweep route R8 across all 29 profiles, intersecting profile targets with formula-declaring casillas to find targets the engine refuses as inputs

## Scope

- `src/cadrumo/_data/registry/aeat/modelos`
- `.vault/audit`

## Description

- Parsed every revision fragmented `formulas/` subdirectory with
  `tomllib` and built the `target_casilla_id` set per (modelo,
  revision).
- Intersected each of the 29 profile `target_casillas` id lists
  against its own revision formula-target set.
- Read `_DECLARATION_CASILLA_RECONCILE_MODELOS` and its docstring in
  `application/modelo/_reconcile.py` and cross-referenced the 20
  profiles carrying an intersection against the six enrolled modelos.
- Checked the docstring stated exclusion reasons for the modelos
  outside the enrolled set against the live registry.

## Outcome

Confirmed 20 of 29 profiles target at least one casilla the engine
also computes by formula, ranging from 0.07 to 0.95 of a profile
targets. Cross-referencing against the reconcile module enrolled set
(M100, M111, M130, M190, M303, M390) splits the 20 into 11
profiles belonging to enrolled modelos, where the intersection is the
designed input to the reconcile arbitration, and 9 profiles (115,
both 123 revisions, all three 131 revisions, 180, 193, 202)
belonging to modelos outside the enrolled set, where a reconcile
attempt is refused cleanly today rather than silently mishandled.
The governing ADR declaracion-real-render-verification now records
this same nine-profile scope in its Constraints section as a
non-live defect deliberately left undecided pending its own evidence,
which this measurement made possible to state exactly.

Also found: the enrolled-set docstring gives Modelo 202 as an example
of a modelo with no declaracion_pdf surface at all, which is false --
Modelo 202 carries one (2025-y-siguientes, 4 targets, 2
formula-computed). Modelo 200, the docstring other example, is
correctly described. This is out of the report-only grant for this
audit to fix and is recorded as a first-class finding and
recommendation instead.

Findings and full detail: see the specimen-less static route audit
document for this feature, sections
r8-formula-computed-targets-are-widespread-not-modelo-303-specific,
r8-six-modelos-are-enrolled-in-the-reconcile-arbitration-the-rest-
are-not, and r8-reconcile-docstring-misstates-modelo-202-
declaracion-pdf-surface.

## Notes

None. This axis was not named in the original dispatch brief; it
surfaced from the sweep itself and was reported as a new finding
rather than folded silently into R3/R4.
