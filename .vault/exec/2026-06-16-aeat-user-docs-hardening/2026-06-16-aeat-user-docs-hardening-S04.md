---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S04'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden choose-modelo.md

## Scope

- `docs/how-to/choose-modelo.md`

## Description

- Verify-close: read `choose-modelo.md` in full against the aeat-user-docs-hardening + aeat-documentation-workflow standard and confirm the page's audit findings are resolved at HEAD.
- Confirm finding M7 (overview explain vs profile preflight read as a contradiction): the page now explains the distinction on-page - applicability facts vs filing-context facts - so a `ready` preflight is not sold as an applicability confirmation.
- Confirm finding m8 (domain enumeration incomplete): the domain list now includes `cross_tax`, `irnr`, `patrimonio`, and `iae`, and the `modelo describe` structure counts are documented.
- Confirm every documented `aeat ...` command resolves against the live CLI (conformance gate).

## Outcome

- Page verified compliant at HEAD; audit findings M7 and m8 resolved (via the 2026-06-19 documentation batch). Delta: none required this pass.
- Voice is imperative, taxpayer-general (NIF/CIF/DNI/NIE), story-driven with resolving cross-links; no first-person-plural, gerund-header, or self-praise anti-patterns.

## Notes

- CLI conformance gate green (58 passed) across the how-to surface. No page edit needed.
