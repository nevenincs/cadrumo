---
tags:
  - '#exec'
  - '#source-casilla-integration'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d9b395226da598335fedbcc4075a1e9d6a86c4f2e395c4558e593a815abe7c24'
step_id: 'S39'
related:
  - "[[2026-08-22-source-casilla-integration-plan]]"
---

# implement inventory repository resolution, diagnostics, source identity, and fingerprint provenance

## Scope

- `src/cadrumo/application/aggregation/_inventory.py`

## Description

- Resolve strict 2025 inventory bindings from the encrypted schema-v3 ledger through the sole inventory projection.
- Preserve activity and year coordinates, stable source identity, and sealed projection-fingerprint provenance.
- Emit closed, value-free diagnostics for absent, unreadable, incomplete, tampered, conflicting, and unsupported state.
- Normalize encrypted document validation failures at the repository boundary without retaining decrypted exception context.
- Add fake and real encrypted repository coverage for success, absence, corruption, determinism, conflict, tamper, and confidentiality.

## Outcome

The application now has a canonical allocation-free inventory source resolver for the three approved 2025 operations. It reads the encrypted inventory document, selects the exact activity ledger, delegates all arithmetic and authority validation to the sealed domain projection, and returns source-owned values for casillas 0177, 0181, and 0182 with stable source identity and the projection fingerprint.

Missing and malformed selectors, absent ledgers, unsupported contexts, encrypted read failures, incomplete or tampered projections, and retained closing conflicts have distinct machine-readable dispositions. Diagnostic messages, logs, and exception surfaces carry no financial values, evidence references, content digests, actor, or command data. The persistence adapter translates strict rehydration failures into the canonical inventory error outside the caught exception handler, leaving neither a cause nor a context containing decrypted input.

Both independent reviews finished clear with zero findings. Thirteen focused tests passed against fake and real encrypted repositories; Ruff, the type checker, scoped diff hygiene, and the feature vault check were clean.

## Notes

The canonical bare-modelo vocabulary gate no longer reports the S39 resolver. Its repository-wide run remains red only for four unrelated concurrent offenders in filing rendering and CLI specification files, which were not changed or committed here. Resolver enrollment and connected disposition remain owned by S40.
