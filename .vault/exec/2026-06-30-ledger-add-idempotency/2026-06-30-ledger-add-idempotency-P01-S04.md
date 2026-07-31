---
tags:
  - '#exec'
  - '#ledger-add-idempotency'
date: '2026-06-30'
modified: '2026-07-17'
body_hash: 'sha256:774076f96baa663cd9aea111892973acba4b3f6ff7183c6703d03a73484f5770'
step_id: 'S04'
related:
  - "[[2026-06-30-ledger-add-idempotency-plan]]"
---

# Surface the duplicate no-op outcome as an info Notice on the ledger add envelope through the typed notice channel, never as a bespoke result field

## Scope

- `src/aeat/entrypoints/cli/_ledger.py`

## Description

- Detect the guarded no-op in the `ledger add` CLI handler via the empty `bucket_event_ids` returned by `create_manual_transaction`.
- Emit a typed info `Notice` (code `ledger.add.idempotent_noop`) on the envelope notices channel and fold the same localised line into text output so JSON and text cannot drift.
- Add the `cli.ledger.add.idempotent_noop` locale leaf in en/es/ca/hu.

## Outcome

Landed in commit `02c664890`. No bespoke result field added; the uniform mutation quintet is unchanged. Locale parity and translation-honesty gates pass.

## Notes
