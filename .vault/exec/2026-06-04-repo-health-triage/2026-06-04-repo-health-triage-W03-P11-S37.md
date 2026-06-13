---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'W03.P11.S37'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-live-auth-decomposition-adr]]'
  - '[[2026-06-04-repo-health-triage-live-auth-split-invariants-audit]]'
---

# W03.P11.S37 - Prepare dedicated live-auth decomposition ADR

Scope: persist the architecture decision for live/auth decomposition boundaries before implementation.

## Description

- Used the repo-health triage research and W03.P11.S36 live/auth invariant audit as grounding.
- Wrote the dedicated live-auth decomposition ADR.
- Kept the decision docs-only: no code movement, auth behavior change, schema change, or test rewrite.

## Outcome

- The ADR selects custody-boundary decomposition:
  - application auth owns session acquisition, provider selection, active-profile identity checks, acquisition locking, and operator-safe auth projections;
  - AEAT auth adapters own provider mechanics, metadata, diagnostics capture, and verification;
  - browser adapters own Playwright context construction and certificate/storage-state injection;
  - application live owns live-read orchestration and persistence handoff;
  - CLI owns argument and rendering surfaces only.
- The ADR rejects per-command, per-modelo, and per-live-surface auth definitions.
- The ADR carries regression evidence requirements for the future implementation slices.

## Verification

- `uv run --no-sync vaultspec-core vault plan check .vault/plan/2026-06-04-repo-health-triage-plan.md`

## Notes

- The ADR uses existing research plus the S36 audit because no separate live-auth decomposition research file existed.
- No Ruff or pytest target was run because the slice changes only VaultSpec artifacts.
