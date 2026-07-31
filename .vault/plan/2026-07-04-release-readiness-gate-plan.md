---
tags:
  - '#plan'
  - '#release-readiness-gate'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:f343e29e848d311bdecaa17374839daf0adcc9dbb5bd9b49b9bfaf807f713bd1'
tier: L1
related:
  - '[[2026-07-04-release-readiness-gate-adr]]'
  - '[[2026-07-06-release-readiness-gate-research]]'
---
# `release-readiness-gate` plan

## Description

Deliver GitHub issue #415 (iteration 23: RC soak, audit-state gate, rollback
path) as read-only gate logic and process documentation, without touching
the actual release/publish surface. `dev/release/readiness.py` checks
version-surface parity, `CHANGELOG.md` sanity, the most recent
packaging-smoke evidence, and (best-effort via `gh`) no open
`priority:P0-blocker` issue, wired into `just release-apply` as a hard
pre-check. `docs/_release_checklist.yaml` machine-validates the RC-soak
window, versioning discipline, hotfix cycle times, and rollback triggers.
`RELEASING.md` documents the RC-soak procedure (local pre-release build,
packaging-smoke matrix, scratch-venv install, 48-72h hold) and the rollback
procedure (revert + tag, PyPI yank, hotfix cycle times); `just
release-rollback` prints that procedure without ever executing it.

## Steps

- [x] `S01` - Implement the release audit-state gate, RC-soak procedure, and rollback procedure per GH issue #415; `dev/release/readiness.py, dev/release/tests/test_readiness.py, docs/_release_checklist.yaml, docs/_release_notes_template.md, justfile, RELEASING.md, src/aeat/tests/test_release_config.py`.

## Parallelization

Single Step; no parallelization applicable.

## Verification

- `uv run --no-sync pytest dev/release/tests src/aeat/tests/test_release_config.py -q`
  passes (25 real-behavior tests, no mocks/stubs).
- `uv run --no-sync ruff check dev/release src/aeat/tests/test_release_config.py`
  and `ruff format --check` pass.
- `uv run --no-sync ty check dev/release` and
  `uv run --no-sync pyright dev/release` pass with zero diagnostics.
- `uv run --no-sync pytest --collect-only -q src/aeat --ignore=src/aeat/entrypoints/mcp/tests`
  collects cleanly (pre-existing `pywintypes` collection error is unrelated,
  environment-caused, and outside this Step's ownership boundary).
- `just release-readiness` runs against the live repository and reports its
  real verdict (confirmed BLOCKED on the genuinely open `priority:P0-blocker`
  issue #116, proving the gate is live, not a stub).
- No outward release action (tag, push, publish) is performed by any new
  surface; `release-rollback` only prints the procedure.
