---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S375'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S375 app-live runtime boundary

## Scope

- `src/aeat/entrypoints/cli/_app_live.py`
- `src/aeat/entrypoints/cli/_app_live_payloads.py`
- Focused live IVA, live filed-capture, and live read-subgroup tests
- Locale catalogue audit via `python -m aeat.locales`

## Description

- Audited the app-live CLI boundary against the `runtime-default` target for `secure-object`, `active-profile`, `manifest-bucket`, and `plain-file` signals.
- Confirmed `_app_live.py` has no direct `SecureObjectRepository` construction and no direct `os.environ` or `os.getenv` access.
- Confirmed bucket-bound local read commands resolve the active bucket through `require_active_bucket_id`, while live capture commands delegate to application services that own active-profile runtime repository construction.
- Confirmed IVA wallet pull/history/capture-history/capture-remote-state command payloads remain registered through `_app_live_payloads.py`.
- Repaired live and workflow locale drift through the mandated `python -m aeat.locales set` CLI path while validating the locale catalogue; a stale-key removal attempt correctly reported that the audited path was not a literal YAML leaf, and the final locale audit passed in the shared worktree.
- Validated the focused live/IVA CLI and application test slice.

## Outcome

- AFR-273 closed: `_app_live.py` is an orchestration boundary over application live services and does not introduce an independent storage runtime path.
- The plan checkbox was closed through `vaultspec-core vault plan step check` for `S375`; the AFR-273 register row was reconciled to `closed`.
- Validation passed: focused ruff, focused live/IVA pytest slice, and locale audit via `python -m aeat.locales audit`.

## Notes

- `src/aeat/application/live/__init__.py` and adjacent live tests remain dirty from concurrent live IVA work and were validated but intentionally not staged by this step.
- Workflow/modelo resume files and locale files remain dirty from concurrent modelo-addressing work; locale audit drift caused by those changes was reconciled through the locale CLI validation path, but no workflow/modelo code or locale files were staged by this step.
- `vaultspec-rag search` timed out twice on port 8766 during this closure, so semantic RAG evidence was not available for the final S375 record.
