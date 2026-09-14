---
tags:
  - '#exec'
  - '#justfile-design'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:dabfc480780052bfaf02ba96abc62b441d6d8787a2ea5aab54849ba73491b39d'
step_id: 'S37'
related:
  - "[[2026-09-11-justfile-design-plan]]"
---

# Implement explicit path-scoped Ruff/ty/format repair, keep prek replay manual-only, reconcile setup claims, and prove Just/CI dispatch

## Scope

- `developer-tooling repair and replay surface`

## Changes

- `M` `.github/ci-contract-allow.txt`
- `M` `.github/workflows/ci-full.yml`
- `M` `.github/workflows/ci.yml`
- `A` `.vault/audit/2026-09-14-justfile-design-pre-commit-repair-review-audit.md`
- `A` `.vault/exec/2026-09-11-justfile-design/2026-09-11-justfile-design-W05-P14-S37.md`
- `M` `.vault/index/justfile-design.index.md`
- `M` `dev/ci/tests/test_ci_workflow.py`
- `M` `dev/init/README.md`
- `M` `dev/init/__main__.py`
- `M` `dev/init/contract.py`
- `D` `dev/init/hooks.py`
- `M` `dev/quality/fixes.py`
- `M` `dev/quality/metadata/import_load_targets.json`
- `A` `dev/quality/tests/test_fixes.py`
- `A` `dev/quality/tests/test_ty_fix_boundary.py`
- `A` `dev/tests/test_precommit_policy.py`
- `M` `justfile`
- `M` `prek.toml`
- `verify:` `uv run --no-sync prek validate-config prek.toml` -> `pass`
- `verify:` `just check-workflows` -> `pass`
- `verify:` `just check-gate-contracts` -> `pass`
- `verify:` `test-ci-contracts focused normal selection` -> `pass`
- `verify:` `repair p95 performance selection` -> `pass`

## Notes

The full `test-ci-contracts` aggregate remains red from concurrent product,
fixture, generated-data, and secure-storage changes outside S37; the focused
blocking selection owned by this step passes. Declared-lane reachability still
reports two unrelated product tests and no longer reports the repair benchmark.
