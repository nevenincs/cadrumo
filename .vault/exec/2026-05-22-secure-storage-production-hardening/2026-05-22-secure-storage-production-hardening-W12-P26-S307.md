---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:b8a2f97976a06b4a8075811d57c340b34d6e709dc235ea802f0112c3a0f7759d'
step_id: 'S307'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Close `AFR-205` for `src/aeat/core/observability/_sink.py` with signals `plain-file`, target `plaintext-exception`, and owner `W12.P24.S96`

## Scope

- `src/aeat/core/observability/_sink.py`

## Description

- Reconstructed the redacted diagnostic-sink exception from closeout commit `1efd3399c5`.
- Confirmed the sink is the explicitly allowed redacted diagnostics boundary.
- Ran the targeted current sensitive-persistence and diagnostic-sink validation suite.

## Outcome

The diagnostics sink remains a justified plaintext exception with redaction controls; targeted validation passed 21 tests.

## Notes

This record does not classify the sink as a profile-data persistence backend.
