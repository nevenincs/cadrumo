---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:c9fcd01143ba2fe47faa5e14d69f8ce522ecda3abd9efa798b3718864fe6a5d0'
step_id: 'S142'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Refactor the size-budget subjects in _export.py into cohesive siblings without raising any threshold.

## Scope

- `src/cadrumo/application/filing/_export.py`

## Changes

- `M` `src/cadrumo/application/filing/_export.py`
- `A` `src/cadrumo/application/filing/_export_envelope.py`
- `A` `src/cadrumo/application/filing/_export_verification.py`
- `M` `src/cadrumo/application/filing/_export_proof.py`
- `M` `src/cadrumo/application/filing/__init__.py`
- `M` `src/cadrumo/application/filing/tests/test_export_post_write_verification.py`
- `M` `src/cadrumo/application/filing/tests/test_export_value_policy.py`
- `A` `.vault/exec/2026-08-05-ci-lane-deconflation/2026-08-05-ci-lane-deconflation-P05-S142.md`
- `M` `.vault/plan/2026-08-05-ci-lane-deconflation-plan.md`
- `verify:` `uv run --no-sync ruff check src/cadrumo/application/filing/_export.py src/cadrumo/application/filing/_export_envelope.py src/cadrumo/application/filing/_export_verification.py src/cadrumo/application/filing/_export_proof.py src/cadrumo/application/filing/__init__.py src/cadrumo/application/filing/tests/test_export_post_write_verification.py src/cadrumo/application/filing/tests/test_export_value_policy.py` -> `All checks passed!` (exit 0)
- `verify:` `uv run --no-sync ruff format --check src/cadrumo/application/filing/_export.py src/cadrumo/application/filing/_export_envelope.py src/cadrumo/application/filing/_export_verification.py src/cadrumo/application/filing/_export_proof.py src/cadrumo/application/filing/__init__.py src/cadrumo/application/filing/tests/test_export_post_write_verification.py src/cadrumo/application/filing/tests/test_export_value_policy.py` -> `7 files already formatted` (exit 0)
- `verify:` `uv run --no-sync pytest --collect-only -q src/cadrumo/application/filing/tests/test_export_post_write_verification.py src/cadrumo/application/filing/tests/test_export_value_policy.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `39 tests collected in 0.86s` (exit 0; deselected 0)
- `verify:` `uv run --no-sync pytest -q src/cadrumo/application/filing/tests/test_export_post_write_verification.py src/cadrumo/application/filing/tests/test_export_value_policy.py src/cadrumo/application/filing/tests/test_export_semantic_vocabulary.py src/cadrumo/application/filing/tests/test_export_proof_contracts.py` -> `3 failed, 36 passed in 45.09s` (exit 1)
- `verify:` `uv run --no-sync python -c "import cadrumo.application.filing._export as e; import cadrumo.application.filing._export_envelope as n; import cadrumo.application.filing._export_verification as v; import cadrumo.application.filing._export_proof as p; assert e.FilingEnvelopeRenderRequest is n.FilingEnvelopeRenderRequest; assert e.DeclaracionExportResult is v.DeclaracionExportResult; assert p.DeclaracionExportResult is v.DeclaracionExportResult; print('canonical-direct-imports-ok')"` -> `canonical-direct-imports-ok` (exit 0)
- `verify:` `(Get-Content src/cadrumo/application/filing/_export.py).Count; (Get-Content src/cadrumo/application/filing/_export_envelope.py).Count; (Get-Content src/cadrumo/application/filing/_export_verification.py).Count` -> `817`, `310`, `384` (exit 0)

## Notes

- The focused run's three failures are pre-existing registry authority-grade refusals while constructing modelo 200 filing snapshots: `RegistryValidationError: modelo 200 revision 2025-y-siguientes declares 'calculation' authority grade, which cannot satisfy the requested 'filing' snapshot authority.` They occur in `test_export_value_policy.py` before the moved verifier functions execute; the remaining 36 focused tests passed.
- `_export.py` had a peer-owned import-order hunk before S142. It is preserved in the shared worktree and excluded from S142's isolated commit.
