---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W10.P046..W10.P050'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-config-cli-profile-surface-adr]]"
---

# `cli-workflow-redesign` W10 closeout (config profile service surface)

Closed plan rows: every row of `W10.P046..W10.P050` (`S0271..S0300`).

## Commit

- `a9e0321f` `aeat config profile {use, show, remove, duplicate}`
  verbs, locale strings (en/es/ca/hu), and CLI tests.

## Delivered `aeat config profile` verb tree

| Verb | Status | Backend |
|------|--------|---------|
| `list` | live (W09) | `record_to_path_values` over active record |
| `get KEY` | live (W09) | `fact_value(record, KEY)` |
| `set KEY VALUE` | live (W09) | `set_active_field` + `UserProfileFact` |
| `unset KEY` | live (W09) | `set_active_field(value=None)` |
| `status` | live (W09) | `build_wizard_status` |
| `use NAME` | live (W10) | `select_profile` |
| `show [NAME]` | live (W10) | `service.read` + `record_to_path_values` |
| `remove NAME --yes` | live (W10) | `service.remove` (tombstone) |
| `duplicate SOURCE TARGET` | live (W10) | `service.duplicate` + pointer threading |

Nine canonical verbs are live now and route through the
`ProfileLifecycleService` + `_orchestration` surface. Three deferred
items in the ADR's verb table (`add`, `edit`, `validate`,
`preflight`, `export`, `import`) are scope-creep onto W74A's
profile-noun-group reconciliation and are tracked there; they need
either UX design (`add` vs `init` flag overlap), registry binding
(`preflight`), or format design (`export`, `import`) that W10
alone cannot resolve.

## Per-phase rationale

### P046 (backend implementation)

The canonical backend already exists from W09.P041:
- Pydantic command contracts: `RegisterProfileCommand`,
  `EditProfileFieldCommand`, `EditProfileSectionCommand`,
  `RemoveProfileCommand`, `DuplicateProfileCommand` (+ result and
  listing models) in `application/user_profile/__init__.py`.
- Domain/service wiring: `ProfileLifecycleService` composes
  `ProfileValidationService` + `UserProfileLifecycleRepository`.
- Persistence + bucket events: secure-DB envelopes via
  `UserProfileLifecycleRepository.save/delete`; bucket events
  emitted by `ProfileLifecycleService` per W09.P042.
- Routed legacy callers: every consumer migrated in W09.P042.
- Error codes / log fields: registered `ErrorCode`s for
  `ProfileSchemaValidationError`, `ProfileAlreadyExistsError`,
  `ProfileNotFoundError` through the canonical lifecycle service.

### P047 (shadow duplicate removal)

W09.P042 already retired `aeat.application.profile`. No new
shadow surface entered W10's scope.

### P048 (de-shim and de-stub cleanup)

No shim survived W09. The new CLI verbs use the canonical service
directly; no transitional helpers added.

### P049 (real behavior verification)

- Service contract tests: `application/user_profile/test_lifecycle.py`
  (9 tests covering register/edit/remove/duplicate/listing).
- Persistence integration: `application/user_profile/test_repository.py`
  (7 tests against real secure object store).
- Negative tests: `test_config_profile_use_refuses_unknown_profile`,
  `test_config_profile_remove_requires_yes`,
  `test_config_profile_duplicate_refuses_existing_target`.
- Command behavior tests: 8 tests in
  `entrypoints/cli/test_profile_lifecycle_verbs.py`.
- End-to-end: existing `test_workflow_surface.py` end-to-end
  test from W09.P042.
- Targeted slice: `pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py
  src/aeat/entrypoints/cli/test_config_setter.py` returns 13
  passed / 0 skipped / 0 xfailed.

### P050 (thin CLI exposure)

- Accepted handlers: nine verbs live under `aeat config profile`.
- Argument parsing isolated: each handler reads typer arguments
  and immediately delegates.
- Delegated to centralized services: every handler routes through
  `_orchestration` or `ProfileLifecycleService`.
- `_emit` rendering: every handler ends with `_emit(ctx, payload,
  lines)`.
- Central error boundary: `CliRefusedBoundaryError` for refusals;
  domain exceptions surface through registered `ErrorCode`s.
- Help vocabulary: every key example is a canonical schema path;
  locale strings in en/es/ca/hu mirror the contract.

## Guards held

- No CLI-local business logic; every handler is a thin adapter.
- No new compatibility helpers or transitional readers.
- The `add`/`edit`/`validate`/`preflight`/`export`/`import` verbs
  are not stubbed as `NotImplementedError` placeholders. They
  simply are not yet registered; their absence is the
  architectural state until W74A delivers them.
