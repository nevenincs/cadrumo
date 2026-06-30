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

### profile-show-option-target | medium | command-local options can masquerade as explicit show target

Corrective commit `3a451a94` preserves explicit `config profile show
<label|uuid>` inspection under a stale tombstoned active UUID, but the
real-entrypoint verb parser can treat a command-local option value such as
`--output-language en` as a fourth verb-path token. That makes no-arg
`config profile show --output-language en` look like targeted inspection,
skipping stale-active normalization even though no profile target was supplied.
No-arg `config profile show` must remain active-profile dependent; only an
explicit profile label or UUID argument should bypass stale active-profile
normalization.

### ledger-diagnostics-rereview | low | final ledger correction is review-clear

Corrective commit `2c78a89da` resolves the verified re-import diagnostics
regression by passing direction-qualified fingerprints into diagnostics and by
matching stamped, direction-derived, and legacy unstamped catalogue
fingerprints. The final ledger review reported no findings for W02.P04, and the
focused ledger gate reported 62 passed and 7 deselected.

### profile-option-target-rereview | low | final profile correction is review-clear

Corrective commit `e7482b35` resolves the command-local option masking edge.
The root CLI target detector now skips value-taking options such as
`--output-language en`, so no-arg `config profile show --output-language en`
remains active-profile dependent while explicit
`config profile show <label|uuid> --output-language en` remains reachable for
read-only tombstoned inspection. Final profile review reported no findings for
W02.P05.S12-S14, and the focused profile gate reported 55 integration tests
passed.

### renta-annual-verification-blocked-by-registry-wip | medium | S19 cannot close while shared registry is invalid

W03.P07.S19 annual Renta verification currently stops before the product surface
under review because dirty Modelo 100 registry files fail registry validation
with singleton `semantic_role` declarations for C. Valenciana carry and DANA
deduction roles. Focused M100 verification and export-refusal tests abort at
registry load before reaching application behavior. The implicated files are
already modified by another active registry campaign, so this persona campaign
must not repair them or claim S19 closed until that owner lands a valid registry
state.

### borrador-preview-csv | low | S18 parser evidence boundary fixed

Commit `1758194e5` fixes the Modelo 100 borrador parser so only filed
`DECLARACION` artefacts retain CSV values. `BORRADOR` and `PREDECLARACION`
artefacts now clear CSV even when a preview contains a CSV-looking footer, so
draft evidence cannot masquerade as filed AEAT evidence.

### local-export-evidence-notice | low | S20 export receipt evidence messaging fixed

Commit `d2cc0120e` adds explicit local-export evidence status to modelo export
results, CLI text receipts, JSON warning notices, and export help text. The
operator-facing message now states that a generated local fichero is not
official AEAT filing evidence and points to justificante, declaration
consultation, CSV cotejo, or filing-record import after external filing.

## Recommendations

- Keep W02.P03 closed: corrective commit `5abb0081e` distinguishes a declared
  zero carry-forward from automatic `first_period_zero`, and the M303 locale and
  seed-help verification gates passed.
- Keep W02.P04 closed: corrective commits `34873aa5a` and `2c78a89da` preserve
  the raw-provider boundary, direction-qualified duplicate diagnostics,
  unsupported-source paths, and corpus import/export refusal behavior.
- Keep W02.P05 closed: corrective commits `5083d57e6`, `3a451a94`, and
  `e7482b35` preserve tombstone-aware read-only inspection while keeping live
  active-profile routing guarded against tombstoned UUIDs.
- Keep W03.P07.S18 and W03.P07.S20 closed on the committed parser and local
  export evidence fixes. Do not close W03.P07.S19 until the external Modelo 100
  registry validation blocker is repaired and the annual Renta verification and
  M100 export-refusal gates can run to assertion.
