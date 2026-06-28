---
tags:
  - '#exec'
  - '#repo-health-triage'
date: '2026-06-04'
modified: '2026-06-04'
step_id: 'S73'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
---

# `repo-health-triage` `W06.P19.S73`

Scope: `src/aeat/application/wizard/_commands.py`.

## Description

- Reduced `build_wizard_command` by extracting command-body responsibilities
  into top-level helpers.
- Kept the Typer dynamic-signature construction in `build_wizard_command`.
- Preserved the existing behavior around output-language overrides, translated
  AEAT error rendering, profile create/edit identity checks, foral CCAA refusal,
  patch edit dispatch, full-flow persistence, JSON output, and tabular output.
- Used the resident VaultSpec RAG server on port `8766` to ground the target
  hotspot and existing tests.

## Outcome

S73 is closed. The wizard command factory is no longer a production cognitive
complexity hotspot.

## Notes

Verification:

- `uv run --no-sync vaultspec-rag search "build_wizard_command wizard command catalogue cognitive complexity refactor" --type code --max-results 10 --port 8766 --json`
- Focused Complexipy check for `src/aeat/application/wizard/_commands.py`
- `uv run --no-sync ruff check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py`
- `uv run --no-sync ty check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py --output-format concise`
- `uv run --no-sync pyright src/aeat/application/wizard/_commands.py src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py --level warning --warnings`
- `uv run --no-sync pytest src/aeat/application/wizard/test_commands.py src/aeat/application/wizard/test_commands_helpers.py src/aeat/application/wizard/test_wizard_translations_resolve.py -q`
- `just audit-complexity-production`

Residual evidence:

- Pyright reported 0 errors and 14 warnings for existing private-helper/test
  reach-ins.
- The wider wizard/root test selection failed on an unrelated shared-worktree
  modelo import break involving
  `_require_persisted_iva_compensation_decision_matches_revision`.
