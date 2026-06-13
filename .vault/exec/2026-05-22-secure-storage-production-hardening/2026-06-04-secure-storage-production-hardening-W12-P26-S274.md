---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S274'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s274-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S274`

Closed `AFR-172` for wizard answer persistence.

## Description

- Audited `src/aeat/application/wizard/_persistence.py` for active-profile, manifest-bucket, and plaintext-file concerns.
- Verified create/edit writes delegate to canonical user-profile orchestration through `register_active_profile` and `set_active_fields`.
- Verified `Path` is used only as a typed wizard answer value, not as a file IO route.
- Verified edit-mode refusal uses an AEAT exception with a locale key.
- Hardened patch persistence so unknown supplied question ids fail closed with a localized AEAT exception instead of being silently skipped.
- Ran focused wizard persistence, setup-runtime, and pointer-atomicity gates.

## Outcome

`AFR-172` is closed as `manifest-discovery`. No code change was required: wizard
persistence remains a projection layer over canonical profile-fact orchestration and
does not own bucket manifests, master-key material, or plaintext side files.
Unexpected supplied patch question ids now produce a localized
`WorkflowInputMismatchError` with bounded context, preserving the no-silent-swallowing
rule at the wizard patch boundary.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_persistence.py src/aeat/application/wizard/test_persistence_canonical.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_create_pointer_atomicity.py`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_persistence_canonical.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_create_pointer_atomicity.py`
- `uv run --no-sync vaultspec-rag search "wizard persistence persist_answers persist_patch register_active_profile set_active_fields profile facts manifest bucket" --type code --port 8766 --max-results 8`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_persistence_canonical.py`
- `python -m aeat.locales audit`

## Notes

The broader plan check still reports only the existing `PLAN022` monotonic-order warning.
