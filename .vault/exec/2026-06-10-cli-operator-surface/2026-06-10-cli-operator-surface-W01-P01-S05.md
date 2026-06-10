---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-10'
step_id: 'S05'
related:
  - "[[2026-06-10-cli-operator-surface-plan]]"
---




# correct the evidence-id help string that promises unambiguous prefix to state exact-equality matching, via the aeat.locales CLI

## Scope

- `src/aeat/locales/{en,es,ca,hu}.yml`

## Description

Decision: REWORD the help string, not implement prefix resolution. The
evidence-id (`uuid.uuid4().hex[:16]`) is matched by exact equality across the
evidence service's `view` / `update` / `remove` paths. The only reusable prefix
resolver (`resolve_transaction_id`) is hex-and-bucket-transaction-id specific and
not reusable for opaque evidence ids without inventing a new generic resolver and
threading it through three commands - behaviour the ADR (D5: "no behavior
invention") tells us to avoid. The owning doc already says "Note the full ID
down", consistent with exact equality.

Corrected `cli.app.ledger.evidence.evidence_id_help` from
"(or unambiguous prefix)" to an exact-match phrasing across all four locales via
`python -m aeat.locales set` (no hand-edit of the yml).

## Outcome

The evidence-id help now states exact matching, matching the handler. Locale
parity, translation-honesty, and `scaffold --check` gates pass. No docs claimed
prefix matching for evidence ids.

## Notes

The other "(or unambiguous prefix)" strings (invoice/snapshot/work-unit ids) were
left untouched: those ids ARE resolved by prefix through their respective
resolvers, so their help is honest.

