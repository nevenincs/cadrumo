---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S324'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S324 registry plaintext exception

## Scope

- `src/aeat/domain/calculations/registry/_formula_runtime.py`

## Description

- Audited `domain.calculations.registry._formula_runtime` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module is a pure-Python formula evaluator over registry-validated `FormulaDefinition` records; no file I/O, no network call, no plaintext persistence — the `plain-file` signal is the read-path artefact of consuming registry data that itself ships as bundled TOML through the loader chain.
- The evaluator is bucket-scope-neutral by design (formulas compute over typed binding values supplied by the caller) and writes nothing.

## Outcome

- AFR-222 closed: justified plaintext exception (in-memory formula evaluator). No source change required.

## Notes

- Audit-only Step.
