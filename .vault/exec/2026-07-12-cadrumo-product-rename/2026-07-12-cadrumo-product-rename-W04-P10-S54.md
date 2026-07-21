---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S54'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Prove manifest validation, bundle members, and honest signing behavior

## Scope

- `packaging/mcpb/tests/test_build.py`

## Description

- Validate the committed manifest through both its production loader and real `--check` script entry point.
- Build a real `cadrumo.mcpb` archive and prove its exact member and embedded-manifest contract.
- Assert Cadrumo server, command, tool, display, filename, and diagnostic identities while retaining AEAT authority prose.
- Exercise the host's real signer availability and require an honest signed or explicit unsigned outcome.

## Outcome

The secondary bundle now has a five-test real-behavior proof covering manifest
validation, the exact `cadrumo.mcpb` member set, canonical Cadrumo identities,
and honest signing diagnostics. On this host the real outcome is explicitly
unsigned because no signer is available. Ruff and all five focused tests pass.

## Notes

Earlier shared WIP simulated missing and successful signers with monkeypatches.
S54 removed those substitutes and observes only the actual host state. The
tests do not claim installation, publisher verification, or a configured
release identity.
