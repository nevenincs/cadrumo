---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
body_hash: 'sha256:82c7f93f843a46b0526231f04508496aa94514d4872c87e2997b0d640081abfa'
step_id: 'S09'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add the anti-tautology corrupt-payload proof: mutate the on-disk register to delete a field, reload, assert ValidationError or strict inequality surfaces

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`

## Description

- Add two anti-tautology proofs to the roundtrip suite that reach into the encrypted `SecureObjectRow`, decrypt with the payload AAD, mutate the on-disk document, re-encrypt, and reload.
- Corrupt probe: rewrite the first entry's `provisional_percentage` and assert the strict-equality witness surfaces the drift (`reloaded != original`, value now the corrupted one).
- Absent-field probe: delete the required `regime` field and assert the load path raises `pydantic.ValidationError` naming `regime`, never a silent re-default.

## Outcome

Both probes bite: the corruption is caught by strict inequality and the deleted required field raises at load. If either passed silently, the register persistence boundary would be tautological.

## Notes

The absent-field probe deletes `regime` (a required, non-defaultable field) rather than an optional field, so the drop genuinely raises; an optional field would silently re-default and not prove the boundary.
