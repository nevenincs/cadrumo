---
tags:
  - '#plan'
  - '#auth-frontend-uniformity'
date: '2026-10-02'
tier: L1
related:
  - '[[2026-07-25-censal-profile-autofill-adr]]'
  - '[[2026-08-11-tui-architecture-adr]]'
  - '[[2026-08-13-auth-certificate-lifecycle-successor-adr]]'
modified: '2026-10-02'
body_schema: body-v2
body_hash: 'sha256:71cb794a2a7c5f1e819a5babb8bbfc652f029a588ff5500901fe554b396dfca1'
---

# `auth-frontend-uniformity` plan

## Description

Approved 2026-10-02

The user explicitly requested uniform backend use from CLI and TUI, removal of duplicate implementation, and equally rigorous sanitization and envelopes. This authorizes local corrections and verification. Accepted profile-auth, operation-supervision, and certificate-lifecycle decisions govern all Steps; no new credential lifecycle or persisted schema is introduced. The profile preference records operator intent; workflow auth state records operational configuration and session metadata. Configuration keeps them aligned through one application owner, and live selection honors profile intent. Frontends submit the same registered operation and consume safe typed results and refusal codes. Credential data remains under existing encrypted profile and secret boundaries. Preserve concurrent filing and locale work.

## Steps

- [x] `S01` - Unify provider configuration with encrypted profile preference, baseline checks, reset, and idempotent application results; `src/cadrumo/application/auth and src/cadrumo/application/user_profile/fact_write.py and owning tests`.
- [ ] `S02` - Dispatch CLI and TUI authentication selection through the same registered operation and safe public contracts; `src/cadrumo/entrypoints/cli/config and src/cadrumo/entrypoints/tui/profile and installed account composition and owning tests`.
- [ ] `S03` - Prove cross-frontend persistence, refusals and sanitization, refresh captures, and finish integrated review; `dev/tui/harness and auth/profile integration tests and generated CLI reference and scoped audit`.

## Parallelization

Execute sequentially in the shared worktree. One writer owns authentication, profile composition, and verification. No agent delegation.

## Verification

Run real encrypted-profile CLI/TUI integration checks for each provider, QR/app routing, repeated configure, reset, missing route, invalid choice, stale baseline, locked profile, and identity refusal. Exercise the registered operation envelope, public observation, and strict result serialization. Assert sensitive inputs never appear in results, events, diagnostics, or refusal text. Run owning tests, Ruff format/lint, ty, import/operation boundary checks, and scoped vault checks. Generate current authentication and wizard PNG sets in separate named runs and verify HTTP bytes, source fingerprints, geometry, and glyph coverage. Record unrelated baseline failures separately. Review the integrated change before plan closure.
