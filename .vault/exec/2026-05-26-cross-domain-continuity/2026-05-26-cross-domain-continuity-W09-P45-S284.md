---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-01'
modified: '2026-07-17'
body_hash: 'sha256:04794b593a977115c00a8cdda25a174c17f4f50a78c6385cc7b21197a3d350bd'
step_id: 'S284'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# HARDCODED_USER_STRING sweep S98 follow-up: route diagnostics/secure_objects.py:42-43 BadParameter via tr()

## Scope

- `plus locales/cli.py lines 38 40 42 44 62 (missing/extra/ok labels + scaffold-updated message) via tr()`
- `plus entrypoints/cli/__init__.py:130 version echo via tr()`
- `plus application/wizard/_commands.py:800-804 profile/status/next tab labels via tr()`
- `src/aeat/`

## Description

- Ground S284 with RAG against the open cross-domain plan row and current locale/wizard/version implementations.
- Verify the retired `aeat.diagnostics` secure-objects target is absent and not reintroduced.
- Verify `locales/cli.py` already routes audit drift labels and scaffold-updated output through locale keys.
- Preserve bare `aeat --version` as intentional machine-format semver output with its existing rationale.
- Localize live wizard success text labels for profile, active profile, and next-step rows through existing `application.wizard.output_labels.*` keys.
- Preserve JSON wizard payload keys and next-step notice shape.
- Update focused application and CLI tests to assert locale-derived text labels instead of hardcoded wizard-row literals.
- Run a scoped code review after implementation; the reviewer reported no findings.

## Outcome

S284 is closed. The live residual in `application/wizard/_commands.py` now renders all wizard success text labels through `tr()`: `profile`, `status`, create-only `active_profile`, and `next`. The stale portions of the row remain intentionally untouched: the retired `aeat.diagnostics` package is absent, locale CLI audit/scaffold output was already localized, and the root version fast path stays machine-format rather than operator text.

## Notes

Validation:

- `uvx vaultspec-rag search "W09 P45 S284 diagnostics secure_objects locales cli version echo wizard status tab labels tr" --type vault --doc-type plan` returned the S284 plan row.
- `uvx vaultspec-rag search "secure_objects BadParameter locales cli missing extra ok scaffold updated version echo wizard profile status next tr" --type code` returned current localized locale CLI and wizard patterns.
- `uv run --no-sync pytest src/aeat/application/wizard/tests/test_commands.py src/aeat/application/wizard/tests/test_commands_output.py -q` passed with five tests.
- `uv run --no-sync pytest -m integration src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py::test_config_profile_create_second_profile_uses_requested_identity_while_first_is_active src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py::test_config_profile_create_quiet_emits_confirmation src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py::test_config_profile_edit_quiet_emits_updated_confirmation src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py::test_legal_entity_profile_creates_non_interactively_without_spouse_flags src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py::test_non_resident_irnr_create_guides_to_m210_discovery_not_work_create -q` passed with five tests.
- `uv run --no-sync ruff check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/tests/test_commands.py src/aeat/application/wizard/tests/test_commands_output.py src/aeat/entrypoints/cli/tests/test_profile_lifecycle_verbs.py src/aeat/entrypoints/cli/tests/test_profile_create_taxpayer_type_paths.py` passed.
- `git diff --check` passed for the S284 path set, with only an existing CRLF normalization warning on `src/aeat/application/wizard/_commands.py`.

Notes:

- Curie implemented the code/test patch.
- Reviewer Chandrasekhar reported no findings and confirmed JSON result keys and notice shape were preserved.
- Curie also attempted the unrelated custody subprocess test `test_profile_create_provisions_file_custody_and_unlock_reopens_it`; it failed before output-label assertions because that path now refuses missing `--entity-type` and `--surnames`. The failure was not caused by S284 and no custody test files were changed.
