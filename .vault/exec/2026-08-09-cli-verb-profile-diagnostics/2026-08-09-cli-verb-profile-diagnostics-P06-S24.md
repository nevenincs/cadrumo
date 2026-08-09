---
tags:
  - '#exec'
  - '#cli-verb-profile-diagnostics'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:8ebb68d332191d6e1e721751a4d82ff4081f8a7fb7ffbcaf86f5e370777e8fd6'
step_id: 'S24'
related:
  - "[[2026-08-09-cli-verb-profile-diagnostics-plan]]"
---
# Add real tests asserting the export refusal names the missing declarant-identity facts by operator label

## Scope

- `src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py`

## Description

- Added an anchor test asserting all three identity fields have labels differing from their paths.
- Added tests for the single-field and multi-field renderings, asserting the label appears and the raw path does not.
- Added a test asserting the rendering carries no Python container punctuation.
- Corrected the pre-existing export header test that pinned the raw-path context, to assert the schema-derived label instead.

## Outcome

All three refusal branches are covered against the real committed schema.

The punctuation test is not cosmetic pedantry: it pins the specific defect the previous shape had, where a list interpolated into the message surfaced brackets and quotes to the operator. Without it, a future change back to passing a list would satisfy every label assertion and silently restore that.

The corrected header test now derives its expectation from the schema rather than hardcoding a label, so it asserts the refusal routes through the canonical builder rather than pinning one spelling that a locale change would break.

## Verification

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_export_declarant_identity_grounding.py -n 0 -q
    4 passed in 1.17s

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_export_headers.py -m "unit or integration" -n 0 -q
    6 passed in 15.73s

## Notes

Each corrected assertion carries a guard that the derived label differs from the path, so a schema change collapsing the two would fail loudly rather than turning the assertion into a no-op.
