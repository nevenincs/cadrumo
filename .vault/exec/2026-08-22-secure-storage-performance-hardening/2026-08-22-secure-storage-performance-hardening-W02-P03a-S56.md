---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:b833a70d999f573d8d7cee5cf9656749ee341a27adf8a0e43faa01ffbd9e256e'
step_id: 'S56'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---




# Prove clean-checkout direct-source and editable-install CLI assembly, help, completion, census, schema, operator, MCP/HITL, and write-routing behavior from tracked CommandSpec modules without generation or development imports, including explicit absence of both command JSON names and generator paths

## Scope

- `src/cadrumo/entrypoints/cli/tests/ and dev/packaging/`

## Description

Archive the tracked revision into an isolated temporary checkout.
Prove direct-source CLI assembly, help, completion, census, schema, operator, MCP/HITL, and write routing from that checkout.
Install the archived project through its editable-install metadata and repeat the same projection proof with controlled site processing.
Reject both retired command JSON artifacts and both deleted generators from the tracked checkout.
Attest that first-party module origins remain inside the archived checkout and that no development module is imported.
Derive expected schema and exposed-command identities independently from `CommandSpec` nodes and compare every consumer projection exactly.
Run an adversarial independent review and remediate every critical, high, and medium finding.

## Outcome

The clean tracked-source and editable-install lanes both assemble the 361-node command tree and its 296 result-schema identities without generation. Root help and Bash completion execute successfully. Schema references, resolved schema types, verb inputs, operator projection, and MCP descriptors equal independently derived `CommandSpec` sets. HITL and write-routing samples retain their authored policies.

The editable proof uses `python -S`, explicitly processes only the archived editable target's `.pth`, appends the dependency directory without processing its current-worktree editable hooks, and verifies the resolved `cadrumo`, CLI, and harness module files are inside the archive.

## Notes

The first editable-lane implementation placed an editable target on `PYTHONPATH`; Python does not process `.pth` files from ordinary `PYTHONPATH` entries, so the independent review reproduced a false pass through the developer environment's existing editable install. The lane was replaced with controlled site processing and explicit origin attestations before acceptance.

The gate is marked `integration`; callers must select that marker explicitly. No generated artifact, compatibility reader, fallback, alias, shim, or development authority was introduced.
