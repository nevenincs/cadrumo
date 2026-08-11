---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-11'
modified: '2026-08-11'
body_schema: 'body-v1'
body_hash: 'sha256:048bbf41a8d994de5df4b75ff056f138099b9dde14a0b6c3df3e2a46e17aa583'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# `cli-action-envelope-hardening` audit: `S57 adapters-part2 lifecycle review`

## Scope

Independent final review of S57, covering the accepted action-envelope boundary, the committed `src/cadrumo/core/errors/registry/_adapters_part2.py` change, its immutable historical preimage, current relocated-rehoming ledger, runtime registry behavior, focused real-behavior tests, and scoped static and Vault checks. The review does not close the plan step or alter implementation artifacts.

## Findings

### recovery-authority-retirement | low | no registry recovery authority remains

Current `HEAD` is `5b448bebab9842bc96fffbf6a18a01d630ff91ee`. Its source-scoped change is exactly three deletion-only hunks removing nineteen stale recovery-rationale comment lines, with zero additions. The comment-insensitive `_DECLARED_ERROR_CODES` AST exactly matches its commit parent at SHA-256 `54b26fd7a741e320b77960404d1078312956a57e4877b2b99914046083f1363b`. The delivered source has zero comments, zero recovery/action/localization authority assignments, and zero embedded CLI-command literals. It remains locale-neutral: registry rows carry taxonomy and message keys only.

### taxonomy-integrity | low | 63 unique canonical rows remain intact

The direct production import returns 63 rows. Every row has the exact ordered field shape `code`, `category`, `message_key`, `retryable`, `runbook_id`; source qualnames and codes are individually unique, and no corresponding qualname or code redeclares in another registry shard. Ruff, formatting, BasedPyright, and scoped diff integrity checks pass. The two focused suites pass 16 and 30 tests without mock, patch, monkeypatch, fake, stub, skip, or xfail shortcuts.

### historical-rehoming-boundary | low | historical recovery remains outside S57

The immutable preimage contains 63 `adapters_part2` rows, of which 18 were recovery-bearing. The current relocated ledger maps those exact 18 identities to 16 `migration_required` rows and 2 `retired_or_unreachable` rows. The 60 migration fingerprint owners are exclusively S68=19, S69=17, S70=16, S89=4, S94=2, S101=1, and S115=1; there is no S50 or S57 current owner. The retired rows are `AUTH_GOOGLE_CLIENT_REVOKED` and `AUTH_GOOGLE_REVOKED`, each with no current owner.

At 2026-08-11T17:13:38.0464601+02:00 through 2026-08-11T17:14:09.2789987+02:00, the direct validator returned `E_REHOMING_VALIDATED:238`. The expected read-only replay returned `E_REHOMING_MIGRATION_CHECK_CONTENT` with exit 1 and retained ledger SHA-256 `1CF48AF26B010D7BBCDD5F15A93F87D83FDDAF431E9373F6A09C4407044F4457`. It found zero row, structural, ownership, disposition, or current-error deltas. Five locator-only deltas are external and time-bound: S101=2, S103=1, S114=1, and S88=1; S57 locator delta is zero. The complete relocated-rehoming suite passes 74 tests in 247.22 seconds.

## Recommendations

- Keep ErrorCode registry shards restricted to taxonomy and locale message keys; place action selection and refusal preconditions in their canonical producer and catalogue/schema-resolved envelope path.
- Continue treating locator movement as diagnostic-only evidence. Reconcile structural identities, owners, dispositions, and current errors rather than source coordinates.
