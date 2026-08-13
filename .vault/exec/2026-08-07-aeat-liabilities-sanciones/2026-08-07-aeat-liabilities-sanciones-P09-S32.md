---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:1c2ebda9ea885e994730b1e8fcea28ea143884b23aa613d25f41c62cad85b6d5'
step_id: 'S32'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Write parse_sancion_documento running the label dispatch over text lifted by the existing extract_pages_text_from_bytes and converting captured amounts with the existing parse_spanish_decimal, adding no second PDF text extractor and no second decimal parser, verified by a parse unit test over a synthetic specimen reproducing the observed label set

## Scope

- `src/cadrumo/adapters/inbound/notificacion/_sancion.py`

## Description

- Delete the hand-rolled decimal conversion from the money and percentage readers.
- Delegate both conversions to the canonical Spanish decimal parser, refusing when it declines.
- Keep the anchored gate ahead of the delegation.

## Outcome

Delivered. The anchored gate stays and runs first, so the canonical parser's deliberate permissiveness - it accepts forms AEAT does not print - is unreachable on this path. Strictness is preserved while the second decimal conversion is gone.

This closed a live red gate as a side effect: the tree-wide unvalidated string-to-decimal check listed both call sites, and its findings dropped from five to three.

One part of the row was already satisfied differently and was left alone. The row asked for the label dispatch to run over text lifted by the canonical byte-level extractor. The parse entry point takes text, not bytes, and the bytes-to-text lift happens one layer up in the application service through exactly that extractor. That is correct layering - the adapter parses, the application orchestrates - and it introduces no second extractor, which a sweep confirmed: there is no PDF text extraction call anywhere under the notificacion package.

## Notes

The delegation was proved load-bearing rather than cosmetic: poisoning the canonical parser at runtime makes the sancion reader refuse, so the reader genuinely depends on it and is not carrying a silent fallback.
