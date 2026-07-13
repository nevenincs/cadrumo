---
tags:
  - '#plan'
  - '#docs-terminology-search'
date: '2026-07-13'
modified: '2026-07-13'
tier: L3
related:
  - '[[2026-07-13-docs-terminology-search-adr]]'
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
     Replace docs-terminology-search with a kebab-case feature tag, e.g. #foo-bar.
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

# `docs-terminology-search` plan

## Wave `W01` - Measure

Ground every later decision in committed measurements: corpus coverage of the shipped relevance mapping, the held-out miss-rate baseline, and the synonym ratification queue state.

<!-- One-line headline summary plan. -->

### Phase `W01.P01` - Coverage, miss-rate, and queue reports

Read-only measurement runs against the resident RAG service producing committed reports.

- [x] `W01.P01.S01` - Generate the coverage report: derive the candidate query surface from calc-grade casilla labels/sections and legal-catalogue provision vocabulary, list every derivable target with no inbound relevance entry, and commit the report; `dev/docs/terminology/, .vault/audit/`.
- [x] `W01.P01.S02` - Run the held-out golden queries through the shipped relevance mapping with the miss-rate machinery and commit the baseline miss-rate report; `dev/docs/terminology/_miss_rate.py, .vault/audit/`.
- [x] `W01.P01.S03` - Inventory the synonym candidate queue (mined, unratified) and commit the inventory with a ratify-or-clear disposition per candidate; `dev/docs/terminology/_synonym_mining.py, .vault/audit/`.

## Wave `W02` - Hook wiring

Wire the repo extractors into the shipped upstream vaultspec-rag preprocess seam, prove per-kind parity against the committed sidecars, then cut over atomically and retire the sidecar tree.

### Phase `W02.P02` - Adapter, rules, parity, cutover

Build the upstream-schema adapter and rule file, gate config validity, prove parity per source kind, then one atomic cutover commit.

- [x] `W02.P02.S04` - Implement the upstream-schema adapter: serialize the repo PreprocessOutput to the upstream PreprocOutput JSON contract behind a python -m entry point, with unit tests against the pinned schema major; `dev/docs/preprocess/`.
- [x] `W02.P02.S05` - Author the preprocess rule file for the four corpus source kinds and add the strict preprocess-check repo gate test; `.vaultragpreprocess.toml, dev/docs/preprocess/tests/`.
- [x] `W02.P02.S06` - Prove per-kind parity: preprocess run-one output text equals the committed sidecar text for a representative source of each kind, asserted by a committed test; `dev/docs/preprocess/tests/`.
- [ ] `W02.P02.S07` - Atomic cutover: retarget the terminology resolver path rules to source-file paths, delete the committed sidecar tree, correct the stale preprocess docstring, and prove an equal-or-superset sweep target set, in one explicit-path commit; `dev/docs/terminology/_resolution.py, dev/docs/preprocess/__init__.py, src/cadrumo/_data/corpus/`.

## Wave `W03` - Widen

Extend the sweep query vocabulary from the coverage report over the bundled legal corpus and casilla registry, re-run the sweep, and land the widened relevance mapping as a reviewed diff.

### Phase `W03.P03` - Vocabulary widening and sweep re-run

Author the widened query vocabulary from the coverage report, reindex, sweep, wrangle, and land the reviewed mapping diff.

- [ ] `W03.P03.S08` - Author the widened query vocabulary from the coverage report through the Handbook enrolment surfaces, keeping the synonym ratification ratchet; `src/cadrumo/_data/terminology/`.
- [ ] `W03.P03.S09` - Run incremental reindex then the widened sweep through the resident service, wrangle through the typed resolution, and land the widened relevance mapping as a reviewed committed diff; `src/cadrumo/_data/terminology/relevance/relevance.json`.

## Wave `W04` - Rung-2 gate

Take the deferred rung-2 decision on the post-widening miss-rate number per ADR D3 and commit the measurement either way.

### Phase `W04.P04` - Gate decision

Re-measure the held-out miss-rate post-widening and apply the ADR D3 numeric gate.

- [ ] `W04.P04.S10` - Re-run the held-out miss-rate over the widened mapping, commit the measurement, and apply the ADR D3 gate: implement rung 2 only above the ten-percent top-five miss line, else record the standing baseline; `dev/docs/terminology/, .vault/audit/`.

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
