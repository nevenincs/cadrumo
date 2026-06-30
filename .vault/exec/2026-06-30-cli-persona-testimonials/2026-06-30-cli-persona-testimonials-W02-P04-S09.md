---
tags:
  - '#exec'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
step_id: 'S09'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# Harden ledger provider detection and unsupported-source diagnostics

## Scope

- `src/aeat/adapters/inbound/financial/providers`

## Description

- Keep canonical AEAT ledger CSV exports out of the raw bank CSV provider.
- Render unsupported-source diagnostics with the offending path.
- Validate provider refusal and error-contract behavior with focused tests.

## Outcome

Commits `402f8a5d` and `34873aa5a` first surfaced and then corrected the
provider boundary. Canonical AEAT ledger CSV export headers are now explicitly
refused by `src/aeat/adapters/inbound/financial/providers/_csv.py` instead of
being accepted as a raw bank layout. Unsupported auto-source refusals render the
path through the localized reason.

## Notes

Final ledger verification included provider CSV and ledger import error tests:
62 passed and 7 deselected across the focused ledger/transaction set.
