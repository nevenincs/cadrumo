---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:1eb274724ff7ce1a02eb462d6858f6377e80de8a727b3a518a01588ad56d8bb5'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
  - "[[2026-06-21-m303-carry-reconciliation-adr]]"
---
## Scope

Read-only review of S17's first half against the carry-reconciliation ADR and the S17/S19 plan boundary. The review covered public Modelo 303 U export with its distinct charge account, unchanged D refund behaviour with a refund account, I and N DID omission, the shared DID predicate and parity derivations over D/V/X/U versus C/I/N/G, and the explicit deferral of Nota 3 inputs to S19.

## Findings

No triaged finding. The public U path resolves the selected positive settlement to `U`, renders the DID record with only the separately recorded charge IBAN, and refuses when that charge account is absent even if a refund account exists. Public D coverage preserves the refund account as the DID source and excludes the distinct charge account. Public I and N exports omit the DID page. The core account-required axis and the renderer/parity predicate agree that D/V/X/U carry the page while C/I/N/G suppress it; `U` remains outside the refund/carry axis.

## Recommendations

- Retain the public U, public D, I/N omission, and all-disposition predicate regressions when changing account-page behaviour. Keep Nota 3 casilla 111 and the page-3 cancellation marker out of the disposition predicate until S19 threads both inputs through the renderer and parity paths.
