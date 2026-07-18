---
tags:
  - '#plan'
  - '#user-docs-localization'
date: '2026-07-18'
modified: '2026-07-18'
tier: L3
related:
  - '[[2026-07-18-user-docs-localization-adr]]'
  - '[[2026-07-18-user-docs-localization-research]]'
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
     Replace user-docs-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries the AUTHORIZING documents (ADR, research, reference, prior
     plan) for every Step in this plan; Steps inherit this chain;
     per-row reference footers do not exist.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution Record artifact: <Step Record>.
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
     in plan body. Authorizing documents go in the plan's `related:`
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
     guaranteed only when the CLI performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `user-docs-localization` plan

## Wave `W01` - localization infrastructure and gates

Land the gettext extraction, catalogue tree, per-language build wiring, and the all-languages completeness gates

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - gettext tooling and catalogue scaffold

Dependencies, POT extraction, conf.py language wiring, committed es/ca/hu catalogue tree, justfile targets

- [x] `W01.P01.S01` - Add sphinx-intl and babel to the docs dependency group, refresh the lockfile, and verify both import under uv; `pyproject.toml, uv.lock`.
- [x] `W01.P01.S02` - Implement user-scope gettext POT extraction as a dev.docs build step writing uncommitted templates with gettext_compact disabled; `dev/docs/build.py, dev/docs/i18n.py`.
- [x] `W01.P01.S03` - Wire the Sphinx config to read the build language from an environment switch validated against OutputLanguage, with locale_dirs pointing at the committed catalogue tree and en as default; `docs/conf.py`.
- [x] `W01.P01.S04` - Scaffold the committed es, ca, and hu per-page catalogue trees via sphinx-intl update from the extracted templates; `docs/locales`.
- [x] `W01.P01.S05` - Add justfile targets for gettext extraction, a single-language user-scope build, and the full language-matrix build; `justfile`.

### Phase `W01.P02` - holistic completeness gates

All-languages-present gate, OutputLanguage parity gate, per-language -W build matrix, docs-check integration

- [x] `W01.P02.S06` - Author the all-languages completeness gate asserting every user-scope page catalogue exists with zero untranslated and zero fuzzy entries per target language, failures enumerated by page, language, and counts; `dev/docs/tests/test_docs_localization.py`.
- [x] `W01.P02.S07` - Author the language-set parity gate asserting the docs target languages equal the OutputLanguage members minus the English source exactly; `dev/docs/tests/test_docs_localization.py`.
- [x] `W01.P02.S08` - Extend the build gate with per-language nitpicky warnings-as-errors user-scope builds for es, ca, and hu; `dev/docs/tests/test_docs_build.py`.
- [x] `W01.P02.S09` - Enroll the localization gates in the docs-check lane under the docs marker and confirm the lane runs them; `justfile, dev/docs/tests`.

## Wave `W02` - translation of the user-scope corpus

Translate every user-scope page catalogue into Spanish, Catalan, and Hungarian until the completeness gate is green per language

### Phase `W02.P03` - Spanish translation

Translate all user-scope page catalogues to es with domain context, gate green

- [x] `W02.P03.S10` - Translate the how-to section catalogues to Spanish with full-page domain context; `docs/locales/es`.
- [x] `W02.P03.S11` - Translate the explanation and reference section catalogues to Spanish; `docs/locales/es`.
- [x] `W02.P03.S12` - Translate the index, architecture, top-level, and remaining catalogues to Spanish and drive the Spanish completeness gate green; `docs/locales/es`.

### Phase `W02.P04` - Catalan translation

Translate all user-scope page catalogues to ca with domain context, gate green

- [x] `W02.P04.S13` - Translate the how-to section catalogues to Catalan with full-page domain context; `docs/locales/ca`.
- [x] `W02.P04.S14` - Translate the explanation and reference section catalogues to Catalan; `docs/locales/ca`.
- [x] `W02.P04.S15` - Translate the index, architecture, top-level, and remaining catalogues to Catalan and drive the Catalan completeness gate green; `docs/locales/ca`.

### Phase `W02.P05` - Hungarian translation

Translate all user-scope page catalogues to hu with domain context, gate green

- [x] `W02.P05.S16` - Translate the how-to section catalogues to Hungarian with full-page domain context; `docs/locales/hu`.
- [x] `W02.P05.S17` - Translate the explanation and reference section catalogues to Hungarian; `docs/locales/hu`.
- [x] `W02.P05.S18` - Translate the index, architecture, top-level, and remaining catalogues to Hungarian and drive the Hungarian completeness gate green; `docs/locales/hu`.

## Wave `W03` - deployment, verification, and close

Per-language deploy roots and switcher, full matrix verification, code review, honesty review, campaign close

### Phase `W03.P06` - deploy matrix and campaign close

Per-language site roots and switcher, full verification, reviews, close

- [x] `W03.P06.S19` - Emit per-language site roots from the deploy publisher with a theme language switcher and per-language search index regeneration; `dev/deploy/docs_static_site.py, docs/_templates`.
- [ ] `W03.P06.S20` - Run the full docs-check lane and the complete language matrix at HEAD and record the green evidence; `dev/docs/tests, docs/locales`.
- [ ] `W03.P06.S21` - Dispatch an independent code review over the campaign commits and action every finding; `.vault/audit`.
- [ ] `W03.P06.S22` - Run the fresh-context honesty review against the closure summary and persist the audit before declaring the campaign complete; `.vault/audit`.

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. -->

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
     Wave depends on it, and which authorizing documents back it.

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

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelized when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in the plan is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the authorizing
documents linked in the `related:` frontmatter. -->
