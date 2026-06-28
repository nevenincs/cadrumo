---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-27'
modified: '2026-05-27'
step_id: 'S02'
related:
  - '[[2026-05-27-schema-hardening-m036-standardization-plan]]'
---



# `schema-hardening-m036-standardization` `P01.S02`

Mechanically split Modelo 036 from a root-level single TOML file into the
generic directory/fragments layout.

- Deleted: `036.toml`
- Created: `036/manifest.toml`
- Created: `036/revisions/2025-02-03-y-siguientes/revision.toml`
- Created 9 ordered revision section fragments under `036/revisions/2025-02-03-y-siguientes/`

## Description

The split preserved the exact line order and bytes of the original Modelo 036
registry source. The mechanical split script reconstructed all generated
fragments in source order and compared the result with the original `036.toml`
bytes before deleting the single-file source.

No schema semantics, loader behavior, casilla definitions, bindings,
application links, schedule metadata, extraction profile fields, construct
membership, or completeness manifest content were changed.

## Tests

Verification is recorded in S03. This step's pre-test guard was the
byte-for-byte reconstruction check before deleting `036.toml`.
