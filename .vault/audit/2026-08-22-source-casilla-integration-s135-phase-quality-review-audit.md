---
tags:
  - '#audit'
  - '#source-casilla-integration'
date: '2026-08-22'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:6fde3cd4d675e0acc03e8c6f2375eedecbb42b3f172d1775b258a4f088ddb219'
related: []
---

# `source-casilla-integration` audit: `s135 phase quality review`

## Scope

Reviewed the accepted composite-provenance amendment, Steps S149-S154, the canonical application/domain provenance carriers, calculation revision identity, encrypted persistence, IVA wallet lineage, M720 blocking posture, CLI projection, and live connectivity authority. Re-ran semantic sentinels and focused unit/integration suites against current HEAD.

## Findings

### s135-phase-quality-review | high | S135 does not itself corrupt the encrypted payload

The integration test persists valid rival revisions and proves authority refusal, and the encrypted round-trip suite separately deletes required provenance keys from decrypted secure-object payloads. However, S135's own `anti_tautology_mutation=True` proof is not paired with a raw encrypted-record mutation in its scoped test file. The evidence is real across the combined suite but the S135 claim is not self-contained.

Resolved on 2026-08-23: S135 now asserts strict encrypted round-trip equality, deletes `lineage_role` from the stored catalogue payload, re-encrypts it, and proves repository rehydration refuses the corrupted record.

### s135-phase-quality-review | medium | retired provenance names remain in domain documentation and validation text

`CalculationSourceRef` documents `source_kind` and `binding_source`, and its validation errors use those retired names even though the strict schema exposes `contributor_source_kind` and `contributor_binding_source`. This does not create a compatibility path, but it misstates the public persisted contract and weakens failure diagnosis.

Resolved on 2026-08-23: the carrier documentation and validation messages now name the canonical resolved and contributor axes, with focused domain verification.

## Recommendations

- Add a raw secure-object payload deletion or mutation test directly to S135 and assert strict rehydrated equality before corruption.
- Rewrite the persisted carrier documentation and validation messages to name the canonical contributor axes; retain existing locale keys only where they are internal identifiers rather than user-visible schema vocabulary.
