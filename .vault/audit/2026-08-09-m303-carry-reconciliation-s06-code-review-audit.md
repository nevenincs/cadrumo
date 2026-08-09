---
tags:
  - '#audit'
  - '#m303-carry-reconciliation'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:6eb1c226bcf8790a3457608fbc1a0dbc5677437ec1d1e942c24ddae19f040eb7'
related:
  - "[[2026-08-07-m303-carry-reconciliation-plan]]"
---
# `m303-carry-reconciliation` audit: `M303 carry reconciliation S06 code review`

## Scope

Reviewed S06's Modelo 390 annual-partition reader and its migrated real-behaviour tests against the amended carry-reconciliation ADR and the S06 plan row. The review covered only the envelope reader and listed test migrations; S08 wallet recurrence remains outside this S06 scope.

## Findings

No open findings. The reader accepts `ObservationEnvelopePayload` rather than bare casilla observations, validates each persisted envelope after decryption and again before FIFO state construction, and refuses missing explicit generated or available values rather than reconstructing `available` from `posterior + generated`. The shared normalized-envelope validation rejects missing, duplicate, invalid, sign-incompatible, and conflicting disposition evidence, plus inconsistent available/generated pairs. Identical negative inputs with `C` and `D` dispositions stay distinct: carry reaches the FIFO partition only for `C`, while `D` contributes zero to Modelo 390 boxes 97 and 662. Existing carried-pending FIFO and live M390 oracle lanes remain real-store tests and retain their pre-existing assertions.

## Recommendations

Approved for S06. Keep S08 as a separate wallet-consumer change using the already validated envelope contract; do not let the wallet recover disposition from bare casillas or reintroduce an available reconstruction fallback.
