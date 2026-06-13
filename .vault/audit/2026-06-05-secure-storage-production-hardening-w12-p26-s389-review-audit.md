---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-06-05-secure-storage-production-hardening-W12-P26-S389]]'
---

# `secure-storage-production-hardening` `W12.P26.S389` Review

## S389-001 | PASS | Root landing rendering is presentation-only

Reviewed the S389 scope as `vaultspec-code-reviewer`. `_root_landing.py` consumes a
`RootLandingReport` and emits localized CLI lines. It does not resolve active-profile
pointers, inspect manifests, load settings, construct storage repositories, read
environment variables, or catch exceptions.

## S389-002 | PASS | Active-profile state is projected upstream

The renderer only branches on `landing.active_profile is not None` and interpolates the
already-projected profile label into localized text. The root callback and application
operator-surface builder own discovery; the renderer has no storage authority.

## S389-003 | FIXED | Root-help assertion matched stale tax-id placeholder

The installed-console refusal currently guides operators with
`--tax-id DNI/NIE/NIF/CIF`. The root-help test still asserted the older `--tax-id NIF`
substring, so it failed against the localized guidance. The assertion now matches the
current user-facing placeholder.

## S389-004 | PASS | Validation

- Focused ruff passed for the root landing renderer, related root-help tests, and the
  shared Google config module loaded by the command tree.
- Focused integration tests passed with 7 selected root-help/operator-surface tests.
- `python -m aeat.locales audit` passed.

Reviewer note: no critical, high, medium, or low findings remain for the S389 slice.

Disposition: close `AFR-287` as `manifest-discovery`.
