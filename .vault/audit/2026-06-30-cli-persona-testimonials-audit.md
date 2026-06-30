---
tags:
  - '#audit'
  - '#cli-persona-testimonials'
date: '2026-06-30'
modified: '2026-06-30'
related:
  - "[[2026-06-30-cli-persona-testimonials-plan]]"
---

# `cli-persona-testimonials` audit: `W02 worker code review`

## Scope

Review of the first W02 worker commits for the persona hardening campaign:
`c35feaba5`, `402f8a5d`, and `e6c0295`. The audit checks whether W02.P03,
W02.P04, and W02.P05 can be closed under the plan's review gate. It records
blockers found by reviewer agents and drives follow-up worker dispatches.

## Findings

### m303-seed-help | medium | seed help conflates zero amount with proven first period

Commit `c35feaba5` improves Catalan and Hungarian help text but overclaims the
seed command's proof value in `src/aeat/locales/ca.yml` and
`src/aeat/locales/hu.yml`. The text says `--amount 0` is the true first-period
case and that reconciliation treats it as `first_period_zero`. The seed command
only persists a declared carry-forward balance; the automatic first-period path
is proved by activity-start and registry conditions in
`src/aeat/application/modelo/_iva_wallet_gate.py` and reconciliation logic in
`src/aeat/application/calculations/_iva_wallet_reconciliation.py`. A prior filer
can also seed `--amount 0` when the last filed M303 left no pending
compensation.

### ledger-export-import | high | canonical ledger CSV enters through raw bank import

Commit `402f8a5d` registers an `AEAT_LEDGER_EXPORT_LAYOUT` in
`src/aeat/adapters/inbound/financial/providers/_csv.py` and changes
`src/aeat/entrypoints/cli/tests/test_ledger_corpus_import_export.py` to require
canonical ledger CSV export re-import through the bank CSV provider. That weakens
the ledger ADR's raw-bank plus separate-oracle boundary: a rich local ledger
export can enter through the raw financial import surface rather than a distinct
restore or backup path.

### ledger-dedup-fingerprint | high | import duplicate detection still ignores direction and currency

The W02.P04 commit did not harden a known data-loss edge: import duplicate
fingerprints in `src/aeat/domain/transactions/_models.py` still key on effective
date, amount magnitude, and normalized narrative while omitting direction and
currency. `_evaluate_import_rows` in `src/aeat/application/ledger/_actions_import.py`
then skips matching rows as duplicates. Same-date opposite-direction movements or
same numeric amount in different currencies can collapse.

### ledger-unsupported-source-message | medium | unsupported-source path is not rendered

Commit `402f8a5d` includes `path` in unsupported-source exception context, but
the localized message does not render that path and the new test only asserts
that rendered text exists. Operators can receive a generic "cannot be imported:
invalid ledger document" message without the offending path, so S09 is not yet
fully satisfied.

### profile-active-uuid-tombstone | high | tombstoned UUIDs still bypass active-profile routing

Commit `e6c0295` filters tombstoned UUIDs in `resolve_profile_bucket`, but the
CLI root active-profile path in `src/aeat/entrypoints/cli/__init__.py` still
uses `read_profile_bucket_by_id` directly and returns for any manifest, including
tombstoned buckets. `AEAT_ACTIVE_PROFILE=<uuid>` or an active-profile pointer can
therefore bypass the live-surface lifecycle filter that explicit `--profile`
coverage now exercises.

### profile-show-by-uuid | medium | tombstoned profile inspect parity is still label-only

`config profile show` still resolves inspect targets through the label scanner in
`src/aeat/entrypoints/cli/_config/__init__.py`. The new tests prove tombstoned
profiles can be shown by label, but not by UUID. That leaves S14 open for the
by-id command-family sweep and conflicts with the resolver contract that
inspection callers may include tombstoned profiles by UUID.

### m303-seed-help-rereview | low | M303 wording correction is review-clear

Corrective commit `5abb0081e` resolves the M303 seed-help overclaim. The
Catalan and Hungarian `seed_help` entries now state that `--amount 0` declares a
zero opening balance, including prior-filer cases where the last M303 left no
pending compensation, and separately state that automatic `first_period_zero`
is independent of `seed` and proven during calculation and reconciliation from
activity-start and registry conditions. The re-review found no placeholder,
YAML, or formatting issue.

### ledger-diagnostics-direction | medium | verified re-import diagnostics lost duplicate signal

Corrective commit `34873aa5a` resolves the original high data-loss and
raw-provider-boundary blockers, but it regresses verified re-import diagnostics.
The persisted import path stamps direction-qualified fingerprints, while
`import_ledger_with_diagnostics` in `src/aeat/application/transactions/_import.py`
still receives only raw rows and recomputes fingerprints without parsed
direction. The ledger import path in `src/aeat/application/ledger/_actions_import.py`
passes `tuple(parsed.raw for parsed in parsed_rows)`, so existing duplicate
diagnostics coverage in `src/aeat/application/ledger/tests/test_actions_review_query_imports.py`
now reports only `gap`, not `duplicate`.

### profile-inspect-stale-active | medium | stale tombstoned active profile blocks inspect commands

Corrective commit `5083d57e6` fixes live app routing and baseline tombstoned
`config profile show <uuid>` parity, but a stale active profile environment
variable or pointer that names a tombstoned UUID is refused by the root callback
before `config profile show <label|uuid>` can reach its tombstone-aware inspect
resolver. Live app commands should still refuse tombstoned active UUIDs, but the
read-only inspect surface must remain reachable.

## Recommendations

- Do not close W02.P03 until the M303 seed help text distinguishes declaration of
  a zero carry-forward from automatic proof of `first_period_zero`, and W02.P03
  exec records tie the no-change code finding to RAG and test evidence.
- Do not close W02.P04 until canonical ledger exports are kept out of the raw
  bank-provider import path, dedup fingerprints include the missing financial
  discriminators, unsupported-source diagnostics render the source path, and
  verified re-import diagnostics retain duplicate reporting.
- Do not close W02.P05 until active-profile UUID routing applies the tombstone
  filter, `config profile show <uuid>` has real CLI coverage for tombstoned
  inspection, and stale tombstoned active profiles do not block explicit
  read-only profile inspection.
