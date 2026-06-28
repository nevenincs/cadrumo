---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m308-standardization-plan]]'
---



# `schema-hardening-m308-standardization` `P01.S02`

Mechanically split Modelo 308 from a root-level single TOML source into the
generic directory/fragments registry layout.

- Deleted: `308.toml`
- Created: `308/manifest.toml`
- Created: `308/revisions/2009-y-siguientes/revision.toml`
- Created: `308/revisions/2009-y-siguientes/workbook_parity_refs/0001-workbook-parity-refs.toml`
- Created: `308/revisions/2009-y-siguientes/casillas/0001-casillas.toml`
- Created: `308/revisions/2009-y-siguientes/live_cross_references/0001-live-cross-references.toml`
- Created: `308/revisions/2009-y-siguientes/application_links/0001-application-links.toml`
- Created: `308/revisions/2009-y-siguientes/filing_schedules/0001-filing-schedules.toml`
- Created: `308/revisions/2009-y-siguientes/constructs/0001-constructs.toml`

## Description

The split preserved the original section order and content exactly before
removing the root-level file. The revision remains `2009-y-siguientes`;
only the storage layout changed. No schema semantics, identifiers, labels,
application links, extraction behavior, construct definitions, or loader
behavior were normalized while moving the data.

Because this split removes the final committed root-level single-file
modelo, the generic loader regression tests were updated to accept an
all-directory committed corpus while continuing to cover single-file loader
behavior through the existing temporary round-trip fixtures.

## Tests

The split script rebuilt the original source from the generated fragments
and rejected the edit unless the bytes matched. A second guard compared the
fragment reconstruction against `HEAD` with normalized line endings and
reported `normalized HEAD reconstruction match: True`.
