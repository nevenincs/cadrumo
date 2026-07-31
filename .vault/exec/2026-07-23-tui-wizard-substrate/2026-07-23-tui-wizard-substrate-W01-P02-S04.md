---
tags:
  - '#exec'
  - '#tui-wizard-substrate'
date: '2026-07-23'
modified: '2026-07-23'
body_hash: 'sha256:b44c86549f9b2e4a856fba400e02b158cfd1b5e395d4c48010452cc99cbf1a81'
step_id: 'S04'
related:
  - "[[2026-07-23-tui-wizard-substrate-plan]]"
---

# Port the widget validators and add the typed validator slots (per-answer, section-exit, flow-scope) returning i18n message keys with redacted diagnostics

## Scope

- `src/cadrumo/application/flows/_validators.py`

## Description

- Port the widget-shape validators to the substrate with the blank-optional policy carried over, add the three-scope validator registries (per-answer, section-exit, flow-scope) returning typed verdicts with i18n message keys, and the redaction funnel for diagnostics.
- Land in commit 91c5e51afc.

## Outcome

Registries reject duplicate ids; verdict contexts never carry raw answers (reviewer-verified redaction pass).

## Notes

Domain validators (tax-id checksum, postcode) intentionally not ported: they register per-flow via the answer-validator registry.
