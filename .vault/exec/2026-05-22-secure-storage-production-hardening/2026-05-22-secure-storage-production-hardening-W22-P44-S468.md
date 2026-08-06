---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-07-10'
modified: '2026-07-17'
body_hash: 'sha256:09f97e65f54caa6eff4c18542bf666ad1ee47fad2e352b1e3257d21b14caec3c'
step_id: 'S468'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# Verify user guidance names the D1 profile-switch command

## Scope

- `docs/how-to`

## Description

- Scanned the operator how-to guides for the retired `config unlock` spelling and canonical `config switch` guidance.
- Ran the live documented-command conformance suite at `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` with the integration marker.

## Outcome

The how-to guidance consistently teaches `aeat config switch <name>` and does
not mention the retired command. All 60 documented-command conformance tests
pass against the live CLI tree.

## Notes

The older rule path under `dev/docs` no longer hosts the documented-command
conformance test; the authoritative current test lives under the CLI test
surface. No documentation change was needed.
