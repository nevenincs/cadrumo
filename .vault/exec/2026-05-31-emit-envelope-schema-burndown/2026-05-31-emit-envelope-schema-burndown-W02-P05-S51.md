---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S51
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W02.P05 — repair-verb payload classes

## Outcome

Authored `_config_payloads.py` (new file) with four repair-verb `OutputSchema` subclasses: `RepairLogsResult`, `RepairQuarantineResult`, `RepairResetStateResult`, `RepairConnectivityResult`, each decorated with `@register_schema`. Shared sub-models `QuarantineNamespacePayload` and `WorkflowFingerprintPayload` carry nested structure without registering.

Migrated all bare `_emit` sites in `_config/__init__.py` for repair.logs (1 site), repair.quarantine (3 branches: no-active-profile, dry-run, live), repair.reset_state (4 branches: no-active-profile, dry-run, live, guard), and repair.connectivity (1 site) to `_emit_envelope` calls. Each branch constructs a typed result model then calls `_emit_envelope(ctx, command=..., result=..., lines=...)`.

## Files changed

- `src/aeat/entrypoints/cli/_config_payloads.py` — new file, repair schema classes (S44, S46, S48, S50)
- `src/aeat/entrypoints/cli/_config/__init__.py` — 9 repair emit sites migrated (S45, S47, S49, S51)

## Gate

Conformance gate passes for all 4 newly registered config.repair.* paths.
