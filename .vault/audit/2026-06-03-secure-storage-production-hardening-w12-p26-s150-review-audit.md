---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-03-secure-storage-production-hardening-W12-P26-S150]]'
---

# `secure-storage-production-hardening` `W12.P26.S150` Review

## S150-001 | PASS | Path-containment errors now render through locale keys

`PathContainmentError` was registered with `INTEGRITY_STORAGE_PATH_CONTAINMENT`, but callers constructed it with raw English `args`. The core error resolver prefers `translated_message`, then raw `args[0]`, then the registry message key. That meant operator-facing path-containment messages bypassed the existing `tr()` locale surface.

Resolution: `PathContainmentError` now sets `translated_message="errors.integrity.integrity_storage_path_containment"` while preserving the diagnostic `message` argument for legacy `str(error)` and `pytest.raises(..., match=...)` compatibility.

## S150-002 | PASS | Repository-id refusals no longer echo supplied tokens

`safe_repository_id()` previously included the rejected token repr in path-separator and dot-token messages. Those identifiers can contain taxpayer/profile material, so they should not be copied into user-facing or envelope context.

Resolution: refusal messages now name the context and violation class without echoing the token. Structured context carries only `path_context` and `violation`.

## S150-003 | PASS | Plaintext exception remains bounded

The helper still only resolves and validates path shapes. It does not persist sensitive payload data and remains covered by the strict core containment helpers plus the typed storage error family.

Validation:

- `uv run --no-sync pytest -q src/aeat/adapters/persistence/storage/test_path_safety.py src/aeat/adapters/persistence/storage/test_substrate_smoke.py -k "path_safety or path_containment or safe_repository_id"` passed with 25 selected tests.
- `uv run --no-sync ruff check src/aeat/adapters/persistence/storage/_path_safety.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/test_path_safety.py` passed.
- `uv run --no-sync -q python -m aeat.locales audit` passed.
- `git diff --check -- src/aeat/adapters/persistence/storage/_path_safety.py src/aeat/adapters/persistence/storage/errors.py src/aeat/adapters/persistence/storage/test_path_safety.py` passed.
- Case-sensitive touched-file hygiene scan found no direct settings construction, environment access, direct output, suppressing pragmas, fake/stub/monkeypatch markers, skipped/xfail tests, broad exception catches, raw UTF-8 literals, or local `Path("db://secure_objects")` construction.
- Subagent reviewer Archimedes reported no findings. Residual scope note: `PathContainmentError` intentionally preserves diagnostic `args` for compatibility, so future callers must keep path-safety context labels non-sensitive.

Disposition: close `AFR-048` as `plaintext-exception`.
