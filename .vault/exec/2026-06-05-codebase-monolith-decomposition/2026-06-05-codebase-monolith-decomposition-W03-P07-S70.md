---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S70'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S70 Registry Applicability Verification

Scope: `W03.P07.S70` verified applicability behavior and facade imports after decomposition.

## Description

- Run ruff over `_applicability.py`, `_applicability_payer_facts.py`, and `_applicability_modelo202.py`.
- Verify registry facade identity for `PayerFact`, `Modelo202Modality`, `Modelo202ModalityVerdict`, and `derive_modelo_202_modality`.
- Run modelo applicability, canonical-rule, cross-reference applicability, Modelo 202 registry, and public API boundary tests.
- Verify no application, entrypoint, or non-facade domain code imports the new private applicability modules directly.

## Outcome

Verification passed: 29 applicability/public API tests passed, ruff passed, the root line count is 1227, and private-module import discovery found no external consumers.

## Notes

The plan check still reports only the known `PLAN022` non-monotonic canonical-id warning.
