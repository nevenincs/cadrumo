---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:349d35917e83f4bae298d04f493831237a1d86e78620a9b12b8198a4735bab4e'
step_id: 'S313'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---
# remove 6 genuine unused imports flagged by F401: test_certificate_live.py CertificateBackend

## Scope

- `test_verify.py VerifyBrowserContextLike + VerifyBrowserPageLike`
- `test_fx_conversion.py ExchangeRateProvider`
- `test_calendar_applicability_consistency.py derive_modelo_applicability`
- `review _adapters.py TransactionDirection  -  straightforward refactor`
- `src/aeat/`

## Description

Reconciled the retained historical execution evidence for this Step. The related reconciliation audit names commit `19c283b388` as the direct evidence.

No production sources changed.

## Outcome

Restores one-Step/one-record traceability for this checked Step without rewriting historical implementation.

## Notes

The related reconciliation audit names the exact historical evidence. This documentation-only record makes no new production-behavior claim.
