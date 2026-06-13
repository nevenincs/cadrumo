---
tags:
  - '#audit'
  - '#modelo-addressing-ux'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-06-05-modelo-addressing-ux-plan]]'
  - '[[2026-06-04-modelo-addressing-ux-adr]]'
  - '[[2026-06-04-modelo-addressing-ux-research]]'
---

# `modelo-addressing-ux` Code Review

## MODELO-DECOMP-001 | LOW | Broad all-CLI size guard has unrelated drift

The touched decomposition files pass Ruff and focused real-behavior lifecycle and readiness tests. A broad run of `test_cli_module_size.py` currently reports `_doc_reference.py` above its frozen budget. That file is outside the modelo decomposition slice and was already dirty in the shared worktree, so this execution did not raise its budget or revert it.

Recommended follow-up: have the owner of the `_doc_reference.py` change either shrink that module or update its own tracked plan and budget. Modelo decomposition verification should continue using path-scoped feature-surface gates unless a full-repo stabilization pass is explicitly requested.

## MODELO-DECOMP-002 | LOW | Full discovery extraction remains open after readiness split

The `readiness` command is extracted and verified, but the wider registry discovery surface still remains in the legacy root: `list`, `describe`, `casillas`, `formulas`, and the `bindings` subgroup. This is expected because W02.P04.S14 through W02.P04.S16 remain open.

Recommended follow-up: continue with W02.P04.S14 by extracting registry discovery commands behind focused modules or application facades, then rerun discovery CLI shape tests and lower the `_modelo.py` size budget again.

## MODELO-ADDR-003 | LOW | S41 contract slice review passed with no blocking findings

Reviewed the `S41` addressing-contract diff against the accepted natural-key addressing ADR and the June 5 continuation plan. The slice is additive: it defines typed visible filing targets, exact work-unit targets, revision picks, resolved work projections, and resolved revision projections in `src/aeat/application/modelo/_work_addressing.py` without rewiring CLI behavior or changing persistence authority.

One contract hardening point was addressed before closure: explicit revision picks now require a `calculation_revision_id`, and non-explicit picks reject exact revision IDs. Ruff, Python compilation, and focused selector tests passed after the correction.

No unresolved review finding blocks closing `W01.P11.S41`.

## MODELO-ADDR-004 | LOW | S42 private facade implementation review passed

Reviewed the `S42` work-target facade functions in `src/aeat/application/modelo/_work_addressing.py`. The implementation keeps resolution behind the existing selector boundary: supported target shapes are coerced into `ModeloWorkAddress`, visible/exact targets resolve through `resolve_modelo_work_address`, and projection helpers expose visible metadata without changing persistence identity or creating a new storage path.

The remaining architectural requirement is public export through the top-level modelo application package before CLI or external consumers use these names. That is tracked by `W01.P12.S44` and should be executed immediately so consumers do not import private submodules.

No unresolved review finding blocks closing `W01.P12.S42`.

## MODELO-ADDR-005 | LOW | S44 public application facade export review passed

Reviewed the `S44` export changes in `src/aeat/application/modelo/__init__.py`. The new addressing contracts and facade helpers are available from the top-level modelo application package, which preserves the hexagonal boundary for CLI and external application consumers. Consumers should import these names from `aeat.application.modelo`, not from private `_work_addressing` modules.

The same file also contains registry discovery exports from an existing concurrent slice; those were not reverted or reworked. Ruff, a public import smoke test, and focused selector tests passed.

No unresolved review finding blocks closing `W01.P12.S44`.

## MODELO-CALC-006 | LOW | S17-S20 calculate extraction review passed with one unrelated gate failure

Reviewed the calculate extraction and support-module move. The focused calculate command body lives in `_modelo_work_calculate_cli.py`, `_modelo.py` mounts it through `register_work_calculate_commands`, and calculate transport parsing now lives in `_modelo_cli_support.py`.

The boundary split is acceptable: `_modelo_cli_support.py` parses operator tokens and delegates to `build_work_calculate_input_bundle`; `_calculate_input.py` still owns casilla normalization, non-numeric casilla refusal, row aggregate validation, binding splitting, relation coercion, and legal shortcut application. The support module imports row/input contracts through the top-level `aeat.application.modelo` facade.

Verification passed for Ruff, parser regressions, real calculate CLI regressions, row/borrador/source-mesh tests, and casilla normalization checks. The broad `test_cli_module_size.py` guard still fails on unrelated `_app_live.py` growth (`2262 > 2117`), outside this slice.

No unresolved review finding blocks closing `W03.P05.S17` through `W03.P05.S20`.

## MODELO-CALC-007 | LOW | S21-S24 calculate verification review passed with unrelated size guard residual

Reviewed the calculate verification phase. Real CLI calculation, row parsing, borrador, source mesh, and casilla-normalisation lanes passed after the extraction. Exact and semantic audits support the intended boundary: CLI calculate modules parse/render/delegate, while `_calculate_input.py` owns calculation input policy and shortcut application.

The lowered modelo size budget is present: `_modelo.py` budget is `2321`, no legacy `work_calculate` command budget remains, and current touched line counts are `_modelo.py=2321`, `_modelo_cli_support.py=556`, `_modelo_work_calculate_cli.py=456`.

Residual risk is limited to the broad `test_cli_module_size.py` module-size test failing on unrelated `_app_live.py` growth (`2262 > 2117`). That failure should stay visible to the owner of `_app_live.py`; this slice did not alter it.

No unresolved review finding blocks closing `W03.P06.S21` through `W03.P06.S24`.

## MODELO-RESUME-008 | LOW | S25-S27 resume design gate and workflow ambiguity review passed

Reviewed the resume contract and workflow ambiguity additions. The contract stays within the accepted natural-key ADR: normal resume should resolve visible filing targets through centralized modelo addressing, while exact workflow run ids and exact work-unit ids remain compatibility escape hatches. No new ADR was required because no hidden state or new legally meaningful selector axis was introduced.

The workflow layer now exposes `find_unique_run_for_period`, `WorkflowResumeRunAmbiguousError`, `WorkflowResumeRunCandidate`, and `workflow_resume_candidate_lines` through the top-level `aeat.application.workflow` facade. Multiple natural-key workflow-run matches now have an application-level refusal shape with candidate guidance instead of forcing the CLI to invent that policy.

Verification passed for Ruff, workflow resume tests, locale placeholder coverage, YAML parsing, and public import smoke tests. No unresolved review finding blocks closing `W04.P07.S25` through `W04.P07.S27`.

## MODELO-CALC-008 | LOW | W05.P09 cadence review passed with one unrelated residual

Reviewed the W05.P09 cadence closure records for the calculate extraction slice. The records now capture plan status/check, per-step execution records, focused real-behavior regressions, exact search, semantic RAG search, and architecture guard verification.

The touched production CLI modules no longer import private `domain.modelos._*` modules. `_modelo.py` consumes the top-level `aeat.application.modelo` facade for calculation revision, filing evidence kind, row DTO, and work-unit contracts. The stricter architecture guard gives the legacy root a zero private-domain import budget.

Verification passed for Ruff, compileall, application selector/addressing tests, natural-key CLI UX tests, real calculate CLI tests, row flag tests, architecture boundaries, and the command-function size guard. The only residual is the unrelated broad `_app_live.py` module-size failure already tracked as outside this modelo slice.

No unresolved review finding blocks closing `W05.P09.S32` through `W05.P09.S35`.

## MODELO-RESUME-009 | LOW | S28 workflow resume resolver review passed

Reviewed the workflow resume application boundary after the central resolver additions. The workflow package now exports `WorkflowResumeTargetResolution`, `resolve_modelo_workflow_resume_target`, and the visible/exact target helpers from the top-level `aeat.application.workflow` facade. The resolver delegates visible filing target lookup, exact work-unit lookup, revision selector handling, visible work projection, and workflow-period conversion to the public `aeat.application.modelo` facade instead of reaching into private selector modules.

Natural-key visible targets still refuse ambiguous workflow-run matches with candidate guidance. Legacy exact work-unit addressing preserves latest-run compatibility, while exact workflow run ids remain a direct resume escape hatch.

Verification passed for scoped Ruff, `src/aeat/application/workflow/test_resume.py`, and a public import smoke test for the workflow resume facade. No unresolved review finding blocks closing `W04.P08.S28`.

## MODELO-RESUME-010 | LOW | W04.P08 resume CLI and projection review passed

Reviewed the remaining resume implementation rows. The `work resume` CLI now offers the natural-key path with `--modelo --year --period`, keeps direct workflow run ids and exact work-unit ids as compatibility escape hatches, and delegates target resolution to the top-level `aeat.application.workflow` facade. Exact work-unit and calculation-revision option validation uses shared helpers from `_modelo_cli_support.py`; mixed positional target interpretation is centralized in the workflow resolver.

The workflow resolver delegates visible filing lookup, revision selector picks, work projection, and workflow-period conversion to the top-level `aeat.application.modelo` facade. It no longer imports private domain id types for its public signature. Resume output and JSON payloads now include `resolved_source`, visible filing metadata, work-unit ids, short work-unit ids, and calculation revision ids where available.

Verification passed for scoped Ruff, focused CLI/application resume tests, locale scaffold check, locale audit, hardened locale coverage, placeholder parity, exact `rg` discovery, and serialized `vaultspec-rag` semantic discovery over the workflow resolver, CLI resume command, and revision selector surfaces. The RAG service initially timed out during a held writer lock; after a clean restart and serialized searches, semantic evidence was collected successfully. No unresolved review finding blocks closing `W04.P08.S29`, `W04.P08.S30`, `W04.P08.S31`, `W04.P08.S46`, or `W04.P08.S47`.

## MODELO-CENTRAL-011 | LOW | S49 static centralized-addressing guard review passed

Reviewed the new architecture-boundary guard for extracted modelo CLI modules. It blocks raw exact-id regex use outside `_modelo_cli_support.py` and blocks legacy selector calls such as direct work-unit lookup, direct calculation-revision lookup, latest workflow-run selection, and workflow-period conversion from extracted modules. The guard intentionally scopes to extracted modules so the remaining `_modelo.py` legacy root debt is still represented by open W05 rows rather than converted into an always-failing broad test.

Verification passed for scoped Ruff and `src/aeat/entrypoints/cli/test_architecture_boundaries.py`. No unresolved review finding blocks closing `W05.P13.S49`.

## MODELO-CENTRAL-012 | LOW | S50 exact audit and registry repair review passed

Reviewed the exact audit results. Raw exact-id regex use is now confined to `_modelo_cli_support.py`, with `work resume` retaining only operator help text for exact legacy ids. Extracted resume and workflow surfaces route through centralized addressing helpers; remaining direct work-unit lookup and selector-helper usage is in the legacy `_modelo.py` root or in `_modelo_cli_support.py` for explicit error guidance. That residual root debt remains open under W05 and was not hidden by this closure.

The audit exposed one current-state blocker from peer work: `ModeloWorkPeriodTokenError` had been added without an error-code registry entry. That is now repaired with `REFUSED_MODELO_WORK_PERIOD_TOKEN`, deferred translated messages, and locale entries added through `python -m aeat.locales set`. The stale current test docstring `work resume WORKFLOW_RUN_ID` was also updated.

Verification passed for scoped Ruff, focused resume/workflow tests, architecture-boundary tests, locale scaffold check, locale audit, hardened locale coverage, and placeholder parity. No unresolved review finding blocks closing `W05.P13.S50`.

## MODELO-CENTRAL-013 | LOW | W05.P13 centralized addressing closure review passed

Reviewed the final W05.P13 centralized-addressing slice. The application layer now owns the operator-target facade for modelo work addressing: period normalization, exact-or-visible work-target address construction, work-unit resolution, and command-specific calculation-revision resolution live in `aeat.application.modelo` and are exported through the top-level package. The legacy `_modelo.py` shims still exist while decomposition continues, but they now validate CLI token shape and delegate target selection to the application facade.

The export CLI no longer receives a private resolver callback from the legacy root; it imports and consumes `resolve_modelo_revision_for_operator_target` from the top-level application facade. Resume continues to consume `resolve_modelo_workflow_resume_target` from the top-level workflow facade. The architecture guard now blocks CLI modules from importing or calling low-level work-address and calculation-revision-address primitives directly.

Verification passed for scoped Ruff, compileall, application work-addressing and selector tests, workflow resume tests, CLI natural-key work/resume/export tests, compare/projection/reconcile tests, architecture-boundary tests, locale scaffold/audit checks, exact `rg` discovery, serialized `vaultspec-rag` discovery, and docs conformance with the `docs` marker. No unresolved review finding blocks closing `W05.P13.S48` through `W05.P13.S52`.

Post-closure surface-gate validation found one remaining extracted CLI selector-policy violation in `_modelo_work_revision_cli.py`: the revision command fetched a work unit directly to render Modelo 202 modality metadata. It was repaired to use `resolve_modelo_work_unit_for_operator_target` from the top-level application facade. Scoped Ruff and architecture/resume workflow tests passed after the repair. The only failing touched-test lane is still the broad module-size guard, and its offenders are unrelated `_app_live.py` and `_ledger.py` budget drift.

## MODELO-FINAL-014 | LOW | Final decomposition and addressing review passed with tracked residuals

Reviewed the final plan surface after W05.P13. The main product risk called out by the ADR has been addressed: normal CLI work and revision addressing no longer requires operators to copy/paste raw work-unit or calculation-revision ids. Natural modelo/year/period resolution is centralized in `aeat.application.modelo`, resume resolution is centralized in `aeat.application.workflow`, export consumes the application facade directly, and static guards prevent CLI modules from returning to low-level addressing primitives.

The remaining `_modelo.py` file is still large at 2242 lines, but it is materially reduced from the original 4248-line baseline and its budget is ratcheted to the current size. It still contains residual command bodies that should continue through focused decomposition work. That is structural debt, not an active duplicate selector-policy path. Broad module-size verification remains red for unrelated shared-worktree `_app_live.py` and `_ledger.py` growth; this plan did not normalize those budgets.

Verification passed for the focused modelo surface. Residual risks and ADR-required future decisions are recorded in the W05.P10 execution records and the follow-up ADR queue. No unresolved review finding blocks closing `W05.P10.S36` through `W05.P10.S39`.
