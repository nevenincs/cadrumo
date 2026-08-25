---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:a3c8164781826dc125bcb1e779f4caa6ee6cb3f2524bcef65e9a0160a411b163'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S53 domain-part1 lifecycle review`

## Scope

Independent verification-only review of `src/cadrumo/core/errors/registry/_domain_part1.py`, its immutable historical join, current fingerprint ownership, corrected execution record, and shared no-write boundary. The source has no diff from `HEAD`; it declares exactly 88 error-code rows with taxonomy keywords and locale keys only. Final verdict: PASS. `W05.P08.S53` remains open for lifecycle handling outside this audit.

## Findings

### taxonomy-only-domain-registry | high | A domain error registry must not redeclare action or recovery authority

AST inspection proves all 88 rows have only `code`, `category`, `message_key`, `retryable`, and `runbook_id`. No default, action, no-recovery, suggestion, command, raw-command, localized, or recovery authority exists in fields or comments. Direct import reports 88 registrations. The 16-test core registry suite and 30-test live CLI registry-contract suite pass under explicit unit and integration markers; their source contains no fake, mock, stub, patch, monkeypatch, skip, or xfail shortcut. Ruff, format, BasedPyright, and scoped diff hygiene pass. No production source mutation is warranted.

### immutable-domain-part1-join | high | Historical recovery evidence must remain separate from current producer ownership

The immutable non-null `domain_part1` preimage and rehoming partitions join exactly at 47 identities. Forty-four rows are `migration_required` with current ownership exclusively in later producer steps S31, S36, S38, S39, S40, S67, S70, S74, S76, S79, S83, S86, S89, S90, S94, S96, S97, S105, S107, S108, S113, and S114. Three rows are `retired_or_unreachable` with no current ownership. Historical S53 allocation remains immutable evidence only; no current ownership belongs to S50 or S53.

### current-external-rehoming-drift | high | Shared producer movement prevents current global rehoming convergence

At `2026-08-11T14:30:33+02:00`, the no-write migration retained ledger SHA-256 `7d7483ea2c9712db6d65151838b5f64b7ba9ce83a41316aa89996b660159676c` and returned `E_REHOMING_MIGRATION_CHECK_CONTENT`; at `2026-08-11T14:30:17+02:00`, the direct validator returned `E_REHOMING_FINGERPRINT_MULTISET:cadrumo.application.modelo._action_errors.ModeloProfileReadinessError`. Regeneration has zero preimage, disposition, current-qualname, S53 owner, and S53 locator delta. Its external delta is two S96 structural additions and two removals: the same-hash constructors in `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py` moved from `resolve_m303_regimen_simplificado_scope` to `m303_regimen_simplificado_scope_for_profile`. It also has 80 locator-only changes owned by S37 (7), S80 (6), S91 (36), and S96 (31). No TOML write was made.

## Recommendations

Keep registry shards taxonomy- and locale-key-only, with localized human rendering derived outside them. Retain the exact immutable join and exclusive current-owner rule. The S37, S80, S91, and S96 owners should reconcile their own source changes through the rehoming ledger and rerun the global validator and no-write replay; S53 requires no ledger or source change.
