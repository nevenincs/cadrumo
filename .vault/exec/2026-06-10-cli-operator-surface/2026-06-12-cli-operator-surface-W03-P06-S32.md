---
tags:
  - '#exec'
  - '#cli-operator-surface'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S32'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
---

# W03.P06.S32 Switch Rename Reconciliation

Scope: reconcile the already-landed config-surface hard rename from `unlock` to `switch`.

## Description

- Verified live `aeat config --help` lists `aeat config switch NAME`.
- Verified live `aeat config unlock operator` resolves as an unknown command.
- Verified generated CLI reference contains `aeat config switch` with registry key `config.switch`.
- Reconciled the plan row wording with the current no-retired-ledger state.

## Outcome

S32 is closed as an evidence reconciliation. The live operator surface uses `switch`; `unlock` is not registered as an alias or deprecation path.

## Notes

- The first focused pytest attempt was blocked by a duplicate `INTEGRITY_STORED_PROFILE_DRIFT` error-code registration in the shared dirty worktree. The redundant application-part registration was removed, leaving the domain-owned declaration.
- Checks run after the registry fix: focused switch/profile lifecycle pytest, documented-command plus retired-literal pytest, CLI-reference drift pytest, and ruff for the touched registry file.
