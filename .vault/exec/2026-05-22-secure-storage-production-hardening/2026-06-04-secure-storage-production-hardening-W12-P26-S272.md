---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S272'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-04-secure-storage-production-hardening-w12-p26-s272-review-audit]]'
---

# `secure-storage-production-hardening` `W12.P26.S272`

Closed `AFR-170` for the declaration verification boundary.

## Description

- Audited `src/aeat/application/verification/_verify.py` for plaintext exception and storage-custody concerns.
- Replaced raw registry verification failure messages with localized AEAT exceptions carrying structured context.
- Added locale catalogue entries through `python -m aeat.locales`.
- Added real registry-behavior tests for missing registry snapshots and missing external binding values.
- Ran focused verification, locale, and semantic-duplication gates.

## Outcome

`AFR-170` is closed as `plaintext-exception`. The verification boundary still reads
registry snapshots through the established resource authority path and now reports
catastrophic verification failures through locale keys instead of raw formatted
exception strings.

Validation passed:

- `uv run --no-sync ruff check src/aeat/application/verification/_verify.py src/aeat/application/verification/test_verify.py src/aeat/locales`
- `uv run --no-sync pytest -q src/aeat/application/verification/test_verify.py src/aeat/application/verification/test_verify_helpers.py`
- `python -m aeat.locales audit`
- `uv run --no-sync vaultspec-rag search "verify_declaracion registry_root VerificationError missing binding registry snapshot" --type code --port 8766 --max-results 6`

## Notes

The locale scaffold was required before setting the new verification keys and also
preserved existing catalogue parity repairs already present in the shared worktree.
