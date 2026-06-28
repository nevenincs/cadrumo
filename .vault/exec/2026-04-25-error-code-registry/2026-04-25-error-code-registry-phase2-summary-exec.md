---
tags:
  - "#exec"
  - "#error-code-registry"
date: 2026-04-25
modified: '2026-04-25'
title: "error-code-registry phase2 summary"
related:
  - "[[2026-04-25-error-code-registry-plan]]"
  - "[[2026-04-25-error-code-registry-adr]]"
  - "[[2026-04-25-error-code-registry-research]]"
  - "[[2026-04-25-error-code-registry-phase1-summary-exec]]"
---

# error-code-registry phase2 summary

## Scope

- Added registry enforcement and regression coverage:
  `test_registry_enforcement`, `test_registry`, `test_envelope`,
  `test_windows_encoding`, and `test_error_decorator`.
- Updated adjacent tests that depended on pre-registry behavior:
  `aeat.adapters.outbound.aeat.auth.test_clave_movil`, `aeat.entrypoints.cli.test_manual_cli`, and
  `aeat.domain.casillas.errors`.
- Added the generator `scripts/generate_error_codes_doc.py` and committed the
  generated `docs/error-codes.md`.
- Updated `docs/coverage/kent-capabilities.md` to mark the Kent error-message
  capability as delivered by issue #398.

## Verification

The local project gates were rerun after implementation and after the final
targeted fixes:

- `just lint`
- `just typecheck`
- `just test`
- `just hooks`

All four gates passed on the Windows worktree. Full `pytest` completed with
`2982 passed, 13 skipped, 24 deselected`.

## Notes

- The Cl@ve Móvil changes in this branch are test-only. The fake page in
  `aeat.adapters.outbound.aeat.auth.test_clave_movil` was updated so it reflects the current polling
  implementation in `aeat.adapters.outbound.aeat.auth._clave_movil` without modifying sibling-branch
  production code.
- `aeat.domain.casillas.errors` keeps its historical per-instance short codes for
  verifier output while the class-level registry binding remains available on
  the exception type.
