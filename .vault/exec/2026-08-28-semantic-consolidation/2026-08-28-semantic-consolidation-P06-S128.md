---
tags:
  - '#exec'
  - '#semantic-consolidation'
date: '2026-08-31'
modified: '2026-08-31'
body_schema: 'body-v2'
body_hash: 'sha256:de4470d3bcc4929a7d0b6105fbf4cf3123757e44e3242d9accd68367b97fbd7f'
step_id: 'S128'
related:
  - "[[2026-08-28-semantic-consolidation-plan]]"
---

# Rule on the operator-clave accumulator, whose docstring calls it a mutable accumulator while its config freezes it, so every aggregation write raises

## Scope

- `src/cadrumo/domain/calculations/registry/invoice_bindings.py`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/invoice_bindings.py`
- `verify:` accumulator mutates (`base_total += 100`, legal name filled) and still refuses `country_code = 5`
- `verify:` `pytest test_invoice_bindings + test_counterpart_bindings + test_contraparte_clave_row_grouping -n 0 -m ""` -> pass (43)

## Notes

The step describes it exactly: three private classes whose docstrings say
"Mutable accumulator" while their config froze them, so
`bucket.base_total += observation.base_amount` raised `frozen_instance` and
every aggregation over a non-empty observation set failed. These are the three
failures that have been red in every registry run this campaign made.

Ruled in favour of the docstrings. The frozen discipline protects a persisted or
returned record; these are local buckets inside one function, never persisted and
never returned -- the rows are built as plain mappings afterwards -- so there is
nothing here for it to protect.

### The fix weakened something and a probe caught it

Dropping `frozen` alone made every assignment bypass validation: the class went
from refusing a Decimal sum to accepting `country_code = 5`. That is a worse
defect than the one being fixed, because it is silent. `validate_assignment` is
therefore part of the config rather than an afterthought, and the reason is
recorded beside it.

Worth keeping as a general point: removing a constraint to permit a legitimate
operation can remove a second constraint that was riding on it. The probe that
found this was three lines and ran before the tests did.
