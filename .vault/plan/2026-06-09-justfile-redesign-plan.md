---
tags:
  - '#plan'
  - '#justfile-redesign'
date: '2026-06-09'
tier: L1
related:
  - '[[2026-06-09-justfile-redesign-adr]]'
  - '[[2026-06-09-justfile-redesign-research]]'
---


# `justfile-redesign` `implementation` plan

- [x] `S01` - extract complexity calculation heredocs with zero-noise success filtering; `scripts/audit_complexity.py`.
- [x] `S02` - implement programmatic semantic audit checks with silent-on-success assertions; `scripts/audit_semantic.py`.
- [x] `S03` - reconcile docs marker and statement-order test integrity failures; `src/aeat/tests/test_marker_integrity.py`.
- [x] `S04` - relocate test_workbook_parity.py to nested workbook_parity directory; `src/aeat/domain/calculations/registry/tests/workbook_parity/test_workbook_parity.py`.
- [x] `S05` - ignore the relocated workbook_parity directory in pytest options; `pyproject.toml`.
- [x] `S06` - refactor declaracion conftest.py to eliminate wildcard imports; `src/aeat/adapters/inbound/declaracion/tests/conftest.py`.
- [x] `S07` - refactor auth conftest.py to eliminate wildcard imports; `src/aeat/adapters/outbound/aeat/auth/tests/conftest.py`.
- [x] `S08` - refactor sede conftest.py to eliminate wildcard imports; `src/aeat/adapters/outbound/aeat/sede/tests/conftest.py`.
- [x] `S09` - refactor sql conftest.py to eliminate wildcard imports; `src/aeat/adapters/persistence/storage/sql/tests/conftest.py`.
- [x] `S10` - refactor storage conftest.py to eliminate wildcard imports; `src/aeat/adapters/persistence/storage/tests/conftest.py`.
- [x] `S11` - refactor ledger conftest.py to eliminate wildcard imports; `src/aeat/application/ledger/tests/conftest.py`.
- [x] `S12` - refactor modelo conftest.py to eliminate wildcard imports; `src/aeat/application/modelo/tests/conftest.py`.
- [x] `S13` - refactor registry conftest.py to eliminate wildcard imports; `src/aeat/domain/calculations/registry/tests/conftest.py`.
- [x] `S14` - refactor justfile recipes to standardized prefix taxonomy and purge PM metadata comments; `justfile`.
- [x] `S15` - implement RAG service daemon process control recipes; `justfile`.
- [x] `S16` - implement RAG search and index management recipes; `justfile`.
- [x] `S17` - implement static quality check and prek runner wrappers; `justfile`.
- [x] `S18` - update CI workflow step names and just commands; `.github/workflows/ci.yml`.
- [x] `S19` - run local pre-commit and check-all validations to verify harness health; `justfile`.
- [x] `S20` - delete temporary backup file once verification passes; `justfile.bak`.
Redesign the root build harness and project quality checks to enforce naming prefix standards, script separation, verify-only hooks, and programmatic RAG semantic audits.

## Description

This plan implements the build harness and project quality gate redesign authorized by `2026-06-09-justfile-redesign-adr`. It restructures the `just` recipe taxonomy under standardized prefixes, extracts inline python calculations into discrete scripts with zero-noise success filtering, resolves pre-existing pytest marker contradictions, and implements programmatic semantic audits with silent-on-success assertions.

## Steps

## Parallelization

Relocating complexity calculations in `S01`, implementing the semantic checker in `S02`, and resolving test framework contradictions in `S03` can be executed independently. Relocating workbook parity tests in `S04` and ignoring them in `S05` can also run in parallel. Refactoring the sub-level `conftest.py` files in `S06` through `S13` is independent. Refactoring the build harness in `S14` through `S17` depends on the scripts, test fixes, and conftest cleanups being in place. Updating CI workflows in `S18` requires the new harness recipes to exist. Step `S19` executes the complete verification, and `S20` performs the final cleanup.

## Verification

The plan is complete when:
1. The static linter and test suite pass successfully via the new `check-all` command.
2. Programmatic semantic assertions verify the repository without drift or false positives, exiting silently with code 0 on success.
3. The marker integrity checks pass cleanly, and workbook parity runs are isolated and ignored in default runs.
4. Actionable complexity checks exit with zero noise and code 0 when all files satisfy the thresholds.
5. The temporary backup file `justfile.bak` is removed from the directory tree.
6. All execution steps have completed with valid step records.

