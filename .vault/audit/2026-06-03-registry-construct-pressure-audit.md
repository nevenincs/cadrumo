---
tags:
  - '#audit'
  - '#registry-construct-pressure'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-03-registry-construct-pressure-plan]]"
---

# `registry-construct-pressure` audit: `M200 construct fragment split boundary audit`

## Scope

Audit `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records`
for P01.S01. The audit checked local diff state, file-size pressure, construct
fragment shape, and generic loader support before any registry data movement.

## Findings

- PASS: The target records directory has no local diff in the current shared
  worktree.
- PASS: The only remaining line-count pressure file in the directory is
  `constructs.part-002.toml` at 1,465 lines. The next construct files are
  `constructs.part-001.toml` and `constructs.part-001b.toml` at 900 lines each.
- PASS: `constructs.part-002.toml` is line-count pressure only. Its largest row
  is 110 characters, while the wider rows in the records directory are in other
  files.
- PASS: `constructs.part-002.toml` contains one same-id construct fragment for
  `modelo-200-2024-foundation`.
- PASS: The pressure is almost entirely the `casillas` array: line span 3-1427
  with 1,423 item entries. The remaining construct member arrays start at line
  1428 and are small append-only tails.
- PASS: Generic loader support already exists. `_CONSTRUCT_APPEND_ARRAYS` covers
  the construct member arrays used by this file, and `_merge_revision_fragment_field`
  delegates same-id construct arrays through `_merge_table_array_fragments`.
- PASS: Existing coverage includes
  `test_directory_mode_merges_construct_member_fragments_by_construct_id`, which
  verifies that construct membership lists can be split across fragments without
  redeclaring a new construct.

## Recommendations

- Execute P02.S02 as a mechanical split of `constructs.part-002.toml` only.
- Split at a `casillas` item boundary and preserve the original casilla order.
- Replace the current file with a lexically sorted pair such as
  `constructs.part-002a.toml` and `constructs.part-002b.toml` so directory load
  order preserves the original array order.
- Put the remaining casillas plus the small trailing arrays in the second
  fragment. Repeat only the construct table header and
  `id = "modelo-200-2024-foundation"`.
- Do not add loader, schema, inheritance, delta, or modelo-specific behavior for
  this split.
- Verify P02.S02 by comparing the loaded casilla sequence against the committed
  source before the split, then run the construct-fragment merge test, registry
  reviewability tests, and committed registry load tests.

## Codification candidates

No codification candidate from this audit-only step. The governing fragment
architecture and reviewability limits are already tracked by the linked plan and
fragment architecture ADR.
