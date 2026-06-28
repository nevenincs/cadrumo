---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-06-15'
step_id: 'S06'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---




# Add DependencyStatus + per-service probes (ollama reachability/model, playwright, google creds, provider CLIs) that never raise on absence

## Scope

- `src/aeat/application`

## Description

- Add `aeat.application.provisioning` with `DependencyStatus` + probes (ollama reachability/model via /api/tags, subprocess providers via available_llm_providers, Playwright via a fast browsers-cache filesystem scan). Probes never raise on absence.

## Outcome

Typed availability probes back the graceful-degradation paths and the doctor.

## Notes

Renamed from a diagnostics/ package that shadowed the existing diagnostics.py module (fixed in commit 16c34887b). The Playwright probe scans the cache dir rather than launching the sync driver, which hangs inside the CLI process.

