---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S328'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S328 registry plaintext exception

## Scope

- `src/aeat/domain/calculations/registry/_record_design.py`

## Description

- Audited `domain.calculations.registry._record_design` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module defines AEAT Diseño de Registros parser shapes used to project filing artefacts onto operator-readable record layouts; pure schema + pure-Python transformers.
- The `plain-file` signal is the read-path artefact of the bundled record-design TOML; the actual TOML read happens in the loader (S326) and the typed records flow through these in-memory shapes.

## Outcome

- AFR-226 closed: justified plaintext exception (in-memory record-design shapes). No source change required.

## Notes

- Audit-only Step.
