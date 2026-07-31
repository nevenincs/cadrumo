---
tags:
  - '#exec'
  - '#arch-remediation-ports-inversion'
date: '2026-07-03'
modified: '2026-07-17'
body_hash: 'sha256:5506a63562381d11c4d81cdc01072c38d57add64cd9cff97e137a8f0cf84e057'
step_id: 'S20'
related:
  - "[[2026-07-02-arch-remediation-ports-inversion-plan]]"
---

# Declare the domain-not-adapters layer contract exhaustively rather than by exception list now that the seam is at zero

## Scope

- `.importlinter`

## Description

- Declare the `domain -> adapters` seam exhaustively rather than as a per-production-edge exception list in the broad layered contract.
- Add a first-class `[importlinter:contract:domain-not-adapters]` forbidden contract (sibling of `domain-not-application`): `source_modules = aeat.domain`, `forbidden_modules = aeat.adapters`, `allow_indirect_imports = true`, `unmatched_ignore_imports_alerting = error`.
- Pin the 53 sanctioned domain test-file roundtrip/anti-tautology edges individually as `ignore_imports`; production coupling is zero, so a new non-deferred production `domain -> adapters` import now fails this contract loudly.
- Correct the stale layered-contract comment that claimed the calculation/filing/verification sibling modules still hold lazy adapters imports (all migrated at HEAD).

## Outcome

Complete in commit `be5ca85b22`. `lint-imports --config .importlinter`: the new "Domain must not import adapters" contract is KEPT (all 53 test edges correctly ignored, zero production violation). This graduates the domain -> adapters seam from a buried exception list in the `layered` contract to its own enforced boundary, mirroring the S21 `domain-not-application` treatment. Opens the ADR's endgame: with this seam at zero, the only remaining sanctioned cross-layer holes are application -> adapters wiring and core resource loaders.

## Notes

The `layered` contract remains BROKEN — this is the pre-existing, separately ratchet-tracked application -> adapters wiring set, unchanged by this step and containing zero `domain -> adapters` violations. Committed with explicit pathspec verified before commit.
