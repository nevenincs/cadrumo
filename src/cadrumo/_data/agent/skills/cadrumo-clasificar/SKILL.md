---
name: cadrumo-clasificar
description: >-
  Classify and apportion the ledger: assign IRPF/IVA categories, allocate mixed-use
  items, and set business-use ratios and prorrata. Use after the ledger is clean and
  before preparing a modelo.
applies_when:
  workflow_phase: classification
---

# Classify and apportion

Classification decides which casillas a transaction feeds. Classify by the records
and the law, never to reach a convenient number.

## Preconditions

- A clean, imported ledger (`aeat app ledger check` is clean).

## Procedure

1. Classify transactions: `aeat app ledger classify` into their IRPF/IVA
   categories. Read the accepted category set from the CLI rather than guessing.
2. Allocate mixed-use or shared items: `aeat app ledger allocate`.
3. Set business-use ratios and prorrata: `aeat app ledger ratios set`, then review
   with `aeat app ledger ratios list` and `aeat app ledger ratios validate`.
4. Act on any unconsumed-IVA or unclassified advisory the CLI surfaces - a
   classification gap is reported, not silent.

## Success assertions

- Every transaction that feeds a casilla carries a category; no declarable item is
  left unclassified.
- `aeat app ledger ratios validate` reports the ratios consistent.
- No category is overridden to change a downstream value.

## Hand off

A classified ledger is ready for the modelo-preparer (see the per-modelo skill,
e.g. `cadrumo-preparar-modelo-130`).
