---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
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
- Corrected the overflow context to report only unconsumed-answer and asked-question
  counts, not raw leftover canonical-token values.
- Updated prompter and setup-runtime tests to assert localized AEAT errors and prove
  unconsumed answer values are absent from exception context.
- Ran focused lint, prompter tests, questionary smoke tests, and the canonical locale
  audit through `python -m aeat.locales`.

## Outcome

`AFR-173` is closed as `plaintext-exception`. The PATH prompt remains token-only, and
scripted fixture drift now fails through registered AEAT wizard exceptions with
localized message keys and redacted diagnostic context.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/wizard/_prompter.py src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync pytest -q src/aeat/application/wizard/test_prompter.py src/aeat/application/wizard/test_setup_runtime.py src/aeat/application/wizard/test_questionary_smoke.py`
- `uv run --no-sync -q python -m aeat.locales audit`

## Notes

No translation catalogue edit was required; the existing error-registry message keys
already cover wizard scripted underflow and overflow. A previous closeout statement
claimed bounded overflow context while the code still carried raw unconsumed values;
this step record now reflects the applied redaction repair.
