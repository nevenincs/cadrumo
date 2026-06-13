---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-14'
modified: '2026-05-14'
step_id: 'W09.P042.S0247'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-07-user-profile-backend-schema-adr]]"
---

# `cli-workflow-redesign` `W09.P042.S0247`

Closed plan rows:

- `W09.P042.S0247`

## Description

Audited the duplicate implementations that overlap the schema-driven user-profile backend. Produced an inventory in the linked audit doc:

- **Canonical (KEEP)**: `aeat.domain.user_profile`, `aeat.application.user_profile`, `registry/aeat/user_profile/schema.toml` — W09.P041's output.
- **Legacy duplicates (DELETE)**: six surfaces named by the ADR — `aeat.application.profile` package, `AutonomoProfile` + `autonomo_profile_from_mapping`, `PROFILE_KEYS`, tax-residence flat storage, usage-ratio root, untyped CLI profile dicts.

Quantified:

- 21 files reference `ProfileRecord` (5 in the legacy package, 11 already in the new canonical packages — name collision on case — and 5 legacy consumers need migration).
- 18 files reference `AutonomoProfile` / `autonomo_profile_from_mapping` (1 defining module, 10 deadlines/filing/overview/wizard/workflow consumers, 7 tests).
- 11 files reference `PROFILE_KEYS`.

Sequenced the remaining W09.P042 steps:

- **S0248** — delete `aeat.application.profile` after migrating 5 consumers (`wizard/_verifier.py`, `workflow/_persistence.py` + `_models.WorkflowState.active_profile_record`, two reset tests, `test_config_setter.py`). Block: add three projection helpers to `aeat.application.user_profile` first — `projection_for_deadlines`, `projection_for_filing`, `projection_for_autonomo`.
- **S0249** — remove `_profile_to_autonomo` and the un-typed `aeat config init` scalar flow from CLI.
- **S0250** — migrate every `AutonomoProfile` consumer in `domain/deadlines`, `application/filing/runtime.py`, `application/overview`, `application/wizard/_status.py`, `application/workflow/_adapters.py`/`_engine.py`/`_protocols.py` to the new projection helpers.
- **S0251** — delete legacy tests and rewrite the deadlines / overview tests on the new projection.
- **S0252** — record the deleted files in `entrypoints/cli/test_backend_boundary.py` so a future sweep keeps them absent.

## Modified Paths

- `.vault/audit/2026-05-14-cli-workflow-redesign-W09-P042-S0247-duplicate-profile-surfaces-audit.md` (created)
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Tests

No source changes; audit only.

Block for S0248 implementation: the three projection helpers must land first. They compose against `UserProfileSnapshot.facts` for filing-approval consumers and against `UserProfileRecord.facts` for live consumers.
