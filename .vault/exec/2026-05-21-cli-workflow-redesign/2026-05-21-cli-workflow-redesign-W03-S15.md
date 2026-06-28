---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S15'
related:
  - '[[2026-05-21-state-architecture-plan]]'
  - '[[2026-05-21-state-architecture-testimonial-regression-audit]]'
---

# `cli-workflow-redesign` `W03.S15`

Re-ran the profile lifecycle testimonial regression with the real CLI
against an isolated local storage root.

- Modified: `.vault/plan/2026-05-21-state-architecture-plan.md`
- Modified: `.vault/audit/2026-05-21-state-architecture-testimonial-regression-audit.md`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`
- Created: `.vault/exec/2026-05-21-cli-workflow-redesign/2026-05-21-cli-workflow-redesign-W03-S15.md`

## Description

The persona pass used the production CLI with `AEAT_LOCAL_STORAGE_ROOT`
set to `var/tmp/state-w03-s15-profile-persona`,
`AEAT_SECRET_STORE_BACKEND=unsecured`, and `AEAT_ALLOW_UNENCRYPTED=1`.
The sequence exercised cold `profile status`, two profile creations,
`profile list`, `profile rename`, named `profile show`,
`profile switch`, active `profile status`, `profile delete --yes`,
post-delete list and switch refusal, tombstone inspection, and
tombstoned-label reuse.

The run confirmed that rename is label-only from the operator surface:
`cafe-luna` renamed to `cafe-luna-centro`, then `profile show` and
`profile status` continued to report the same UUID,
`274f1b11-982b-4a81-bfd6-21e858d1c2bb`, with readiness `ready`.
Switching between `cafe-luna-centro` and `studio-sol` succeeded and
status reported the active display label rather than a bucket path.

The tombstone regression stayed closed. After `profile delete
cafe-luna-centro --yes`, `profile list` showed only `studio-sol`;
`profile switch cafe-luna-centro` refused with exit code 2; named
`profile show cafe-luna-centro` rendered `readiness tombstoned` and
`status tombstoned`. Recreating `cafe-luna-centro` succeeded with a
fresh UUID, `4ad3b288-dacd-413e-86c3-c33a38cc93c2`, proving the
tombstoned display name is reusable.

The focused test gate then exposed a direct-subapp boundary defect:
`profile_app` invoked directly leaked `ProfileAlreadyRegisteredError`
for duplicate `profile create` attempts, leaving `result.output`
empty. The root CLI already decorates lazy-loaded subcommands, but
these direct tests intentionally exercise the `profile_app` object.
The repair decorates `profile_app` after all profile and census verbs
are registered, preserving the broader direct `config` app behavior
while giving profile lifecycle tests the same rendered refusal
contract operators see through the root CLI.

## Tests

Validation commands:

- `uv run aeat config profile status`
- `uv run aeat config profile create cafe-luna --quiet --tax-id 00000000T --name "Cafe Luna" --activity cafeteria --iva-regime GENERAL --tax-residence-ccaa madrid --entity-type natural_person`
- `uv run aeat config profile create studio-sol --quiet --tax-id 00000001R --name "Studio Sol" --activity design --iva-regime GENERAL --tax-residence-ccaa madrid --entity-type natural_person`
- `uv run aeat config profile list`
- `uv run aeat config profile rename cafe-luna cafe-luna-centro`
- `uv run aeat config profile show cafe-luna-centro`
- `uv run aeat config profile switch cafe-luna-centro`
- `uv run aeat config profile status`
- `uv run aeat config profile switch studio-sol`
- `uv run aeat config profile delete cafe-luna-centro --yes`
- `uv run aeat config profile list`
- `uv run aeat config profile switch cafe-luna-centro`
- `uv run aeat config profile show cafe-luna-centro`
- `uv run aeat config profile create cafe-luna-centro --quiet --tax-id 00000002W --name "Cafe Luna Nuevo" --activity cafeteria --iva-regime GENERAL --tax-residence-ccaa madrid --entity-type natural_person`
- `uv run aeat config profile status`

All expected-success commands exited 0. The deleted-profile switch
refusal exited 2, which is the expected refusal path.

Focused gates:

- `uv run ruff check src/aeat/entrypoints/cli/_config/__init__.py src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py`
- `uv run pytest src/aeat/entrypoints/cli/test_profile_lifecycle_verbs.py -q`
- `uv run pytest src/aeat/entrypoints/cli/_config/test_apoderado.py src/aeat/entrypoints/cli/test_profile_census_verbs.py -q`
- root CLI duplicate-create smoke with an expected exit-2 refusal
- `uv run vaultspec-core vault plan check .vault/plan/2026-05-21-state-architecture-plan.md`
- `uv run vaultspec-core vault plan status .vault/plan/2026-05-21-state-architecture-plan.md --json`

The focused profile lifecycle suite passed: 42 passed. The direct
`config` app and profile census compatibility suite passed: 14
passed. The root duplicate-create smoke rendered the expected
`Refused.` message and exited 2.
