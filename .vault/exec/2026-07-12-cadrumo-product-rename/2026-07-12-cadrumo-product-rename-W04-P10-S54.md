---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-13'
body_hash: 'sha256:eac3a07212df2735af66b27e0809cf56230e8b17ed73be1680d409cc37f77d05'
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
- Assert the exact Cadrumo server, command, `CADRUMO_MCP_PERSONA`, tool,
  display, filename, and diagnostic identities while retaining AEAT authority
  and `aeat` human-CLI referents.
- Exercise the host's real signer availability and require an honest signed or explicit unsigned outcome.
- Remove simulated signer tests so the suite contains no fakes, mocks, patches,
  monkeypatches, skips, or xfails.

## Outcome

The secondary bundle now has a six-test real-behavior proof covering manifest
validation, the exact `cadrumo.mcpb` member set, executable `cadrumo-mcp`,
product environment and tool identities, and honest signing diagnostics. On
this host the real outcome is explicitly unsigned because no signer is
available. Ruff and all six focused tests pass.

## Notes

Earlier shared WIP simulated missing and successful signers with monkeypatches.
S54 removed those substitutes and observes only the actual host state, including
the distinct diagnostics for an unavailable signer, a real successful signer,
or a real signer failure. The tests do not claim installation, publisher
verification, or a configured release identity.

The mandatory independent review found one low-severity Ruff formatting defect
in the real signer-failure assertion. A formatting-only remediation applied the
formatter's exact wrap, after which Ruff formatting, lint, and all six MCPB tests
passed without behavior changes.
