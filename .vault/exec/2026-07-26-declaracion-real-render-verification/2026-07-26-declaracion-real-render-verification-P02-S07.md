---
tags:
  - '#exec'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
body_hash: 'sha256:70c37629708f544fa07e7e4c9a0dfded93923545a8e1fc058b1dfa2b43ccc9b9'
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
belonging to modelos outside the enrolled set. At the time this Step
closed, the claim that this refuses cleanly rather than silently
mishandling the value rested on the enrolled-set docstring's own
stated behaviour, not on independently reading the function body --
and the governing ADR was cited back here as though it independently
confirmed the same claim, which was circular, since the ADR had
adopted it from this campaign's own then-unverified wording. A
companion research audit (r8-arbitration-enrollment-readiness) has
since read _require_declaration_enrolled_modelo directly and confirmed
the refusal fires before parse_declaracion is invoked and before any
file opens; that companion document, not this sentence, is the actual
grounding now. The nine-profile scope named here remains this Step's
own measurement.

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
