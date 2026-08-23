---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:695ae88278ced7e458179cc0626e0b1ef8d66ddd9f0a6841f13ffec33f3c414f'
step_id: 'S175'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# redact raw row-source identities while exposing safe cohort fingerprints in operator output

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Define an independent allowlisted CLI review payload and construct every approved field explicitly.
- Expose row provenance only as binding, row index, source kind, and fingerprint in JSON and text review output.
- Refuse raw identity fields with value-free validation and prevent secure serialization contexts from bypassing the CLI projection.
- Exercise the registered CLI success and encrypted corruption paths and scan every output, exception, traceback, and log channel.

## Outcome

Ordinary modelo work review output now carries safe row cohort fingerprints without carrying opaque source-row identities. The CLI boundary cannot inherit future application fields implicitly, and legitimate operator activity labels remain unaffected.

Independent review reported zero findings. Two real CLI tests passed, including a non-vacuous encrypted orphan-coordinate failure retaining both sensitive canaries in the failing ciphertext; Ruff and ty were clean.

## Notes

An exploratory command referenced a nonexistent command-schema test module and ran zero tests; it was replaced by the exact registered CLI envelope test. No locale keys were needed, and S176 inventory cohort enumeration remains out of scope.
