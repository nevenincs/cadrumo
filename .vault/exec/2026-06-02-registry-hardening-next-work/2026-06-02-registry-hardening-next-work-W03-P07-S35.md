---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S35'
related:
  - '[[2026-06-02-registry-hardening-next-work-plan]]'
---

# `schema-hardening` `W03.P07.S35` step record

Scope: `W03.P07.S35` - Audit current committed registry TOML file-size and row-width headroom.

## Description

- Scan committed registry TOML files under the modelos data directory.
- Record largest-file and widest-row measurements.
- Identify current soft-band pressure candidates.
- Recommend post-fragmentation gate thresholds for the next step.

## Outcome

The committed corpus has 15,345 TOML files, no files above 1,500 lines, and no rows above 600 characters. The remaining largest file is M123 2024-and-later `revision.toml` at 1,218 lines, and the widest row is 572 characters.

## Notes

No production code, schema, loader, validation, or registry data was changed in this step.
