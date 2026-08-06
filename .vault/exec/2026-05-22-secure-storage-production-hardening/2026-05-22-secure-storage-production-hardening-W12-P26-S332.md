---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-03'
modified: '2026-07-17'
body_hash: 'sha256:46c94eea210c3c4b4961930c9f39b979033a20db9f1da8250fb25d5f6afe0010'
step_id: 'S332'
related:
  - "[[2026-05-22-secure-storage-production-hardening-refactor-plan]]"
---

# W12.P26.S332 registry audit close

## Scope

- `src/aeat/domain/calculations/registry/_validate_evidence.py`

## Description

- Audited `domain.calculations.registry._validate_evidence` against the target `plaintext-exception` (owner `W12.P24.S96`).
- Confirmed the module evaluates `required_text` corpus-citation evidence claims declared on legal references against the matching corpus body; the cross-check is a pure-Python validator over already-loaded corpus text.
- The `plain-file` signal is the read-path artefact of consuming corpus HTML/text loaded by the loader chain; this module itself does no I/O and writes nothing.

## Outcome

- AFR-230 closed: justified plaintext exception (in-memory corpus-citation cross-check). No source change required.

## Notes

- Audit-only Step.
