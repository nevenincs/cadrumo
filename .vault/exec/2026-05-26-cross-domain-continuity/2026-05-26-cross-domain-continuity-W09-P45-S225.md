---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S225'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-C pre-profile error language

## Scope

- `when active-profile pointer is malformed the language resolver cannot read output_language and defaults to Spanish`
- `on subsequent runs after restore the message appears in Catalan`
- `either hardcode multi-language critical-error rendering OR cache last-known-language outside the profile envelope OR document the inevitable Spanish-fallback in the error suggestion`
- `src/aeat/`

## Description

- Ground the malformed active-pointer edge with `vaultspec-rag` against pointer IO, settings route derivation, and i18n fallback.
- Keep the no-bucket-id boundary honest: a malformed active-profile pointer cannot identify a trustworthy bucket and therefore cannot read the bucket-local S221 language hint.
- Make i18n output-language resolution fall back to the default language when settings loading raises a core integrity error, so rendering `ActiveProfilePointerError` does not recursively fail.
- Document the pre-profile Spanish fallback in the recovery suggestion for the malformed-pointer error.
- Add a real CLI regression that creates a Catalan profile, corrupts the active-profile pointer, and verifies the malformed-pointer error renders in Spanish with the explicit fallback note.

## Outcome

- Malformed active-profile pointer errors now render cleanly instead of risking a recursive settings/i18n failure during error rendering.
- The operator sees Spanish fallback text and an explicit recovery note that this fallback remains in force until the active-profile pointer is readable.
- The implementation does not infer or guess the Catalan profile language without a readable pointer or bucket id.

## Notes

- Validation: `uv run --no-sync ruff check src/aeat/core/i18n/_render.py src/aeat/core/errors/__init__.py src/aeat/entrypoints/cli/tests/test_profile_malformed_pointer_language.py`; `uv run --no-sync pytest src/aeat/core/i18n/tests/test_render_override.py src/aeat/core/tests/test_storage_route_classification.py -q`; `uv run --no-sync pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_malformed_pointer_language.py -q`; `uv run --no-sync pytest -m "integration and hex_entrypoint" src/aeat/entrypoints/cli/tests/test_profile_output_language.py -q`; `uv run --no-sync pytest -m "unit or integration" src/aeat/adapters/persistence/storage/bucket/tests/test_output_language_hint.py src/aeat/entrypoints/cli/tests/test_profile_output_language.py -q`.
- Review note: the reviewer suggested importing `pointer_path` through `aeat.core`; that was rejected because this campaign requires defining-module imports rather than reexports.
