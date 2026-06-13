---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
  - "[[2026-04-13-aeat-mantenimiento-detection-adr]]"
---

# phase1-step1-1 hoist site-health-error

## Intent

Hoist `SiteHealthError` into `aeat.core.errors` as a direct `AeatError`
subclass carrying a strict `status: SiteHealthStatus` attribute. The
class is defined under a `TYPE_CHECKING` guard so the module avoids
a circular import against `aeat.status`.

## Changes

- `src/aeat/errors.py` — added `from __future__ import annotations`,
  a `TYPE_CHECKING` import of `SiteHealthStatus`, and a
  `SiteHealthError` class with a keyword-only `status` argument. The
  string message mirrors `status.state.value`.

## Acceptance

- `python -c "from aeat.core.errors import SiteHealthError"` succeeds
  (verified in Phase 8 gates).
- Subclass of `AeatError` preserved.

## Deviations

None.
