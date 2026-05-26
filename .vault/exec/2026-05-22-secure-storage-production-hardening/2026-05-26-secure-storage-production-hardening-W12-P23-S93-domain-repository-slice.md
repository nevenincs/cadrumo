---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-05-26'
step_id: 'S93'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

<!-- DO NOT add 'Related:', 'tags:', 'date:', or other frontmatter fields
     outside the YAML frontmatter above -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline `code`. -->

# `secure-storage-production-hardening` `W12.P23.S93` Domain Repository Slice

Moved another S93 domain persistence slice from explicit SQL route setup onto the sanctioned runtime-profile helper.

## Changes

- Replaced the transaction repository test's manual `Settings(aeat_database_url=...)`, injected engine, and direct `SecureObjectRepository(engine=...)` setup with `isolated_runtime_profile`.
- Replaced the transaction roundtrip tests' hand-built active session, explicit engine creation, and direct SQL mutation with `isolated_runtime_profile` plus runtime-owned `profile.repository.load/save` mutation.
- Replaced the attachment repository tests' autouse `AEAT_DATABASE_URL` monkeypatch and manual ephemeral key provider setup with `isolated_runtime_profile`.
- Replaced the justificante repository tests' autouse `AEAT_DATABASE_URL` monkeypatch, manual secret-store override, and raw default secure-object classification seeding with the runtime-profile repository.
- Replaced the submission repository tests' autouse `AEAT_DATABASE_URL` monkeypatch, manual secret-store override, and raw default secure-object classification seeding with the runtime-profile repository.
- Tightened the transaction anti-tautology proof from a broad `except Exception` sentinel to an explicit `ValidationError` assertion.
- Replaced the transaction anti-tautology payload mutation with runtime-owned `profile.repository.load/save`.
- Replaced usage-ratio corruption seeding with `profile.repository` writes and tightened the malformed JSON proof to assert the `ValidationError` root cause and message.
- Replaced modelo anti-tautology direct engine/ORM mutation with runtime-owned `profile.repository.load/save` mutation for calculation revisions, filing records, work units, and verification reports.
- Removed broad exception sentinels from the modelo anti-tautology proofs; invariant failures now assert explicit `ValidationError` where the model boundary must reject, or strict inequality where a dropped defaultable field must surface.

## Validation

- `uv run --no-sync pytest src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/attachments/test_repository.py src/aeat/domain/justificante/test_repository.py src/aeat/tests/test_secure_sql.py -q` - 27 passed.
- `uv run --no-sync ruff check src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/attachments/test_repository.py src/aeat/domain/justificante/test_repository.py` - passed.
- `uv run --no-sync pytest src/aeat/domain/submission/test_repository.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/attachments/test_repository.py src/aeat/domain/justificante/test_repository.py src/aeat/tests/test_secure_sql.py -q` - 46 passed.
- `uv run --no-sync ruff check src/aeat/domain/submission/test_repository.py src/aeat/domain/transactions/test_repository.py src/aeat/domain/transactions/test_repository_roundtrip.py src/aeat/domain/attachments/test_repository.py src/aeat/domain/justificante/test_repository.py` - passed.
- `uv run --no-sync pytest src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/usage_ratios/test_service.py src/aeat/tests/test_secure_sql.py -q` - 22 passed.
- `uv run --no-sync ruff check src/aeat/domain/modelos/test_calculation_repository_roundtrip.py src/aeat/domain/modelos/test_filing_record_repository_roundtrip.py src/aeat/domain/modelos/test_secure_storage_roundtrip.py src/aeat/domain/modelos/test_verification_report_roundtrip.py src/aeat/domain/usage_ratios/test_service.py` - passed.
- `rg -n "AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(|monkeypatch|except Exception|pragma: no cover|noqa|type: ignore\[no-untyped-def\]" ...domain slice...` - no matches.
- `rg -n "get_engine|session_scope|SecureObjectRow|AEAT_DATABASE_URL|aeat_database_url|create_engine_from_settings|SecureObjectRepository\(|EphemeralMasterKeyProvider|monkeypatch|except Exception|pragma: no cover|noqa|type: ignore\[no-untyped-def\]" ...combined migrated slice...` - no matches.
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-22-secure-storage-production-hardening-refactor-plan.md` - passed.

## Review

The `vaultspec-code-reviewer` review found no issues in the domain repository slice. A later reviewer pass found direct ORM mutation and a weak malformed JSON assertion in the modelo/usage slice; both were fixed and re-reviewed with no findings. S93 remains open because the plan row covers the broader `src/aeat` migration, and additional non-refusal explicit database setup sites remain outside this slice.
