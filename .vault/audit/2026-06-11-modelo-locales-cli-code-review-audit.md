---
tags: ['#audit', '#modelo-locales-cli']
date: '2026-06-11'
related:
  - '[[2026-06-11-modelo-locales-cli-plan]]'
  - '[[2026-06-11-modelo-locales-cli-adr]]'
  - '[[2026-06-11-modelo-locales-cli-research]]'
---

# `modelo-locales-cli` Code Review

## MODELCLI-000 | LOW | No actionable findings in P01.S01 through P01.S03

Reviewed the first manager slice covering typed schema-local locale records, contained registry-root resolution, and deterministic TOML load/write behavior. The implementation keeps writes under the registry modelo tree, preserves the runtime distinction between continuity-key and revision-key locale files, and does not mutate committed schema locale TOML during this slice.

Focused evidence reviewed: `ruff check` passed for the touched locales modules, a real M130 locale file parsed through the manager, a temporary registry-local locale file wrote and re-parsed through `tomllib`, and traversal-like modelo ids were refused before path joining.

## MODELCLI-001 | LOW | S04/S05 stale-target gap found and resolved

Reviewed the registry-backed inventory and coverage/drift layer. Initial review found that `drift_records` only inspected targets with expected inventory keys, so a modelo-level locale file could avoid stale-key reporting when the audited revision had no continuity ids. The manager now audits both modelo-level and revision-level targets for every revision coverage request, using empty expected/valid sets when a target has no applicable schema keys.

Focused evidence reviewed after the fix: `ruff check` passed, committed M130 coverage remains complete, committed M303 inventory still derives 240 revision-local leaves, and a synthetic real-loader registry with a modelo-level stale key now reports the stale key plus missing selected-revision leaves.

## MODELCLI-002 | LOW | No actionable findings in P02.S06 through P02.S12

Reviewed the modelo Typer sub-application, audit/scaffold/set/remove/coverage commands, static localized diagnostic keys, and locale catalogue entries for the new command surface. The commands delegate schema validation and path containment to `ModeloLocaleManager`, preserve the separation between eager CLI YAML strings and registry-local schema TOML, and keep audit/check commands non-writing.

Focused evidence reviewed: `ruff check` passed for the touched locale modules; `python -m aeat.locales modelo --help` and `python -m aeat.locales modelo scaffold --help` render localized command help; `python -m aeat.locales modelo coverage/audit en 130 2019-y-siguientes` reports complete coverage; `python -m aeat.locales modelo audit ca 303 2023-y-siguientes` reports localized missing-key drift and exits nonzero as expected for incomplete campaign coverage.

Residual verification note: a fresh top-level `python -m aeat.locales scaffold --check` is currently blocked by an unrelated active worktree import regression in `application/filing/_export.py`, where `re` is referenced without import during f-string registry discovery.

## MODELCLI-003 | LOW | S13 empty modelo-scope scaffold file found and resolved

Reviewed the first manager test slice. The new scaffold preservation test found that `scaffold_revision` wrote an empty modelo-level locale TOML file when the selected revision had no modelo-scope expected keys and no existing modelo-level locale file. The manager now creates missing files only for targets with expected translation leaves while still rewriting existing files when stale keys need cleanup.

Focused evidence reviewed after the fix: `ruff check` passed for the manager and manager tests, and `pytest src/aeat/locales/tests/test_modelo_manager.py -q` passed with real copied M130 registry data.

## MODELCLI-004 | LOW | No actionable findings in P03.S14

Reviewed the modelo CLI integration test slice covering coverage, audit drift, scaffold check, scaffold write, set, remove, and invalid-key refusal. The tests invoke the real Typer app against copied bundled M130 registry data and verify non-writing check mode plus the empty modelo-scope file regression from S13.

Focused evidence reviewed: `ruff check` passed for the touched locale CLI, manager, and tests; `pytest src/aeat/locales/tests/test_modelo_cli.py -q -m integration` passed; and the combined `pytest src/aeat/locales/tests/test_modelo_manager.py src/aeat/locales/tests/test_modelo_cli.py -q -m "unit or integration"` run passed.

Residual verification note: the repository default pytest marker is `-m unit`, so integration-marked CLI tests are deselected unless the focused command overrides the marker expression.

## MODELCLI-005 | LOW | No actionable findings in P03.S15

Reviewed the catalogue isolation regression tests. The new assertions hash eager locale YAML catalogues before and after modelo-local CLI writes and reload the copied registry to prove `CasillaDefinition.label` stays the official Spanish value while `get_label("en")` reflects the schema-local override.

Focused evidence reviewed: `ruff check` passed for the touched CLI, manager, and CLI tests, and `pytest src/aeat/locales/tests/test_modelo_cli.py -q -m integration` passed.

## MODELCLI-006 | LOW | No actionable findings in P03.S16

Reviewed the registry-loader roundtrip coverage. The new test writes a schema-local translation through `ModeloLocaleManager` and loads the copied real Modelo 130 registry directory through `load_modelo_directory`, proving manager-written TOML is accepted by the runtime loader while the official Spanish schema label is unchanged.

Focused evidence reviewed: `ruff check` passed for the registry locale loader test; `pytest src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py -q -m unit` passed; and the combined registry/locale focused run passed.

Residual verification note: an attempted full real-M130 pydantic JSON roundtrip exposed unrelated strict validation gaps for serialized formula expression tuples and deadline `Period` values, so this step intentionally verifies the loader roundtrip rather than changing registry serialization behavior.

## MODELCLI-007 | LOW | P03 feature-surface gate evidence recorded

Reviewed the P03 feature-surface gate evidence added to the plan. The path-scoped ruff gate passed, the focused pytest gate passed with 18 tests, and the plan-specific vault check passed.

Residual verification note: `vault check all --feature modelo-locales-cli` still reports an unrelated live-censo-calendar-reconciliation exec filename structure error, indicating the feature filter does not fully isolate the structure check in this worktree. No unrelated vault repair was performed.

## MODELCLI-008 | LOW | S18 revision-local dedupe regression found and resolved

Reviewed the seeded scaffold migration. The initial M100 scaffold exposed that all-revision inventory deduped revision-local records without `revision_id`, which made selected-revision translations look stale when the same casilla id appeared in a different revision. This caused M100's three seeded translated leaves per locale to be replaced by placeholders during scaffold.

The manager now includes `revision_id` in revision-local inventory identity, preserving per-revision validity while still deduping modelo-level continuity keys across revisions. The lost M100 seeded leaves were restored via `python -m aeat.locales modelo set`, and a regression test now covers repeated revision-local keys across revisions.

Focused evidence reviewed: M100 scaffold is now idempotent; M100 coverage reports three translated labels and help leaves per seeded non-Spanish locale; `test_registry_locales_parity.py` passes; and the manager regression test passes.

## MODELCLI-009 | LOW | No actionable findings in P04 closeout

Reviewed the P04 rollout artifacts, codified rule, handoff research, seeded scaffold state, and focused verification output. The implementation preserves the separation between eager locale YAML, registry-local modelo TOML, and official Spanish schema labels. The new project rule names the correct authority and cites the ADR/audit sources.

Focused evidence reviewed: `ruff check` passed for touched feature-owned Python files; focused pytest passed with 21 tests; `python -m aeat.locales scaffold --check` and `python -m aeat.locales audit` passed; seeded modelo coverage was recorded for M100, M130, M200, and M303; and `vault plan check` passed.

Residual scope note: the broader translation goal remains incomplete. M100, M200, and M303 have scaffold placeholders that must be replaced by human translations in later campaigns.
