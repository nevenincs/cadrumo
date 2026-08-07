---
tags:
  - '#exec'
  - '#invoice-canonical-structure'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:364822cdc3d98bac40f83bac8402be39158034abf2230a4d45783af3e50ede12'
step_id: 'S32'
related:
  - "[[2026-08-06-invoice-canonical-structure-plan]]"
---

# Enrol the invoice decomposition contract as a capability-inventory row with both production consumers and the modelos each serves, the renta sales-evidence gate running the full grounded check and the M349 gate narrowed to the two self-contradiction defects, and record which record classes each would exclude after the fold

## Scope

- `src/cadrumo/domain/invoices/_decomposition.py`

## Description

- Swept production consumers of the decomposition contract at `HEAD` rather than carrying the campaign's earlier line citations forward.
- Recorded the inventory row with both consumers, the modelos each serves, and the record classes each excludes after the fold.

## Outcome

**The decomposition contract has exactly two production consumers, and they run it at DIFFERENT strengths.** That asymmetry is the row's whole point — a single-strength reading would mis-predict what the fold does to each lane.

| Consumer | Modelos served | Strength | Excludes after the fold |
|---|---|---|---|
| `application/aggregation/_renta_income_ledger.py:711` | renta income (sales evidence) | **Full** — refuses any record that is not grounded | Any record with no IVA category, including every record carrying only the facts a slim record could hold |
| `application/invoices/_source_resolver.py:307` | M349 only | **Narrowed** — self-contradiction defects only | Only records that contradict themselves; absence is deliberately not disqualifying |
| — | M347 | **Not run at all** | Nothing |

**The second consumer is the one an inventory misses**, and the reason is worth stating: it lives in a module that reads as a *resolver*, so it does not look like a decomposition consumer. It is one, and it is the consumer that decides whether a record reaches a recapitulative return.

**M347 is a third position rather than a variant of the second.** The contract is not run there at all — not narrowed, not weakened. Its declared figure is the total contraprestación with one third party, which the invoice's own totals identity already bounds and which no IVA category conditions. Reading that as "the check is weak on M347" would invite someone to strengthen it, which would drop real above-threshold operations out of an informativa on the strength of an unrelated missing field.

So the fold's effect is asymmetric by design: income narrows, the informativas do not. That is what the next Step proves.

## Verification

Closed by a complete artefact rather than a green assertion. The consumer set was measured at `HEAD`:

    rg -n "decompose_invoice|is_grounded" src/cadrumo --glob "!**/tests/**" (excluding the contract's own module)
    _renta_income_ledger.py:711   decompose_invoice(invoice).is_grounded    -- full
    _source_resolver.py:307       decompose_invoice(invoice) + defect filter -- narrowed

Two consumers, no others. The earlier campaign citation for the M349 consumer was `:286`; it now reads `:307` after this campaign's own docstring correction, which is why the sweep was re-run rather than trusted.

## Notes
