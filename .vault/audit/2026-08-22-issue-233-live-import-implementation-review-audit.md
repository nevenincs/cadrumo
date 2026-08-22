---
tags:
  - '#audit'
  - '#issue-233-live-import'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:f74614c129c43267eaaa8cd36b416671d4bc855f6baea6c1873f0b6b372d58da'
related: []
---

# `issue-233-live-import` audit: `implementation review`

## Scope

Reviewed the issue 233 phase-two live filed-observation composition, its
justificante-only boundary, source lexical retention, missing-work-unit path,
refusal behavior, amendment reach, and filed-pull CLI reporting.

## Findings

### baseline-time | medium | Imported historical filing uses capture-run time

The live source passes no clock to `import_external_filing_source`, so the
external baseline is dated at the current capture run rather than the filed
observation's authoritative `presented_at`. This makes historical amendments
chronologically misleading and must be corrected before commit.

## Recommendations

Pass the filed observation's `presented_at` as the baseline clock and pin it in
the behavioral test. Retain the current refusal of M303, non-numeric manifests,
and justificante-only metadata; none of those sources can honestly satisfy the
numeric complete-baseline contract.

The finding is resolved in the corrective implementation: the live observation
now supplies `presented_at` as the baseline clock, and the real persistence test
asserts the filed-record timestamp exactly.
