---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m347-standardization-plan]]'
---



# `schema-hardening-m347-standardization` `P01.S02`

Mechanically split Modelo 347 from a root-level single TOML file into the
generic directory/fragments layout.

- Deleted: `347.toml`
- Created: `347/manifest.toml`
- Created: `347/revisions/2008-y-siguientes/revision.toml`
- Created: `347/revisions/2008-y-siguientes/casillas/0001-casillas.toml`
- Created: `347/revisions/2008-y-siguientes/parameters/0001-threshold.toml`
- Created: `347/revisions/2008-y-siguientes/workbook_parity_refs/0001-record-designs.toml`
- Created: `347/revisions/2008-y-siguientes/live_cross_references/0001-surfaces.toml`
- Created: `347/revisions/2008-y-siguientes/application_links/0001-links.toml`
- Created: `347/revisions/2008-y-siguientes/filing_schedules/0001-anual.toml`
- Created: `347/revisions/2008-y-siguientes/deadline_windows/0001-2018-2026.toml`
- Created: `347/revisions/2008-y-siguientes/extraction_profiles/0001-declaracion-pdf.toml`
- Created: `347/revisions/2008-y-siguientes/constructs/0001-informative.toml`

## Description

The split preserved the exact line order and bytes of the original Modelo 347
registry source. The mechanical split script reconstructed all generated
fragments in source order and compared the result with the original `347.toml`
bytes before deleting the single-file source.

No schema semantics, loader behavior, casilla definitions, parameters,
references, schedule windows, extraction profile fields, or construct
membership lists were changed.

## Tests

Verification is recorded in S03. This step's pre-test guard was the
byte-for-byte reconstruction check before deleting `347.toml`.
