---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S69'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W03.P07.S69 Registry Applicability Decomposition

Scope: `W03.P07.S69` decomposed applicability rule-family logic behind the registry facade.

## Description

- Extract payer-fact predicates into `src/aeat/domain/calculations/registry/_applicability_payer_facts.py`.
- Extract the Modelo 202 modality gate into `src/aeat/domain/calculations/registry/_applicability_modelo202.py`.
- Keep `_applicability.py` re-exporting the public `PayerFact`, `Modelo202Modality`, `Modelo202ModalityVerdict`, and `derive_modelo_202_modality` surface.
- Preserve the canonical `_MODELO_APPLICABILITY_RULES` table in `_applicability.py`.

## Outcome

The applicability root is 1227 lines, under the 1250-line hard target, with payer-fact and Modelo 202 modality families split into focused private modules.

## Notes

No applicability semantics or legal refs were changed.
