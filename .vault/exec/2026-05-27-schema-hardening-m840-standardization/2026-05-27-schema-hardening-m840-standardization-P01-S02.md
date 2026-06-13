---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m840-standardization-plan]]'
---



# `schema-hardening-m840-standardization` `P01.S02`

Mechanically split Modelo 840 from a root-level single TOML source into the
generic directory/fragments registry layout.

- Deleted: `840.toml`
- Created: `840/manifest.toml`
- Created: `840/revisions/2003-y-siguientes/revision.toml`
- Created: `840/revisions/2003-y-siguientes/casillas/0001-casillas.toml`
- Created: `840/revisions/2003-y-siguientes/workbook_parity_refs/0001-workbook-parity-refs.toml`
- Created: `840/revisions/2003-y-siguientes/live_cross_references/0001-live-cross-references.toml`
- Created: `840/revisions/2003-y-siguientes/application_links/0001-application-links.toml`
- Created: `840/revisions/2003-y-siguientes/filing_schedules/0001-filing-schedules.toml`
- Created: `840/revisions/2003-y-siguientes/extraction_profiles/0001-declaracion-pdf.toml`
- Created: `840/revisions/2003-y-siguientes/constructs/0001-constructs.toml`

## Description

The split preserved the original section order and content exactly before
removing the root-level file. The revision remains `2003-y-siguientes`;
only the storage layout changed. No schema semantics, identifiers, labels,
application links, extraction profile settings, construct definitions, or
loader behavior were normalized while moving the data.

## Tests

The split script rebuilt the original source from the generated fragments
and rejected the edit unless the bytes matched. A second guard compared the
fragment reconstruction against `HEAD` with normalized line endings and
reported `normalized HEAD reconstruction match: True`.
