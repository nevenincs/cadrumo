---
generated: true
tags:
  - '#index'
  - '#period-grammar-standardisation'
date: '2026-08-16'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:dc56a37cc86955b4915d001a6f461b087ed6d56470489fc4e70dc861c909587b'
related:
  - '[[2026-06-11-period-grammar-standardisation-adr]]'
  - '[[2026-06-11-period-grammar-standardisation-code-review-audit]]'
  - '[[2026-06-11-period-grammar-standardisation-exec]]'
  - '[[2026-06-11-period-grammar-standardisation-plan]]'
  - '[[2026-06-11-period-grammar-standardisation-research]]'
  - '[[2026-06-12-period-grammar-standardisation-closeout-audit]]'
---

# `period-grammar-standardisation` feature index

Auto-generated index of all documents tagged with `#period-grammar-standardisation`.

## Documents

### adr

- `2026-06-11-period-grammar-standardisation-adr` - `period-grammar-standardisation` adr: `core Period value object: one typed period across the backend` | (**status:** `accepted`)

### audit

- `2026-06-11-period-grammar-standardisation-code-review-audit` - `period-grammar-standardisation` Code Review
- `2026-06-12-period-grammar-standardisation-closeout-audit` - `period-grammar-standardisation` Closeout Audit

### exec

- `2026-06-11-period-grammar-standardisation-W01-P03-S08` - W01.P03.S08 Combined Parser Regex Removal
- `2026-06-11-period-grammar-standardisation-W02-P07-S21` - Re-seat application/aggregation Period on core.Period: drop the raw combined-string field, delegate from_year_and_token to core.from_year_and_code, and prove the live ledger-filter parity is preserved
- `2026-06-11-period-grammar-standardisation-W02-P08-S23` - Replace the period: str / ledger_period fields in the state projection with core.Period and add a save->load->equality roundtrip plus anti-tautology proof at that persistence boundary
- `2026-06-11-period-grammar-standardisation-W02-P08-S24` - Replace the period: str fields in the aggregation service, source mesh and retenciones models with core.Period
- `2026-06-11-period-grammar-standardisation-W02-P08-S25` - Replace the period: str fields in the iva prorrata, submission, verification schema, filing schema and modelo export models with core.Period
- `2026-06-11-period-grammar-standardisation-W02-P08-S33` - DEFERRED C2: migrate CalculationSourceContext.period to core.Period plus resolver mesh
- `2026-06-11-period-grammar-standardisation-W02-P11-S28` - W02.P11.S28 Period Parser Cleanup
- `2026-06-11-period-grammar-standardisation-W02-P11-S30` - W02.P11.S30 Add Combined Period String Gate
- `2026-06-11-period-grammar-standardisation-W02-P11-S35` - W02.P11.S35 Remove Aggregation Period Wrapper
- `2026-06-11-period-grammar-standardisation-exec` - period-grammar-standardisation <display-path>

### plan

- `2026-06-11-period-grammar-standardisation-plan` - `period-grammar-standardisation` `period grammar standardisation: AEAT-token-only, year always separate, conflation burn-down` plan

### research

- `2026-06-11-period-grammar-standardisation-research` - `period-grammar-standardisation` research: investigation backing the decision
