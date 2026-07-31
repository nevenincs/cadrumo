---
tags:
  - '#research'
  - '#cli-workflow-redesign'
date: '2026-05-12'
modified: '2026-07-17'
body_hash: 'sha256:d7e321522bc9d8bb2a821f6a16cf47e130495dab607ec186df5a460961b0cdfb'
related:
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# `cli-workflow-redesign` research: `iva-prorrata-art-101-103`

## Findings

`domain/usage_ratios` is proportional expense usage, not the legal IVA
prorrata mechanism. Vault references mention prorrata in formula work, but
implementation remains missing.

The legal source is LIVA arts. 101-103. Source:
`https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740`.

Target implementation is a legal prorrata substrate under `domain/vat`, with
application aggregation producing ledger observations for Modelo 303 and Modelo
390. Profile/config may store regime axes and percentages, but app ledger
ratios are not the persistence shape for IVA prorrata.

Reject reusing `app ledger ratios`, reusing `domain/usage_ratios`, adding
`app ledger prorrata` as the legal persistence surface, or shimming usage
ratios into prorrata.
