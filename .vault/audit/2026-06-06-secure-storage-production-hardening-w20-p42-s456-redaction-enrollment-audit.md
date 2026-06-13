---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-06'
modified: '2026-06-06'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
  - '[[2026-05-28-centralized-output-redaction-adr]]'
  - '[[2026-06-02-centralized-output-redaction-audit]]'
---

# S456 redaction enrollment audit

## S456-001 | MEDIUM | Wizard success text bypassed the central renderer

The previous direct-output inventory covered production CLI and diagnostics modules but did not scan application wizard output. The wizard success helper wrote tabular text with `_typer.echo` directly, so profile-like values in that path did not receive the same central `render_command_output` text redaction as CLI `_emit` output.

Status: resolved. Wizard success text now passes through `render_command_output(format_name="text", ...)` before the Typer write, and a unit test captures real output with a UUID-like profile label to prove central redaction occurs.

## S456-002 | MEDIUM | Output-surface inventory missed `_typer.echo` aliases and application wizard output

The inventory gate detected `typer.echo` but not `_typer.echo`, and its root calculation only worked when the integration test was not selected. That left the wizard success output invisible to the guard.

Status: resolved. The inventory root is corrected to `src/aeat`, `_typer.echo` aliases are detected, and the application wizard output package is now part of the reviewed direct-output surface.

## S456-003 | INFO | Existing centralized redaction baseline remains valid

RAG search over vault and code reconfirmed the centralized-output-redaction ADR, rollout audit, `core.redaction`, `core.output_rendering`, and `test_output_surface_inventory.py` as the current authority chain. CLI `_emit_envelope`, JSON success, stderr, and live-stream surfaces still use their documented centralized boundaries.

Status: no action required beyond the wizard enrollment fix.
