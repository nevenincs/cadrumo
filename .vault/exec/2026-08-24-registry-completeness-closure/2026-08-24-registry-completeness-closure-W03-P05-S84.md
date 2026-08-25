---
tags:
  - '#exec'
  - '#registry-completeness-closure'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:9de8b1e41cb00822931984490f29bd9a9b5e1476854ae990906d1a0fb733174d'
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
- Required source-owned replay evidence to carry a one-for-one expected-byte value for every declared official probe. Custody compares each emitted payload slice exactly before it can persist an all-true record; offsets that are merely in bounds are insufficient.
- Disabled the legacy source-owned live-proof route fail-closed so it cannot write a taxpayer-bearing payload through a plaintext temporary path.
- Kept canonical conformance and replay enrollment empty; S85 owns enrollment.

## Outcome

The S84 proof-port and custody boundary are implemented. Both channels use the sole `export_draft` writer. Secure replay uses the typed in-memory destination and encrypted profile custody without a plaintext output path. The canonical authority cannot accept a public receipt as input, and missing source/custody authorities produce explicit secure-replay refusal. Public conformance vectors cannot carry taxpayer-capable filing inputs. Public replay receipts exclude taxpayer values, draft and producer state, payload bytes, payload digest, output path, and emitted extent.

The original implementation was captured across shared-tree commits `b7852e8196` (application contract) and `f5af07f91f` (registry integration and initial execution record). Independent audit `8fd32b7853` then found HIGH caller receipt self-attestation, HIGH taxpayer-capable public conformance inputs, and MEDIUM legacy plaintext-temporary exposure. S84 was reopened through the Vault CLI. Remediation was captured by shared writer commit `44a055dcaf`, which also included concurrent non-S84 filing/modelo/operator-output/wizard/core files; this provenance is recorded without rewriting shared history. Opaque receipt identity and the negative public-API assertion followed in `7f1c8bc266`. Re-review audit `e738673a8d` confirmed the original findings resolved and identified one residual MEDIUM: custody bounds-checked probe spans but did not compare expected bytes. Scoped remediation `dba75ffaa9` added that exact comparison. Final independent Terra review `8433e0886d` passed with no findings. S84 was then closed through the Vault CLI.

Verification: scoped Ruff passed; focused application/registry/custody tests passed (`11 passed`); encrypted storage namespace/lineage tests passed (`49 passed`). The custody tests use the real isolated bucket runtime and existing encryption, verify exact round-trip, scan for plaintext canaries, refuse a validly re-encrypted receipt-identity substitution, and refuse a same-length wrong-byte payload probe. The canonical API test proves a preconstructed receipt keyword is refused at runtime. The feature-scoped Vault check passed all gates with two pre-existing body-section warnings on the source-casilla predecessor reconciliation audit.

## Notes

- No filing revision, representative year, taxpayer fixture, accepted payload digest, or replay receipt was enrolled by this step.
- The storage-only custody fixture uses a deliberately non-registry coordinate and is not acceptance evidence.
- S33 remains open; S85 and S86 retain dynamic enrollment and dual-channel release-gate ownership.
