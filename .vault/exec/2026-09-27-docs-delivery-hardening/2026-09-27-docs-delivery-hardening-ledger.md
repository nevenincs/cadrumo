---
tags:
  - '#exec'
  - '#docs-delivery-hardening'
date: '2026-09-27'
modified: '2026-09-27'
body_schema: 'body-v2'
body_hash: 'sha256:54bdd166b588ee5a649c41d544a0907f5a86e7019373b773a5800b3554cf2888'
related:
  - "[[2026-09-27-docs-delivery-hardening-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `docs-delivery-hardening` ledger

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

- `S01` `A` `dev/deploy/docs_asset_manifest.py`
- `S01` `A` `dev/deploy/docs_asset_delivery.py`
- `S01` `M` `dev/deploy/r2_objects.py`
- `S01` `A` `dev/deploy/tests/test_docs_asset_delivery.py`
- `S01` `verify:` `Focused publisher tests 7 passed; Ruff and ty` -> `pass`
- `S02` `M` `dev/deploy/docs_static_site.py`
- `S02` `M` `dev/deploy/docs_asset_delivery.py`
- `S02` `M` `dev/deploy/docs_asset_manifest.py`
- `S02` `A` `dev/deploy/docs_delivery_settings.py`
- `S02` `A` `dev/deploy/docs_health.py`
- `S02` `M` `.github/workflows/release.yml`
- `S02` `A` `.github/workflows/docs-health.yml`
- `S02` `M` `RELEASING.md`
- `S02` `M` `dev/deploy/tests/test_docs_asset_delivery.py`
- `S02` `M` `dev/deploy/tests/test_docs_delivery.py`
- `S02` `verify:` `105 unit tests plus 37 integration tests including one registry-race rerun` -> `pass`
- `S02` `verify:` `Ruff, ty, actionlint and zizmor` -> `pass`
- `S02` `M` `dev/deploy/cloudflare_api.py`
- `S02` `D` `dev/deploy/tests/test_docs_worker.py`
- `S02` `D` `worker/docs-site.mjs`
- `S02` `D` `worker/docs-site.test.mjs`
- `S02` `M` `justfile`
- `S02` `M` `dev/tests/test_lane_reachability.py`
- `S02` `A` `.vault/audit/2026-09-27-docs-delivery-hardening-audit.md`
- `S02` `verify:` `Final focused deployment lane 103 tests; Ruff ty actionlint zizmor` -> `pass`

## Notes

- `S02` Six broader reachability failures enumerate an unrelated nested .claude worktree; retained untouched. Native mixed conditional precedence and per-host handshake minimum remain platform limitations.
