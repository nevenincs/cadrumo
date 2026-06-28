---
tags:
  - '#exec'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S156'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
---

# W04.P09.S156 Production Residual Module Split

Scope: decompose the remaining oversized production modules before enabling the hard 1250-line module guard.

## Description

- Moved authenticator boundary records and browser protocols into `_authenticator_types.py`.
- Moved Cl@ve Movil pure support records, policy construction, diagnostics helpers, and failure classes into `_clave_movil_support.py`.
- Moved Cl@ve Movil page-driving methods into `_clave_movil_page_flow.py`.
- Preserved compatibility imports from `_authenticator.py` and `_clave_movil.py`.
- Moved AEAT sede declaration diagnostics and remote-read guards into `_declarations_diagnostics.py` and `_declarations_remote.py`.
- Moved core settings enum/coercion support into `_config_support.py` while preserving public re-exports from `aeat.core.config`.
- Moved record-design calculation-closure and coverage derivations into `_record_design_coverage.py` while preserving `_record_design.py` as the public record-design facade.
- Updated adapter error registry qualnames for moved Cl@ve Movil error classes.

## Outcome

All production modules are now below the 1250-line hard budget. Public facade imports remain stable for auth, sede declarations, core config, and registry record-design consumers.

## Notes

Verification passed for:

- Ruff over all changed S156 production modules and the moved adapter error registry entry.
- Compileall over changed auth, sede, core, and registry package surfaces.
- 69 focused sede declaration tests.
- 53 focused authenticator tests.
- 51 focused Cl@ve Movil tests.
- 34 focused core error registry tests.
- 42 focused core config tests.
- 177 focused registry record-design/schema/referential-integrity tests.
- 2-test codebase size budget guard.
- Direct production inventory showing no non-test `src/aeat` module over 1250 lines.

RAG grounding was rerun through the resident `vaultspec-rag` service on port 8766 after local backend access reported the Qdrant lock; code search surfaced the new `_record_design_coverage.py` implementation and the existing record-design test coverage.
