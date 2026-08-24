---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:8ccd04c1f19a5304f492a5f78af37f32fc2cb3f9e9868b73e9b567256a07c825'
step_id: 'S10'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---




# Re-adjudicate and repair Modelo 190 deadline identity against bundled and official AEAT authority while retaining following-January physical dates

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/190/`

## Description

- Re-adjudicate the 2024 and 2025 annual deadline identities from bundled legal and official-calendar evidence.
- Align each redundant `filing_year` with its canonical `Period.filing_year` tax year.
- Retain the following-January statutory opening and nominal closing dates unchanged.
- Replace the 2024 window's non-timing article citation with the plazo authority and propagate that required legal reference to its construct.
- Update focused assertions to prove tax-year identity independently from physical filing dates and holiday shifting.

## Outcome

Both Modelo 190 windows now identify the exercise they report: `2024 0A` is keyed by
2024 while physically filing from 1 through 31 January 2025, and `2025 0A` is keyed by
2025 while physically filing from 1 through 31 January 2026. The latter remains stored
at the nominal statutory month-end; the existing holiday resolver derives the published
Monday 2 February 2026 operational close.

Bundled `orden-eha-3127-2009:art-5` states that Modelo 190 reports amounts for the
immediately preceding year and establishes the 1-to-31-January electronic filing span.
Bundled official source `aeat-calendario-contribuyente-2025` lists Modelo 190 under
"Resumen anual 2024" through 31 January. Bundled official source
`aeat-calendario-contribuyente-2026-hasta-2-febrero` lists Modelo 190 under "Resumen
anual 2025" through 2 February, corroborating the existing weekend shift without
changing the nominal statutory close stored by the registry.

Focused verification passed: all seven Modelo 190 registry tests, Ruff for the focused
test module, and a cold bundled-authority construction.

## Notes

The following-calendar AEAT sources are evidence for adjudication but are not added to
the 2024 revision's source set: revision-scoped source applicability is keyed to the tax
year, so a source beginning in 2025 is intentionally rejected for a revision ending in
2024. No dates were speculated or changed.
