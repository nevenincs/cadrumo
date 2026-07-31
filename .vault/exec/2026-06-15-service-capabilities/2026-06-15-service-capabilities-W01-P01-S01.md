---
tags:
  - '#exec'
  - '#service-capabilities'
date: '2026-06-15'
modified: '2026-07-17'
body_hash: 'sha256:92c67e95525a11f337677741f296ee5773460b4038a8cb85c1041a62f38b14ce'
step_id: 'S01'
related:
  - "[[2026-06-15-service-capabilities-plan]]"
---

# Add ServiceCapability StrEnum (cloud_evidence_upload, llm_vision, google_export) in core with per-member docstrings

## Scope

- `src/aeat/core`

## Description

- Add the `ServiceCapability` StrEnum (cloud_evidence_upload, llm_vision, google_export) in `core/_capabilities.py` with schema_path + default_enabled and per-member docstrings; export from core.

## Outcome

The closed capability set has one core authority shared by schema, resolver, and CLI.

## Notes

None.
