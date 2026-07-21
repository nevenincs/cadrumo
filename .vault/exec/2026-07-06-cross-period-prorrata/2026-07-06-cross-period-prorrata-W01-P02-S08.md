---
tags:
  - '#exec'
  - '#cross-period-prorrata'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S08'
related:
  - "[[2026-07-06-cross-period-prorrata-plan]]"
---

# add the strict save/load/equality roundtrip test with every defaultable field populated non-default, using the real EphemeralMasterKeyProvider and SQLite engine (aeat-roundtrip-discipline)

## Scope

- `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py`

## Description

- Add the strict save/load/equality roundtrip test in `src/aeat/adapters/persistence/profile/tests/test_prorrata_register_roundtrip.py` using the real `EphemeralMasterKeyProvider` and SQLite engine via `isolated_runtime_profile`.
- Populate every defaultable field across the register with a non-default value: a fully-settled carried entry (provisional percentage + provenance + source-observation identity + definitive percentage + both volume inputs) and a second AEAT-authorised especial entry carrying a sector id and authorisation reference.
- Assert `loaded == original` field-for-field, plus an upsert-replaces-by-key roundtrip.

## Outcome

The register survives the encrypted SQL cycle field-for-field; the upsert path replaces a key's entry in place. Real adapters throughout (no mocks), per the roundtrip discipline.

## Notes

None.
