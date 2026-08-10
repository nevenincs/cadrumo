---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:62109059914c8e2c232d8023598f69f17a69bf3ceab8f0dd5e1371bd4f4f4589'
step_id: 'S08'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# Retype Deuda.clave_liquidacion onto AeatClaveLiquidacion, and retype the second bare-str clave_liquidacion on the operator-facing wire payload in the same change

## Scope

- `src/cadrumo/adapters/outbound/aeat/sede/_deudas.py`

## Description

- Retype the debt model's clave field onto the shared alias at its existing bound.
- Keep the field enrolled in the module's blank-rejecting validator and record why in that validator's docstring.

## Outcome

Landed in `c272504f9d`. The debt model confirmed relocated out of the sede schema module before this row ran, as the row itself warned, so both sites were re-verified against the tree rather than trusted from the row's earlier file reference.

## Notes

**The blank guard was deliberately retained and this is the substantive decision in the row.** The alias constrains length only, which is exactly the bound the existing validator exists to supplement: a length of one admits a whitespace-only string, which is what an empty listing cell parses to. Dropping the field from the validator on the grounds that it is "now typed" would have silently re-admitted the blank. The validator's own docstring now says so, so the next reader does not remove it as redundant.

The validator also covers the debt's procedural-state label, which is an adjudicated non-identifier explicitly excluded from this taxonomy. Removing the whole validator would therefore have weakened a second, unrelated guard as collateral.

**The second site named by the row was not in scope at execution time.** The operator-facing wire payload copy sits in a package an external campaign held when this row ran. That reservation has since been revoked, so the remaining site is carried into the CSV batch rather than deferred — it is named here so it does not read as covered by this record.
