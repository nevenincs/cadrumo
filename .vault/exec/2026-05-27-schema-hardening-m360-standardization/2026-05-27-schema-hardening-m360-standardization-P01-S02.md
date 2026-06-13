---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m360-standardization-plan]]'
---



# `schema-hardening-m360-standardization` `P01.S02`

Mechanically split Modelo 360 from a root-level single TOML file into the
generic directory/fragments layout.

- Deleted: `360.toml`
- Created: `360/manifest.toml`
- Created: `360/revisions/2010-y-siguientes/revision.toml`
- Created 9 ordered revision section fragments under `360/revisions/2010-y-siguientes/`

## Description

The split preserved the exact line order and bytes of the original Modelo 360
registry source. The mechanical split script reconstructed all generated
fragments in source order and compared the result with the original `360.toml`
bytes before deleting the single-file source.

No schema semantics, loader behavior, casilla definitions, parameters,
references, application links, schedule metadata, deadline windows,
refund-operation row bindings, or construct membership were changed.

## Tests

Verification is recorded in S03. This step's pre-test guard was the
byte-for-byte reconstruction check before deleting `360.toml`.
