---
tags:
  - '#audit'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:08e39fe4491b8c30ea4bba7aa571c44b5d81558bec976122660c66ad267f413d'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
  - "[[2026-08-25-registry-completeness-closure-s33-two-channel-export-proof-adr]]"
---
# `registry-completeness-closure` audit: `S84 independent two-channel proof review`

## Scope

Read-only independent review of commits `b7852e8196` and `f5af07f91f` against the accepted S33 two-channel export-proof ADR, supporting research and decision review, plan row `W03.P05.S84`, and its execution record. The review used semantic discovery, whole-file and exact-symbol inspection, and a fresh-current-state check. It covers sole-writer/destination topology, dynamic refusal, value-independent conformance, secure source-owned replay, custody, receipt secrecy, test integrity, and plan integrity.

## Findings

### secure-replay-self-attestation | high | A caller-built public receipt can satisfy the secure channel without custody

`CanonicalTwoChannelFilingExportProofAuthority.assess_for` in `dev/registry/filing_export_proof.py:185` selects a member of the caller-supplied `secure_replay_receipts` tuple and checks only freshness and public provenance before returning a complete proof. `FilingExportSecureReplayReceipt` in `src/cadrumo/application/filing/_export_proof.py:286` is directly constructible, with every substantive outcome claim defaulting to `True`; the contract test constructs one directly. Whole-tree confirmation finds no concrete `resolve_secure_replay` or `persist_secure_replay` implementation, only the protocols at `src/cadrumo/application/filing/_export_proof.py:231` and `:273`. Once S85 supplies conformance, a fabricated fresh provenance-matching receipt can therefore satisfy secure replay without approved source resolution or encrypted custody, contrary to S33.

### public-vector-self-classification | high | The value-independent channel admits taxpayer-capable models on its public vector

`FilingExportConformanceRequest` at `src/cadrumo/application/filing/_export_proof.py:120` carries `ModeloDraft`, `FilingProducerSnapshot`, and arbitrary dictionary values; those models contain taxpayer tax identifiers, identity facts, accounts, and casilla values. The asserted public classification at `:130` is only the required literal `non_sensitive_mechanism_vector`, and `STRICT_FROZEN_HIDDEN_INPUT_CONFIG` only suppresses invalid input in validation errors. `FilingExportConformanceVector` at `dev/registry/filing_export_proof.py:148` adds no independent classifier, provenance source, or serialization guard. The type boundary therefore cannot prevent a real taxpayer draft or producer snapshot from becoming a committed S85 vector, violating S33's value-independent and secret-free conformance constraint.

### legacy-proof-temp-output | medium | The remaining live-proof route will write an enrolled source-owned payload to plaintext temp storage

`FilingExportLiveProofEntry` in `dev/registry/filing_export_proof.py:103` accepts a draft, producer snapshot, and accepted payload digest, while `_execute_export` at `:481` writes the rendered result through `TemporaryDirectory`. Its canonical entry tuple is currently empty, so no current secret is exposed, and S84's new consumer route itself avoids a file. Nevertheless this is still the live closure authority's export path; enrolling a source-owned entry there would violate secure-storage-only custody rather than refusing or routing via encrypted in-memory replay.

## Recommendations

- Replace caller-supplied replay receipts with a custody-backed resolver that retrieves and validates an encrypted internal record or opaque, verifiable attestation before projecting its secret-free receipt. Add a forged-receipt refusal test and real secure-storage roundtrip plus mutation tests.
- Split public conformance inputs from taxpayer-capable filing models. Derive a restricted non-sensitive specimen type or approved public data source, make classification independently verifiable, and prove committed vectors cannot serialize taxpayer identity, values, accounts, payloads, digests, paths, or byte extents.
- Fail closed on source-owned entries in the legacy live-proof route and reserve filesystem temporaries for independently classified public conformance only. Route any real replay through the typed in-memory destination and encrypted custody.
- Do not represent S84 as a completed secure source-owned replay boundary until these findings are resolved and verified under S85/S86's dynamic enrollment and gate work.
