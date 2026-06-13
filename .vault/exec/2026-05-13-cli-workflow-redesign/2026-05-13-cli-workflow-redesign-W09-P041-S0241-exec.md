---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W09.P041.S0241'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w09-p041-s0241-profile-service-ownership-audit]]"
---

# `cli-workflow-redesign` `W09.P041.S0241`

Closed plan rows:

- `W09.P041.S0241`

## Description

Mapped the user-profile-backend-schema ADR into non-CLI service ownership in the linked audit report. Findings:

- The domain layer is already built: `src/aeat/domain/user_profile/` exposes the strict Pydantic schema records, value records, TOML loader, and registry-contract validator. The TOML schema at `registry/aeat/user_profile/schema.toml` is 659 lines covering all 15 ADR sections.
- The application layer is not yet built. There is no `aeat.application.user_profile` package and the existing `aeat.application.profile` package is still the legacy fragmented surface the ADR is replacing.
- 41 source files still import `PROFILE_KEYS`, `AutonomoProfile`, or `ProfileRecord`. Migration is not started.

The audit fixes ownership for the remaining W09 phases:

- `aeat.application.user_profile` (new) — owns lifecycle (add/remove/edit/duplicate/list/read), snapshot creation, validation, preflight, export/import. Pydantic command and result records named in the audit.
- `aeat.domain.user_profile` (existing) — schema, values, registry contract, projections.
- `aeat.adapters.persistence.storage` — two new `SecureObjectRepository` namespaces: `aeat.application.user_profile.value` and `aeat.application.user_profile.snapshot`. Per-bucket isolation rides the W61.P301 active-bucket plumbing.
- `aeat.core.errors` — six new error codes (REFUSED_PROFILE_NOT_FOUND, REFUSED_PROFILE_ALREADY_EXISTS, VALIDATION_PROFILE_SCHEMA_VIOLATION, VALIDATION_PROFILE_PREFLIGHT_MISSING, INTEGRITY_PROFILE_SNAPSHOT_HASH_MISMATCH, INTEGRITY_PROFILE_SNAPSHOT_NOT_FOUND).
- `aeat.entrypoints.cli` — `aeat config profile {add,remove,list,show,edit,duplicate,export,import,validate,preflight}` lands only in W09.P045 as a thin adapter.

The audit also names the eight consumer migration boundaries (`filing/runtime.py`, `overview/__init__.py`, `wizard/_catalogue.py`, Renta aggregation, usage ratios, VAT aggregation, `cli/_common.py:_profile_to_autonomo`, registry validation already integrated) and specifies the three new `FilingDraft` fields (`profile_snapshot_id`, `profile_snapshot_hash`, `profile_schema_version`) plus the `PROFILE_SNAPSHOT_CHANGED` stale reason that integrate with `compute_current_approval_basis`.

## Modified Paths

- `.vault/audit/2026-05-13-cli-workflow-redesign-W09-P041-S0241-profile-service-ownership-audit.md` (created)
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

No source changes; the mapping is documentary. S0242-S0246 land the application contracts, services, persistence, routing, and error registry. S0247-S0252 migrate consumers off the legacy profile surfaces.
