---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S18'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Bind the identity pages to the core.identity per-answer validators with per-IdentityDocument format-hint and failure copy references

## Scope

- `src/cadrumo/application/wizard/`

## Description

Identity, date, and amount pages now carry their full shape story;
executed across three landings, verified and closed by the coordinator.

- Identity pages bind the canonical `cadrumo.core.identity` per-answer
  validator (carried through the bridge from the widget layer) with
  per-`IdentityDocument` failure keys (the identity localization
  landing) and the worked-example format hint showing all three
  NIF/NIE/CIF shapes (the content batch).
- Date and decimal pages carry first-class shape-validated widget
  kinds: `PAGE_WIDGET_KINDS` assigns DATE to the eight date questions
  and DECIMAL to INCN plus the seven módulos unit fields (fractional
  units are real), folded into the single decoration walk beside the
  format hints — bridge and `WizardWidget` untouched.
- Real-engine drives prove a malformed date/decimal refuses as a typed
  verdict (`flows.errors.invalid_date` / `invalid_decimal`) while the
  ISO/Decimal value commits.

## Outcome

Commits `695fc9a4fa` (hints + explainer catalogues), `5478da4102`
(widget kinds, 2 files). Coordinator verification: content suite 8/8 at
HEAD; the executor's runs: flows 100, wizard 284 (1 peer-owned red from
untracked bundle-flow WIP), conformance 348, clean collection at 13671.

## Notes

Count correction over the staged spec prose: 16 shape pages (8+8), not
15. Peer-owned anomalies recorded for the ledger: the untracked
`test_frontend_parity.py` hangs headless (Textual Pilot under
asyncio.run) and the bundle-flow WIP is missing its 36 cli.* keys —
both substrate/bundle-lane surfaces.

