---
tags:
  - '#plan'
  - '#modelo-locales-cli'
date: '2026-06-11'
modified: '2026-06-11'
tier: L2
related:
  - '[[2026-06-11-modelo-locales-cli-research]]'
  - '[[2026-06-11-modelo-locales-cli-adr]]'
---








# `modelo-locales-cli` `aeat.locales modelo schema localization CLI` plan

### Phase `P01` - registry locale manager contract

Define the registry-local locale manager as the only writer for modelo schema translation TOML while preserving the runtime registry loader contract.



- [x] `P01.S01` - Define registry-local locale manager models; `src/aeat/locales/_modelo_manager.py`.
- [x] `P01.S02` - Implement contained registry-root resolution; `src/aeat/locales/_modelo_manager.py`.
- [x] `P01.S03` - Implement TOML load and write preservation; `src/aeat/locales/_modelo_manager.py`.
- [x] `P01.S04` - Implement registry-backed schema key inventory; `src/aeat/locales/_modelo_manager.py`.
- [x] `P01.S05` - Expose coverage and drift records; `src/aeat/locales/_modelo_manager.py`.

### Phase `P02` - aeat.locales modelo command surface

Expose the modelo schema-localization workflow under python -m aeat.locales with audit, scaffold, set, remove, and coverage verbs.

- [x] `P02.S06` - Add modelo Typer sub-application; `src/aeat/locales/cli.py`.
- [x] `P02.S07` - Add modelo audit command; `src/aeat/locales/cli.py`.
- [x] `P02.S08` - Add modelo scaffold command and check mode; `src/aeat/locales/cli.py`.
- [x] `P02.S09` - Add modelo set command; `src/aeat/locales/cli.py`.
- [x] `P02.S10` - Add modelo remove command; `src/aeat/locales/cli.py`.
- [x] `P02.S11` - Add modelo coverage command; `src/aeat/locales/cli.py`.
- [x] `P02.S12` - Localize modelo CLI help and diagnostics; `src/aeat/locales`.

### Phase `P03` - verification gates and fixtures

Prove the CLI through real registry-backed behavior, malformed-file refusals, key drift checks, and no direct YAML or schema-label mutation.

- [x] `P03.S13` - Add registry locale manager behavior tests; `src/aeat/locales/tests/test_modelo_manager.py`.
- [x] `P03.S14` - Add modelo CLI integration tests; `src/aeat/locales/tests/test_modelo_cli.py`.
- [x] `P03.S15` - Add catalogue isolation regression tests; `src/aeat/locales/tests/test_modelo_cli.py`.
- [x] `P03.S16` - Add registry-loader roundtrip coverage; `src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py`.
- [x] `P03.S17` - Add feature-surface gate command evidence; `.vault/plan/2026-06-11-modelo-locales-cli-plan.md`.

### Phase `P04` - migration and rollout discipline

Move existing seeded schema translations under CLI control, document campaign usage, and codify the direct-edit prohibition after the CLI lands.

- [x] `P04.S18` - Scaffold seeded modelo locale files through CLI; `src/aeat/_data/registry/aeat/modelos`.
- [x] `P04.S19` - Record modelo localization campaign usage; `.vault/plan/2026-06-11-modelo-locales-cli-plan.md`.
- [x] `P04.S20` - Codify modelo locale CLI authority candidate; `.vaultspec/rules/rules/project/modelo-locales-cli-authority.md`.
- [x] `P04.S21` - Run locale and registry verification gates; `src/aeat/locales`.
- [x] `P04.S22` - Hand off remaining modelo translation campaigns; `.vault/research/2026-06-11-registry-schema-localization-research.md`.
- [x] `P04.S23` - Verify Catalan Modelo 100 2024 translation slice; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/locales/ca`.
- [x] `P04.S24` - Verify English Modelo 100 2024 translation slice; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/locales/en`.
- [x] `P04.S25` - Complete Hungarian Modelo 100 2024 help slice; `src/aeat/_data/registry/aeat/modelos/100/revisions/2024/locales/hu`.

## Description

Extend the existing aeat.locales governance surface so modelo schema localization is controlled by the same CLI authority as codebase translation strings. The implementation keeps the storage domains separate: core application strings remain in the aeat.locales YAML catalogues, while registry-local modelo schema labels, help text, descriptions, and human-facing schema messages remain under the modelo revision locale TOML files loaded by the registry localization layer.

The CLI becomes the only intended writer for registry-local schema locale files. It must audit drift against canonical registry schemas, scaffold missing keys without replacing translated values, set and remove individual translations, report coverage per modelo and revision, and refuse writes outside the registry data root. The rollout deliberately stops direct schema locale editing and first establishes the manager, command surface, tests, and campaign control points needed for safe multi-language translation work.

## Steps







## Parallelization

Phase P01 must land before P02 because CLI commands depend on the registry locale manager contract. P03 can begin once the specific manager and CLI entry points it tests exist, but the full gate evidence waits for P01 and P02 to settle. P04 is intentionally last: migration, codification, and campaign handoff must use the implemented CLI rather than direct file edits.

Within P01, S01 and S02 are prerequisites for the remaining manager work. Within P02, S06 comes before the command-specific rows. Within P03, manager tests and CLI tests can be written in parallel after their corresponding surfaces exist. Translation campaign work must not resume until the scaffold, set, audit, and coverage commands have passing tests.

## Verification

Success requires the modelo subcommands to operate through python -m aeat.locales, with coverage and drift output that can drive per-modelo translation campaigns. Scaffold and set operations must preserve translated leaves unless the user explicitly targets a key, and must not mutate the core YAML catalogues except for normal CLI help and diagnostic strings introduced by the command surface.

The plan is complete when all 22 steps are closed, vaultspec-core vault plan check passes, the focused aeat.locales tests pass, registry locale loader roundtrip tests pass, and the feature-surface gate records the exact ruff and pytest commands used for the changed paths.

## Feature-surface gate evidence

Recorded on 2026-06-11 for P03.S17.

- Ruff: `uv run --no-sync ruff check src/aeat/locales/__init__.py src/aeat/locales/_modelo_manager.py src/aeat/locales/cli.py src/aeat/locales/tests/test_modelo_manager.py src/aeat/locales/tests/test_modelo_cli.py src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py` passed with `All checks passed!`.
- Pytest: `uv run --no-sync pytest src/aeat/locales/tests/test_modelo_manager.py src/aeat/locales/tests/test_modelo_cli.py src/aeat/domain/calculations/registry/tests/test_registry_locales_loader.py -q -m "unit or integration"` passed with 18 tests passed.
- Vault plan check: `uv run --no-sync python -m vaultspec_core --target . vault plan check .vault/plan/2026-06-11-modelo-locales-cli-plan.md` passed.
- Vault feature check: `uv run --no-sync python -m vaultspec_core --target . vault check all --feature modelo-locales-cli` did not pass because the checker still reported unrelated `.vault/exec/2026-06-05-live-censo-calendar-reconciliation/2026-06-11-live-censo-calendar-reconciliation-W03-P03-S06-S07-hardening.md` filename structure drift. The same run also warned that this plan still contains template annotation comments and that no `modelo-locales-cli` feature index exists.

## Modelo localization campaign usage

Recorded on 2026-06-11 for P04.S19.

Campaign agents must use the modelo locale CLI for schema-local translation work:

- Inspect coverage with `uv run --no-sync python -m aeat.locales modelo coverage <locale> <modelo> <revision>`.
- Align selected seeded files with `uv run --no-sync python -m aeat.locales modelo scaffold <locale> <modelo> <revision>`.
- Set one translated leaf with `uv run --no-sync python -m aeat.locales modelo set <locale> <modelo> <revision> labels|help <key> <value>`.
- Remove one translated leaf with `uv run --no-sync python -m aeat.locales modelo remove <locale> <modelo> <revision> labels|help <key>`.
- Treat values equal to the schema key as untranslated scaffold placeholders, not completed translation.
- Do not hand-edit registry-local `locales/*.toml` files except for emergency repair of the CLI implementation itself.
- Do not create Spanish schema-local TOML as routine campaign work. Spanish schema labels remain the official fallback embedded in the legally grounded schema.

Current seeded coverage after P04.S18:

- M100 2024: `ca`, `en`, and `hu` each report `labels=3/2068 help=3/2068` after preserving the existing translated seeded leaves and scaffolding placeholders for the rest.
- M130 2019-y-siguientes: `ca`, `en`, and `hu` each report `labels=20/20 help=20/20`.
- M200 2024-y-siguientes: `ca`, `en`, and `hu` each report `labels=2/3232 help=2/3232`.
- M303 2023-y-siguientes: `ca`, `en`, and `hu` each report `labels=2/120 help=2/120`.

Next translation campaigns should prioritize replacing placeholders in the scaffolded M100, M200, and M303 files. New modelo/revision enrollment should begin with `coverage`, then `scaffold`, then a sequence of `set` calls for translated leaves, followed by `coverage` again to record progress.
