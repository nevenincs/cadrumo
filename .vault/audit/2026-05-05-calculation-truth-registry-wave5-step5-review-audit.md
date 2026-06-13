---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-05'
modified: '2026-05-05'
related: []
---

# Modelo 131 2024 And 2025 Revision Review

## Review Scope

- `registry/aeat/modelos/131.toml`
- `src/aeat/domain/calculations/registry/test_committed_registry.py`
- `.vault/plan/2026-05-03-calculation-truth-registry-rebuild-plan.md`

## Findings

- No blocking findings in the focused Modelo 131 revision slice.
- Modelo 131 now has explicit 2019-2023, 2024, 2025, and 2026 revisions instead
  of a single current-only revision.
- The committed behaviour test now proves the runtime selects the correct
  revision for 2019, 2023, 2024, 2025, and 2026 and calculates casillas 04, 06,
  07, 10, 13, and 15 from real registry snapshots.
- Focused Modelo 131 validation passes.

## Residual Risk

- Modelo 131 export remains open: the historical 2019-2023 record design and
  the 2024-and-later DPA/DID structures still require explicit export schema
  work before filing-grade export roundtrips can be enabled.
- Whole-tree registry verification passes after the concurrent Modelo 180
  duplicate IDs were resolved elsewhere in the worktree.
