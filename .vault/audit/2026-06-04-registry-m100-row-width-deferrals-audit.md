---
tags:
  - '#audit'
  - '#registry-m100-row-width-deferrals'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-06-04-registry-m100-row-width-deferrals-plan]]'
  - '[[2026-06-04-registry-row-width-pressure-audit]]'
---

# `registry-m100-row-width-deferrals` audit: `target inventory`

## Scope

Inventory the five M100 rows deferred by the row-width pressure plan and
confirm they are clean before formatting.

## Clean targets

- `100/revisions/2024/completeness/0001-manifest.toml:19`: 552-character
  `legal_refs` array.
- `100/revisions/2023/completeness/0001-manifest.toml:19`: 552-character
  `legal_refs` array.
- `100/revisions/2022/completeness/0001-manifest.toml:19`: 552-character
  `legal_refs` array.
- `100/revisions/2021/completeness/0001-manifest.toml:19`: 552-character
  `legal_refs` array.
- `100/revisions/2020/casillas/0146-0153.toml:7`: 545-character inline
  `constraints` table containing `sign`, `legal_refs`, and `source_refs`.

`git diff --` for these five target files is empty.

## Exclusions

The shared worktree has unrelated dirty M100 completeness fragments:

- `100/revisions/2024/completeness/0004-casillas.part-003.toml`
- `100/revisions/2025/completeness/casillas-0569-1607.toml`

Those files are not row-width targets and must not be edited by this plan.

## Formatting contract

S02 may wrap only the four top-level completeness `legal_refs` arrays and must
prove parsed M100 equality. S03 may convert the inline `constraints` table only
if loaded M100 equality passes against a pre-edit copy. No legal-reference,
source-reference, schema, or loader semantics may change.
