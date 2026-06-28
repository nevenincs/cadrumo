---
tags:
  - '#exec'
  - '#schema-hardening'
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'S18'
related:
  - '[[2026-05-22-schema-hardening-plan]]'
---



# `schema-hardening` `P06.S18`

Audited the loader revision-fragment contract across fragmented and
non-fragmented modelos without adding per-modelo schema definitions.

- Reviewed: `src/aeat/domain/calculations/registry/_loader.py`
- Modified: `.vault/plan/2026-05-22-schema-hardening-plan.md`

## Description

The loader remains generic. The only modelo-id handling in `_loader.py` is the
source-discovery key used to reject duplicate layouts; there are no branches for
M100, M200, M303, M349, or any other regulatory modelo.

Discovery evidence from the committed registry:

- M100 is a directory-mode modelo with six `fragment_directory` revisions.
- M200 is a directory-mode modelo with one `fragment_directory` revision.
- M131 is a directory-mode modelo with four `revision_file` revisions.
- M130 remains a `single_file` modelo.
- The committed corpus currently discovers 26 modelo sources: 11 directory
  sources and 15 single-file sources.
- Directory-mode revisions currently include 23 fragment-directory revisions
  and four revision-file revisions.

No loader code change was required. S17 already added the regression gate that
compares discovered fragment paths with the filesystem TOML inventory so this
generic contract is now covered by tests.

## Tests

`rg -n "100|200|303|349|modelo_id|M100|M200|fragment" src/aeat/domain/calculations/registry/_loader.py`
showed no modelo-specific branches.

The loader discovery probe completed successfully and reported the inventory
summarized above.

`uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-05-22-schema-hardening-plan.md`
passed after closing S18.
