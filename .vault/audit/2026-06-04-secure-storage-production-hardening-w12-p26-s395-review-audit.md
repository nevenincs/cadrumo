---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S395]]'
---

# `secure-storage-production-hardening` `W12.P26.S395` Review

## S395-001 | PASS | Locale manager stays inside catalogue maintenance

`src/aeat/locales/manager.py` owns locale YAML loading, strict duplicate-key parsing, key discovery, scaffold reconciliation, and single-leaf set/remove operations. It does not manage secure-object repositories, active-profile buckets, master-key material, or application data storage.

## S395-002 | PASS | Exceptions and diagnostics follow project conventions

`LocaleError` derives from `AeatError`. Invalid locale codes, path traversal, missing keys, namespace writes/removes, duplicate YAML keys, and malformed edit targets raise typed `LocaleError` failures. OSError during codebase key scanning is logged at debug level before the scanner continues, and scaffold parse fallback logs a warning before rebuilding from an empty mapping.

## S395-003 | PASS | Write paths are constrained

The single-leaf write helpers resolve locale codes through `_locale_path()`, constrain writes to existing locale files under `locales_dir`, and preserve YAML layout instead of writing arbitrary paths. The tests exercise real temporary YAML files for set, append, remove, and traversal rejection without mocks or monkeypatches.

## S395-004 | PASS | Locale catalog was reconciled through the CLI

The full parity test exposed four live keys that the manager scan requires: two filed-capture CLI help strings and two modelo work-address error-registry strings. They were added to all supported locales through `python -m aeat.locales set`. Subsequent canonical audit reconciliation retained the live `create_stub_modelo_*` work-creation refusal keys and removed the stale `relation_not_decimal` leaf; the final audit returned clean.

## S395-005 | PASS | Duplication review

Vaultspec RAG semantic search clustered the slice with `LocaleManager` set/remove helpers, strict YAML loading, the locale CLI, and parity tests. The manager remains the central owner for `_covered_by_namespace`, `set_locale_value()`, and `remove_locale_value()`; the CLI imports those behaviors rather than duplicating them.

## S395-006 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/locales/manager.py src/aeat/locales/test_parity.py`
- `uv run --no-sync pytest -q src/aeat/locales/test_parity.py`
- `PYTHONPATH=src uv run --no-sync -q python -m aeat.locales audit`
- `uvx vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md`

Disposition: close `AFR-293`.
