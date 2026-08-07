---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:8eaeee23d47d55f78a1373072e37a85968412ecba028e7448a6ef8e07971c77c'
step_id: 'S57'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S57

## Outcome

Recorded as `2026-08-07-calculation-chain-integrity-iva-regimen-surface-boundaries-audit`, with both claims verified at HEAD rather than restated from the Step.

## Verified: the four regimes are notice phrases only

`TRAVEL_AGENCY_REGIME`, `USED_GOODS_REGIME`, `ART_OBJECTS_REGIME` and `ANTIQUES_COLLECTORS_REGIME` exist in the tree only as `InvoiceLegalMention` members (`domain/invoices/_enums.py:157-160`) — RD 1619/2012 art. 6.1.n and 6.1.o fixed legal notices, the literally-quoted phrases an issuer must print.

Searching `domain/iva/_schema.py` and `application/aggregation/_iva_ledger.py` for REBU, bienes usados and agencias de viajes returns nothing. So none is an `IvaCategory` member and none is a modelled settlement treatment.

## Verified: group-member rollup is topology

`per_grupo_member` is described at its own canonical site (`application/calculations/_per_grupo_member_keys.py`) as the 353-from-322 cross-member fan-in. It answers who files what into which return, not how an operation settles, and it surfaces as a `grouping` on a `previous_filing` selector rather than as a category or treatment axis.

## Why the two halves are kept distinct in the record

They are both "not a regimen", for different reasons, and collapsing them would lose the useful part:

- the four regimes are **unmodelled and correctly so** — they change how a margin is computed, nothing here computes those margins, and the notice enum explicitly refuses to derive a printed mention from our own classification;
- the group rollup is **modelled, just not as a regimen** — it is a real mechanism living on the right axis.

## The positive edge

The audit also states what a modelled regimen looks like here, because a boundary needs both sides. `IvaCashAccountingTreatment` is the shape: a typed axis crossed with the category rather than a fan-out of category members, carrying real settlement consequence. That is the precedent `W06.P08.S56` follows for the rate axis.

## Why it was worth a record

A reader comparing `InvoiceLegalMention`'s seven members against `IvaCategory` sees four regime names on one side and none on the other, and files four missing categories. The register this campaign inherited filed a structurally identical shortfall once already — the four-of-ten clave table `S42` had to settle — so putting the scope boundary at the point of confusion is what stops it recurring.
