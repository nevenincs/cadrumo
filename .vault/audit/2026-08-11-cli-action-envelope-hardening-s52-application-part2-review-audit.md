---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:2b2c7a260e2c86ad3e969c5cf3d7106d6d1702e4dc4ee116c662deace2c23a16'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S52 application-part2 lifecycle review`

## Scope

Independent verification-only review of `src/cadrumo/core/errors/registry/_application_part2.py`, its immutable preimage join, current ownership ledger partition, and corrected execution evidence. The source has no diff from `HEAD`; it declares exactly 100 error-code rows with taxonomy keywords only. Final verdict: PASS. `W05.P08.S52` remains open for lifecycle handling outside this audit.

## Findings

### taxonomy-only-registry | high | An application error registry must not redeclare recovery authority

AST inspection proves all 100 rows have only `code`, `category`, `message_key`, `retryable`, and `runbook_id`, with no default, action, no-recovery, localized, command, or suggestion authority in fields or comments. Direct import reports 100 registrations. The 16-test core registry suite and 30-test live CLI registry-contract suite pass under their explicit unit and integration markers; Ruff, format, BasedPyright, and scoped diff hygiene pass. No source mutation is warranted: this shard already meets the S28 taxonomy boundary.

### current-external-rehoming-drift | high | Current shared-source movement prevents global rehoming convergence

At `2026-08-11T14:07:57+02:00`, no-write regeneration against ledger SHA-256 `7d7483ea2c9712db6d65151838b5f64b7ba9ce83a41316aa89996b660159676c` preserved the ledger byte-for-byte and returned `E_REHOMING_MIGRATION_CHECK_CONTENT`. The corresponding validator at `2026-08-11T14:07:41+02:00` returned `E_REHOMING_FINGERPRINT_MULTISET:cadrumo.application.modelo._action_errors.ModeloProfileReadinessError`. The derived delta contains zero preimage, disposition, current-qualname, S52 owner, or S52 locator changes. It contains two S96 structural additions and two removals for the lexical-owner move in `src/cadrumo/application/modelo/_m303_regimen_simplificado_scope.py`, plus 73 locator-only changes owned by S80 (6), S91 (36), and S96 (31). This is external to S52 and no TOML write was made.

### immutable-application-part2-join | high | Historical recovery evidence must not become current producer ownership

The non-null `application_part2` preimage and rehoming partitions join exactly at 62 identities. All 62 rows remain `migration_required`; their historical allocation is S52, while their current fingerprint ownership is exclusively later producer work: S37, S72, S82, S89, S91, S96, S97, S101, S102, S103, S104, and S107. No current ownership belongs to S50 or S52.

## Recommendations

Keep registry shards limited to taxonomy and locale keys, and keep verification-only steps source-neutral when that boundary already holds. The S80, S91, and S96 owners should reconcile their own current source movement through the rehoming ledger, then rerun the global validator and no-write replay. Preserve the exact immutable preimage join and exclusive current producer ownership rule.
