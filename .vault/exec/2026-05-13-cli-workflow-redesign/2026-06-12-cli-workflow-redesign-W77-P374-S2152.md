---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-06-12'
modified: '2026-06-12'
step_id: 'S2152'
related:
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-05-12-cli-workflow-redesign-adr]]'
  - '[[2026-05-12-cli-workflow-redesign-bucket-adr]]'
  - '[[2026-06-03-cli-workflow-redesign-adr]]'
---

# W77.P374.S2152 - apex R08 closeout reconciliation

## Scope

- `.vault/adr/2026-05-12-cli-workflow-redesign-adr.md`
- `.vault/adr/2026-05-12-cli-workflow-redesign-bucket-adr.md`
- `.vault/adr/2026-06-03-cli-workflow-redesign-adr.md`
- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`

## Description

- Updated the apex §3.4 text so bucket maintenance is recorded as a backend/application lifecycle service, not an operator-facing `aeat config bucket` command group.
- Kept §4.2 ratios documented as the key-value exception and W77's other R08 axis.
- Updated R08 progression and the 2026-06-03 refresh table: export/import are landed, search is deferred to the bucket-search ADR, and the retired `config bucket` mount is not a closure blocker.
- Updated the bucket child ADR and composition ADR with the same closeout state.
- Reconciled historical plan notes that still presented `aeat config bucket history` as the live operator spelling; the accepted operator surface is `aeat config profile history PROFILE`, while `config.bucket.history` remains a JSON token.

## Outcome

S2152 is complete. R08 is closed for W77: ledger ratios are ratified as a key-value exception, bucket-maintenance service operations are lifecycle services, `aeat config bucket` stays retired, and search is explicitly separated into the bucket-search follow-up.

## Checks

- `uv run --no-sync vaultspec-core vault plan status .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `rg -n "config bucket history|aeat config bucket maintenance|aeat config bucket\\{|CLI-mount|partial \\(3/6|search.*pending|R08 therefore remains partial" .vault/adr/2026-05-12-cli-workflow-redesign-bucket-adr.md .vault/adr/2026-06-03-cli-workflow-redesign-adr.md .vault/adr/2026-05-12-cli-workflow-redesign-adr.md .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
