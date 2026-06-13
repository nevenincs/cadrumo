---
tags:
  - '#exec'
  - '#secure-object-integrity'
date: '2026-05-22'
modified: '2026-05-22'
step_id: 'S16'
related:
  - '[[2026-05-22-secure-object-integrity-attribution-plan]]'
---




# `secure-object-integrity` `P05.S16`

Ran the final mandatory secure-object-integrity review, resolved the high blockers it found, and persisted the re-review audit showing no critical or high blockers remain.

- Modified: `src/aeat/application/repair_integrity.py`
- Modified: `src/aeat/application/test_repair_integrity.py`
- Modified: `src/aeat/application/diagnostics.py`
- Modified: `src/aeat/application/test_diagnostics.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Modified: `src/aeat/entrypoints/cli/test_repair_privacy_contract.py`
- Modified: `src/aeat/tests/secure_sql.py`
- Modified: `src/aeat/tests/test_secure_sql.py`
- Modified: `src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `.vault/audit/2026-05-22-secure-object-integrity-P05-S16-review.md`

## Description

The first final review found three high blockers. The non-dry-run quarantine path still allowed active secure-object archive/delete after `--yes`, unreadable-row origin attribution still emitted placeholder values, and the touched secure-SQL verification surface accepted pytest monkeypatch isolation as a clean pattern.

The remediation made non-dry-run quarantine preserve-first and fail-closed at both CLI and application layers. `config repair quarantine --yes` now refuses active quarantine and tells the operator to use dry-run preview and integrity attribution; `quarantine_unreadable_secure_objects()` also raises under the preserve-first policy. Tests prove the destructive path creates no quarantine archive table and leaves rows in `secure_objects`.

Unreadable-row attribution now derives `likely_origin` and `origin_confidence` from safe namespace and key-context metadata. Coverage distinguishes classified tax evidence keychain or restore mismatch, classified repository mismatch, explicit test namespace residue, unregistered namespace storage-routing fault, and missing active-profile bucket context without printing private natural keys.

The touched secure-SQL isolation helper and privacy tests now use direct `os.environ` save/restore with engine disposal instead of pytest monkeypatch. The hygiene guard recognizes direct temporary `AEAT_DATABASE_URL` assignment as the clean pattern and keeps legacy monkeypatch-based files in the explicit P02.S06 backlog classification rather than accepting them as clean.

The new quarantine refusal locale key was created with `uv run python -m aeat.locales scaffold` and translated in English, Spanish, Catalan, and Hungarian. The final S16 re-review appended resolution entries to the audit and found no remaining critical or high blockers.

## Tests

Focused gates passed after remediation:

- `uv run ruff check` over the scoped remediation files.
- `uv run python -m aeat.locales audit`
- `uv run python -m aeat.locales scaffold --check`
- `uv run pytest src/aeat/locales/test_parity.py src/aeat/locales/test_locale_translation_honesty.py -q`
- `uv run pytest src/aeat/application/test_repair_integrity.py src/aeat/application/test_diagnostics.py -q`
- `uv run pytest src/aeat/adapters/persistence/storage/test_ephemeral_key_hygiene.py src/aeat/tests/test_secure_sql.py src/aeat/core/test_storage_route_classification.py src/aeat/entrypoints/cli/test_root_fallback_write_guard.py src/aeat/entrypoints/cli/test_repair_bootstrap_exempt.py src/aeat/entrypoints/cli/test_repair_privacy_contract.py -q`
- `uv run pytest src/aeat/domain/calculations/registry/test_referential_integrity.py -q`
- `uv run aeat --format json app registry verify --registry-root src/aeat/_data/registry/aeat --source-root src/aeat/_data`

Mandatory final review and re-review are persisted in `2026-05-22-secure-object-integrity-P05-S16-review`; no critical or high blockers remain.
