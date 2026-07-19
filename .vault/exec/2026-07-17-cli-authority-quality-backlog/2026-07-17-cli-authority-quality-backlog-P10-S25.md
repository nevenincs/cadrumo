---
tags:
  - '#exec'
  - '#cli-authority-quality-backlog'
date: '2026-07-18'
modified: '2026-07-19'
step_id: 'S25'
related:
  - "[[2026-07-17-cli-authority-quality-backlog-plan]]"
---

# Triage the two low-severity entrypoints structural duplications the duplication-authority audit surfaced (repeated iterator shapes and thin synchronous wrappers): confirm each on the current tree by exact declaration, caller, and writer-path inspection, then either record a disposition note classifying it as intentionally distinct incidental similarity or consolidate it behind one shared abstraction proven substitutable against every consumer contract, so no duplicated policy, state ownership, or persistence behavior survives unclassified

## Scope

- `src/cadrumo/entrypoints/`

## Description

- RAG-searched the entrypoints surface for repeated iterator shapes and thin synchronous wrappers, then confirmed each candidate on the current tree by exact declaration, caller, and writer-path inspection.
- Located both low-severity categories the duplication-authority audit surfaced as optional, non-blocking review candidates.
- Applied the substitutability pre-filter to each category before deciding a disposition.

## Outcome

Both categories are recorded as intentionally distinct incidental similarity. Neither carries duplicated policy, state ownership, or persistence behavior; the substitutability pre-filter excludes both from consolidation, so no code change was made.

Category one, repeated iterator shapes. The concrete instances are the `lines=(...)` projection tuples built from `_metric_line(name, report.<attr>)` inside `src/cadrumo/entrypoints/cli/registry.py` (the inspect, verify, and audit-oracle command bodies) and the single kind-then-name enumeration `_iter_entries` in `src/cadrumo/entrypoints/mcp/_resources.py`. The shared mechanics are already single-sourced: `_metric_line` and `_join` are module-level helpers every registry site calls, and `_iter_entries` is itself the one canonical enumeration that both the list and read surfaces derive from. What remains repeated is the enumerated field list each command projects, and those lists diverge by command: verify prepends a `verified` line, and each command binds to a distinct result schema (RegistryInspectResult versus RegistryVerifyResult and siblings). The divergent field set and per-command schema binding is a constraint-shape divergence, so the sites are not promotable to one abstraction. Collapsing them would erase the per-command result-schema binding while removing no duplicated policy, state, or persistence, since none is duplicated.

Category two, thin synchronous wrappers. The concrete instances are the CLI command bodies that bridge sync Typer verbs to async capture coroutines via `asyncio.run(...)` in `src/cadrumo/entrypoints/cli/_app_live.py` and its siblings (`_app_live_justificante_cli.py`, `_app_live_expedientes_cli.py`, `_app_live_notifications_cli.py`, `_config/_auth.py`, `_modelo_reconcile_cli.py`). Each wrapper targets a distinct coroutine (`capture_iva_compensation_wallet`, `capture_notifications`, `capture_expedientes`, `login_operator_auth`, and so on), passes per-verb arguments, runs a per-verb auth preflight, and projects a distinct result payload (IvaWalletPullResult, NotificationsCaptureResult, and siblings). The only shared mechanic is the stdlib `asyncio.run` sync/async boundary, which is already single-sourced. Divergent target coroutine, arguments, and payload ownership is a constraint-shape and state-ownership divergence, so the wrappers are not substitutable. A shared higher-order dispatch would add indirection without removing any duplicated policy, state, or persistence.

The concrete jscpd clone groups underlying category one are already recorded as `advisory-residue` (visible advisory debt, not an elimination mandate) in `dev/audit/duplication_dispositions.toml`; this triage confirms that classification remains correct at HEAD and extends the same intentional-distinctness verdict to the synchronous-wrapper category. No production code was modified, so no pytest, ruff, or hygiene gate was triggered by an edit.

## Notes

No incidents. No code change; disposition-only closure. Peer-owned files (the operator auth/custody door files and the peer-authored `dev/audit/duplication_dispositions.toml`) were inspected read-only and left untouched.
