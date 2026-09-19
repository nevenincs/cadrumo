---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:7ed4099bdaec766bce54092cd427d1f718e2b06a994ae3caf6ef018317475e33'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# `profile-password-custody` audit: `S259 M220 grounding review`

## Scope

Reviewed `W06.P12.S259` at current HEAD, with provenance traced through commits
`2b8164c1ae` and `62e45d6c59`. The review checked the Modelo 220 2025 revision,
its legal and record-design source identities, exact applicability windows,
revision selection, and the literal widened-2026 refusal snapshot in
`test_catalogue_verification.py`. The focused refusal test was executed directly
and passed. A mandatory post-S260 re-review then ran the complete M220-focused
selection set with 11 passing tests and the exact healthy referential-preflight
witness with 1 passing test. Production code and registry data were not modified.

## Findings

No findings. The 2025 revision is bounded by both `valid_from` / `valid_to` and
the period selector to calendar 2025. Its legal source identity names the 2025
declaration product even though the approving Orden was published in 2026, and
the source's `applies_from` / `applies_to` window is exactly 2025. The cited AEAT
record design is likewise `aeat-dr-220-2025`; no 2026 design or approving
authority is borrowed.

The refusal test asserts the committed 2025 bounds, proves 2025 selection,
requires literal 2026 selection to raise `NoRevisionForPeriodError`, then widens
only the selector in an immutable copy and proves the shared source-coverage
predicate still rejects the 2025 record design at 2026-12-31. This is a
non-tautological regression witness for the exact temporal overclaim S259 closes.

The post-S260 current state retains the exact same closed identities and windows:
`aeat-dr-220-2025` is an AEAT layout-authority source bounded from 2025-01-01
through 2025-12-31, and `boe-modelo-220-2025-form` truthfully names the 2025
declaration product approved by the 2026-published Orden while carrying that
same 2025 applicability window. The full M220 selection matrix and healthy
referential preflight both pass, so the intervening Modelo 182 repair introduced
no cross-model regression. No finding is open at any severity.

## Recommendations

No remediation is required for S259. Preserve the closed 2025 source window and
the literal 2026 refusal witness until a separately grounded 2026 Modelo 220
record design and approving authority are enrolled.
