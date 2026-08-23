---
tags:
  - '#exec'
  - '#issue-620-external-pdf-signal'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:9e15b4e0c0e49d06ff2402e70765e02e01ce9b827d6a7d00e78bcd82611621cb'
step_id: 'S12'
related:
  - "[[2026-08-23-issue-620-external-pdf-signal-plan]]"
---




# Adjudicate all ten candidates against pinned official bases and registry applicability

## Scope

- `src/cadrumo/tests/fixtures/external_layout_candidates/{036`
- `130`
- `131`
- `303`
- `349}/*.json`

## Description

- Replace the legacy unverified flag in all ten candidate sidecars with
  independent artifact-authenticity, official-base-derivation, and registry-
  applicability verdicts.
- Pin every official AEAT or BOE source by URL, SHA-256, complete one-based page
  mapping, measured comparison evidence, and the opposite candidate's digest.
- Remove the temporary legacy-authority compatibility field and require the
  adjudication contract for every loaded sidecar.
- Update the focused contract test to reject the removed legacy field.

## Outcome

- All ten artifacts remain explicitly classified as third-party samples while
  their derivation from pinned official form bases is recorded separately.
- M130 and M131 align with current authored revisions; M303 aligns with the
  historical authored `2025` revision; M036 and M349 retain historical layout
  evidence without claiming an authored applicable revision.
- Exact 96-dpi pair equality is recorded only for M130, M131, and M303. M036
  and M349 record their measured normalized-MAE similarities instead.
- Ruff passed for the contract implementation and unit module.
- The focused candidate-contract unit module passed: 36 tests.

## Notes

No candidate byte is called official, and no live network availability is
required by the offline contract.
