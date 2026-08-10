---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:42a0d71c06cc22b8f8b2fad3c1b64f4e3464b2ca708099d6ad648bc310fb7b94'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `aeat-export-fragment-generator-authority` audit: `S33 render-profile refusal review`

## Scope

Independent S33 review of the render-profile loader and refusal validators, plus the real-behavior tests for profile mutations and the record-design intermediate. The review checked the accepted authority ADR, the S08 authority-gap research, and the S33 criteria: missing, duplicate, overlap, conflict, unknown-anchor, inapplicable, defaulted, legacy-derived, and source-hash drift refusal; real `Total:` recovery; distinct unsigned `Num` and signed `N` policy; and preservation of the `DP200000` variable envelope.

PASS: `validate_render_profile_authority` requires exact eligible-anchor equality, duplicate/overlap rejection, type-specific width-17 membership, and explicit singleton shapes. `load_render_profile` now enumerates every directory entry and refuses non-regular TOML fragments, so legacy-derived siblings cannot be silently ignored. Identity and source-evidence checks bind profiles to the expected design and hash-pinned binary.

The real workbook tests independently read `Total:` cells through `openpyxl`, compare every recovered integer with the intermediate, and retain the variable envelope markers. The real profile test asserts 3,323 unsigned `Num` anchors, 2,227 signed `N` anchors, 126 individually authored smaller rules, and excludes `DP200000` from fixed-field eligibility. Mutation tests use direct production models and no mocks, fakes, stubs, patches, skips, or xfails.

## Findings

No findings identified.

## Recommendations

PASS: No critical, high, medium, or low findings. Accept S33. Keep the variable-envelope composition and emitted-byte proof in the planned S32/S34 integration gates; no compatibility or fallback change is required here.
