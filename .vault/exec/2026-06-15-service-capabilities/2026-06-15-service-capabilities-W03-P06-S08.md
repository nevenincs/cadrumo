---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S08'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Add aeat config doctor: per-service availability + active-profile capability posture + remediation

## Scope

- `typed envelope + non-zero exit on opted-in-but-missing`
- `src/aeat/entrypoints/cli/_config`

## Description

- Add `aeat config check`: per-service dependency availability (probes) + the active profile's capability posture (resolver) + remediation, exiting non-zero when an opted-in capability has a missing dependency; typed payload + locales; CLI test. Named `check` because `config doctor` is a retired path.

## Outcome

One command reports the capability/dependency/safety axes together with the fix per gap.

## Notes

Resilient to a locked secret store (falls back to defaults). Avoid on/off as locale key leaves (YAML boolean coercion); reused the capabilities enabled/disabled keys.

