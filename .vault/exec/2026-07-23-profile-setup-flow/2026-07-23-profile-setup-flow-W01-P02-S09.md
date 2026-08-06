---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:e62c2b1848f34a5afad520a043f5f322491d1176528155bbbf2bb44cda872cca'
step_id: 'S09'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Promote the profile-domain terminology concepts the pages will cite from draft to approved through the Handbook lifecycle

## Scope

- `src/cadrumo/_data/terminology/concepts/`

## Description

- Inventory the Handbook against the setup pages' concept-help axes
  (identity document, censo, censal vehicle, IVA regímenes).
- Verified ALREADY APPROVED and page-citable today: `nif`,
  `modelo-036`, `censo`, `recargo-equivalencia`,
  `iva-recargo-equivalencia`, `iva-regimen-simplificado`.
- Ruled the neighborhood drafts NON-PROMOTABLE: `tema-profile` and
  `tema-regimens` are docs-topic scaffolds, not taxpayer-facing AEAT
  concepts - the glossary-concepts rule forbids approving machinery
  entries, and promoting them would be exactly the mis-enrolment that
  rule guards.
- Ruled against hand-creating new concepts (estimación directa or
  objetiva, situación familiar) ahead of need: the scaffold-preserve
  contract enrols new entries through the Handbook scaffold as drafts,
  never by hand-authored files; enrolment fires when the W03 page
  authoring pins the concrete concept_ids the pages cite.

## Outcome

No lifecycle changes needed or made: the citable approved set exists
today, the approved-only gate on the copy assembler enforces the
discipline at render, and the remaining enrolments ride the Handbook
scaffold alongside the W03 page catalogue.

## Notes

If the W03 pages end up citing a concept absent from the approved set,
the copy assembler's loud unresolved-ref refusal makes that a visible
authoring failure, not a silent gap.
