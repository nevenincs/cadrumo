---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:d76320b5d62d46bc6cda23006c476bea46b1e33ed27606617f2dfa1ead2150fd'
step_id: 'S11'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---




# Re-adjudicate and repair Modelo 193 deadline identity against bundled and official AEAT authority while retaining following-January physical dates

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/193/`

## Description

- Re-adjudicate the 2024 and 2025 annual deadline identities against bundled
  `orden-eha-3377-2011:art-5` and the official AEAT 2025 and 2026 calendars.
- Align each redundant `filing_year` with its annual `Period` tax year while
  preserving the following-January nominal dates.
- Ground each window and containing construct in the deadline article and the
  corresponding official calendar source.
- Add a two-revision regression for tax-year identity, nominal dates, and
  calendar provenance.

## Outcome

Both committed Modelo 193 windows now use the tax year as semantic identity:
the 2024 return retains 1--31 January 2025, and the 2025 return retains 1--31
January 2026. The existing business-day resolver continues to derive 2 February
2026 from the nominal Saturday close without rewriting the legal date.

Focused Modelo 193 and deadline identity tests passed (8 tests), and Ruff passed
for the changed test module. A cold `RegistryValidator` construction is exercised
by the focused tests before snapshot construction.

## Notes

The two `filing_year` corrections were already present as concurrent uncommitted
edits when this step began. They were validated and retained; this step added the
missing source-grounding consistency and regression coverage without duplicating
or reverting concurrent work.
