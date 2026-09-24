---
tags:
  - '#exec'
  - '#docs-build-performance'
date: '2026-09-24'
modified: '2026-09-24'
body_schema: 'body-v2'
body_hash: 'sha256:a00f599b193fcf0ba3a0da5d28b451c445ca984b2f2ec625517755b4dae7cdb0'
related:
  - "[[2026-09-24-docs-build-performance-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `docs-build-performance` ledger

## Changes

<!-- MECHANICAL LOG, append-only, one row per path touched per Step, written
     by `--row`:
       - `S##` `A` `path`   added
       - `S##` `M` `path`   modified
       - `S##` `D` `path`   deleted
       - `S##` `R` `old` -> `new`   renamed
     Paths are repo-relative, in backticks. No prose: the Step row states the
     intent and the commit carries the diff.

     Optional per-Step rows, written by `--verify` and `--by`:
       - `S##` `verify:` `<command>` -> `pass` | `fail`
       - `S##` `by:` `<persona>`

     Rows are appended in Step order and never rewritten. Only rows in this
     section register a Step as covered. `--note` adds a `## Notes` section
     ONLY on exception (data loss, skipped work, a scaffold left in code, a
     persistent failure), one `S##`-prefixed line each; it is otherwise
     omitted. -->
- `S01` `A` `dev/docs/navigation.py`
- `S01` `A` `dev/docs/tests/test_navigation.py`
- `S01` `M` `docs/conf.py`
- `S01` `verify:` `pytest dev/docs/tests/test_navigation.py` -> `pass`
- `S02` `M` `dev/deploy/docs_static_site.py`
- `S02` `M` `worker/docs-site.mjs`
- `S02` `M` `worker/docs-site.test.mjs`
- `S02` `M` `dev/deploy/tests/test_docs_static_site.py`
- `S02` `M` `dev/deploy/tests/test_docs_delivery.py`
- `S02` `M` `docs/conf.py`
- `S02` `M` `RELEASING.md`
- `S02` `verify:` `node --test worker/docs-site.test.mjs` -> `pass`
- `S03` `M` `dev/docs/sequences/runner.py`
- `S03` `A` `dev/docs/sequences/verdict_cache.py`
- `S03` `A` `dev/docs/sequences/tests/test_verdict_cache.py`
- `S03` `M` `dev/docs/sequence_build_gate.py`
- `S03` `A` `dev/docs/pagefind_service.py`
- `S03` `M` `dev/docs/pagefind_index.py`
- `S03` `M` `dev/docs/pagefind_inject.py`
- `S03` `M` `dev/quality/metadata/import_load_targets.json`
- `S03` `verify:` `pytest dev/docs/sequences/tests` -> `pass`

## Notes

- `S03` Also removed the Pagefind client's per-response sleep: the search pass over every root fell from over 29 min to 101 s.
