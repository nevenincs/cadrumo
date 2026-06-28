---
tags:
  - '#audit'
  - '#residual-cli-hardening'
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-10-cli-operator-surface-plan]]'
  - '[[2026-06-10-cli-envelope-notice-standardisation-plan]]'
  - '[[2026-05-13-cli-workflow-redesign-epic-plan]]'
  - '[[2026-06-10-cli-operator-surface-closure-review-audit]]'
  - '[[2026-06-03-cli-workflow-redesign-audit]]'
---

# `residual-cli-hardening` audit: `handover triage and closeout`

## Scope

Triage of the residual CLI hardening handover that named Claude session
`cd16345c-b982-407a-9c40-69c32f8ba8c9` plus three primary plans. A vault search
did not find that exact session id, so this note is grounded in the named plans,
their exec/audit records, and the current test results.

## Near-closeout status

CLI envelope notice standardisation is now complete: `W04.P05.S17` is checked,
and the plan reports 25 of 25 steps complete. The closeout removed the remaining
CLI blockers in the selected entrypoint slice: source-bound M130 calculation
tests now seed real ledger source rows instead of overriding casilla `01`, the
M202 Art. 40.2 test supplies the declared prior-M200 binding for casilla `01`,
and the inventory list payload accepts both summary rows and full typed
inventory ledger rows.

The green S17 evidence is recorded in the S17 exec note under the
`2026-06-10-cli-envelope-notice-standardisation` exec directory. Traceability
backfill notes now cover the older checked rows that predated this closeout, so
the plan status no longer reports missing exec ids.
Key checks:

- `pytest src/aeat/entrypoints/cli/tests/test_ledger_interface_contract_payloads.py::test_invoice_inventory_evidence_and_rule_apply_lists_use_typed_rows src/aeat/entrypoints/cli/tests/test_cli_module_size.py src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py -m "unit or integration" -q`: 195 passed.
- `pytest src/aeat/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py src/aeat/entrypoints/cli/tests/test_modelo_compare.py src/aeat/entrypoints/cli/tests/test_modelo_projection.py src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py -m "unit or integration" -q`: 16 passed.
- `pytest src/aeat/entrypoints/cli -q`: 77 passed, 1746 deselected.
- `vaultspec-core vault plan status .vault/plan/2026-06-10-cli-envelope-notice-standardisation-plan.md`: 25 of 25 complete, `exec_missing_ids: []`.
- `vaultspec-core vault plan check .vault/plan/2026-06-10-cli-envelope-notice-standardisation-plan.md`: passed with only existing `PLAN022`.

The local `C:\Users\hello\AppData\Local\Temp` volume was nearly full, so the
green pytest runs used workspace-local `--basetemp` directories on `Y:`.

One workflow-redesign stale row from the setup cluster was safely closed:
`W83.P400.S2281` is now
checked in the epic plan. The existing 2026-06-03 audit states the required
setup event emissions are structurally wired and the optional pair is dormant;
the focused regression test passed during this triage
(`src/aeat/application/setup/tests/test_event_emission_contract.py`: 5 passed).
The vault plan CLI printed `Closed Step S2281` and then failed only in its graph
cache invalidation hook due to missing workspace context; the plan checkbox was
written and the unrelated CLI-inserted comment churn was removed.

One W77 child-ADR row was also safely closed during the continuation pass:
`W77.P374.S2153` is checked because the bucket and ratios child ADRs already
carry the required 2026-06-03 composition-pattern amendments. The exec note for
that row records this as evidence reconciliation only; it does not claim that
R08 or the remaining bucket-maintenance verbs are complete.

## Operator-surface subdivision

Do not hand off the operator-surface plan as a raw unchecked-row count. After
this continuation, the plan reports 55 of 55 steps complete. The final W02
restore/lineage rows were closed from current implementation evidence, focused
real-behavior tests, live help, and conformance/reference gates. `rg` finds no
unchecked rows in the plan. A later full `vault plan check` retry exited
cleanly.

- **Closed restore and lineage work:** `W02.P04.S15` through `W02.P05.S31` are
  now closed. Restore moves STASHED/ARCHIVED rows back to ACTIVE through the
  ledger application service, emits `LEDGER_TRANSACTION_RESTORED`, preserves the
  finalized-modelo guard, has CLI bulk-stash recovery coverage, and has synced
  help/docs/reference evidence. The stable lineage handle resolves old edit ids
  through `history`, `view`, and `track` while keeping content-addressed
  transaction ids authoritative for storage and audit.
- **Closed preflight default work:** `W01.P02.S07` through `W01.P02.S10` are
  now closed. `config profile preflight` defaults `--revision-id` from modelo,
  filing year, and period, keeps the explicit override for exact replay,
  refuses ambiguous natural keys with candidates, and the choose-modelo guide
  no longer teaches a revision-id paste-back detour for normal preflight.
- **Closed switch rename work:** `W03.P06.S32` through `W03.P06.S35` are now
  closed. Live `aeat config --help` lists `aeat config switch NAME`, `aeat
  config unlock operator` returns click's unknown-command refusal, docs no
  longer teach `config unlock`, and the stale `_RETIRED_VERBS` plan wording was
  reconciled to the already-accepted no-ledger/no-alias behavior.
- **Closed period grammar work:** `W03.P08.S39` through `W03.P08.S44` are now
  closed. The plan rows were reconciled to the 2026-06-10 ADR amendment:
  ledger period commands use the strict AEAT token plus `--year` shape, calendar
  shapes and year-qualified hybrids are refused, help/docs teach one grammar,
  and the 42-test ledger period grammar suite is green.
- **Closed read-back baseline work:** `W04.P09.S45` through `W04.P10.S55` are
  now closed. M036 list/view, reconciliation history, and IVA wallet correction
  surfaces are live, focused real-behavior suites passed, and the CLI-reference
  drift gate is green after fixing an application-modelo import cycle.
- **Closed vocabulary work:** `W03.P07.S36`, `W03.P07.S37`, and `W03.P07.S38`
  are now closed. `config repair reset-progress` keeps the hard-renamed verb
  and no `reset-state` alias, while help/text output no longer leaks
  workflow-state, envelope, fingerprint, or bucket wording. `config profile
  history` accepts an operator profile token, help/docs no longer teach
  `BUCKET_ID`, `config bucket` remains unknown, the generated CLI reference is
  synced, and the stable `config.bucket.history` machine token is documented as
  a non-operator carve-out.
- **Operator-surface closeout state:** all rows are checked. Treat the plan as
  implementation-complete; the later full plan check retry exited cleanly.

## Workflow-redesign residuals

After the W77 continuation pass, the older workflow epic has no unchecked rows.
`S2131`, `S2132`, `S2145`, and `S2152` are now closed from real service
implementation, real service-contract tests, and ADR reconciliation. W77's
closed scope is `BucketMaintenanceService` browse, export, import, rename, and
delete as backend/application lifecycle operations. Search is intentionally
deferred to the accepted bucket-search ADR and is not a storage-wide scan or a
W77 closure blocker.

The workflow plan status reports 2360 of 2360 steps complete. Its
`exec_missing_ids` count remains high because the old epic predates the current
exec-record discipline across many historical rows; that archive-wide gap is a
separate curation task and should not be conflated with current implementation
residuals.

W77 checks:

- `ruff check src/aeat/application/bucket_maintenance src/aeat/adapters/persistence/storage/bucket`: passed.
- `pytest src/aeat/application/bucket_maintenance/tests src/aeat/adapters/persistence/storage/bucket/tests -m "unit or integration" -q --basetemp Y:/tmp/pytest-w77-bucket-maintenance-final-2`: 127 passed.
- `vaultspec-core vault plan status .vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`: 2360 of 2360 complete, with historical exec-missing warnings only.

`S2150` is now closed as a supersession reconciliation, not as a bucket-app
implementation. The workflow plan row and older workflow/bucket ADRs now state
that `aeat config bucket` is retired, must not be reintroduced, and that
bucket-maintenance service verbs remain backend/application lifecycle operations
until a future profile-named operator surface is explicitly accepted.

No local plan, exec, or audit record matches `W7070` exactly. The closest
workflow target is W70, which already has a closeout exec record and checked
rows in the workflow redesign epic.

The envelope-notice plan can move to closeout review as implementation-complete
because its final row is checked, the S17 gate is green, and the vault status
exec-record warning has been reconciled. Operator surface can move to closeout
review as implementation-complete because its status is 55 of 55 and the full
plan-check retry succeeded.
Workflow redesign can move to closeout review as implementation-complete. Its
only remaining issue is historical exec-record curation for old checked rows,
not an open implementation row.

## Files touched

- `.vault/plan/2026-05-13-cli-workflow-redesign-epic-plan.md`
- `.vault/plan/2026-06-10-cli-operator-surface-plan.md`
- `.vault/adr/2026-05-12-cli-workflow-redesign-adr.md`
- `.vault/adr/2026-05-12-cli-workflow-redesign-bucket-adr.md`
- `.vault/adr/2026-06-03-cli-workflow-redesign-adr.md`
- `src/aeat/entrypoints/cli/_config/_bucket_history.py`
- `src/aeat/entrypoints/cli/_config/_repair_cli.py`
- `src/aeat/application/bucket_maintenance/__init__.py`
- `src/aeat/application/bucket_maintenance/_service.py`
- `src/aeat/application/bucket_maintenance/tests/test_service_import_export.py`
- `src/aeat/core/errors/registry/_application_part2.py`
- `src/aeat/entrypoints/cli/_app_live.py`
- `src/aeat/entrypoints/cli/_ledger_payloads.py`
- `src/aeat/entrypoints/cli/_ledger_rule_payloads.py`
- `src/aeat/entrypoints/cli/_modelo_payloads.py`
- `src/aeat/entrypoints/cli/_payloads_modelo_reconcile.py`
- `src/aeat/entrypoints/cli/tests/_m130_source_support.py`
- `src/aeat/entrypoints/cli/tests/test_modelo_calculation_through_real_cli.py`
- `src/aeat/entrypoints/cli/tests/test_modelo_compare.py`
- `src/aeat/entrypoints/cli/tests/test_modelo_projection.py`
- `src/aeat/entrypoints/cli/tests/test_modelo_work_natural_key.py`
- `src/aeat/entrypoints/cli/tests/test_ledger_verb_spine.py`
- `src/aeat/entrypoints/cli/tests/test_config_custody_profile_lifecycle.py`
- `src/aeat/entrypoints/cli/_config/tests/test_repair_reset_progress.py`
- `dev/docs/cli_reference.py`
- `dev/docs/tests/test_cli_reference_conformance.py`
- `docs/how-to/profile-setup.md`
- `docs/how-to/troubleshooting.md`
- `src/aeat/domain/modelos/__init__.py`
- `.vault/exec/2026-06-10-cli-envelope-notice-standardisation`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P07-S36.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P06-S32.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P06-S33.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P06-S34.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P06-S35.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W01-P02-S07.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W01-P02-S08.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W01-P02-S09.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W01-P02-S10.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P08-S39.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P08-S40.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P08-S41.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P08-S42.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P08-S43.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P08-S44.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P09-S45.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P09-S46.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P09-S47.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P09-S48.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P09-S49.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P10-S50.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P10-S51.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P10-S52.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P10-S53.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P10-S54.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W04-P10-S55.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P07-S37.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W03-P07-S38.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S15.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S16.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S17.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S18.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S19.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S20.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S21.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S22.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S23.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P04-S24.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P05-S25.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P05-S26.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P05-S27.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P05-S28.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P05-S29.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P05-S30.md`
- `.vault/exec/2026-06-10-cli-operator-surface/2026-06-12-cli-operator-surface-W02-P05-S31.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-06-12-cli-workflow-redesign-W77-P374-S2150.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-06-12-cli-workflow-redesign-W77-P374-S2153.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-06-12-cli-workflow-redesign-W77-P370-S2131.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-06-12-cli-workflow-redesign-W77-P370-S2132.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-06-12-cli-workflow-redesign-W77-P373-S2145.md`
- `.vault/exec/2026-05-13-cli-workflow-redesign/2026-06-12-cli-workflow-redesign-W77-P374-S2152.md`
- `.vault/audit/2026-06-12-residual-cli-hardening-triage-audit.md`
- `.vault/audit/2026-06-12-residual-cli-hardening-code-review-audit.md`

## Next worker brief

No immediate next implementation worker is needed for the three named plans.
Next work should be a closeout-review / vault-curation brief: verify the three
plans, decide whether to archive or backfill the old workflow epic's historical
exec-missing rows, and then open a separate bucket-search worker only if the
accepted bucket-search ADR is being executed. The envelope-notice,
operator-surface, and workflow-redesign plans are implementation-complete.
