---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:228f1c4618fd7008c126e0332a93b43c026ac787d80b72dd83f5b327e73794c5'
step_id: 'S178'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S178`

## Scope

- `P05.S178`

## Changes

- `A` `src/cadrumo/core/errors/registry/_application_profile_bundle.py`
- `M` `src/cadrumo/core/errors/registry/_application_part2.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S178.md`

## Notes

- `uv run --no-sync ruff check` on both registry shards emitted `All checks passed!` (exit 0); `ruff format --check` emitted `2 files already formatted` (exit 0).
- The module-size probe measured `_application_part2.py` at 1228 lines against the default 1250 (exit 0); no size baseline or policy changed.
- Registry test collection found 23 nodes (exit 0). The focused run reached `23 passed` / `[100%]`, then its shared plugin teardown did not return an exit to the command wrapper; no source failure was emitted.
- Directly importing registry internals outside the normal bootstrap raises the pre-existing `error_codes`/registry partial-initialization cycle, so mapping verification remains with the normal registry suite.
