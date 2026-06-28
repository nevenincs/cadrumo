---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-manual-ledger-storage-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-ledger-transaction-management-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-event-history-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-app-review-queue-execution-adr]]'
  - '[[2026-05-13-cli-workflow-redesign-profile-output-language-adr]]'
---



# `cli-workflow-redesign` Code Review

Status: REVISION REQUIRED

S1826-001 | HIGH | Planned ledger `read` command is not exposed
`W61.P305.S1826` requires ledger read, list, status, and tracking commands under `aeat app ledger`. The backend read service exists as `get_manual_transaction` and is exported from `src/aeat/application/ledger/__init__.py`, but `src/aeat/entrypoints/cli/_ledger.py` registers only `create`, `list`, `status`, `track`, `import`, and `review`. `src/aeat/entrypoints/cli/test_cli_surface.py` exercises `list`, `status`, and `track`, but it has no negative or positive assertion for `aeat app ledger read`. Operators therefore cannot perform the planned single-row read through the canonical S1826 surface. Falling back to `track` changes the command meaning to audit lineage, and falling back to `review --id` preserves a review-shaped path rather than the planned ledger read lifecycle command.

S1826-002 | HIGH | Output-language fallback contradicts the profile-owned language ADR
The accepted profile output-language ADR specifies this precedence: `AEAT_OUTPUT_LANGUAGE`, active profile `output.language`, then the settings default, with no profile value falling through to Spanish. The implementation in `src/aeat/core/i18n/_render.py` documents and returns English as the clean-install fallback, and `src/aeat/core/config.py` sets `aeat_output_language` to `en`. `src/aeat/core/i18n/test_output_language.py` locks this in through `test_clean_install_defaults_to_english`. That makes clean installs and unsupported profile-language fallback render English despite the ADR and wizard setup default using Spanish. This is a user-visible precedence regression in the low-level resolver.

S1826-003 | MEDIUM | Output-language resolver is not fully fail-soft for unreadable workflow state
The profile language lookup in `src/aeat/core/i18n/_render.py` catches `OSError`, `ValueError`, `KeyError`, `AttributeError`, and `ImportError`, but `WorkflowStateRepository.load()` can raise `WorkflowError`, `ClassificationError`, and `EnvelopeVersionError` for malformed envelopes, classification mismatches, and unsupported envelope versions. The error-registry resolver in `src/aeat/core/errors/_registry.py` also catches only `ValueError`, `OSError`, and `AttributeError`. Those exceptions can therefore escape translation or error rendering instead of falling back to settings, contrary to the ADR requirement that malformed profile state and storage read problems be read-only and fail-soft.

S1826-004 | MEDIUM | Locale catalogue parity is broken
The requested locale verification fails. `src/aeat/locales/test_parity.py::test_codebase_to_locale_parity` reports every locale file missing `aggregation.iva_ledger.errors.bucket_mismatch`, `aggregation.modelo_bindings.errors.unsupported_period`, and `aggregation.renta_ledger.errors.bucket_mismatch`, while carrying extra unused `access_gate.errors.default_translatable`, `cli.ledger.errors.row_not_found`, and `cli.ledger.labels.fields` keys. The stale ledger keys line up with an incomplete read/show surface, and the missing aggregation keys mean locale rendering can fall back to raw keys for code paths now present in the worktree.

Verification:

- `uv run pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/core/i18n/test_output_language.py src/aeat/locales/test_parity.py` did not start because `.venv/Scripts/aeat.exe` was locked by another process.
- `.venv\Scripts\python.exe -m pytest src/aeat/application/ledger/test_actions.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/core/i18n/test_output_language.py src/aeat/locales/test_parity.py` ran 56 tests: 55 passed, 1 failed in `src/aeat/locales/test_parity.py::test_codebase_to_locale_parity`.
- `.venv\Scripts\python.exe -m aeat.locales audit` confirmed the exact missing and extra locale keys listed above.
- `.venv\Scripts\python.exe -m pytest src/aeat/entrypoints/cli/test_cli_surface.py::test_app_ledger_create_manual_transaction_persists_in_active_bucket` passed.

## Re-review 2026-05-14

Status: CLEAN FOR S1826 PRIOR FINDINGS

All prior audit findings are resolved for the requested S1826 scope.

S1826-001 is resolved. `aeat app ledger read` is registered in `src/aeat/entrypoints/cli/_ledger.py`, delegates to `get_manual_transaction`, renders through `_emit`, and is exercised by `src/aeat/entrypoints/cli/test_cli_surface.py` alongside `list`, `status`, and `track`.

S1826-002 is resolved. `src/aeat/core/config.py` now defaults `aeat_output_language` to `es`, `src/aeat/core/i18n/_render.py` resolves precedence as environment override, active profile `output.language`, then settings default, and `src/aeat/core/i18n/test_output_language.py` now asserts clean installs default to Spanish.

S1826-003 is resolved. `src/aeat/core/i18n/_render.py` and `src/aeat/core/errors/_registry.py` now fail soft on output-language resolution failures by catching broad resolution exceptions and falling back to `es`, preserving error rendering for malformed or unreadable workflow state.

S1826-004 is resolved. The locale catalogue now includes the previously missing aggregation keys and no longer reports the stale ledger/access-gate extras in the locale audit.

Verification:

- `uv run ruff check` was blocked by locked `.venv/Scripts/aeat.exe`.
- `.venv\Scripts\python.exe -m ruff check` ran and is rejected for full-repo verification because it reports 72 pre-existing or out-of-scope lint findings outside the S1826 focus, including `_label_regex.py`, AEAT auth/browser tests, storage helpers, registry imports, and unrelated Google/modelo tests.
- `.venv\Scripts\python.exe -m ty check` ran and is rejected for full-repo verification because it reports 77 pre-existing or out-of-scope diagnostics in Google OAuth and modelo external-evidence tests.
- `.venv\Scripts\python.exe -m aeat.locales audit` passed: `ca.yml`, `en.yml`, `es.yml`, and `hu.yml` all reported `ok`.
- `.venv\Scripts\python.exe -m pytest src/aeat/application/ledger/test_actions.py src/aeat/domain/buckets/test_event_catalogue.py src/aeat/entrypoints/cli/test_cli_surface.py src/aeat/core/i18n/test_output_language.py src/aeat/entrypoints/cli/test_profile_output_language.py src/aeat/core/errors/test_registry.py src/aeat/locales/test_parity.py` collected and passed 84 tests.
