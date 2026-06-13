---
tags:
  - "#exec"
  - "#emit-envelope-schema-burndown"
date: '2026-05-31'
modified: '2026-05-31'
step_id: S65
related:
  - "[[2026-04-25-json-output-contract-adr]]"
  - "[[2026-05-31-emit-envelope-schema-burndown-plan]]"
---

# emit-envelope-schema-burndown W02.P06 — config and profile verb payload classes

## Outcome

Extended `_config_payloads.py` with seven config/profile verb `OutputSchema` subclasses: `ConfigListResult`, `ConfigProfileSwitchResult`, `ConfigProfileShowResult`, `ConfigProfileDeleteResult`, `ConfigProfileDuplicateResult`, `ConfigStatusResult`, `ConfigResetResult`. Shared sub-models `ProfilePointerPayload`, `ProfileIssuePayload`, `ProfileFactPayload` carry nested structure.

`ConfigStatusResult` is a union-branch schema covering five distinct readiness states (none, dangling_pointer, missing/unreadable record, incomplete config, ready) via Optional fields. `ConfigProfileShowResult` covers success, missing-record, and unreadable-record branches similarly.

Migrated all bare `_emit` sites for config.list (1 site), config.profile.switch (1 site), config.profile.show (1 site), config.profile.delete (1 site), config.profile.duplicate (1 site), config.status (5 branches), config.reset (1 site) to `_emit_envelope`.

## Files changed

- `src/aeat/entrypoints/cli/_config_payloads.py` — 7 schema classes added (S52, S54, S56, S58, S60, S62, S64)
- `src/aeat/entrypoints/cli/_config/__init__.py` — 11 config/profile emit sites migrated (S53, S55, S57, S59, S61, S63, S65)

## Gate

Conformance gate passes for all 7 config/profile paths. 103 config tests pass.
