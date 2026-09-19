---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:85f640ca7e715717fb90446d926943c54dd026e05ee7f313d83575a2586adb06'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S54 domain-part2 lifecycle review`

## Scope

Independent verification-only review of `src/cadrumo/core/errors/registry/_domain_part2.py`, its immutable historical join, current ownership, preserved peer taxonomy row, relocated rehoming tool, and current live-source validation. The original failure evidence is retained below. After structural reconciliation, the current source and global structural contract are green; the remaining no-write refusal is one external non-gating locator change. Final verdict: PASS. `W05.P08.S54` remains open for lifecycle handling outside this audit.

## Findings

### preserved-peer-taxonomy-row | high | Peer-owned taxonomy work must remain exact while registry authority is reviewed

AST comparison proves `HEAD` has 93 rows and the shared tree has 94: the only delta is `cadrumo.domain.calculations.registry._errors.M303RegimenSimplificadoEvidenceRequiredError`. The existing 93 tuples are unchanged and the added row has exactly `code`, `category`, `message_key`, `retryable`, and `runbook_id`. All 94 current rows are taxonomy-only; no default, action, no-recovery, suggestion, command, raw-command, localized, or recovery authority exists in fields or comments. The peer row was preserved without modification.

### immutable-domain-part2-join | high | Historical recovery evidence must remain separate from present producer ownership

The non-null `domain_part2` preimage and ledger partitions join exactly at 39 identities: 34 `migration_required` rows and 5 `retired_or_unreachable` rows. Live ownership is exclusively S59, S88, S91, S96, and S105; terminal rows carry none. Historical S54 allocation remains immutable evidence only, and no current ownership belongs to S50 or S54.

### current-rehoming-contract-red | critical | Shared producer movement breaks the relocated exact-source rehoming suite

The relocated `dev/quality` rehoming tool imports and its moved ledger retains SHA-256 `7d7483ea2c9712db6d65151838b5f64b7ba9ce83a41316aa89996b660159676c`. Its no-write replay at `2026-08-11T14:55:12+02:00` returned `E_REHOMING_MIGRATION_CHECK_CONTENT` without altering the ledger. The current direct validator reports fingerprint-multiset errors for `ModeloPriorDomiciliationElectionRefusedError` and `ModeloProfileReadinessError`. The complete relocated unit lane finished `2 failed, 72 passed` in 276.23 seconds: its exact live-source join and locator-metadata regression both fail on those same external fingerprints. This blocks a PASS even though the S54 shard itself has zero preimage, disposition, current-qualname, owner, and locator delta.

### evolved-external-drift | high | The external boundary has advanced beyond the execution snapshot

Current regeneration derives three structural additions and two removals, plus 95 locator-only changes owned by S37 (7), S80 (6), S89 (1), S91 (36), and S96 (45). The changed structural identities are S96-owned `ModeloPriorDomiciliationElectionRefusedError` and `ModeloProfileReadinessError` source evolution. This is distinct from the S54 execution record's time-bounded 81-locator snapshot and remains outside S54 ownership. The shared `dev/quality` relocation and its moved ledger are also external canonical-home work; no source or TOML restoration was attempted.

### structural-reconciliation-rereview | high | The former live-source fingerprint failure is reconciled

The shared `HEAD` now contains all 94 taxonomy rows, including the preserved M303 peer row, and matches the current shard exactly. At `2026-08-11T15:38:54+02:00`, the relocated direct validator returned `E_REHOMING_VALIDATED:238`; the complete relocated rehoming lane subsequently passed 74 tests in 254.21 seconds. At `2026-08-11T15:39:10+02:00`, no-write replay preserved ledger SHA-256 `1cf48af26b010d7bbccdd5f15a93f87d83fddaf431e9373f6a09c4407044f4457` and returned `E_REHOMING_MIGRATION_CHECK_CONTENT` only because one S114-owned locator differs. Regeneration reports zero preimage, disposition, current-qualname, structural, owner, and S54 locator delta. The original critical finding is remediated; the S114 locator remains external diagnostic metadata, not a structural gate failure.

## Recommendations

The S37, S80, S89, S91, and S96 owners should reconcile their current source changes through the relocated rehoming ledger, including both failing error types, then rerun the direct validator, no-write replay, and complete 74-test lane. Retain the exact 94-row domain-part2 taxonomy surface and preserved M303 peer row. Re-review S54 only after the live rehoming contract is green; do not solve this external drift by changing S54 source or ownership.

That re-review condition is now satisfied. Keep future locator-only movement non-gating and time-bounded, with the responsible current owner refreshing it through the canonical relocated ledger before any closure that requires replay convergence.
