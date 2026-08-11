---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:3ac7eaabd560120b9e3201fb47d15a62318d1fbd3626fe0808b22fb75210906a'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S55 domain-part3 lifecycle review`

## Scope

Independent verification-only review of `src/cadrumo/core/errors/registry/_domain_part3.py`, its immutable preimage join, current producer ownership, relocated validation contract, and current no-write replay. Final verdict: PASS. `W05.P08.S55` remains open for lifecycle handling outside this audit.

## Findings

### taxonomy-only-domain-shard | high | A registry shard must not redeclare action or recovery authority

AST comparison proves all 50 current rows are identical to `HEAD` and each has only `code`, `category`, `message_key`, `retryable`, and `runbook_id`. The authority-field and comment scans are empty. Direct production import reports 50 rows. The selected registry and CLI contract sources contain no fake, mock, stub, patch, monkeypatch, skip, or xfail shortcut. The 16-test registry suite and 30-test live CLI contract suite pass under their explicit markers; Ruff, format, BasedPyright, and scoped diff hygiene pass.

### immutable-domain-part3-join | high | Historical recovery evidence must remain distinct from current producer ownership

The immutable non-null `domain_part3` preimage and ledger partitions join exactly at three identities, all `migration_required`, with no retired row. Their eight current fingerprints belong exactly to S70 (3), S96 (1), S101 (2), and S114 (2). Historical S55 allocation is immutable evidence only; no current ownership belongs to S50 or S55.

### locator-only-external-replay | high | Current replay refusal is non-gating diagnostic movement outside S55

At `2026-08-11T16:14:59+02:00`, the relocated direct validator returned `E_REHOMING_VALIDATED:238`. At `2026-08-11T16:15:12+02:00`, no-write replay retained ledger SHA-256 `1cf48af26b010d7bbccdd5f15a93f87d83fddaf431e9373f6a09c4407044f4457` and returned `E_REHOMING_MIGRATION_CHECK_CONTENT`. In-memory regeneration proves zero preimage, disposition, current-qualname, structural, owner, and S55 locator delta. The only differences are two non-gating locators owned by S103 and S114. The complete relocated rehoming lane passes 74 tests in 250.65 seconds, so this external locator movement does not block the S55 verdict. No TOML write was made.

## Recommendations

Keep registry shards taxonomy- and locale-key-only. Preserve the exact immutable join and exclusive current-owner rule. The S103 and S114 owners should refresh their own locator metadata through the canonical relocated ledger when their work requires replay convergence; such locator-only movement must stay time-bounded and must not be misattributed to S55.
