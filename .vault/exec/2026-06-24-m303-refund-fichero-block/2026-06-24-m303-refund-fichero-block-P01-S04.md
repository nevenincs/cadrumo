---
tags:
  - '#exec'
  - '#m303-refund-fichero-block'
date: '2026-07-04'
modified: '2026-07-17'
body_hash: 'sha256:34f2743a0c78ca68df3ae52c63617a319ab3c27f1638b375d02ef4433cf9ac46'
step_id: 'S04'
related:
  - "[[2026-06-24-m303-refund-fichero-block-plan]]"
---

# Add the secure-storage roundtrip and anti-tautology proof for the new financial refund-account fields

## Scope

- `src/aeat/domain/user_profile/tests`

## Description

- Add the secure-storage roundtrip test for the refund-account financial fields: build a profile carrying the IBAN, SWIFT-BIC, and the full foreign-bank block at non-default values, push it through the real encrypted SQL boundary, reload, and assert strict equality plus per-field value equality.
- Populate the foreign-bank block with a genuinely non-default fixture (US bank, CHASUS33XXX SWIFT-BIC, full address) so a save-drops-field regression cannot hide behind a default.
- Add the anti-tautology proof: surgically corrupt the persisted IBAN fact inside the on-disk JSON envelope, reload through the real decrypt/parse pipeline, and assert strict inequality against the in-memory original.

## Outcome

- `src/aeat/application/user_profile/tests/test_refund_account_persistence_roundtrip.py` exercises the real `EphemeralMasterKeyProvider` / SQLite encrypted boundary, asserts `loaded == original`, and asserts each refund-account fact value survives the cycle.
- The anti-tautology test corrupts exactly one persisted IBAN fact and asserts the reload surfaces the corruption as strict inequality, so a broken boundary reds the gate.
- The test also carries the IBAN validator acceptance/rejection cases. The full file passes at HEAD.

## Notes

- This record documents the verified landed state at HEAD; the test satisfies the roundtrip-discipline mandate (real adapters, strict pydantic equality, non-default fixture, anti-tautology proof).
