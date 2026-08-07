---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a503ce858e0e7576ff4b67d2fa6bf62b36e5ec38fb0e8aebfd749314945effba'
step_id: 'S40'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W02.P03.S40

## Outcome

The gate exists and is green: `test_reconciliation_pair_category_parity.py`, landed by `1c0bcf6428`. Verified at HEAD rather than re-implemented — a second parity gate over the same surface would be the duplicate authority this campaign's sweep phase exists to find.

## What it gates

Both sides of every reconciliation pair must aggregate the same IVA categories into the concepts they both model. The defect it was built from is recorded in its own docstring and is the shape this Step names: routing a new intra-community SERVICES category onto the Modelo 303 quarterly line without the Modelo 390 annual line gave 63.00 goods + 21.00 services = 84.00 on the quarters against 63.00 on the annual return, and nothing in the suite objected. The annual surface had tests; none compared the two sides' category sets.

## Three tests, and the third is the one that matters

- `test_reconciliation_pairs_aggregate_the_same_categories` — the gate itself.
- `test_every_reconciliation_casilla_belongs_to_a_derived_pair` — closes the reverse direction, so a reconciliation casilla whose pair the derivation misses cannot hide.
- `test_reconciliation_pair_derivation_is_not_vacuous` — the anti-vacuity guard. Without it, a derivation that enumerated zero pairs would pass the parity assertion trivially and forever, which is the same false-green shape `W02.P03.S07` found in the reachability probe.

## Limits, already stated in the gate itself

Its docstring names three, and they are the right three: selecting the same categories is not producing the same VALUE (that is the reconciliation blocking rules' job); only concepts BOTH sides model are compared, since a concept absent from one side is a registry-completeness question with its own grounding; and only `ledger_iva_aggregation` bindings are compared, since a concept fed by a relation on one side and ledger aggregation on the other is not a category-parity question.

Nothing to add. The Step's requirement — enumerated from both declaration sites — is satisfied by the derivation `W06.P08.S39` records.
