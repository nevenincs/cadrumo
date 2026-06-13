---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-02-secure-storage-production-hardening-w12-p23-s93-cli-ledger-fixture-slice-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P23.S93` CLI Ledger Fixture Slice

## Description

- Remove remaining shortcut fixture remnants from CLI ledger verb tests that already use centralized profile-storage isolation.
- Preserve real CLI command behavior, real profile bootstrap, and persisted repository assertions.

## Changed Surface

- `src/aeat/entrypoints/cli/test_inventory_verbs.py`
- `src/aeat/entrypoints/cli/test_business_invoice_verbs.py`
- `src/aeat/entrypoints/cli/test_ratios_verbs.py`

## Outcome

Closed for this slice.

The three fixtures no longer accept unused `monkeypatch` parameters and no longer call local `dispose_engine()` around centralized `isolated_profile_storage_root` setup. The fixtures still register a real minimal profile through `profile_create_storage_span("default")` before invoking the CLI command surfaces.

## Verification

- `uv run --no-sync pytest -q src/aeat/entrypoints/cli/test_inventory_verbs.py src/aeat/entrypoints/cli/test_business_invoice_verbs.py src/aeat/entrypoints/cli/test_ratios_verbs.py` - 23 passed.
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/test_inventory_verbs.py src/aeat/entrypoints/cli/test_business_invoice_verbs.py src/aeat/entrypoints/cli/test_ratios_verbs.py` - all checks passed.
- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/adapters/persistence/storage/test_hardening_convention_guards.py` - 8 passed.
- `rg -n -F -e "monkeypatch" -e "dispose_engine" -e "AEAT_DATABASE_URL" -e "aeat_database_url" -e "create_engine_from_settings" -e "SecureObjectRepository(engine=" -e "pytest.mark.skip" -e "pytest.mark.xfail" -e "_Fake" -e "_Stub" src/aeat/entrypoints/cli/test_inventory_verbs.py src/aeat/entrypoints/cli/test_business_invoice_verbs.py src/aeat/entrypoints/cli/test_ratios_verbs.py` - no matches.
- `git diff --check -- src/aeat/entrypoints/cli/test_inventory_verbs.py src/aeat/entrypoints/cli/test_business_invoice_verbs.py src/aeat/entrypoints/cli/test_ratios_verbs.py` - no whitespace errors.

## Notes

No HIGH or CRITICAL issue was identified in this slice.

S93 remains open because the row covers the broader `src/aeat` migration. Remaining scan hits include approved low-level route/storage tests and other residual CLI or adapter surfaces outside this bounded fixture cleanup.
