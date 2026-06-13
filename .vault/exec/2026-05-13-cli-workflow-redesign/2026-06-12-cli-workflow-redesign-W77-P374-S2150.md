---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S2150'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-06-10-cli-operator-surface-adr]]'
---

# W77.P374.S2150 - retired config bucket mount reconciliation

## Scope

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/adr/2026-05-12-cli-workflow-redesign-adr.md`
- `.vault/adr/2026-05-12-cli-workflow-redesign-bucket-adr.md`
- `src/aeat/entrypoints/cli/_config/_bucket_history.py`
- `src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py`
- `src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`
- `docs/how-to/profile-setup.md`

## Description

- Rewrote the stale S2150 row so it no longer instructs a future worker to register `bucket_app`.
- Added ADR amendments recording that `aeat config bucket` is superseded by the operator-surface ADR and must not be reintroduced.
- Kept event history under `aeat config profile history PROFILE`, resolving the operator profile token to the immutable bucket id only inside the workflow/domain read path.
- Preserved the `config.bucket.history` JSON envelope token as the accepted stable machine-API carve-out.

## Outcome

Closed S2150 as a supersession reconciliation, not as a bucket-app implementation. The accepted closeout state is: no `aeat config bucket` group, no `bucket_app` mount, profile-named event history for operators, and backend/application `BucketMaintenanceService` ownership for storage lifecycle operations.

## Notes

R08 remains partial because `export`, `import`, and `search` service completeness is still open, and any future operator surface for those operations needs a separately accepted profile-named design. This exec record must not be read as closing S2131, S2132, S2145, or S2152.
