---
tags:
  - '#plan'
  - '#honest-all-green'
date: '2026-07-14'
modified: '2026-07-14'
tier: L2
related:
  - '[[2026-07-14-data-output-standardization-audit]]'
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
     Replace honest-all-green with a kebab-case feature tag, e.g. #foo-bar.
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

# `honest-all-green` plan

### Phase `P01` - Renta registry grounding cluster

Root-cause and fix the ~55 registry renta calc-data failures and their ~12 application/modelo cascade, grounded in AEAT/BOE authority, never by editing expectations to match the engine.


<!-- One-line headline summary plan. -->

- [x] `P01.S01` - Diagnose the renta binding-resolution root cause including the profile-has-economic-activity unsupplied binding and classify each failing assertion as engine defect or expectation defect with authority evidence; `src/cadrumo/domain/calculations/registry`.
- [x] `P01.S02` - Fix the renta registry data or engine per the diagnosis with AEAT/BOE grounding and rerun the registry suite sequentially; `registry renta surfaces`.
- [x] `P01.S03` - Verify the application/modelo cascade failures clear downstream and fix any residual independent defects; `src/cadrumo/application/modelo/tests`.

### Phase `P02` - Core hygiene gates

Fix the exception-base-hygiene unregistered roots and the period-combined-string docs findings at root cause.

- [x] `P02.S04` - Register or rehome the FormerProduct exception classes so the exception-base-hygiene gate passes without allowlist mutes; `src/cadrumo/core/errors`.
- [x] `P02.S05` - Resolve the period-combined-string findings in docs at root cause per the gate grammar; `docs period tokens`.

### Phase `P03` - Storage diagnostics and aggregation

Fix the three master-key-rotation secure-object integrity diagnostics failures and the three aggregation source-resolver enrollment and precedence-ladder failures.

- [x] `P03.S06` - Fix the secure-object integrity diagnostics failures after master-key rotation; `src/cadrumo diagnostics integrity`.
- [x] `P03.S07` - Fix the aggregation source-resolver enrollment and precedence-ladder failures; `src/cadrumo/application/aggregation`.

### Phase `P04` - Structural inventory debt

Close the structural-inventory findings honestly: real coverage, real-behavior tests replacing mock and monkeypatch and skip debt, size-budget compliance, marker metadata, mirror-manifest, parser-boundary and extraction-sidecar findings.

- [x] `P04.S08` - Close the structural-inventory findings with real-behavior fixes per finding; `structural inventory surfaces`.

### Phase `P05` - Packaging and parallel robustness

Fix the companion-wheel build errors and make the loader-cache and import-hygiene tests robust under parallel execution without weakening what they prove.

- [x] `P05.S09` - Fix the companion-wheel uv build failures or prove them environment-only with evidence; `packaging`.
- [x] `P05.S10` - Make the loader-cache cross-session proof and the import-hygiene scan robust under parallel execution without weakening them; `parallel-sensitive tests`.
- [x] `P05.S12` - Root-cause the stale registry disk-cache pickles serving pre-correction snapshots under pytest and prove fingerprint invalidation completeness or fix the gap; `src/cadrumo/domain/calculations/registry/_loader.py`.

### Phase `P06` - All-green verification

Full-suite verification runs to a genuinely green state with zero skips and no new baselines or allowlist mutes.

- [ ] `P06.S11` - Run the full suite to genuinely green in parallel and sequential modes and record the closing evidence; `full-tree gates`.

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
