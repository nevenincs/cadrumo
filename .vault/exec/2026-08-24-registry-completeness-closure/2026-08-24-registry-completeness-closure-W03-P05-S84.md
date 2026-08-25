---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:0d896f6f272260d09764daa04d6527bf1356344ea62dfc3e67dcbd7b420eade7'
step_id: 'S84'
related:
  - "[[2026-08-24-registry-completeness-closure-plan]]"
---
# Implement a two-channel filing export proof port: value-independent official-layout conformance plus encrypted operator-specific source-owned replay, using only the canonical export_draft writer.

## Scope

- `src/cadrumo/application/filing/`
- `src/cadrumo/adapters/persistence/profile/`
- `src/cadrumo/adapters/persistence/storage/`
- `dev/registry/`

## Description

- Added strict public conformance, secure replay, composite proof, assessment, and per-channel refusal contracts.
- Extended the canonical `export_draft` writer with an exactly-one destination contract for filesystem output or synchronous validated in-memory custody.
- Made the committed conformance vector coordinate/provenance/probe metadata only. Taxpayer-capable draft, producer, dictionary, election, and product inputs are absent from its model and can only be materialised transiently by the separately enrolled mechanism builder.
- Removed caller-supplied replay receipts from the canonical authority. It now invokes the named source authority and custody itself, validates the source evidence and canonical writer result against the reloaded internal custody record, then projects a public receipt carrying only its opaque identity and non-secret claims.
- Added the `cadrumo.application.filing.export_replay_proofs` financial structured-custody namespace and a concrete `SecureBoundRepository` adapter. Custody persists the internal record through the existing encrypted profile substrate and requires an exact re-read before returning it.
- Disabled the legacy source-owned live-proof route fail-closed so it cannot write a taxpayer-bearing payload through a plaintext temporary path.
- Kept canonical conformance and replay enrollment empty; S85 owns enrollment.

## Outcome

The S84 proof-port and custody boundary are implemented. Both channels use the sole `export_draft` writer. Secure replay uses the typed in-memory destination and encrypted profile custody without a plaintext output path. The canonical authority cannot accept a public receipt as input, and missing source/custody authorities produce explicit secure-replay refusal. Public conformance vectors cannot carry taxpayer-capable filing inputs. Public replay receipts exclude taxpayer values, draft and producer state, payload bytes, payload digest, output path, and emitted extent.

The original implementation was captured across shared-tree commits `b7852e8196` (application contract) and `f5af07f91f` (registry integration and initial execution record). Independent audit `8fd32b7853` then found HIGH caller receipt self-attestation, HIGH taxpayer-capable public conformance inputs, and MEDIUM legacy plaintext-temporary exposure. S84 was reopened through the Vault CLI. Remediation was captured by shared writer commit `44a055dcaf`, which also included concurrent non-S84 filing/modelo/operator-output/wizard/core files; this provenance is recorded without rewriting shared history. The remaining opaque receipt identity and negative public-API assertion were committed separately. Independent re-review remains separate.

Verification after remediation: scoped Ruff passed; focused application/registry/custody tests passed (`10 passed`); encrypted storage namespace/lineage tests passed (`49 passed`). The custody tests use the real isolated bucket runtime and existing encryption, verify exact round-trip, scan for plaintext canaries, and refuse a validly re-encrypted receipt-identity substitution. The canonical API test proves a preconstructed receipt keyword is refused at runtime. A later current-head rerun was blocked during collection by concurrent bucket-pointer WIP (`exclusive_file_lock` missing and a `None` bucket id); those files are outside S84 ownership. S84 therefore remains CLI-open pending a stable-head re-run and independent review.

## Notes

- No filing revision, representative year, taxpayer fixture, accepted payload digest, or replay receipt was enrolled by this step.
- The storage-only custody fixture uses a deliberately non-registry coordinate and is not acceptance evidence.
- S33 remains open; S85 and S86 retain dynamic enrollment and dual-channel release-gate ownership.
