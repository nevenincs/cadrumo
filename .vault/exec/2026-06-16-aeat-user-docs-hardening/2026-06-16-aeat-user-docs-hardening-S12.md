---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S12'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden filing-readiness.md

## Scope

- `docs/how-to/filing-readiness.md`

## Description

- Verify-close: read `filing-readiness.md` in full against the hardening standard and confirm its audit findings are resolved at HEAD.
- Confirm the readiness/dependencies/history/compare/project commands are documented with real flags and resolve against the live CLI; the `--ccaa` usage is the comunidad autónoma of tax residence (correct usage, not a single-group term).
- Confirm the extrapolation-flag caveat and the withholdings-default-to-zero caveat are stated so a reader does not over-trust a partial-quarter projection.

## Outcome

- Page verified compliant at HEAD. Delta: none required this pass.
- Imperative headers, per-command examples, explicit "read the extrapolation flag" caution, resolving cross-links.

## Notes

- Audit findings m9 (`--binding KEY=VALUE` literal placeholder) and m10 (`overview calendar` on a minimal profile) are doc-clean here: `KEY=VALUE` and `<...>` are used consistently as obvious placeholders across the how-to surface, and m10's calendar behaviour is an app/other-page concern. CLI conformance gate green.
