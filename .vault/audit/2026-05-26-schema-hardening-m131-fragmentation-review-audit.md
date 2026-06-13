---
tags:
  - '#audit'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
related:
  - '[[2026-05-26-schema-hardening-m131-fragmentation-plan]]'
  - '[[2026-05-26-schema-hardening-m131-fragmentation-inventory-audit]]'
---

# `schema-hardening-m131-fragmentation` Code Review

M131FRAG-001 | MEDIUM | Fragmentation commit also lands shared-worktree selector bound edits

The M131 split preserved the registry state that was present in the shared
worktree at the moment of splitting. Relative to `42e9cd4dc^`, the fragmented
files also introduce `source_period_offset_from_target = -1` and
`max_year_delta = 0` on the four M131 previous-filing selectors.

Affected paths:

- `src/aeat/_data/registry/aeat/modelos/131/revisions/2019-2023/bindings/0001-bindings.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2024/bindings/0002-bindings.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2025/bindings/0002-bindings.toml`
- `src/aeat/_data/registry/aeat/modelos/131/revisions/2026/bindings/0002-bindings.toml`

Resolution: accepted and documented. The user explicitly allowed
cross-committing in the shared worktree. The fields were not created by a loader
or schema change, and no per-modelo behavior was added. The audit trail now
states that the fields were present in shared-worktree content but first landed
in Git with the fragmentation commit.

M131FRAG-002 | LOW | S02 execution note understated the Git-visible semantic delta

The first S02 record said the selector bound edits were pre-existing. That was
true for the shared worktree but ambiguous for Git history because `42e9cd4dc`
is the first commit that contains those fields.

Resolution: fixed in the S04 closeout commit by updating the S02 record to say
the selector bounds were pre-existing in shared-worktree content and first
committed by the fragmentation commit.

M131FRAG-003 | INFO | Fragment layout and loader behavior pass review

No per-modelo loader or schema behavior was introduced. M131 now discovers as a
directory-mode modelo with four fragment-directory revisions. Focused M131 tests
passed, and the broader registry slice reported 117 passing tests across loader
directory mode, committed registry integrity, referential integrity, and M131
snapshot behavior.
