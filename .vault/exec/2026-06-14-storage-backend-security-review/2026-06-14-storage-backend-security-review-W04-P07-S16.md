---
tags:
  - '#exec'
  - '#storage-backend-security-review'
date: '2026-06-14'
modified: '2026-07-17'
body_hash: 'sha256:b887c6648e08f5eb6504ecafad06025f46ccd1151ef1040c87427e1e73d685ef'
step_id: 'S16'
related:
  - "[[2026-06-14-storage-backend-security-review-plan]]"
---

# Add a cross-OS transaction provenance roundtrip test proving rehydration does not mutate the persisted shape

## Scope

- `src/aeat/domain/transactions/tests/`

## Description

- Add `test_provenance_source_path_is_stored_as_basename_only` (absolute path
  reduced to basename; no directory tokens in the JSON) and
  `test_provenance_basename_survives_rehydration_unchanged` (model_validate_json
  roundtrip is byte-equal, proving no cross-OS mutation).

## Outcome

The cross-OS roundtrip regression is locked. Both tests green. Committed in
`d7b001fa6`.

## Notes

The portable-export bundle inherits the fix automatically (it serialises the same
RawProvenance); no separate export change needed for this finding.
