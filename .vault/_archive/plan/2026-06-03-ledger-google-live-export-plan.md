---
tags:
  - '#plan'
  - '#ledger-google-live-export'
date: '2026-06-03'
modified: '2026-07-14'
body_hash: 'sha256:0a84688d8692542b49c7cd649ac2943e29e59cb79ce8c84ca14781dc57272979'
tier: L2
related:
  - '[[2026-06-02-ledger-operator-hardening-plan]]'
  - '[[2026-06-02-ledger-operator-hardening-adr]]'
  - '[[2026-06-04-ledger-google-live-export-adr]]'
  - '[[2026-06-04-ledger-google-live-export-research]]'
  - '[[2026-07-14-google-optional-adapter-boundary-adr]]'
---

# `ledger-google-live-export` `ledger live Google Drive/Sheets/Gmail export` plan

## Historical status

This plan is retained as historical campaign evidence, not as an executable authority or proof that its checked rows shipped. Its successor is the accepted `2026-07-14-google-optional-adapter-boundary-adr`, which defines Google as an optional interoperability adapter over existing local authorities.

The checked rows preserve their original campaign state only. They do not establish current mandates for a live Google upload of the bucket ledger, a Sheet-to-ledger annotation and apply round trip, Gmail document acquisition, or self-skipping `live_write` tests. Current code instead provides a ciphertext Drive mirror with integrity reads, explicit Drive evidence acquisition through canonical attachment custody, non-authoritative calculation-Sheets export and typed readback, and OAuth Desktop authentication. Gmail acquisition is refused, calculation compute persists nothing, and ledger correction remains owned by the canonical ledger update service.

### Phase `P01` - Live Google Drive/Sheets/Gmail export

This phase recorded a proposed network continuation of earlier ledger work. Its wording and checked rows are preserved below for provenance; they must not be used as current implementation evidence or as authorization to recreate the claimed live-ledger, Gmail, or test behavior.

- [x] `P01.S01` - Live Drive/Sheets upload of the bucket ledger (outbound adapter) for manual review; `src/aeat/adapters/outbound/google/`.
- [x] `P01.S02` - Operator manual-review-in-Drive round trip (open exported sheet, annotate, re-pull, apply); `src/aeat/adapters/outbound/google/`.
- [x] `P01.S03` - Live Gmail/Drive document-link resolution: fetch justificante/invoice from recorded links; `src/aeat/adapters/outbound/google/`.
- [x] `P01.S04` - OAuth credential wiring: load the staged client-secret and run the authenticated session; `src/aeat/adapters/outbound/google/_oauth_flow.py`.
- [x] `P01.S05` - live_write opt-in integration tests self-skipping without OAuth credentials; `src/aeat/adapters/outbound/google/`.

## Description

Historical plan record superseded by the accepted optional-adapter boundary.

## Steps

No Steps in this file remain executable. The checked state is historical metadata.

## Parallelization

None. Any future Google or provider-neutral capability requires current authority in its owning domain.

## Verification

Verify current behavior against the accepted successor ADR, its implementation Reference, and current source rather than these checkbox states.
