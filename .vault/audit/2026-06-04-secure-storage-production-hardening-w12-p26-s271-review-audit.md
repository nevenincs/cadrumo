---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-W12-P26-S271]]'
---

# `secure-storage-production-hardening` `W12.P26.S271` Review

## S271-001 | PASS | Test helper delegates to canonical orchestration

`src/aeat/application/user_profile/_testing.py` is a test convenience over
`register_active_profile`, `select_profile`, and `set_active_fields`. It does not create
a fake repository, monkeypatch storage, read environment variables, or write profile
state outside the canonical orchestration path.

## S271-002 | PASS | Shared constants and enums are reused

The helper derives distinct valid NIF values through `nif_check_letter`, uses the core
manual-provenance constant, and uses `IVARegime.GENERAL` instead of re-declaring local
tax identity, provenance, or IVA vocabulary.

## S271-003 | PASS | Duplication and test review

Vaultspec RAG semantic search clustered this helper with real
`register_minimal_profile` call sites, pointer integration tests, output-language tests,
and adjacent profile projection helpers. The helper remains a thin fact seeding layer
over runtime-backed profile registration, not a duplicate persistence backend.

## S271-004 | PASS | Validation

- `uv run --no-sync ruff check src/aeat/application/user_profile/_testing.py src/aeat/application/user_profile/test_orchestration_pointer.py src/aeat/tests/test_output_language.py src/aeat/entrypoints/cli/_config/test_auth_round5_surface.py`
- `uv run --no-sync pytest -q src/aeat/application/user_profile/test_orchestration_pointer.py src/aeat/tests/test_output_language.py`

Disposition: close `AFR-169`.
