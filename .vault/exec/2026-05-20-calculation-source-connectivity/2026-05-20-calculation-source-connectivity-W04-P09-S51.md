---
tags:
  - '#exec'
  - '#calculation-source-connectivity'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S51'
related:
  - "[[2026-05-20-calculation-source-connectivity-plan]]"
---

# Emit bucket events with source mesh diagnostics and fingerprints

## Scope

- `src/aeat/application/modelo/_actions.py`

## Description

- Emit `source_provenance_count` and an order-independent `source_provenance_trace_sha256` digest on the `MODELO_CALCULATION_CREATED` bucket-event payload.
- Fold each provenance row's stable source_kind / source_ref / fingerprint triple into the digest in sort-canonical order, mirroring the existing `borrador_bindings_trace_sha256` join-record pattern; an empty tuple yields the empty-string digest.
- Keep the additions purely additive so existing per-key payload readers are unaffected.

## Outcome

An audit reader can now detect a source-connectivity change from the bucket event's digest without decrypting the calculation revision, and can count the contributing source objects. The event stays a compact pointer back to the persisted revision, which carries the full typed trace.

## Notes

Folded into the same wave as S50 once the persisted `source_provenance` field existed. Confirmed no existing test asserts an exact `MODELO_CALCULATION_CREATED` payload key set (all readers use per-key access), so the additive keys are safe.
