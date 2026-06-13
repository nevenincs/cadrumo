---
tags:
  - '#audit'
  - '#cli-workflow-redesign'
date: '2026-05-15'
modified: '2026-05-15'
related:
  - "[[2026-05-13-cli-workflow-redesign-epic-plan]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
  - "[[2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr]]"
---



# `cli-workflow-redesign` audit: `Apex CLI workflow redesign — 85-wave ground-truth audit`

## Scope

A session crash mid-refactor left the apex `cli-workflow-redesign` epic plan in a suspected inconsistent state. The plan declared all 2,353 Steps `[x]` across 85 Waves, 414 Phases, with 66 bound ADRs and 190 execution records. This audit verifies each Wave's claimed completion against the actual state of the codebase at HEAD on branch `chore/eliminate-shims`.

Method: one read-only `Explore` subagent per Wave (85 total), dispatched in five batches of seventeen. Each agent read only its target Wave block in the plan, then verified every concrete artefact named in the Wave's Step rows and completion notes against the filesystem (source files, named symbols, CLI verbs, registry TOMLs, test files, exec records).

## Findings

### Headline counts

| Verdict | Waves | % |
|---|---|---|
| grounded (high confidence) | 65 | 76% |
| partially-grounded | 14 | 16% |
| drifted (real implementation gaps) | 5 | 6% |
| deferred-correct (W51) | 1 | 1% |

The plan was approximately **76% truthful** at the checkbox level before remediation. Fifty-four step rows were unchecked by this audit. Sixteen Wave headers carry an `**Audit note (2026-05-15)**` block summarising the verified state.

### Drifted Waves (code missing despite `[x]`)

- **W27 bank provider expansion.** The bound ADR specifies ING / Sabadell / Openbank / Bankinter / Triodos. The shipped CSV providers under `src/aeat/adapters/inbound/` are BBVA / Santander / CaixaBank / Revolut / N26. Step rows were templated and described work that did occur, so they remain `[x]`; the ADR catalogue and the code diverge and must be reconciled separately.
- **W28 foreign currency normalization.** Domain service exists at `src/aeat/domain/currency/` with four passing unit tests; no application wiring, no CLI mount, no exec records. Reopened: `S0830`, `S0831`, `S0832`, `S0833`, `S0835`, `S0836`, `S0837`, `S0838`, `S0839`, `S0840`.
- **W74 profile noun-group CRUD.** Three claimed bucket events (`profile.exported`, `profile.imported`, `profile.activated`) are absent from `BucketEventType`; the implementation uses `profile.selected` and `profile.bucket.created` under different names. `export` / `import` CLI commands are absent. Reopened: `S2058`, `S2067`, `S2069`, `S2074`.
- **W77 ratios + bucket noun-groups.** Largest single drift in the audit. `BucketMaintenanceService` is entirely absent from the codebase. `bucket.exported`, `bucket.imported`, `bucket.renamed`, `bucket.deleted` are absent from `BucketEventType`. `ledger.ratios.set` / `ledger.ratios.unset` emission is unwired. `aeat config bucket {browse, search, export, import, rename, delete}` verbs do not exist. Reopened: `S2131`, `S2132`, `S2133`, `S2140`, `S2145`, `S2146`, `S2147`, `S2148`, `S2150`, `S2152`, `S2153`.
- **W80 workflow + preflight + resume wiring (engine-linkage half).** `aeat app modelo work resume` verb, `resume_modelo_workflow` service, and preflight invocation are wired. But the engine-linkage promised by both the W59 and W80 execution records — a `WorkflowResult.resumed_from` field and a `WorkflowEngine.run_for_period(resumed_from=...)` parameter — was never landed in `src/aeat/application/workflow/_models.py` or `_engine.py`. Templated rows remain `[x]`; the gap is captured here.

### Partially-grounded Waves (functionality real but incomplete)

- **W02 cli backend boundary.** No exec records; rows reference `tests/entrypoints/cli/` which doesn't exist (tests live source-adjacent). No uncheck — functionality grounded.
- **W08 profile read path retirement.** `profile` package was renamed to `user_profile`; multiple completion-note test paths cite the old name and missing archive / filing tests. No uncheck — rename is intentional and core functionality grounded.
- **W23 ledger transaction management.** Plan and exec docs claim sixteen verbs; code has nineteen (the extras `split`, `merge`, `history` are real, the plan documentation is stale; the rejected legacy aliases `create` / `edit` / `read` are correctly rejected). No uncheck — code is ahead of plan documentation.
- **W43 modelo filing record.** `FilingRecord.external_evidence` and `FilingRecord.amends_filing_record_id` fields persist correctly but the CLI `list` / `show` emitters omit them. Reopened: `S1288`.
- **W44 actor attribution.** `--by` flag wired on `discard` / `file` / `amend`, absent from `calculate` / `rename` despite the row's broad "mutations" wording. Reopened: `S1315`.
- **W48 borrador 100 binding integration.** Bindings list `--modelo 100` does not show the `borrador_capable` column. The actual missing piece is W47 bindings list extension; W48 rows technically grounded.
- **W57 evidence bundle shape.** `EvidenceBundleService` and CLI handlers present; `test_evidence.py` import-broken; shadow-duplicate Phase P282 never executed against the codebase; CLI behaviour / help-vocabulary tests absent. Reopened: `S1687`-`S1692`, `S1701`-`S1704`, `S1710`.
- **W59 workflow resumption semantics.** Templated rows remain `[x]`; exec-record claim about engine linkage is fiction. See W80 above.
- **W63 declaracion verification parser harvest.** `aeat app modelo reconcile` CLI verb absent. Reopened: `S1853`.
- **W68 export serializer boundary harvest.** `aeat app modelo export` CLI verb absent (only `audit export` exists, scoped under W57). Reopened: `S1913`.
- **W69 attachment evidence storage harvest.** Functionality grounded; the batch closeout's reference to a non-existent `application/attachments/` directory is a labelling error (responsibility lives correctly in `application/ledger/` + `domain/attachments/`). No uncheck.
- **W72 Reconciliation: modelo grammar reconcile.** `aeat app modelo reconcile`, `aeat app ledger link`, `aeat app ledger check`, `aeat app ledger preflight` all unshipped despite R02 / R03 closure claim. Reopened: `S2014`, `S2015`, `S2019`, `S2022`, `S2024`. **R02 and R03 should be reverted to open in the apex §12 ledger.**
- **W81 Reconciliation: overview shape completion.** Only `aeat app overview status` shipped. `calendar`, `agenda`, `backlog`, `explain` verbs and `next_due` agenda payload absent. Reopened: `S2232`, `S2233`, `S2247`, `S2248`, `S2249`.
- **W83 Reconciliation: config init backend service.** Three event names mismatched: `profile.activated` does not exist (closest is `PROFILE_SELECTED`), `bucket.created` does not exist (closest is `PROFILE_BUCKET_CREATED`), and `auth.provider.configured` / `config.env.updated` / `setup.state.migrated` are unwired. Reopened: `S2281`.
- **W84 Reconciliation: aggregation taxonomy enforcement.** Application aggregators implemented. But `registry/aeat/modelos/349.toml` still contains 16+ `source = "invoice"` declarations despite the migration claim in `S2309`. Reopened: `S2309`.
- **W85 Reconciliation: modelo foundations.** `aeat app modelo reconcile from-justificante PATH` and Modelo 036 lifecycle verbs (`alta`, `modificacion`, `baja`) not wired to CLI. Reopened: `S2342`, `S2349`. R22 deferral remains verified-correct.

### Deferred-correct

- **W51 modelo 145 foundation.** Confirmed absent as expected. **Governance drift**: a separate successor `2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr` exists at `accepted` status with P01 / P02 already executed and P03+ deferred. The successor lives outside this epic plan and should be linked from the apex ADR's R22 row.

### Patterns

1. **CLI exposure waves are the weakest link.** The recurring pattern is "backend service exists, application contract exists, but the promised `aeat …` verb was never wired". Ledger maintenance verbs (W72 / W77), modelo `reconcile` (W63 / W72 / W85), modelo `export` (W68), overview verbs (W81), and Modelo 036 lifecycle verbs (W85) all match this pattern.
2. **The Reconciliation waves W71-W85 (added 2026-05-14) themselves contain the most undelivered work.** They were authored to ratify what shipped and retire what didn't, but several R-rows were marked closed while the prescribed CLI / event work was still open. R02 / R03 (W72), R08 (W77), R17 / R18 partial (W81), R20 partial (W83), R21 partial (W84), R23 / R24 partial (W85) are paper-closed.
3. **Bucket event enum drift is systemic.** Multiple Waves declare event names in plan or exec text that don't match the actual `BucketEventType` enum members. W74 (`profile.exported` / `profile.imported` / `profile.activated`), W77 (`bucket.exported` / `bucket.imported` / `bucket.renamed` / `bucket.deleted`), W83 (`profile.activated` / `bucket.created` / `auth.provider.configured` / `config.env.updated` / `setup.state.migrated`).
4. **Exec records are uncorrelated with truth.** Waves with detailed multi-file exec records (W80) have real implementation gaps; Waves without exec records at all (W26, W84) are largely grounded. Exec records signal that work *happened*, not that the work *matches the plan*.

## Recommendations

Convergence order if you want the plan to match reality without writing the missing code:

1. **Revert apex §12 ledger R02, R03, R08 to open**, and amend R05 / R17-R20 / R21 / R23 / R24 to "partial — see W### audit note".
2. **Decide event-name canonicalisation** for W74 and W83. Either (a) align the plan text to the names actually in `BucketEventType` (`profile.selected`, `profile.bucket.created`, etc.) and uncheck nothing further, or (b) add the missing enum members and emit them.
3. **Decide W27 provider reconciliation.** Either author a successor ADR ratifying the BBVA / Santander / CaixaBank / Revolut / N26 catalogue, or open a wave to add the ING / Sabadell / Openbank / Bankinter / Triodos providers from the original ADR.
4. **Fix the W84 349.toml migration** — either complete the source-kind migration in `registry/aeat/modelos/349.toml`, or relax the registry-layer enforcement to match.
5. **Decide W51 governance.** Fold `2026-05-14-cli-workflow-redesign-modelo-145-reopen-adr` back into the apex plan by linking it from the R22 row, or formally separate it as a sibling decision.

Convergence order if you want the code to match the plan:

1. **W77 ship `BucketMaintenanceService`** (`browse` / `search` / `export` / `import` / `rename` / `delete`) and the four bucket lifecycle events. Largest single piece of missing code in the epic.
2. **W80 / W59 land the engine linkage**: add `resumed_from` to `WorkflowResult` and the `resumed_from=` parameter to `WorkflowEngine.run_for_period`.
3. **CLI verbs**: ship `aeat app modelo reconcile`, `aeat app modelo export`, `aeat app ledger link`, `aeat app ledger check`, `aeat app ledger preflight`, `aeat app overview {calendar, agenda, backlog, explain}`, Modelo 036 `alta` / `modificacion` / `baja`, `aeat app modelo reconcile from-justificante`.
4. **W57 fix `test_evidence.py` imports** and add the missing CLI verification tests for `aeat app modelo audit {show, check, export, replay}`.
5. **W28 wire the foreign-currency service** into application aggregation and expose under an `aeat config` or `aeat app` mount.
6. **W43 / W44**: extend filing-record `list` / `show` emitters to render `external_evidence` and `amends_filing_record_id`; extend `--by` flag to `calculate` and `rename`.
