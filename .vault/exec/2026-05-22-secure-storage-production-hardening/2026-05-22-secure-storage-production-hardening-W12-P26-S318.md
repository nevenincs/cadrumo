---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-06-03'
step_id: 'S318'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---




# W12.P26.S318 apoderamientos catalogue

## Scope

- `src/aeat/domain/auth/apoderamientos/_catalogue.py`

## Description

- Audited `domain.auth.apoderamientos._catalogue` as a justified plaintext-exception under target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the catalogue loads a package-bundled `registry/aeat/apoderamientos/scopes.toml` via `tomllib.loads` against a `bundled_path` resolved through `core.resources`; the file is a content-addressed shipping artefact pinned to the package version, not a per-bucket secure-storage path.
- Confirmed the loaded data flows into strict pydantic v2 models (`ApoderadoScope`, `ApoderamientosCatalogue`) with `extra="forbid"` and field-level validators (`code` must be uppercase alphanumeric); the catalogue is frozen and read-only.
- No persisted operator state and no per-bucket data touches this file; the `plain-file` signal is fully accounted for by the `plaintext-exception` target classification.

## Outcome

- AFR-216 closed as a justified plaintext exception; no source change required.
- No new tests authored — the existing apoderamientos catalogue tests cover the loader contract.

## Notes

- Audit-only Step; the source file is unchanged.
- Paired Step `W12.P26.S319` (`src/aeat/domain/buckets/__init__.py`, signal `secure-object`, target `runtime-default`) intentionally left to a peer to keep this commit's scope minimal.
