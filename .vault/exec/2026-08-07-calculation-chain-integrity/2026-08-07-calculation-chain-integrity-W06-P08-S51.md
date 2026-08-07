---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:4a5807520051ba4eb3c9b61aa69faf6ddd49c91284d9ed0ac36089a005c90892'
step_id: 'S51'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---

# Confirm against live BOE which instrument set the October to December 2024 two and seven point five percent food windows, quoting the operative article text, since three near-identical names are in play and one already sits in the catalogue for an unrelated IRPF purpose

## Scope

- `src/cadrumo/_data/registry/aeat/legal/`

## Description

- Fetch the BOE document and read the operative text of article 1.
- Resolve the three-way instrument-name collision against the catalogue.
- Record the chain of predecessor decree-laws and their bundling status.

## Outcome

Confirmed Real Decreto-ley 4/2024 de 26 de junio as the instrument fixing both
2024 temporary food-rate windows.

The apparent contradiction dissolved on reading the document. Article 1 carries
the temporary windows; article 2 amends the permanent rate article from
2025-01-01; the consolidated text footnotes only article 2 because only it
touched the permanent body. One instrument, two jobs, and the bundled amendment
history shows one of them.

Windows: 1 July to 30 September 2024 at 5 per cent for seed oils and pasta and
0 per cent for basic foods including olive oil, recargo 0,62 and 0; then
1 October to 31 December 2024 at 7,5 and 2 per cent, recargo 1 and 0,26.

The chain runs deeper than assumed. This instrument extends or modifies four
predecessors, none bundled. They govern windows earlier than article 1's start,
which the rate table does not reach, so they are real but non-blocking.

## Verification

```
curl -sS -L https://www.boe.es/diario_boe/txt.php?id=BOE-A-2024-12944
349501 bytes, contains 'del 0,62 por ciento'

Cross-checked against the consolidated rendering clause by clause: all four
operative recargo sentences byte-identical across the two renderings.
```

## Notes

A relayed preamble reading gave the recargo as 0,6 where the operative clause
says 0,62. The coordinator quoted a preamble as authority; the assignee refused
to author from it, weighted the bundled record-design layout above a preamble,
and isolated the discrepancy to one figure by box cohort. The layout was right.

A summarising fetch of the consolidated page also reported article 1's operative
text as absent. It is not; the summary did not surface it. Reading raw bytes
found both the text and the element ids.
