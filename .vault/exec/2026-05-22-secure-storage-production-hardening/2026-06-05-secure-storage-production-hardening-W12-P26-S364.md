---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
step_id: 'S364'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# W12.P26.S364 - Close AFR-262 for submission protocols

Scope: close `AFR-262` for `src/aeat/domain/submission/_protocols.py` with signals
`plain-file, remote-provider`, target `remote-mirror`, and owner `W12.P24.S98`.

## Description

- Audited `_protocols.py` for concrete remote-provider, secure-storage,
  active-profile, settings, environment, filesystem, and runtime repository behavior.
- Confirmed the module defines structural `Protocol` ports and strict/frozen value
  types only: auth-provider description/probe, deadline-window checker, draft shape,
  draft loader, and submission repository port.
- Confirmed `ModeloDraftLoader.load(Path)` is a Protocol declaration only; this file
  does not dereference or persist plaintext paths.
- Confirmed `SubmissionRepositoryProtocol` is a narrow domain-facing port and does not
  import or construct the concrete secure-storage repository.
- Closed `W12.P26.S364` through `vaultspec-core vault plan step check`; `AFR-262` is
  closed in the register.

## Outcome

`AFR-262` is closed. `_protocols.py` is boundary-definition code, not a remote mirror
writer, plaintext side-store owner, or secure-storage repository owner.

Validation passed:

- `uv run --no-sync ruff check src/aeat/domain/submission/_protocols.py src/aeat/domain/submission/_preflight.py src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py`
- `uv run --no-sync pytest -q src/aeat/adapters/outbound/aeat/export/tests/test_preflight.py`
- `uv run --no-sync pytest -q src/aeat/application/workflow/tests/test_engine.py -k "preflight or protocol"`

## Notes

The plan's `plain-file, remote-provider` signals are retained as scanner provenance.
The closeout disposition is that this file declares ports which may be implemented by
remote/provider or loader components elsewhere, but it does not implement those effects.
