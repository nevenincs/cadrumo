---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S221'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# R7-001 / W01.P01 follow-up surface critical storage errors in profile language when the active-profile pointer is readable even if the DEK is malformed

## Scope

- `today DEK-decryption failure surfaces in English regardless of profile output_language`
- `src/aeat/`

## Description

- Ground the defect with `vaultspec-rag` against storage readiness, active-bucket pointer resolution, and profile output-language rendering.
- Add a bucket-local `output-language.hint` sidecar path to the storage namespace registry.
- Persist the last supported `preferences.output_language` value into the bucket-local hint when profile records are saved or selected, and clear the hint when no supported language is present.
- Teach the critical storage runtime and active-profile language resolver to read the bucket-local hint when the active pointer is readable but the encrypted profile record cannot be opened.
- Add a named-bucket hint resolver and pin the config profile-readiness error renderer to the failed target bucket's hint when `config switch NAME` fails while opening the target bucket and no explicit output language is active.
- Add real-behavior sidecar round-trip tests and a CLI regression that corrupts the active bucket DEK, then verifies the critical error renders through the profile language hint.
- Add a review-driven CLI regression for active `alpha` in English, target `beta` in Catalan, corrupt target bucket DEK, and failed `config switch beta` rendering through the target bucket's Catalan hint rather than the old active profile language.
- Replace scoped package-root imports with defining-module imports so the S221 changes do not rely on reexports.

## Outcome

- Critical master-key/DEK failures can now render in the active profile language when the active pointer is still readable and the bucket-local hint is present.
- Target-bucket readiness failures during `config switch` now render through the target bucket's hint instead of the previously active profile's language.
- The encrypted profile record remains authoritative; the sidecar stores only a supported output-language code and fails soft on absence, malformed content, or unsupported values.
- Unsupported hint writes do not overwrite a valid existing hint.
- The S221 plan row is closed with focused storage, CLI, and import-provenance coverage.

## Notes

- Validation: `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/_namespace_registry.py src/aeat/adapters/persistence/storage/bucket/_output_language_hint.py src/aeat/adapters/persistence/storage/runtime.py src/aeat/application/user_profile/_language_resolver.py src/aeat/application/user_profile/_profile_repository.py src/aeat/application/user_profile/_repository.py src/aeat/entrypoints/cli/_config/_profile_readiness.py src/aeat/adapters/persistence/storage/bucket/tests/test_output_language_hint.py src/aeat/entrypoints/cli/tests/test_profile_output_language.py`; `uv run --no-sync pytest -m "unit or integration" src/aeat/adapters/persistence/storage/bucket/tests/test_output_language_hint.py src/aeat/entrypoints/cli/tests/test_profile_output_language.py -q`.
- Review loop: the first review identified a target-bucket gap where `config switch beta` could render through the old active profile language after the target bucket failed to open. The final patch pins the render language from the failed target bucket's sidecar hint for that readiness path.
- The malformed-pointer language fallback remains S225; S221 only covers the readable active-pointer plus malformed DEK edge.
