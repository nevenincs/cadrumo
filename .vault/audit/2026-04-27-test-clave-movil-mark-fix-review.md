---
tags:
  - '#audit'
  - '#test-clave-movil-mark-fix'
date: '2026-04-27'
related:
  - '[[2026-04-27-test-clave-movil-mark-fix-plan]]'
  - '[[2026-04-27-test-clave-movil-mark-fix-adr]]'
---

# `test-clave-movil-mark-fix` Code Review

No findings recorded yet. Formal review runs after verification commands complete.

LOCK-001 | HIGH | Remove unrelated `vaultspec-rag` lockfile upgrade
`uv.lock:3083` upgrades `vaultspec-rag` from `0.2.3` to `0.2.4`, and `uv.lock:3088` adds `packaging` to that package's resolved dependencies. The research, ADR, plan, and execution summary describe a marker-only test change plus vault records; they do not justify a dependency-resolution change. This expands the merge surface for issue 436 and should be reverted or explicitly justified before merge. Status: REVISION REQUIRED.

Review verification notes: `src/aeat/auth/test_clave_movil.py` carries module-level `live_read` and `domain_aeat_remote` markers, the autouse fixture has a return type and docstring, and targeted searches found no stale `--ignore=src/aeat/auth/test_clave_movil.py` references in `justfile`, `.github/workflows`, `docs`, `tests/README.md`, or `.vaultspec/rules`. Source-only default collection reported 14 deselected tests, explicit `live_read` selection with `AEAT_LIVE_TESTS_ENABLED=0` skipped all 14 tests, and explicit `AEAT_LIVE_TESTS_ENABLED=1` ran all 14 tests successfully. No production provider or submission files are changed.

LOCK-001 resolution: reverted the `uv.lock` delta so the dependency graph remains unchanged for issue 436. Status: RESOLVED.
