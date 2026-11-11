---
tags:
  - '#reference'
  - '#ledger-statement-reference'
date: '2026-11-10'
modified: '2026-11-10'
body_schema: 'body-v2'
body_hash: 'sha256:6c043f743d5fdf917d864e014947a2bf25a62a7e4b14579399b9267da4557cb6'
related: []
---

# `ledger-statement-reference` reference: `Where a movement's statement reference lives today`

## Summary

A statement's printed reference reaches the raw transaction only as its provider identifier, and only until the row is edited, split or merged.

- The CSV reader lists the reference column under `external_id` (`src/cadrumo/adapters/inbound/financial/providers/csv.py:157`) and uses it as `provider_transaction_id`, synthesizing an identifier when the row prints none (`src/cadrumo/adapters/inbound/financial/providers/csv.py:615`).
- The synthesized identifier is `{provider}-{sha256[:12]}-{row}` (`src/cadrumo/adapters/inbound/financial/providers/base.py:803`); the mapped tabular, OFX and PDF readers use the same helper (`src/cadrumo/adapters/inbound/financial/providers/mapped_tabular.py:297`, `src/cadrumo/adapters/inbound/financial/providers/ofx.py:309`, `src/cadrumo/adapters/inbound/financial/providers/pdf_statement.py:172`), and the PDF reader always synthesizes.
- Manual entries mint `manual:` identifiers (`src/cadrumo/application/ledger/actions_manual.py:671`); split parts and merged rows mint `split:` and `merged:` identifiers with manual provenance (`src/cadrumo/application/ledger/actions_split_merge.py:756`, `src/cadrumo/application/ledger/actions_split_merge.py:987`).
- An update keeps the provider identifier but rebuilds the raw record with fresh manual provenance and raw fields (`src/cadrumo/application/ledger/manual_update.py:433`, `src/cadrumo/application/ledger/actions_manual.py:467`).
- The transaction id hashes an explicit payload of provider identifier, value date, amount, narrative and own account (`src/cadrumo/domain/transactions/models.py:93`).
- The canonical ledger payload, served by `ledger.list` and `ledger view`, carries no provider identifier or reference (`src/cadrumo/application/ledger/manual_read.py:180`, `src/cadrumo/application/ledger/list_operation.py:60`).
- The transaction catalogue validates stored rows at the current envelope version (`src/cadrumo/adapters/persistence/profile/transactions.py:334`).
