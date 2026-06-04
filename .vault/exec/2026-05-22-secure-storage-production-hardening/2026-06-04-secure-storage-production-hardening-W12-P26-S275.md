---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
step_id: 'S275'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S275 - Close AFR-173 for wizard prompter

Scope: close `AFR-173` for `src/aeat/application/wizard/_prompter.py` with signals
`plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`.

## Description

- Verified the prompter owns prompt rendering only and does not persist secure storage,
  bucket manifests, master-key material, or plaintext side files.
- Verified interactive unsupported-console paths already use localized AEAT exceptions
  and retain the underlying exception as diagnostic cause.
- Replaced scripted prompter underflow and overflow raw English messages with locale
  keys and bounded structured context.
- Updated prompter and setup-runtime tests to assert the localized AEAT error contract.
- Ran focused lint, prompter/runtime tests, questionary smoke tests, and vaultspec RAG
  duplication discovery.

## Outcome

`AFR-173` is closed as `plaintext-exception`. The PATH prompt remains token-only, and
scripted fixture drift now fails through registered AEAT wizard exceptions with
localized message keys.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_prompter.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync vaultspec-rag search "wizard prompter scripted underflow overflow questionary path plaintext exception localized AEAT error" --type code --port 8766 --max-results 8`

## Notes

No translation catalogue edit was required; the existing error-registry message keys
already cover wizard scripted underflow and overflow.
