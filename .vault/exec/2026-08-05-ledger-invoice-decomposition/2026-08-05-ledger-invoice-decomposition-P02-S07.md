---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:33c79dde1a3859f048ff75365677ead72df160d7707e0387f5563d206c09b37d'
step_id: 'S07'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---

# Declare the per-category component-expectation table as registry-grounded data derived from the existing cuota-less frozensets, never a parallel list

## Scope

- `src/cadrumo/domain/iva/_schema.py`

## Description

Coordinator adjudication (invoice-adr, 2026-08-05): the Step's work was executed by the `iva-component-axis` / `income-grounding` lanes and landed before this record was written; the author is weekly-limited, so this body is written from verification at HEAD rather than by the executing agent. The coordinator (team-lead) independently verified the work DONE at HEAD; this record closes the honest gap between the landed work and its empty scaffold.

## Outcome

DONE, landed at `8585c78fd3` (table declared, 50 tests green at landing) and re-keyed on the (category, invoice kind) pair at `1e61fc0d74` per the ADR amendment. Verified at HEAD by one targeted probe: the component-expectation table lives in `src/cadrumo/domain/iva/_components.py` as one declared row per (IvaCategory, kind) pair with per-row `legal_refs`, and the cuota-less set is DERIVED from the table's cuota columns and asserted equal to the canonical `CUOTA_LESS_M303_IVA_CATEGORIES` frozenset by an import-time divergence guard (`_components.py:1043`) — no parallel list exists, which is the Step's load-bearing requirement.

## Notes

Scope divergence, recorded honestly: the plan row sited the work in `src/cadrumo/domain/iva/_schema.py`; the implementation landed in the sibling module `src/cadrumo/domain/iva/_components.py` (the frozensets stay in `_schema.py`, the table derives from them across the module boundary). Same package, same facade, requirement met; the file split follows the module-size convention. A post-landing review finding (carve-out-guard-lost, HIGH) on the later `69b72040b5` upgrade of this table's grounding tiers is tracked separately and does not reopen this Step.
