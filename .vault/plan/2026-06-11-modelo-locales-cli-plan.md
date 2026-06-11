---
tags:
  - '#plan'
  - '#modelo-locales-cli'
date: '2026-06-11'
tier: L2
related:
  - '[[2026-06-11-modelo-locales-cli-research]]'
  - '[[2026-06-11-modelo-locales-cli-adr]]'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries the AUTHORISING documents
       (ADR, research, reference, prior plan) for every Step in
       this plan. Steps inherit this chain; per-row reference
       footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace modelo-locales-cli with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar]]'. The related field
     carries the AUTHORISING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add frontmatter fields
     outside the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution-log artifact: <Step Record>.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 and the writer adds the field on first
     edit). The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Selection is by complexity criteria, not container counting.
     Writer never invents containers to qualify a tier. -->

<!-- IDENTIFIERS AND ROW CONTRACT:
     S##, P##, W## are flat, per-document, append-only, immutable.
     Promotion adds containers without renumbering. Gaps are not
     reused.
     Display paths are computed from current grouping:
       Step path:    L1 S##   L2 P##.S##   L3/L4 W##.P##.S##
       Phase heading:        L2 P##       L3/L4 W##.P##
       Wave heading:                      L3/L4 W##
     Row format:
       - [ ] `<display-path>` - imperative-verb action; `path/to/file`.
     Two-state checkboxes only ([ ] open, [x] closed). No per-row
     reference footers; wiki-links and markdown links are forbidden
     in plan body. Authorising documents go in the plan's `related:`
     frontmatter once.
     ASCII spaced hyphens everywhere; em-dash (U+2014) and en-dash
     (U+2013) are forbidden. Step rows within a Phase are
     contiguous. -->

<!-- NO COMPRESSION:
     N self-similar actions = N rows. Never collapse into "for each
     X, do Y" / "across all callers, do Z" / "in every module,
     replace W". The rule applies at every tier including L1. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change rather than hand-editing the row
     grammar. Hand edits are tolerated by the parser but flagged by
     `vaultspec-core vault plan check`; canonical-identifier preservation is
     guaranteed only when the CLI performs the mutation. See the
     CLI ADR (2026-05-06-plan-hardening-adr) for the full
     subcommand surface. -->

# `modelo-locales-cli` `aeat.locales modelo schema localization CLI` plan

### Phase `P01` - registry locale manager contract

Define the registry-local locale manager as the only writer for modelo schema translation TOML while preserving the runtime registry loader contract.


<!-- One-line headline summary plan. -->

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

## Description

Extend the existing aeat.locales governance surface so modelo schema localization is controlled by the same CLI authority as codebase translation strings. The implementation keeps the storage domains separate: core application strings remain in the aeat.locales YAML catalogues, while registry-local modelo schema labels, help text, descriptions, and human-facing schema messages remain under the modelo revision locale TOML files loaded by the registry localization layer.

The CLI becomes the only intended writer for registry-local schema locale files. It must audit drift against canonical registry schemas, scaffold missing keys without replacing translated values, set and remove individual translations, report coverage per modelo and revision, and refuse writes outside the registry data root. The rollout deliberately stops direct schema locale editing and first establishes the manager, command surface, tests, and campaign control points needed for safe multi-language translation work.

## Steps

<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- IMPORTANT: This document must be updated between execution runs to
     track progress. -->

<!-- PHASE BLOCK FORMAT (L2, L3, L4):
     ### Phase `P02` - rewrite the writer-agent contract

     One sentence stating what this Phase delivers.

     - [ ] `P02.S01` - imperative-verb action; `path/to/file`.
     - [ ] `P02.S02` - imperative-verb action; `path/to/file`.

     At L3/L4 the Phase heading uses the ancestor-aware path
     (### Phase `W01.P02` - ...). The intent sentence is mandatory. -->

<!-- WAVE BLOCK FORMAT (L3, L4):
     ## Wave `W01` - language-only convention rollout

     One paragraph stating what this Wave delivers, which downstream
     Wave depends on it, and which authorising documents back it.

     ### Phase `W01.P01` - ...
     ### Phase `W01.P02` - ...

     The Wave intent paragraph is mandatory. -->

<!-- EPIC INTENT BLOCK FORMAT (L4 only):
     ## Epic intent

     One paragraph stating the strategic goal, the external project-
     management association (milestone name, project board identifier,
     roadmap entry), the timeline horizon, and the teams or agents
     involved.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

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
