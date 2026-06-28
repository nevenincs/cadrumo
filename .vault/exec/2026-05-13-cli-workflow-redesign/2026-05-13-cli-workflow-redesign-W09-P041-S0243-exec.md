---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'W09.P041.S0243'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
  - "[[2026-05-13-cli-workflow-redesign-w09-p041-s0241-profile-service-ownership-audit]]"
---

# `cli-workflow-redesign` `W09.P041.S0243`

Closed plan rows:

- `W09.P041.S0243`

## Description

Wired the two user-profile services that depend only on the domain schema layer (no secure-storage persistence yet — that lands in S0244):

**`ProfileValidationService`** (`_validation.py`) — stateless. Indexes the loaded schema once at construction and exposes:

- `validate_record(record)` — validate every fact on a `UserProfileRecord`.
- `validate_facts(profile_id, facts)` — validate a free-standing collection (e.g. a `RegisterProfileCommand`).

Both surfaces return a `ProfileValidationReport` containing `ProfileValidationIssue` rows. Today the service emits three classes of issue: `unknown_field` (path not in schema), `effective_window_unused` (warning when `valid_from`/`valid_to` are set on a non-effective-dated section/field), and `required_field_missing` (required field absent from the supplied facts).

**`ProfilePreflightService`** (`_preflight.py`) — stateless. Resolves required profile selectors for a target `(modelo, revision_id, filing_year, period)` by inspecting each schema field's `model_selectors`. Returns a `ProfilePreflightReport` with the missing requirement rows and a `ready: bool` flag.

Both services are lazy-imported from the package surface via `__getattr__` so the lightweight contract-only import path stays cheap.

## Modified Paths

- `src/aeat/application/user_profile/__init__.py`
- `src/aeat/application/user_profile/_validation.py` (created)
- `src/aeat/application/user_profile/_preflight.py` (created)
- `src/aeat/application/user_profile/test_services.py` (created)
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

`pytest src/aeat/application/user_profile/` — 5 passed:

- `test_validation_rejects_unknown_field_path`
- `test_validation_reports_missing_required_fields`
- `test_validation_accepts_known_field`
- `test_preflight_returns_ready_when_no_modelo_selectors_match`
- `test_preflight_carries_request_fields_through`

Real schema (`registry/aeat/user_profile/schema.toml`, 659 lines) loaded by every test via the module-scoped fixture — no mocks, fakes, or stubs.

S0244 wires secure-DB persistence and the snapshot service. S0246 registers the typed error codes.
