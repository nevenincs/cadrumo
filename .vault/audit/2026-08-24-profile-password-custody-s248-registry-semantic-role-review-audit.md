---
tags:
  - '#audit'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:af92a603402823d467b744270f0e67d426aca9ce33aad7ff6ee6eecd0782cffd'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---
# `profile-password-custody` audit: `S248 registry semantic-role review`

## Scope

Reviewed the S248 portion of concurrent production commit `5362ab6539` and current HEAD: the Modelo 303 2026 CNAE semantic-role split, Modelo 390 2021 informational-versus-filing role split, continuity identities and evolutions, validator behavior, and authority/anti-tautology tests. Concurrent Modelo 369 work was excluded.

## Findings

No findings.

The five Modelo 303 CNAE roles correctly separate historical three-byte record-design fields from the 2026 four-byte fields without changing their row-specific continuity identities. Modelo 390's 2021 applicability-grade parser observations correctly remain unconstrained informational values, separate from the 2022-and-later bound, non-negative filing roles. Every split is grounded in reviewed AEAT record-design sources and explicit target-owned repurposed evolutions.

The registry validators were not weakened. The concurrent change strengthens declared-evolution validation, and the focused anti-tautology test proves that retaining one shared role across the three-to-four-byte transition still fails compatibility validation.

## Recommendations

- Close S248 on the 160-test focused proof and this formal PASS review.
- Track the unrelated Google source-catalogue literal and pre-existing type annotation diagnostic under their existing owners; neither changes the S248 verdict.
