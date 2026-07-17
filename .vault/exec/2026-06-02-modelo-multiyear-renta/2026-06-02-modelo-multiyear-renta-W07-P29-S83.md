---
tags:
  - '#exec'
  - '#modelo-multiyear-renta'
date: '2026-07-06'
modified: '2026-07-17'
step_id: 'S83'
related:
  - "[[2026-06-02-modelo-multiyear-renta-plan]]"
---

# enroll M720 in the authorization manifest with renta_years claim matching the recorded year-set (vaultspec-code-reviewer)

## Scope

- `src/aeat/_data/registry/aeat/authorization.toml`

## Description

- Keep Modelo 720 enrolled in the directory-mode authorization manifest for 2023 and 2024.
- Update the manifest note to describe strict prior-year binding resolution and explicit-zero evidence honestly.
- Preserve `threshold_continuity` as the evidence class.

## Outcome

- Satisfied by `authorization.d/720.toml`.
- The authorization gate accepts the Modelo 720 manifest entry and matching two-year evidence.
- The manifest no longer claims that an absent legal block is invented as zero.

## Notes

- Verified by the final scoped M720/M721 run, which passed 90 targeted tests after review fixes.
