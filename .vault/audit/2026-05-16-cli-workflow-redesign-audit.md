---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-16'
modified: '2026-05-16'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-15-cli-workflow-redesign-audit]]"
  - "[[2026-05-12-cli-workflow-redesign-workflow-resumption-semantics-adr]]"
---

# `cli-workflow-redesign` audit: `remediation cycle close-out and task triage`

## Scope

This audit closes out the multi-day remediation pass that followed the
2026-05-15 ground-truth audit. The earlier audit catalogued 24 R-rows
where execution records claimed completion that did not match the
shipped code. The remediation pass had to land the missing surfaces,
gates, and contract tests, while a parallel agent was running a
codebase-wide type-normalization sweep across the same files.

In addition, this audit triages the internal task queue and records
which apex-plan steps remain blocked on future wave work that does not
belong to this worktree's chore branch.

## Findings

### Shipped in this remediation cycle

W43 filing-record render — `external_evidence` and
`amends_filing_record_id` now surface in both the JSON payload and
the text-mode renderer, with a CLI surface test pinning the schema
shape. The `external_evidence` schema is exercised by domain tests
and the amendment graph traversal is covered through
`test_amend_flow.py`.

W44 actor attribution — `calculate_modelo_revision` and
`rename_work_unit` accept an `actor` keyword and propagate it into
the bucket-event payload. The `--by` flag landed on `aeat app modelo
work calculate` and `aeat app modelo work rename` with a default
factory pulling the active profile display name. A real-behavior
test asserts the `MODELO_WORK_UNIT_RENAMED` event records both names
and the actor.

W77 ledger ratios emission — the `ratios set` and `ratios unset`
handlers append typed `LEDGER_RATIOS_SET` and `LEDGER_RATIOS_UNSET`
events to the bucket-event-history catalogue with the prior and new
ratio values in the payload. A CLI-driven boundary regression test
asserts the events actually land. The new `BucketMaintenanceError`
hierarchy is in place so the upcoming `BucketMaintenanceService`
can raise narrowly-typed failures.

W80 resume → engine linkage — `WorkflowResult.resumed_from` and
`WorkflowEngine.run_for_period(resumed_from=...)` ship with boundary
shape validation (16-char lowercase hex). The revision-verify gate
forwards `resumed_from` end-to-end. Real-behavior tests pin the
producer/consumer contract between `resume_modelo_workflow` and
the engine, including idempotency over a persistently aborted run
and the stale-id error path. The workflow-resumption-semantics ADR
carries a 2026-05-16 closure addendum.

W84 invoice taxonomy — modelo 349 bindings migrated away from the
bare `invoice` source-kind to `collectible_invoice`, with a
registry-load regression test that scans every modelo TOML.

W48 borrador surface — `aeat app modelo bindings list` renders a
new `borrador_capable` column derived from the registry's
`aeat_prefilled` marker, with a CLI surface test pinning the column
shape per row.

W74 profile activation — `aeat config profile use` emits a typed
`PROFILE_ACTIVATED` event into the bucket-event-history catalogue
alongside the existing workflow-state update; the test suite asserts
the event lands with the expected payload.

W83 / W74 / W77 enum slots — `AUTH_PROVIDER_CONFIGURED`,
`PROFILE_EXPORTED`, `PROFILE_IMPORTED`, `PROFILE_ACTIVATED`,
`BUCKET_EXPORTED`, `BUCKET_IMPORTED`, `BUCKET_RENAMED`,
`BUCKET_DELETED`, `LEDGER_RATIOS_SET`, `LEDGER_RATIOS_UNSET`,
`MODELO_WORK_UNIT_RENAMED`, `CONFIG_ENV_UPDATED`, and
`SETUP_STATE_MIGRATED` are present in `BucketEventType`. The actual
emission wiring is shipped for the ratios and profile-activation
slots; the remaining slots wait on their owning services.

Error registry — narrowly-typed error hierarchies added for
`BucketMaintenance*`, `CurrencyError` adapter failures,
`ReconciliationError` family, `ModeloExportError`,
`Modelo036LifecycleError`, `LedgerLink/Check/PreflightError`, and
`OverviewError` family. The previously missing
`BorradorSnapshotNotFoundError` registry entry is now present.
The import-time invariant test
(`test_every_aeat_error_subclass_has_a_registered_code`) passes.

CLI shape regressions — three negative-shape tests lock the
two-root contract: the bare `aeat reconcile` alias is not
registered, the retired `aeat app deadlines` subgroup is not
mounted, and `aeat app modelo export` remains absent so the
modelo audit `export` verb cannot be confused with a sibling
modelo-revision exporter.

Apex plan / ADR amendments — the apex plan §12 overlay records
verdicts for the 24 R-rows (reverted, partial, or linked to a
successor reopen). The workflow-resumption, bucket, ratios,
overview, app-modelo, actor-attribution, complementaria-external-
filing-path, and config-cli-profile-surface ADRs all carry
2026-05-15 / 2026-05-16 amendments locking the contracts the
remediation needed.

WorkflowState forward-ref fix — `WorkflowState.model_rebuild()` is
called once concrete `InvoiceReviewRecord` and `LedgerReviewRecord`
imports are available, unblocking the entire ratios test suite that
the parallel type-normalization pass had briefly broken.

### W57 evidence-bundle deduplication resolved 2026-05-16

A source-level audit (Explore agent, read-only) sweeping every
`src/aeat/` module for parallel EvidenceBundle instantiations,
manifest.json writers, evidence ZIP builders, audit verb backends,
and `modelo.audit.*` emission sites found **zero duplicates**. The
canonical service `EvidenceBundleService` at
`src/aeat/application/evidence/_service.py` is the only ZIP archive
builder for evidence/audit artifacts; the four `aeat app modelo
audit {show,check,export,replay}` verbs delegate through
`_evidence_bundle_service()` at the CLI layer with no parallel
implementations elsewhere.

`src/aeat/application/evidence/test_evidence.py` collects and
runs all 14 tests cleanly (no import error).

W57 sub-tasks for duplicate removal, alias deletion, internal-caller
migration, fixture cleanup, boundary inventory update, and import-
error fix are therefore no-ops in the current tree. The W57
behavioural follow-ups (negative tests for retired aliases,
command-behaviour coverage of audit show/check/export/replay,
end-to-end audit workflow test, help-text vocabulary audit) remain
open since they add new test coverage rather than remove duplicates.

### Conditional emissions resolved 2026-05-16

The config-init-shape ADR ratifies two conditional events:
`config.env.updated` ("only if env-file persistence survives") and
`setup.state.migrated` ("only for backend-only migration from
legacy setup state"). A code audit on 2026-05-16 found:

- `aeat.core.env_io.write_env_var` and `write_env_vars` exist but
  have zero production callers; only tests exercise them. There is
  no `aeat config env` CLI surface and no application service that
  writes to env files. The `config.env.updated` emission is
  therefore a no-op in the shipped surface; the enum slot remains
  for a future reintroduction.
- No production setup-state migration site exists. The
  `build_wizard_command(SETUP_FLOW)` flow that backs
  `aeat config init` writes directly into the secure workflow state
  via the envelope-versioned `WorkflowStateRepository`; it does not
  read or migrate a legacy `AutonomoProfile` envelope or `.env`
  file. `WorkflowStateRepository.load()` performs an envelope
  version check (`max_supported_version=_STATE_VERSION`) but no
  legacy-format upgrade. The `setup.state.migrated` emission is
  therefore a no-op in the shipped surface; the enum slot remains
  for a future reintroduction if a legacy-format upgrade is added.
  Adding emission-only scaffolding without a migration site would
  violate the project's source-hygiene rule against design-only
  shells.

### Outstanding work — to be executed in this worktree

This worktree owns the remaining implementation work. No waves are
delegated to a separate worktree. The active queue (re-recorded
2026-05-16 after a triage correction) tracks the upcoming sequence:

- W83 emissions for `auth.provider.configured`,
  `config.env.updated`, `setup.state.migrated`, plus the
  fresh-profile integration test.
- W57 evidence-bundle deduplication: audit duplicate
  implementations, delete non-canonical branches, migrate internal
  callers to `EvidenceBundleService`, fix the test_evidence.py
  import error, add negative tests for retired aliases, end-to-end
  audit workflow test.
- W63 modelo reconcile service + Pydantic command/report
  contracts, CLI verb mount under `aeat app modelo reconcile`,
  surface tests, four-locale i18n.
- W68 modelo export service + command/result contracts, CLI verb,
  surface tests, four-locale i18n; help-text gate against any
  phrasing implying live submission.
- W28 currency normalization wiring into aggregation, exchange-
  rate provider adapter, persistence path, CLI `aeat config
  currency` subgroup, error/_emit/boundary wiring, four-locale
  i18n, end-to-end coverage.
- W74 profile export/import services, `aeat config profile
  export/import PATH` verbs, lifecycle event emission, service-
  contract and CLI tests, four-locale i18n, child ADR closure
  amendment.
- W77 `BucketMaintenanceService` skeleton + browse / search /
  export / import / rename / delete methods, Pydantic command and
  result contracts, six `aeat config bucket` verbs, four-locale
  i18n, lifecycle event emission, boundary inventory update,
  central error boundary wiring, parent and child ADR amendments,
  service-contract tests, destructive-action safeguards,
  determinism, collision-handling, ordering, and pagination tests.
- W72 ledger.link / ledger.check / ledger.preflight backend
  actions, three CLI verbs, surface tests, end-to-end modelo
  lifecycle test through the reconciled verb tree, regression
  test for the canonical ledger spine, four-locale i18n.
- W81 OverviewCalendar / Agenda / Backlog / Explain services per
  the adjudicated separate-verb shape, four `aeat app overview`
  verbs, `next_due` field in the agenda payload, CLI surface
  tests, four-locale i18n, festivos/shift_deadline integration
  tests for every modelo cadence.
- W85 reconcile from-justificante backend and CLI subcommand,
  Modelo 036 alta / modificacion / baja lifecycle services with
  state-machine enforcement (modificacion requires prior alta;
  baja is terminal), three CLI verbs, lifecycle events,
  four-locale i18n, foundation ADR amendment.
- Apex / child ADR amendments closing out W77 (bucket-event-
  history), W83 (init-time vocabulary), W63/W72/W85 (reconcile
  unification), W68 (export-surface distinction), and the apex
  §3.4 / §4.2 dual-annotation amendment.
- Plan-body follow-ups for W02, W08, W23, W48, W69.
- Cross-cutting harness work: W71 contract conformance once each
  noun group lands, locale parity audit across four locales, full
  pytest sweep, full `vault check all`, feature index rebuild, and
  the release commit.

### Apex plan step bookkeeping

The apex plan step rows for the open waves stay as they are until
this worktree lands the corresponding code. Each implementation
commit will run `vault plan step check` for its rows alongside the
matching `<Step Record>` under `.vault/exec/`. The 2026-05-15 audit
overlay in apex §12 already records the verdict for the R-rows
inherited from the prior cycle; the §12 overlay is the historical
trail and does not need to be re-edited per commit.

## Recommendations

Sequence the open work as it appears in the task queue. The first
implementation passes that need to land are the ones that unblock
the cross-cutting harness work: W77 BucketMaintenanceService (gates
the `vault check all` clean-room baseline), W83 init-time events
(gates the integration test asserting init emissions land), W74
profile export/import (gates schema-migration testing), then W63 /
W68 / W72 / W81 / W85 in the order their ADRs were ratified. W28
currency wiring slots in alongside whichever modelo wave needs
multi-currency aggregation first.

The 2026-05-16 task queue is the authoritative sequencing record;
the apex plan is the authoritative scope record.
