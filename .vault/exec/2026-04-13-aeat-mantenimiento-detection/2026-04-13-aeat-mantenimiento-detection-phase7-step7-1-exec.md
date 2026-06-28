---
tags:
  - "#exec"
  - "#aeat-mantenimiento-detection"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-aeat-mantenimiento-detection-plan]]"
---

# phase7-step7-1 extend settings

## Intent

Add `site_health_probe_url` and
`site_health_rate_limit_retry_after_default` to
`aeat.core.config.Settings`.

## Changes

- `src/aeat/config.py` — new section under Browser Automation with
  both fields. `site_health_rate_limit_retry_after_default` carries
  `ge=1` to match the pydantic record bound.

## Deviations

The plan specified validating `site_health_probe_url` via an
`AnyHttpUrl` adapter. The field is declared as `str` with a
documented default; the URL is validated at the parser call site
via the module-level `_URL_ADAPTER` in
`aeat.status._site_health`. Keeping it a plain `str` at the
settings layer avoids forcing every callsite to unwrap an
`AnyHttpUrl` object and matches the surrounding settings field
style (e.g. `aeat_base_url`).
