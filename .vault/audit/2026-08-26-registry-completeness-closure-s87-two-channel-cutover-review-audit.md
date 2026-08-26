---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v1'
body_hash: 'sha256:6bf8b7fc575d589d6c1c3d45ecb3d259f1cb5020bba417d14c1b8f7a7333956a'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr]]"
---
# `registry-completeness-closure` audit: `s87 two channel cutover review`

## Scope

Independent current-head review of S87 capture `18a5d6b5de` and plan/record update `467824b98b` against plan row `W03.P05.S87`, the accepted two-channel export-proof ADR, S84-S86 execution records, secure-storage and registry-authority rules, and the live closure command. The mixed registry-facade and loader changes in the first commit were excluded except for interaction checks. The review used Vaultspec-RAG discovery, whole-epicentre and exact-symbol inspection, current-head re-check, and focused safe validation.

## Findings

### replay-receipt-freshness | medium | The generic closure composer can release an expired secure-replay receipt

`FilingExportSecureReplayReceipt` requires only a forward validity window, while `FilingExportProof` requires matching coordinate and provenance. The cutover composer then treats any complete typed assessment as satisfied without comparing `valid_until` to the current instant. The canonical dev authority performs that comparison, but every protocol-conformant authority reaches the generic application boundary, so a substitute authority can make a closure row satisfied with stale replay evidence. This violates the accepted ADR requirement for a current encrypted source-owned replay receipt. Add freshness validation at the application proof or coverage boundary and an expired-receipt injection regression proving a typed refusal.

### secure-custody-refusal-mapping | medium | Configured secure-custody availability failures escape instead of producing the required per-channel refusal

The canonical two-channel authority maps only `FilingExportError`, `OSError`, `RegistryValidationError`, and `ValueError` from replay to `secure_replay:custody_failed`. Real encrypted-storage availability failures, including `KeyringUnavailableError`, derive from the separate `PersistenceError` / `SecretStoreError` hierarchy and therefore bubble from the live command rather than becoming its promised public typed per-channel refusal. The path still fails closed, but it loses the required actionable classification. Map the bounded storage-failure family to `custody_failed` without exposing its exception detail, and cover a raising custody adapter through the canonical authority.

## Recommendations

- Resolve `replay-receipt-freshness` before relying on any non-default filing proof authority for closure eligibility; retain the live authority's existing freshness check as defence in depth.
- Resolve `secure-custody-refusal-mapping` before provisioning a replay source/custody pair for the live command, then re-run the live success/refusal and offline distinction checks on a valid bundled registry.
- The S87 cutover otherwise retains the law-selected model/revision/layout coordinate, requires both receipt objects for success, preserves typed channel refusals, projects no taxpayer payload or digest, and leaves the disabled `proof_for` port outside closure consumption.
