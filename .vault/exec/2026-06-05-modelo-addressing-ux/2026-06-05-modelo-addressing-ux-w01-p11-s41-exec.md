---
tags: ['#exec', '#modelo-addressing-ux']
date: '2026-06-05'
modified: '2026-06-05'
step_id: 'S41'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
---

# W01.P11.S41 typed modelo addressing contracts

Scope:
- `src/aeat/application/modelo/_work_addressing.py`

## Description

- Refresh the vault and code RAG indexes through the running `vaultspec-rag` service before implementation.
- Add `ModeloVisibleFilingTarget` for model/year/period/common-path addressing.
- Add `ModeloExactWorkUnitTarget` for advanced exact work-unit addressing.
- Add `ModeloRevisionPick` for command-specific revision selector and exact-revision picks.
- Add resolved work and resolved revision projection contracts for support-safe bidirectional address rendering.
- Keep `ModeloWorkAddress` as the legacy-compatible transport shape and add projection constructors from the new target contracts.
- Harden `ModeloRevisionPick` so exact revision IDs are only accepted with the explicit selector.

## Outcome

The modelo application addressing module now has explicit typed contracts for the follow-on facade work. Existing callers can continue using `ModeloWorkAddress`, while later steps can migrate CLI and workflow surfaces toward visible filing targets, exact work-unit targets, revision picks, and resolved projections without recreating ad hoc structures.

## Notes

- `uv run --no-sync vaultspec-rag index --type all --port 8766 --json` completed successfully. The service-indexed refresh reported vault `added=91`, `updated=2`, `removed=90`, and codebase `added=15`, `updated=27`.
- `uv run --no-sync ruff check src/aeat/application/modelo/_work_addressing.py` passed.
- `uv run --no-sync python -m py_compile src/aeat/application/modelo/_work_addressing.py` passed.
- `uv run --no-sync pytest src/aeat/application/modelo/test_selectors.py -q` passed with 13 tests.
- A code-review audit entry was appended to `2026-06-05-modelo-addressing-ux-code-review-audit`.
