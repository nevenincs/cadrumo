---
tags:
  - '#exec'
  - '#cross-domain-continuity'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:536e3e3a490da7cd3449aeda93e1ecb90d83412fd508e2fa5a29f69084e77093'
step_id: 'S183'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
  - "[[2026-07-10-cross-domain-continuity-audit]]"
---

# modelo-232-annual-deadline-verification

## Scope

- `src/aeat/_data/registry/aeat/modelos/232/`

## Description

- Grounded the two registered annual windows against the current AEAT calendar, the Modelo 232 instructions, and Orden HFP/816/2017 article 4.
- Resolved the live registry and confirmed 2025 0A opens and closes on 2026-11-01/30, while 2026 0A opens and closes on 2027-11-01/30.
- Added the missing 2025 assertion to the existing real-registry deadline test beside the already-covered 2026 window.
- Ran the dedicated registry suite: 28 passed; `ruff check` also passed.
- Obtained an independent review, then a follow-up review confirming the focused assertion resolves the coverage finding.

## Outcome

Modelo 232 annual windows for fiscal years 2025 and 2026 are legally grounded, runtime-resolvable, and now protected by exact real-registry date assertions.

## Notes

No production behavior changed. The test uses the committed registry and statutory dates rather than a mirrored deadline calculation.
