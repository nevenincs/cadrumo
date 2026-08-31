---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:66fa5d593b51e365d45a8d3b43b930a614940fa35e5e6c0376a3e81e15863f31'
step_id: 'S148'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# `ci-lane-deconflation` execution record: `P05.S148`

## Scope

- `P05.S148`

## Changes

- `M` `src/cadrumo/application/ledger/evidence.py`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S148.md`

## Notes

- `uv run --no-sync ruff check src/cadrumo/application/ledger/evidence.py` emitted `All checks passed!` (exit 0).
- `uv run --no-sync ruff format --check src/cadrumo/application/ledger/evidence.py` emitted `1 file would be reformatted` for CRLF normalization at the S148 helper and call sites (exit 1).
- `uv run --no-sync pytest --collect-only -q src/cadrumo/application/ledger/tests/test_evidence.py` and its target run both stopped during conftest import (exit 4): peer-owned `src/cadrumo/application/calculations/_bienes_inversion_regularizacion.py:52` has an attempted relative import beyond the top-level package.
- The exact AST budget probe measured `src/cadrumo/application/ledger/evidence.py::add` at 179 lines against the default callable limit 180 (exit 0). The repository-wide callable ratchet reported 20 other live offenders, beginning with `evidence_draft.py::confirm_invoice_draft_from_evidence` at 199 lines; no threshold or baseline was changed.
- Initial S148 commit `4b3d118585` accidentally captured the peer-owned clock-import hunk while staging the shared source file. A newer shared documentation commit `bf3aa52c688` made the authorized immediate amend unsafe. The compensating repair restores the committed import to `from ...core.time import now as _utc_now` while retaining the peer's `_clock` import in the worktree. The immutable aggregate proof command is `git diff 4b3d118585^..HEAD -- src/cadrumo/application/ledger/evidence.py`: it retains the helper/call extraction and contains no `core.time` import transition.
