---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:4bbccec569525b4626afa0d62b8a5c24cdd6143194638c4842efc92e4e16efb6'
step_id: 'S64'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# profile-binding-projection-boundary-verification

## Scope

- `apply canonical fix at correct boundary`
- `src/aeat/application/modelo/_profile_binding.py`

## Description

- Reviewed historical change `c5e28ca26e`, which introduced the application profile-binding projection and made the channel-routing decision depend on formula consumption rather than `typed_enum` metadata alone.
- Confirmed `_profile_fact_index` maps each stored canonical fact path and every declared model-selector alias, resolving the documented key-namespace and missing-projection failure classes at the application boundary.
- Re-ran `src/aeat/application/modelo/tests/test_profile_binding_real_path.py`; all 11 current regression tests passed.

## Outcome

The mismatch class was a profile-binding projection and channel-routing gap. It is already repaired at the canonical application boundary and remains covered by the current real-path suite.

## Notes

No new production code was required. The historical test file named by the original change no longer exists at that path; current coverage lives under `src/aeat/application/modelo/tests/`.
