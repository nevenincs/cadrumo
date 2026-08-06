---
tags:
  - '#exec'
  - '#mcp-identity-linked-operation'
date: '2026-07-08'
modified: '2026-07-17'
body_hash: 'sha256:e20e5217d87ca17a5e76034757af324918b1333fbcce03f480b28a0e03306343'
step_id: 'S03'
related:
  - "[[2026-07-08-mcp-identity-linked-operation-plan]]"
---

# Extend the shared-spine conformance test so the success and error envelopes both carry active_profile and a profile-bound command populates it

## Scope

- `src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`

## Description

## Outcome

Landed in commit 154ddf3974 — active_profile label on the SchemaEnvelope + ErrorEnvelope spine, resolved at the CLI and injected into the core emitters (layering-clean); LABEL not UUID; optional/null-default.

## Notes
