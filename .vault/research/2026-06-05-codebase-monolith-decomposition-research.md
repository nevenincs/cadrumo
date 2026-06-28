---
tags:
  - '#research'
  - '#codebase-monolith-decomposition'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-codebase-monolith-decomposition-plan]]'
  - '[[2026-06-05-codebase-monolith-decomposition-adr]]'
---

# `codebase-monolith-decomposition` research: `backend monolith boundary inventory`

This research grounds the remaining decomposition work after the CLI extraction waves. Exact file-size inventory, exact command discovery, and resident RAG semantic search were used to distinguish transport-only CLI decomposition from backend modules that need boundary decisions before splitting.

## Findings

- The CLI transport refactor is partially complete but not finished: `_modelo.py` and `_app_live.py` are under the 1250-line target, while `_ledger.py`, `_config/__init__.py`, and `_config/_google.py` still need additional closure or explicit temporary legacy budgets.
- The backend inventory remains larger than the final target. Current production modules over 1250 lines include application orchestration modules, calculation registry modules, AEAT outbound adapters, secure storage adapters, core error/config modules, and workflow engine code.
- Semantic search confirms the existing architecture contract: `aeat.core` is the bottom cross-cutting layer, `aeat.application` composes domain logic with adapters, and facade identity tests already protect some top-level re-exports.
- Backend decomposition cannot be done as a mechanical move-only split for every file. Modules such as `application/modelo/_actions.py`, `application/ledger/_actions.py`, `domain/calculations/registry/_bindings.py`, `domain/calculations/registry/_schema.py`, and outbound AEAT/Google adapters each carry ownership or external-contract concerns.
- The safe common rule is to split implementation helpers into private submodules while preserving public imports through top-level package/module facades. Consumers should continue importing from the public module surface rather than reaching into newly created private modules.
- The final static guard cannot honestly pass today as a blanket no-module-over-1250 assertion. It must either wait until the remaining over-limit modules are decomposed, or encode a shrinking legacy budget list that makes the residual debt visible and non-growing.

## Queue

- Queue CLI residual closure for `_ledger.py`, `_config/__init__.py`, and `_config/_google.py` until all three are below 1250 or explicitly recorded as temporary exceptions.
- Queue application ADR decisions for `application/modelo/_actions.py`, `application/ledger/_actions.py`, `application/live/__init__.py`, `application/auth/_operator.py`, and `application/workflow/_engine.py`.
- Queue domain ADR decisions for calculation registry schema, bindings, applicability, workbook parity, and record design modules.
- Queue adapter ADR decisions for AEAT declaration/auth adapters, Google Sheets apply, secure object persistence, and master-key storage.
- Queue core ADR decisions for config and error registry modules, preserving `aeat.core` as the bottom layer with no upward dependencies.
