---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S28'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-07-14-google-oauth-audit]]"
---

# `P06.S28` — define the canonical `SourceKind` enum carrying the four values from the cli-workflow-redesign invoice-domain-decoupling ADR (`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`) plus the auxiliary kinds the v1 reverse-merge surfaces consume

## Scope

- `every reverse-merge service`
- `label deriver`
- `prefix router`
- `and bucket-event emitter consumes the enum from one location`
- `src/aeat/domain/source_kind/__init__.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# define the canonical `SourceKind` enum carrying the four values from the cli-workflow-redesign invoice-domain-decoupling ADR (`ledger_transaction`, `purchase_invoice_evidence`, `payable_invoice`, `collectible_invoice`) plus the auxiliary kinds the v1 reverse-merge surfaces consume

## Scope

- `every reverse-merge service`
- `label deriver`
- `prefix router`
- `and bucket-event emitter consumes the enum from one location`
- `src/aeat/domain/source_kind/__init__.py`

## Description

- Reconcile `P06.S28` against the accepted July architecture and current code.
- Ground the disposition with Vaultspec RAG and exact source and CLI evidence.
- Record the result in the related reconciliation audit before closing the row.

## Outcome

Superseded by the canonical `BindingSourceKind` taxonomy and its counterpart-source
subset; introducing a second `SourceKind` declaration would violate the single-taxonomy
architecture.

## Notes

No code changed during reconciliation. This record closes a retired duplicate taxonomy,
not a missing source-kind implementation.
