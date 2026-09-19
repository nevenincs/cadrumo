---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-12'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:cc2a4d091e287b7cfc6a3620b3b49d3563eba6ab96eaaad0972b99b91a5fcf60'
step_id: 'S81'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Migrate review action producers to typed conditions and canonical actions

## Scope

- `src/cadrumo/application/review`

## Description

- Migrate the three review-overlay refusals to the registered review key.
- Carry the offending field and its canonical writer as machine facts.
- Rewrite the assertions that matched on the deleted sentences.

## Outcome

- The declared package carries no operator-facing prose refusal; the only remaining raise is the module facade's attribute protocol error.
- All three refusals guard the same boundary: a durable ledger field must not be written through the review overlay. Each now names the field it refused and the writer that owns it, so a consumer can route the caller to the right surface without parsing text.
- The migration reused the key already registered against the review error class, so no new locale leaf was required.
- The package suite passes one hundred and ninety-five tests serially and is lint clean.

## Notes

- Three assertions matched on the deleted sentences and now assert the typed error alone; the refused field and its canonical writer remain available on the context for any test that needs to distinguish the three cases.
- No carry-forward.
