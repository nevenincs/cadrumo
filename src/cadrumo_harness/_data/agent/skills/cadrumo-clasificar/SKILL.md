---
name: cadrumo-clasificar
description: >-
  Classify and apportion the ledger: assign IRPF and IVA categories, allocate
  mixed-use items, and set and validate business-use ratios and prorrata. Use
  when the ledger is clean and a modelo is about to be prepared, or when a
  classification gap or advisory is reported.
applies_when:
  workflow_phase: classification
---

# Classify and apportion

Classification decides which casillas a transaction feeds. Classify by the records
and the law, never to reach a convenient number.

## Preconditions

- An imported ledger whose `aeat app ledger check` reports nothing blocking; if
  not, load `cadrumo-llevar-libro`.

## Procedure

1. Read the accepted category identifiers with `aeat app ledger categories` (tool
   server: `authority` with query `categories`). Do not guess an identifier.
2. Classify each transaction, telling the person what you will record:
   `aeat app ledger classify <transaction-id> --classification ... --category-id ...`,
   adding `--irpf-category`, `--taxable-base`, `--iva-rate` and `--iva-amount`
   where the row needs them. `--file` takes a CSV for many rows. For
   intra-community or export rows also give `--iva-category`,
   `--counterparty-country` and `--counterparty-identification-state`.
   Operations: `ledger.classify.single` and `ledger.classify.bulk`. `--llm` asks
   the local on-host reader for a suggestion and only previews it unless `--apply`
   is added; use it only when the person has asked for it, and show them the
   preview before applying.
3. Allocate mixed-use or shared items with
   `aeat app ledger allocate <transaction-id> --business-pct <0 to 1>` (operation
   `ledger.allocate`). Do not use it for a row that is entirely business.
4. Set business-use ratios and prorrata with
   `aeat app ledger ratios set <category> <ratio>` (operation
   `ledger.ratios.set`), review them with `aeat app ledger ratios list`, and check
   them with `aeat app ledger ratios validate`.
5. Act on any advisory the tools report about unclassified rows or declarable IVA
   that no calculation would consume. A gap is reported to the person, not
   skipped. `aeat app ledger preflight --period <PERIOD> --year <YEAR>` lists the
   data missing from the rows for a period.

## Success assertions

- Every transaction that feeds a casilla carries a category; no declarable item is
  left unclassified.
- `aeat app ledger ratios validate` reports the ratios valid.
- No category or ratio was changed only to move a downstream figure.

## Next

A classified ledger is ready for the modelo's own skill, for example
`cadrumo-preparar-modelo-130` or `cadrumo-preparar-modelo-303`.
