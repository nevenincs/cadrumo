---
tags:
  - '#audit'
  - '#registry-m100-2025-row-width'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-m100-2025-row-width-plan]]'
---

# `registry-m100-2025-row-width` audit: `target inventory`

## Scope

Inventory the remaining M100 2025 registry TOML rows above 520 characters.

## Clean targets

- `100/revisions/2025/casillas/0615-0549.toml:7`: 528-character `legal_refs`
  array.
- `100/revisions/2025/casillas/0619-0553.toml:9`: 526-character `legal_refs`
  array.
- `100/revisions/2025/casillas/0628-0562.toml:9`: 526-character `legal_refs`
  array.
- `100/revisions/2025/casillas/0629-0563.toml:9`: 526-character `legal_refs`
  array.

`git diff --` for these four target files is empty.

## Exclusions

The shared worktree still carries unrelated dirty M100 completeness fragments:

- `100/revisions/2024/completeness/0004-casillas.part-003.toml`
- `100/revisions/2025/completeness/casillas-0569-1607.toml`

Those files are not row-width targets and must not be edited by this plan.

## Formatting contract

S02 may wrap only the four top-level `legal_refs` arrays listed above. It must
preserve every legal reference id and original ordering, then prove parsed TOML
and loaded M100 equality before commit.
