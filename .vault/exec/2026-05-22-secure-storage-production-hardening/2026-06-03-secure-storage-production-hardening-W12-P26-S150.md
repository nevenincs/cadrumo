---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S150'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-w12-p26-s150-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S150`

Closed `AFR-048` for the persistence path-safety helpers.

## Description

- Reviewed `src/aeat/adapters/persistence/storage/_path_safety.py` against the `plain-file` scanner signal and `plaintext-exception` target.
- Confirmed the helper remains an accepted plaintext exception: it computes guarded filesystem paths but does not persist sensitive records itself.
- Hardened `PathContainmentError` so operator-facing rendering uses the registered locale key `errors.integrity.integrity_storage_path_containment`.
- Preserved `ValueError` compatibility and diagnostic `args` for legacy callers while adding structured context for the path context and violation class.
- Removed caller-supplied repository-id token echoing from path-separator and dot-token refusal messages.
- Added real error-boundary tests for localized message resolution, structured envelope context, inheritance compatibility, and token non-disclosure.
- Closed `W12.P26.S150` through `vaultspec-core vault plan step check` and aligned the AFR register row to `closed`.

## Outcome

`AFR-048` is closed as `plaintext-exception`.

Validation passed:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_path_safety.py src/aeat/adapters/persistence/storage/test_substrate_smoke.py -k "path_safety or path_containment or safe_repository_id"`
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/_path_safety.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/test_path_safety.py`
- `uv run --no-sync -q python -m aeat.locales audit`
- `git diff --check -- src/aeat/adapters/persistence/storage/_path_safety.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/test_path_safety.py`
- Case-sensitive touched-file hygiene scan found no direct settings construction, environment access, direct output, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, broad exception catches, raw UTF-8 literals, or local `Path("db://secure_objects")` construction.

## Notes

The locale key and registry entry already existed before S150. The defect was that `resolve_error_message()` prefers raw exception args unless `translated_message` is set, so the registered key was bypassed for this error family.
