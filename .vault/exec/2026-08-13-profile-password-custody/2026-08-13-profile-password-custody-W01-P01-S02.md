---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:7c26a4a6755f74df6a0060699bd855682e53142b18dc2093a9d2e2a4abdf4ea2'
step_id: 'S02'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# Have Sol Medium review the custody contract and taxonomy against the accepted hard-cutover constraints before cryptographic work starts

## Scope

- `src/cadrumo/adapters/persistence/storage/custody/`

## Description

- Audit the strict current-format custody schema, raw parser, password representation, refusal taxonomy, storage taxonomy ownership, public exports, and localized error registration against the accepted custody decisions.
- Prove exact canonical-byte refusal, duplicate and unknown-member refusal, foreign-version refusal, self-digest integrity, the 704-byte early parser ceiling, bounded generation, and fixed-length canonical base64 closure.
- Prove 15-to-256 Unicode scalar and 1,024-byte strict UTF-8 password semantics without normalization, trimming, folding, or replacement.
- Verify refusal context cannot override the canonical refusal reason and confirm no provider selection, shared-master fallback, legacy reader, or compatibility path enters the new custody package.
- Run focused real production-import tests, storage-taxonomy and error-registry gates, Ruff, and custody-scoped basedpyright.

## Outcome

The custody contract and taxonomy pass the mandatory architecture review with no unresolved critical or high finding. The strict envelope has one canonical byte representation, refuses oversized input before decode or JSON allocation, closes every variable-width field, preserves the approved password sequence exactly, and exposes stable typed refusals through the registered public boundary. Focused verification completed with 64 tests passing, Ruff clean, and custody-scoped basedpyright reporting zero errors.

## Notes

Two review rounds initially found non-canonical raw input acceptance, refusal-context override, and an unbounded durable parser. Each issue was remediated and independently re-proved before this Step was closed. No production code, product storage, remote state, Git state, shared service, or later plan Step was changed by the review.
