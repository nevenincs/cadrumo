---
tags:
  - '#exec'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
modified: '2026-06-06'
step_id: 'S456'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-centralized-output-redaction-adr]]'
  - '[[2026-06-02-centralized-output-redaction-audit]]'
---

# W20.P42.S456 central redaction enrollment

Scope: execute `W20.P42.S456` from the secure-storage production hardening plan.

## Description

- Ground the rollout against the centralized output redaction ADR and closeout audit.
- Run RAG searches over vault and code for central output redaction bypass vocabulary.
- Re-run the direct output inventory with integration markers enabled.
- Enroll wizard success text output through the central command-output renderer.
- Extend the direct-output inventory to include the application wizard output package and `_typer.echo` aliases.
- Add real output capture coverage for wizard success text redaction.

## Outcome

S456 found one application-level direct output surface outside the prior CLI/diagnostics inventory: wizard success text emitted through `_typer.echo`. The text path now renders through `render_command_output(format_name="text", ...)`, so line redaction is centralized before Typer writes. JSON wizard success output was already routed through `emit_json_success`, which performs structured CLI redaction.

Focused validation passed:

- `uv run --no-sync pytest src/aeat/application/wizard/tests/test_commands_output.py -q`
- `uv run --no-sync pytest -m 'unit or integration' src/aeat/entrypoints/cli/tests/test_output_surface_inventory.py src/aeat/entrypoints/cli/tests/test_output_redaction_contract.py src/aeat/core/tests/test_redaction.py -q`
- `uv run --no-sync ruff check src/aeat/application/wizard/_commands.py src/aeat/application/wizard/tests/test_commands_output.py src/aeat/entrypoints/cli/tests/test_output_surface_inventory.py`

## Notes

The default pytest marker expression selects `unit`; the inventory gate is marked `integration`, so S456 explicitly ran it with `-m 'unit or integration'`.
