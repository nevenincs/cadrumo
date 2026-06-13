---
tags:
  - '#audit'
  - '#residual-cli-hardening'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-12-residual-cli-hardening-triage-audit]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-06-10-cli-envelope-notice-standardisation-plan]]'
---

# `residual-cli-hardening` Code Review

## RCH-001 | LOW | `_app_live` export compatibility after size repair

The first split removed the long `_app_live.__all__` block to clear the module
size gate. Direct test imports still passed, but removing `__all__` would alter
star-import behaviour for any local consumer. Fixed before closeout by restoring
the same export set as a compact one-line `__all__`, keeping `_app_live.py`
under the 1250-line module budget.

## RCH-002 | LOW | New modelo payload split should not add a fresh private-domain import

The first reconciliation payload split imported `WorkUnitId` from the private
domain id module in the new payload file. Fixed before closeout by exposing
`WorkUnitId` through the top-level `aeat.domain.modelos` package and importing
that public re-export from the split payload module.

## RCH-003 | INFO | S17 closeout blockers cleared and traceability reconciled

The later closeout pass fixed the stale M130/M202 source-bound calculation
tests and the inventory list row payload contract. The selected CLI entrypoint
suite, extended schema conformance gate, module-size gate, and touched-file
ruff checks are green. `W04.P05.S17` is checked and the envelope-notice plan
reports 25 of 25 steps complete with no missing exec ids after the S17
frontmatter repair and checked-row traceability backfill.

## RCH-004 | INFO | W77 S2153 closure is evidence reconciliation only

`W77.P374.S2153` is correctly closeable from existing ADR evidence: the bucket
and app-ledger-ratios child ADRs already carry the required 2026-06-03
composition-pattern amendments. The exec note did not overclaim service
completion at the time it was written; the later RCH-015 pass closes the
remaining W77 service rows with implementation and test evidence.

## RCH-005 | LOW | W77 S2150 conflicts with newer operator-surface policy

The remaining workflow row `S2150` asks to register verbs under
`aeat config bucket`, but newer operator-surface tests and audit evidence now
assert that standalone operator-facing group is retired. Reintroducing it would
regress the current surface. The row needs supersession/ADR reconciliation
before any implementation worker attempts CLI mounting.

## RCH-006 | INFO | W77 S2150 conflict resolved by supersession, not mount

The continuation pass rewrote S2150 to the accepted current outcome and closed
it with an exec record: `aeat config bucket` remains retired, event history
stays under `aeat config profile history`, and bucket-maintenance service verbs
remain backend/application lifecycle operations until a future profile-named
operator surface is accepted. This avoids the high-risk regression of
reintroducing `bucket_app`.

## RCH-007 | INFO | Profile-history surface now hides bucket ids from operator text

`config profile history` now exposes a `PROFILE` argument and resolves it
through workflow/profile lookup before reading bucket event history. Text output
uses `operation	config.profile.history` and `profile	NAME`; the stable JSON
schema token remains `config.bucket.history` by documented machine-API carve-out.
Focused help and subprocess tests passed, and the JSON/documented-command gates
remained green.

## RCH-008 | LOW | Locale audit still blocked by unrelated extra key

`python -m aeat.locales scaffold --check` and `python -m aeat.locales audit`
still fail on the pre-existing extra `cli.overview.warning.censo_enrolment_unverified`
key in all four locale catalogues. The profile-history locale strings are
present and exercised by help output; this blocker belongs to the separate
overview/censo locale cleanup, not the retired-bucket slice.

## RCH-009 | INFO | S36 reset-progress wording closeout passes focused review

The S36 change keeps CLI behavior inside the entrypoint boundary: it still calls
the existing workflow application services and preserves the stable
`config.repair.reset_progress` JSON envelope, while limiting the text-mode label
changes to presentation. The regression tests cover the visible help and
text-mode dry-run output without fakes or monkeypatches. Review removed a
misleading `--language en` argument from the cached help test because the
assertion is intentionally locale-tolerant; the focused suite and ruff check
passed again after that adjustment.

## RCH-010 | INFO | W03.P06 switch closure verified after registry blocker fix

The W03.P06 closure is evidence reconciliation, not a new CLI rename. Live help
shows `aeat config switch NAME`, `config unlock` returns an unknown-command
refusal, generated docs reference `config.switch`, and focused lifecycle tests
cover activation, activation event emission, and the no-alias retirement. During
verification, pytest import was blocked by a duplicate
`INTEGRITY_STORED_PROFILE_DRIFT` declaration in the shared dirty error registry.
The duplicate application-part registration was removed, leaving the domain
error declaration as the single owner; focused tests and ruff passed afterward.

## RCH-011 | INFO | W01.P02 preflight default closure is evidence-backed

The W01.P02 rows were closed from existing implementation and focused tests.
`config profile preflight --help` now exposes `--revision-id` as an optional
exact-replay override and documents the active-revision default. The dedicated
real-behavior module covers natural-key resolution, explicit override,
unresolvable natural key guidance, invalid override guidance, and ambiguous
candidate listing. The choose-modelo guide uses the natural-key preflight form
and reserves `modelo describe` for catalogue lookup, not a paste-back detour.

## RCH-012 | INFO | W03.P08 period grammar closure matches amended ADR

The P08 plan rows were stale against the 2026-06-10 D4 amendment, which
superseded the older accepted-and-converted calendar-shape wording. The closure
updated the rows to match the implemented strict grammar: ledger period commands
accept AEAT tokens with `--year`, refuse calendar shapes such as `2026Q1`, and
refuse year-qualified hybrids such as `2026-1T`. The 42-test period grammar
suite, documented-command conformance, and CLI-reference drift gate passed.

## RCH-013 | INFO | W04 read-back baseline closed after import-cycle repair

The W04 read-back surfaces are verified: M036 list/view, reconciliation history,
and IVA wallet correction all have live CLI help and focused real-behavior
coverage. During W04 gate execution, CLI-reference generation exposed an
application-modelo import cycle:
`_verification_actions -> _calculation_actions -> _official_box_advisory ->
_verification_actions`. The fix imports IVA wallet blocked-message rendering
from `_iva_wallet_gate`, the owning extracted helper module, instead of reaching
back into `_calculation_actions`. Ruff, focused W04 suites, import smoke, and
CLI-reference drift passed afterward.

## RCH-014 | INFO | W02 restore/lineage closure is evidence-backed

The final operator-surface W02 rows were closed without adding CLI business
logic. Restore is implemented in the ledger application lifecycle service,
emits the distinct `LEDGER_TRANSACTION_RESTORED` event, preserves the
finalized-modelo guard, and the CLI delegates to that service. Lineage
resolution remains a read-boundary behavior: `history`, `view`, and `track`
resolve old edit ids through `resolve_lineage_transaction_id`, while storage and
audit keep the current content-addressed transaction id authoritative. Focused
restore/lineage tests passed (28 tests), the documented-command/D5/reference
gate passed (54 tests), live help was checked for restore/history/view/track,
and touched ledger files passed ruff. `vault plan status` now reports the
operator-surface plan at 55 of 55; a later full `vault plan check` retry exited
cleanly.

## RCH-015 | INFO | W77 service completion keeps CLI/storage boundaries intact

The W77 closeout lands export/import in `BucketMaintenanceService` without
mounting `aeat config bucket` or adding CLI business logic. Export composes the
profile bundle serializer, manifest digest, sealed-archive writer, active DEK or
recovery passphrase wrapping, and `BUCKET_EXPORTED`; import composes the sealed
archive reader, schema/passphrase/collision guards, profile create span,
profile bundle deserializer, and `BUCKET_IMPORTED`. The one private
`UserProfilePortableExport` import found during review was corrected to the
domain package top-level lazy re-export. Focused bucket-maintenance plus sealed
archive tests passed (127 tests), and touched bucket-maintenance/storage files
passed ruff. Search remains explicitly deferred to the bucket-search ADR.
