---
tags:
  - '#adr'
  - '#iva-franquicia-2026-scope'
date: '2026-07-01'
modified: '2026-07-17'
related:
  - "[[2026-07-01-iva-franquicia-2026-scope-research]]"
---

# `iva-franquicia-2026-scope` adr: defer modelling the IVA régimen de franquicia until Spanish transposition | (**status:** `accepted`)

## Problem Statement

Directiva (UE) 2020/285 establishes an EU small-business VAT exemption (régimen de
franquicia) letting qualifying small enterprises not charge output IVA below a
turnover threshold. Issue #350 asked whether and how to model it for the 2026
campaign. The question is whether to ship an active `franquicia` régimen now.

## Considerations

The régimen de franquicia is **not in force in Spain**. Spain missed the
31/12/2024 transposition deadline, received a dictamen motivado (17/07/2025), was
referred to the CJEU (11/03/2026), and Hacienda has signalled it may not apply the
franquicia to domestic operations at all (prioritising the existing régimen
simplificado and recargo de equivalencia, working only on the cross-border
€100.000 leg). At HEAD the feature is entirely absent: no `IVARegime.FRANQUICIA`,
no turnover/`volumen_operaciones` axis on the IVA profile, no registry régimen.

## Considered options

1. **Ship the enum slice now** — add `IVARegime.FRANQUICIA` and exclude it from
   `_IVA_SELF_ASSESSMENT_REGIMES` so M303/M390 auto-resolve NOT_APPLICABLE.
   Structurally clean, no formula-graph change.
2. **Full régimen modelling now** — turnover axis + enrolment + threshold-crossing
   mid-year transfer + non-repercusión + input-IVA non-deduction. XL, ADR-gated.
3. **Defer** — publish the research, keep #350's tracking follow-up, ship nothing
   until Spain transposes.

## Constraints

`aeat-safety-legal-gates` (do not invent legal behaviour; ground in BOE/AEAT) and
`no-silent-under-declaration` (a taxpayer must not silently drop a real filing
obligation) are the binding constraints. The Directive caps the national threshold
at €85.000 and sets the Union-wide threshold at €100.000, but Spain's enacted
national figure and effective date are **unconfirmed because unenacted** (the
widely-cited "€85.000 para autónomos" is the EU cap / a non-binding Congreso PNL).

## Implementation

Decision: **Option 3 (defer).** Ship no active franquicia behaviour. The research
is published (`2026-07-01-iva-franquicia-2026-scope-research`) and a transposition
tracking follow-up is open (#588). The eventual design, gated on a confirmed BOE
transposition with a real effective date, national threshold, and
domestic-vs-cross-border scope, is Option 1's lever: `IVARegime.FRANQUICIA`
excluded from `_IVA_SELF_ASSESSMENT_REGIMES` in
`domain/calculations/registry/_applicability.py`, plus a turnover axis and
`franquicia_enrolled` flag on the IVA profile.

## Rationale

Option 1 was rejected for now: exposing a `--iva-regime franquicia` enrolment for a
régimen not in force in Spanish law invents legal behaviour and would let a
taxpayer silently drop a real M303 obligation — a direct collision with the two
binding constraints. The enum value would be a code-referenced identifier with no
registry or legal backing. Option 2 is premature for the same reason and depends on
profile state that does not exist. Deferral honours #350's own Definition of Done
("Si no activa: issue se cierra con la investigación publicada + follow-up issue
para tracking de la activación").

## Consequences

- #350 is closed via its research-only branch; #588 tracks the transposition watch.
- No franquicia code ships; M303/M390 continue to apply normally to all taxpayers,
  which is correct while the régimen is not in force.
- When Spain transposes, this ADR is superseded by an implementation ADR that fixes
  the enacted threshold, effective date, and scope, then lands the Option 1 lever.
