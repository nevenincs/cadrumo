---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S01'
related:
  - '[[2026-05-26-schema-hardening-m131-fragmentation-plan]]'
---

# `schema-hardening-m131-fragmentation` `P01.S01`

Inventoried Modelo 131 revision-file section boundaries and selected a
mechanical split strategy before touching registry TOML data.

- Created: `.vault/audit/2026-05-26-schema-hardening-m131-fragmentation-inventory.md`
- Created: `.vault/plan/2026-05-26-schema-hardening-m131-fragmentation-plan.md`

## Description

The inventory confirmed that M131 remains a generic directory-mode modelo with
four revision files and no revision-fragment directories. The next edit can use
the existing loader-supported shape: `revisions/<id>/revision.toml` plus
section fragments beneath the revision directory.

The split strategy keeps each contiguous section run separate and numbered.
That avoids semantic merging and preserves later append-only casilla, binding,
and formula blocks exactly as source-adjacent fragments.

## Tests

Validation completed:

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-26-schema-hardening-m131-fragmentation-plan.md`
- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-05-26-schema-hardening-m131-fragmentation-plan.md`
