---
tags:
  - '#audit'
  - '#modelo-addressing-ux'
date: '2026-06-05'
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

## MODELO-CALC-008 | LOW | W05.P09 cadence review passed with one unrelated residual

Reviewed the W05.P09 cadence closure records for the calculate extraction slice. The records now capture plan status/check, per-step execution records, focused real-behavior regressions, exact search, semantic RAG search, and architecture guard verification.

The touched production CLI modules no longer import private `domain.modelos._*` modules. `_modelo.py` consumes the top-level `aeat.application.modelo` facade for calculation revision, filing evidence kind, row DTO, and work-unit contracts. The stricter architecture guard gives the legacy root a zero private-domain import budget.

Verification passed for Ruff, compileall, application selector/addressing tests, natural-key CLI UX tests, real calculate CLI tests, row flag tests, architecture boundaries, and the command-function size guard. The only residual is the unrelated broad `_app_live.py` module-size failure already tracked as outside this modelo slice.

No unresolved review finding blocks closing `W05.P09.S32` through `W05.P09.S35`.
