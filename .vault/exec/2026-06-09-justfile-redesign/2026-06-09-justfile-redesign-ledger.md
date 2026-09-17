---
tags:
  - '#exec'
  - '#justfile-redesign'
date: '2026-06-09'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:4434cc6a418ac2f565fd271abc248b3d1e6f9d990a9052139a96e4bff65fccb3'
related:
  - "[[2026-06-09-justfile-redesign-plan]]"
---

# `justfile-redesign` ledger

## Changes

- `S01` `T` `scripts/audit_complexity.py`
- `S02` `T` `scripts/audit_semantic.py`
- `S03` `T` `src/aeat/tests/test_marker_integrity.py`
- `S03` `T` `src/aeat/tests/test_roundtrip_fixture_saturation.py`
- `S04` `T` `src/aeat/domain/calculations/registry/tests/workbook_parity/test_workbook_parity.py`
- `S04` `T` `src/aeat/domain/calculations/registry/tests/workbook_parity/__init__.py`
- `S05` `T` `pyproject.toml`
- `S06` `T` `src/aeat/adapters/inbound/declaracion/tests/conftest.py`
- `S07` `T` `src/aeat/adapters/outbound/aeat/auth/tests/conftest.py`
- `S08` `T` `src/aeat/adapters/outbound/aeat/sede/tests/conftest.py`
- `S09` `T` `src/aeat/adapters/persistence/storage/sql/tests/conftest.py`
- `S10` `T` `src/aeat/adapters/persistence/storage/tests/conftest.py`
- `S11` `T` `src/aeat/application/ledger/tests/conftest.py`
- `S12` `T` `src/aeat/application/modelo/tests/conftest.py`
- `S13` `T` `src/aeat/domain/calculations/registry/tests/conftest.py`
- `S14` `T` `justfile`
- `S15` `T` `justfile`
- `S16` `T` `justfile`
- `S17` `T` `justfile`
- `S18` `T` `.github/workflows/ci.yml`
- `S19` `T` `justfile`
- `S19` `T` `scripts/audit_complexity.py`
- `S19` `T` `scripts/audit_semantic.py`
- `S19` `T` `pyproject.toml`
- `S20` `T` `justfile.bak`
- `S45` `T`
- `S48` `M` `justfile`
- `S49` `M` `dev/init/README.md`
- `S49` `M` `dev/init/__main__.py`
- `S49` `M` `dev/init/contract.py`
- `S49` `M` `dev/init/plan.py`
- `S49` `M` `dev/init/stamp.py`
- `S49` `M` `dev/EXIT-CODES.md`
- `S50` `M` `.github/workflows/code-health-report.yml`
- `S51` `M` `dev/audit/advisory.py`
- `S51` `M` `dev/audit/security.py`
- `S51` `M` `dev/quality/suite.py`
- `S51` `M` `dev/quality/tests/test_suite_gate_table.py`
- `S52` `M` `CONTRIBUTING.md`
- `S52` `M` `.devcontainer/devcontainer.json`
- `S53` `M` `dev/docs/tests/test_docs_build_localized.py`
- `S53` `M` `dev/quality/tests/test_suite_gate_table.py`
- `S54` `T`
- `S54` `verify:` `uv run --no-sync pytest -q -n0 <focused command-surface tests>` -> `pass`
- `S54` `verify:` `uv run --no-sync ruff check <edited Python files>` -> `pass`
- `S54` `verify:` `just check-workflow` -> `pass`
- `S55` `T`
- `S55` `verify:` `independent Sol reviewer diff audit` -> `pass`
