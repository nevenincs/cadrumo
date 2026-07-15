---
tags:
  - '#audit'
  - '#eliminate-user-cli-shim'
date: '2026-07-12'
modified: '2026-07-12'
related:
  - "[[2026-05-10-eliminate-user-cli-shim-plan]]"
  - "[[2026-05-10-eliminate-user-cli-shim-adr]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-w12-closeout-exec]]"
  - "[[2026-05-13-cli-workflow-redesign-w01-p003-shim-cleanup-review-audit]]"
---

# `eliminate-user-cli-shim` audit: `legacy plan completion reconciliation`

## Scope

Reconcile every unchecked row in the draft May 2026 `user_cli.py` retirement
plan against the accepted retirement ADR, the successor workflow-redesign W12
closeout, shim-removal review, and current source tree.

## Findings

### shim-retirement-delivered | low | all draft migration rows are historical

`src/aeat/application/user_cli.py` is absent from the current tree. The
accepted workflow redesign explicitly records the retirement as closed, and
the W12 closeout identifies the canonical replacements: workflow state is
owned by `application.workflow`, profile values follow the secure bucket
contract, and the workflow CLI uses the accepted configuration profile-state
adapter without a `user_cli` re-export.

The successor closeout records that W12's backend ownership, duplicate-removal,
no-shim, real-persistence testing, and thin-CLI rows are all closed. The shim
cleanup review separately confirms the old operator subapps and compatibility
registries were removed, with negative CLI coverage for their retired
spellings.

The draft plan's exact destination modules and `setup` command names are
historical implementation suggestions, not missing work. The current
architecture deliberately uses its accepted facades and `config`/`app` routing
instead of recreating the draft package layout or compatibility behavior.

## Recommendations

Mark all legacy migration and verification rows complete. Do not restore
`user_cli.py`, add a re-export, or reintroduce a compatibility persistence
namespace. Future workflow-state changes must extend the current canonical
workflow and profile ownership boundaries.
