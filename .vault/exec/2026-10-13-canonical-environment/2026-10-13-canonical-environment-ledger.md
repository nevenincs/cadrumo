---
tags:
  - '#exec'
  - '#canonical-environment'
date: '2026-10-13'
modified: '2026-10-13'
body_schema: 'body-v2'
body_hash: 'sha256:275496012b593c03de767b489f9006724549c36e79e795169c27b5192e6ece96'
related:
  - "[[2026-10-13-canonical-environment-plan]]"
---

<!-- Machine-owned, whole file: `vaultspec-core vault exec log` creates it
     on first use and appends every row; never hand-edit it. Add no
     frontmatter fields. Wiki-links belong in `related:` only.

     ONE ledger per plan, the only execution artifact. Each row's first
     column names its Step. -->

# `canonical-environment` ledger

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

- `S11` `M` `native/cmake/Agent.cmake`
- `S11` `M` `native/CONTRACT.md`
- `S11` `M` `justfile`
- `S11` `M` `dev/provider_catalog/generate.py`
- `S11` `M` `dev/provider_catalog/tests/test_generate.py`
- `S11` `M` `native/desktop/frontend/scripts/agent-catalog-fixture.mjs`
- `S11` `M` `native/desktop/frontend/src/dev/fixtures/agentLanes.generated.ts`
- `S11` `M` `native/desktop/frontend/tests/live/README.md`
- `S11` `M` `native/desktop/frontend/tests/live/attach.live.ts`
- `S11` `M` `native/desktop/frontend/tests/live/fixture.ts`
- `S11` `M` `native/desktop/frontend/tests/live/playwright.config.ts`
- `S11` `verify:` `uv run --no-sync pytest dev/provider_catalog/tests dev/quality/tests/test_no_git_cli.py dev/tests/test_native_build_recipes.py` -> `pass`
- `S11` `verify:` `ruff check and format --check dev/provider_catalog` -> `pass`
- `S11` `verify:` `prettier --check and eslint on scripts/agent-catalog-fixture.mjs tests/live` -> `pass`
- `S11` `verify:` `cmake -P on the real Agent.cmake selector lines: unset, old env name, new env name, missing pyproject, valid -D` -> `pass`
- `S11` `verify:` `node scripts/agent-catalog-fixture.mjs --check with CADRUMO_DEV_AGENT_CHECKOUT` -> `pass`
- `S11` `by:` `rename-lane`

## Notes

- `S11` The lane.py counterpart of the `CADRUMO_DEV_DESKTOP_LIVE_ENDPOINT,` `_ENTRY` and `_RESULTS` rename is owned by package-verification S04; `agent_live.py` `CADRUMO_AGENT_CHECKOUT` is owned by package-verification S03.
- `S11` No full CMake configure was run: build/windows-x64 belongs to the native lane. The selector lines were exercised in script mode instead.
- `S11` agentLanes.generated.ts was regenerated from its generator, so its digest line also moved to the current cadrumo-agent main; the lane data is unchanged.
