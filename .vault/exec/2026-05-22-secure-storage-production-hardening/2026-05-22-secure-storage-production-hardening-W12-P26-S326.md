---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S326'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S326 registry plaintext exception

## Scope

- `src/aeat/domain/calculations/registry/_loader.py`

## Description

- Audited `domain.calculations.registry._loader` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module is the TOML authoring-compiler that reads the bundled registry tree under `src/aeat/_data/registry/aeat/`; the `plain-file` signal is by-design (the loader's contract per the `aeat-registry-authority-flow` rule is to read shipped TOML, compile to typed schema, and hand off to the validated authority).
- The loader writes nothing to disk; every output flows into strict pydantic v2 `ModeloDefinition` / `ModeloRevision` instances cached by the registry tree fingerprint.

## Outcome

- AFR-224 closed: justified plaintext exception (TOML authoring-compiler reads bundled registry data). No source change required.

## Notes

- Audit-only Step.
