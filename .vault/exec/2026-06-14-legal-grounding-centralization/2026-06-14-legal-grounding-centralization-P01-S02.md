---
tags:
  - '#exec'
  - '#legal-grounding-centralization'
date: '2026-06-14'
modified: '2026-06-15'
step_id: 'S02'
related:
  - "[[2026-06-14-legal-grounding-centralization-plan]]"
---




# F5: promote DT12 40% rescate reducción and Ley 44/2015 SAL 10% dotación + 2x cap factor to registry/external_constants with legal_refs->corpus_ref

## Scope

- `src/aeat/domain/modelos/_dt12_reduccion.py`

## Description

- Add three regulatory leaf constants to `core.external_constants`:
  `DT12_RESCATE_REDUCCION_RATE = Decimal("0.40")` (LIRPF DT 12ª),
  `SAL_RESERVA_DOTACION_RATE = Decimal("0.10")` and
  `SAL_RESERVA_CAPITAL_MULTIPLE = Decimal("2")` (Ley 44/2015 art. 14.1,
  BOE-A-2015-11071), each with a binding-provision docstring.
- Rewire `domain/modelos/_dt12_reduccion.py` to multiply by
  `DT12_RESCATE_REDUCCION_RATE` instead of the inline `Decimal("0.40")`.
- Rewire `domain/modelos/_sal_reserva_especial.py` to use
  `SAL_RESERVA_CAPITAL_MULTIPLE` for the 2×-capital cap and
  `SAL_RESERVA_DOTACION_RATE` for the 10 % dotación, replacing the inline literals.

## Outcome

Value-identical centralization (0.40 / 0.10 / 2 unchanged). DT12 oracle (6981.82) and
SAL oracle (12000.00) re-confirmed by direct call; 19 fiscal-reduction tests pass;
`ruff` clean. The two literals that the pass-1 reserva error sat next to now live in
the central authority with full BOE grounding. F5 closed.

## Notes

These values were inline-grounded (docstrings cited the law) but bypassed the central
authority — the exact class that let the pass-1 reserva 50%-vs-2× error survive every
static gate. Promoting them to `external_constants` is the minimum centralization; a
future pass may migrate them further into the registry `legal_refs`→`corpus_ref`
mechanism where the corpus-text gate would guard them (the DT12 ADR originally
sanctioned the inline form, so that further migration is a deliberate follow-on, not a
regression).
