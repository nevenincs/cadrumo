---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S27'
related:
  - "[[2026-06-02-registry-hardening-next-work-plan]]"
---

# Audit M123 revision file for directory-mode fragmentation need

## Scope

- `src/aeat/_data/registry/aeat/modelos/123`

## Description

- Check M123 local diff state before recording any decision.
- Inspect the directory-mode layout under `src/aeat/_data/registry/aeat/modelos/123`.
- Measure fragment line counts and maximum row lengths.
- Identify section-density pressure that would guide a future split.
- Record the no-split decision in the registry M123 fragmentation audit.
- Run vault checks and close P04.S27 through the vault plan CLI.

## Outcome

- M123 already uses directory-mode registry data with one `manifest.toml`, two
  revision directories, and separated completeness manifests.
- No stale `123.toml` sibling exists.
- Largest fragment is `2024-y-siguientes/revision.toml` at 1,218 lines; maximum
  observed row length is 305 characters.
- No registry data was changed. The current shape is below reviewability gates.
- Future M123 growth should split export-layout sections first through the
  generic fragment architecture.

## Notes

- Tests were not run for this step because it is audit-only and made no code or
  registry-data edits.
- Vault checks were run against the new audit feature and the parent
  schema-hardening plan surface before commit.
