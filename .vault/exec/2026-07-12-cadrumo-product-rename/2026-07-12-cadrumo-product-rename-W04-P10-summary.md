---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-17'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# `cadrumo-product-rename` `W04.P10` summary

Phase W04.P10 renamed the secondary MCP bundle and proved its honest build and
signing posture.

- Completed: S52 through S54 Step Records
- Renamed: manifest identity, MCP executable, diagnostics, and output bundle
- Verified: real manifest checker, archive members, CLI build, and host signer state

## Description

The secondary bundle is `cadrumo.mcpb`, contains exactly `manifest.json`, and
declares the Cadrumo display, server, command, and product environment identity.
AEAT remains only in legal-authority prose and search metadata.

The current host produces an explicitly unsigned bundle. Diagnostics distinguish
that state without claiming installation, publisher verification, or signing.
The focused suite uses the real loader, subprocess CLI, zip archive, and host
signer state; it contains no mocks, fakes, stubs, patches, or monkeypatches.

Formal closure reran all five MCPB tests, Ruff, and the manifest checker with no
findings. A stale pre-S54 test version had remained in the shared index beneath
the correct working file; the index was reconciled to the reviewed HEAD bytes
before phase closure.
