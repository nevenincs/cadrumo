---
tags:
  - '#exec'
  - '#google-oauth'
date: '2026-07-14'
modified: '2026-07-14'
step_id: 'S05'
related:
  - "[[2026-05-13-google-oauth-plan]]"
  - "[[2026-07-14-google-oauth-audit]]"
---

# `P03.S05` — implement label-deriver registry with per-namespace registration API and strict refusal (`UnregisteredNamespaceLabelDeriverError`) at startup when an allow-listed namespace lacks a registered deriver

## Scope

- `no silent default`
- `no permissive fallback`
- `src/aeat/adapters/outbound/storage/_labels.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# implement label-deriver registry with per-namespace registration API and strict refusal (`UnregisteredNamespaceLabelDeriverError`) at startup when an allow-listed namespace lacks a registered deriver

## Scope

- `no silent default`
- `no permissive fallback`
- `src/aeat/adapters/outbound/storage/_labels.py`

## Description

- Reconcile `P03.S05` against the accepted July architecture and current code.
- Ground the disposition with Vaultspec RAG and exact source and CLI evidence.
- Record the result in the related reconciliation audit before closing the row.

## Outcome

Superseded by the accepted July remote-ciphertext-manifest architecture.

## Notes

No implementation was added. Any future pull, restore, or conflict workflow requires a new accepted ADR.
