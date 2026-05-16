---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-16'
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

### Task queue triaged

The remediation worktree's internal task queue was triaged from
roughly 313 entries down to 92. The cuts removed:

- Service-implementation tasks for W63 (reconcile), W68 (export),
  W74 (profile export/import), W77 (BucketMaintenanceService),
  W72 (ledger link/check/preflight), W81 (overview verb tree),
  W85 (reconcile-from-justificante and Modelo 036 lifecycle), and
  W28 (currency normalization). These waves require multi-file
  service skeletons, CLI verb mounts, i18n in four locales, and
  end-to-end fixtures. They are tracked in the apex plan and
  belong in their own dedicated worktrees rather than in a
  `chore/eliminate-shims` remediation branch.
- Per-wave "re-check after X lands" follow-ups for the same set,
  which are trivially blocked on the same implementations.
- Documentation tasks (README, developer notes, per-feature docs)
  that the user did not request and that conflict with the
  source-hygiene rule against feature-specific doc files. Commit
  messages and PR descriptions carry the same context.
- Vague vocabulary / locale-parity audits that cannot be acted on
  without an accompanying implementation surface to audit.
- W57 evidence-bundle deduplication, which requires a source-level
  audit and rewrite that is out of scope here.

### Apex plan steps tied to remaining waves

The apex plan retains every step record for the deferred waves
above. No retroactive uncheck or check operations were performed
through `vault plan` because the parallel type-normalization agent
is still rewriting some of the same surfaces. Mass step edits at
this moment would either conflict with that work or freeze a
mid-flight state. The W43 / W44 / W48 / W77 ratios / W80 / W84
steps are already checked or carry `**Audit note (2026-05-15)**`
callouts marking their actual verdict, which the apex §12 overlay
ratifies.

## Recommendations

Treat the W63 / W68 / W74 services / W77 BucketMaintenanceService /
W72 link-check-preflight / W81 overview verb tree / W85 reconcile-
from-justificante + Modelo 036 lifecycle / W28 currency wiring as
separate, charter-bound work items that each warrant their own
worktree, ADR-backed scope, and execution record sequence.

When those waves land, the apex plan steps for the affected R-rows
can be re-checked via `vault plan step check` in the originating
worktree, alongside the corresponding `<Step Record>`. The audit
overlay in apex §12 stays as the historical record of the gap and
the close-out path.

Cross-cutting final gates that remain pending — full pytest sweep
after the parallel type pass settles, full `vault check all`,
feature-index rebuild, and the release commit — should run from a
single coordinating worktree after the in-flight type and packaging
moves stabilise.
