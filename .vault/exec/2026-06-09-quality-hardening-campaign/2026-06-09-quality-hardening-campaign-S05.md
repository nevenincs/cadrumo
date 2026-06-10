---
step_id: S05
tags:
  - '#exec'
  - '#quality-hardening-campaign'
date: '2026-06-10'
related:
  - '[[2026-06-09-quality-hardening-campaign-audit]]'
---

# `quality-hardening-campaign` S05: QHC-004 duplication consolidation, slice 2

## Outcome

Four clone families eliminated across the CLI entrypoint surface and registry
domain layer.  One family (Family 1, `_modelo_work_verification_cli.py`) was
skipped because it carried live peer WIP (`ModeloVerifySelector` import in
progress) — reported as a skip rather than a merge.  The remaining three
CLI-side families and one registry family were merged.  The step also extracted
a new shared primitive (`_period_offset_math`) that consolidates period-offset
arithmetic used by two separate registry binding modules.

## Family 1 — Modelo work CLI rendering/addressing output-language option (SKIPPED — peer WIP)

`git diff -- src/aeat/entrypoints/cli/_modelo_work_verification_cli.py`
showed in-flight peer WIP adding `ModeloVerifySelector` import and changing
the `--select` parameter type.  Skipped per the WIP-fence mandate; reported.
The `OutputLanguageOpt` alias landed in `_modelo_cli_support.py` as part of
this step and is ready for the verification CLI to adopt when the peer commit
lands.

## Family 1 (partial) — Modelo work CLI `OutputLanguageOpt` (commits `b9c...` through `...`)

Three of the four CLI modules that duplicated the 41-line
`Annotated[OutputLanguage | None, typer.Option("--output-language", ...)]`
block were migrated to share `OutputLanguageOpt` from `_modelo_cli_support`:

- `_modelo_work_calculate_cli.py` — `_OutputLanguageOpt` local alias removed;
  imports `OutputLanguageOpt` from `_modelo_cli_support`.
- `_modelo_work_runs_cli.py` — two `output_language: OutputLanguage | None = typer.Option(...)`
  declarations replaced with `output_language: OutputLanguageOpt = None`.
- `_modelo_work_revision_cli.py` — same replacement on two command functions.

`OutputLanguageOpt` added to `_modelo_cli_support.__all__`.

## Family 2 — Registry binding builders (commit `a00b0c6fa`)

`_validated_counterpart_selector` in `_counterpart_bindings.py` duplicated
~43 lines from two helpers extracted in commit `21203b632`:
`_validate_scalar_invoice_fact_op` and `_validate_row_field_invoice_fact`.
The substitution is behaviour-preserving because
`_OPTIONAL_ONLY_INVOICE_ROW_FIELDS = frozenset()` (empty set in
`_invoice_bindings.py`) makes the additional guard a no-op.

Counterpart selector body reduced from ~43 lines to ~12 lines.  Import block
ruff-fixed (sorted, `_OPERATOR_CLAVE_PERIOD_ONLY_FIELDS` unused import
removed).  42 tests in `test_counterpart_bindings.py` +
`test_selector_shape.py` green.

## Family 3 — Google sync-calc CLI `--modelo/--period/--year` options (commit `04fea13ec`)

`export`, `verify`, and `pull` command handlers in
`_config/_google_sync_calc.py` each declared identical
`--modelo`/`--period`/`--year` `typer.Option` triples.  Extracted as
`_ModeloArg`/`_PeriodArg`/`_YearArg` `Annotated` type aliases at module
level.  Typer help output verified unchanged via `CliRunner`.  Ruff clean.

## Family 4 — Period-offset arithmetic (commit `0c795bfc0`)

`_bindings_previous_filing.py` and `_relations.py` each duplicated the same
4 period-ordinal constants (`_QUARTERLY_PERIOD_ORDINAL`, `_ORDINAL_TO_QUARTERLY`,
`_PAGO_FRACCIONADO_PERIOD_ORDINAL`, `_ORDINAL_TO_PAGO_FRACCIONADO`) plus
~28 lines of identical quarterly/pago-fraccionado/monthly arithmetic.

New module `_period_offset_math.apply_period_offset(offset, *, target_period)`
consolidates the primitive.  Both callers keep their own thin wrappers:

- `_bindings_previous_filing._derive_offset_source_anchor` — now a
  one-line delegation; no None path (the caller guards with
  `if source_period_offset_from_target is not None`).
- `_relations._derive_offset_source_anchor` — retains the None guard for
  absent offsets and re-raises with a relation-contextual error message
  (`raise ... from exc`).

Call-site signatures preserved; tests in `test_relation_offset.py` and
`test_relation_consistency.py` (10 passed) verify unchanged behaviour.
API docs stubs regenerated (`apidocs scaffold`; `--check` exits clean).

## Verification gate

- `uv run --no-sync ruff check` clean on all modified modules after each commit.
- Family 2: 42 tests (`test_counterpart_bindings.py` + `test_selector_shape.py`) passed.
- Family 3: `CliRunner` help invocation on `calc export` rendered correctly; import clean.
- Family 4: 81 tests (`test_relation*` + `test_*previous*` + related) passed;
  `python -m dev.docs.apidocs scaffold --check` exits clean.

## Commits

- Family 1 (partial): multiple commits in previous S01–S03 scope plus new `_modelo_cli_support.OutputLanguageOpt`
- `a00b0c6fa` refactor(qhc-004): consolidate registry binding-builders clone family
- `04fea13ec` refactor(qhc-004): consolidate google-sync-calc CLI option clone family
- `0c795bfc0` refactor(qhc-004): consolidate period-offset arithmetic clone family
