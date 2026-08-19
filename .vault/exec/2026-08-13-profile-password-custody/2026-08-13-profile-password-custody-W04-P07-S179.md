---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-18'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:64e6cce51a6858a65fed46720112a7d0c70aecc6fec14728824a5f1cba7b176b'
step_id: 'S179'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Have Sol Medium give the profile-fact write door a surface-neutral name and settle its member vocabulary, since the shared writer and its door enumeration still carry the wizard's name while five of nine members and six of twelve call sites are not the wizard, and one member keeps an English stem beside its Spanish siblings, the rename being a cross-package relocation that also rewrites an emitted history value and therefore wanting its own deliberate change rather than riding a crash repair

## Scope

- `src/cadrumo/application/wizard/_persistence.py and src/cadrumo/entrypoints/cli/_config/`

## Description

- Move the shared profile-fact writer and its door enumeration out of `application/wizard/_persistence.py` into a new `application/user_profile/_fact_write.py`, renamed `ProfileFactWriteDoor` / `apply_profile_fact_changes`.
- Rename the one English-stem member `CLI_CAPABILITY = "cli.capability"` to `CLI_CAPACIDAD = "cli.capacidad"`, matching the Spanish sibling `CLI_DESCENDIENTE`; the CLI verb family `capabilities` stays untouched.
- Promote both names through the `application/user_profile` lazy facade (TYPE_CHECKING block, `_LAZY_EXPORTS`, `__all__`); drop the wizard facade exports without a re-export bridge.
- Sweep all twelve call sites to the owning facade: `wizard/_persistence.py` (ANSWERS, PATCH), `wizard/_commands.py` (PATCH, ANSWERS), `wizard/_checkpoint_store.py` (CHECKPOINT), `wizard/_descendant_door.py` (DESCENDANTS), `cli/_config/_manager_frontend.py` (MANAGER_FIELD x2), `cli/_config/_manager_actions.py` (MANAGER_AUTH, MANAGER_ROW), `cli/_config/_capabilities_cli.py` (CLI_CAPACIDAD), `cli/_config/_descendiente.py` (CLI_DESCENDIENTE).
- Relocate the AST contract gate `test_fact_write_door_contract.py` from `wizard/tests/` to `user_profile/tests/`; update `_WRITER`, the enum import, the class-name assertion and the docstring; `_ENROLLED_DOOR_MODULES` is unchanged because the call-site module set is identical.
- Rewrite the emitted history value: `event_payload["door"]` now carries `"cli.capacidad"`, surfaced raw by the bucket-history payload forwarder; no test or locale key pins a door value.
- Regenerate the API reference stubs with `dev.docs.apidocs scaffold`; stage only the `user_profile` module's own stubs.

## Outcome

- The relocated contract gate passes 4/4; ruff is clean on every touched file after the import-sorting fix.
- Wizard suite: 265 passed; the 8 failures (3 scripted-parity, 1 CLI-translation resolve, 4 legal-zone registry-authority errors) reproduce byte-identically at clean HEAD in a scratch worktree, so they are pre-existing committed-state failures, not introduced here.
- Import-hygiene and docstring-links gates: 10 failures identical at clean HEAD; the lazy-boundary gate passes in both trees.
- Collect-only over `application/` is interrupted only by 2 pre-existing collection errors (`user_profile/tests/test_repository.py`, `test_services.py`), identical at clean HEAD.
- One atomic pathspec commit `16b6c8379d` carries the relocation, the sweep, the gate move and the regenerated stubs.

## Notes

- A scratch baseline worktree at HEAD was used to prove every observed red is pre-existing; it was removed afterwards. No tracked file outside the commit's pathspec was touched.
