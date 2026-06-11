---
tags:
  - '#plan'
  - '#period-grammar-standardisation'
date: '2026-06-11'
tier: L2
related:
  - '[[2026-06-10-cli-operator-surface-adr]]'
  - '[[2026-06-10-ledger-filter-period-adr]]'
  - '[[2026-06-01-registry-period-code-union-cli-boundary-adr]]'
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
     Replace period-grammar-standardisation with a kebab-case feature tag, e.g. #foo-bar.
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

# `period-grammar-standardisation` `period grammar standardisation: AEAT-token-only, year always separate, conflation burn-down` plan

### Phase `P01` - CLI operator-input grammar: AEAT-token-only + separate --year, conversion layer deleted

Ledger --period accepts only canonical AEAT tokens (0A/1T-4T/01-12); year travels on --year; the _aeat_token_to_calendar conversion layer and the 2026-1T hybrid regex are deleted; helpers return a Period built directly from (year, token).


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Delete the _aeat_token_to_calendar conversion layer and the _FILTER_YEAR_QUALIFIED_RE hybrid regex; `make _canonical_period / _filter_canonical_period / _optional_canonical_period build a Period directly from (year, bare-token); `src/aeat/entrypoints/cli/_common.py`.
- [ ] `P01.S02` - Add Period.from_year_and_token(year, token) so the (year, AEAT-token) pair resolves straight to a Period date span with no intermediate calendar string; `src/aeat/application/aggregation/_models.py`.
- [ ] `P01.S03` - Update every ledger CLI caller to the two-argument (token, year=...) period signature so the --filter mini-grammar carries year as a separate clause; `src/aeat/entrypoints/cli/_ledger_list.py, _ledger_review_cli.py, _ledger_read_cli.py, _ledger_import_cli.py, _overview.py`.
- [ ] `P01.S04` - Land the CLI-layer grammar as one explicit-path commit; `confirm CLI import smoke and the ledger period grammar gates pass; `src/aeat/entrypoints/cli`.

### Phase `P02` - Operator refusal regressions and locale messages

Calendar shapes (2026Q1/2026-03/2026) and the 2026-1T hybrid refuse with instructive localised messages naming the AEAT tokens and --year; no dual-notation wording survives.

- [ ] `P02.S05` - Assert calendar shapes (2026Q1/2026-03/2026) and the year-qualified hybrid (2026-1T) refuse at every ledger period site with an instructive message naming the AEAT tokens and --year; `src/aeat/entrypoints/cli/tests/test_ledger_period_grammar.py`.
- [ ] `P02.S06` - Rewrite the period refusal locale messages via the aeat.locales CLI to name the AEAT tokens and the --year argument, removing every both-notations / calendar-shape phrasing; `src/aeat/locales/en.yml`.
- [ ] `P02.S07` - Run the documented-command and educational-docs conformance gates green after the grammar and locale changes; `src/aeat/entrypoints/cli/tests`.

### Phase `P03` - Backend parser de-conflation: domain/period.py + work-period normalisation

Delete the combined-input regexes from parse_canonical_period; remove the round-trip through a combined token in normalize_modelo_work_period; confirm persisted shape is separated (year, registry_token); reconcile the registry parse_modelo_period dialect with the AEAT-token-only mandate.

- [ ] `P03.S08` - Delete the combined-input regexes (_QUARTER_PERIOD_RE, _DASHED_QUARTER_PERIOD_RE, _MONTH_PERIOD_RE, _ANNUAL_PERIOD_RE, _BARE_YEAR_RE) from parse_canonical_period and rewrite the module docstring to drop the combined-token-storage claim; `src/aeat/domain/period.py`.
- [ ] `P03.S09` - Confirm WorkUnit / draft / deadline-window persist a separated (filing_year, registry_token) and add or extend a roundtrip test proving no combined period string is ever persisted; `src/aeat/application/modelo/_work_addressing.py`.
- [ ] `P03.S10` - Remove the round-trip through a combined token in normalize_modelo_work_period; `build (year, registry_token) directly without composing 2026Q1-style intermediates; `src/aeat/application/modelo/_work_addressing.py`.
- [ ] `P03.S11` - Reconcile the registry parse_modelo_period dashed YYYY-Qn dialect with the AEAT-token-only mandate or document why the registry-introspection dialect is out of the operator-period scope; `src/aeat/domain/calculations/registry`.
- [ ] `P03.S12` - Update test_period.py to assert the combined forms now refuse and only the bare-token (with ejercicio), month, 0A and nP tokens are accepted; `src/aeat/domain/tests/test_period.py`.

### Phase `P04` - Docs sweep and final repo-wide conflation gate

Every how-to and reference teaches only --year --period <token>; a repo-wide grep gate confirms zero 2026Q1 / YYYY-nT / period=YYYY usage outside refusal-regression fixtures.

- [ ] `P04.S13` - Sweep every how-to and reference doc to teach only --year --period <token>, removing every 2026Q1 / period=2026-1T / bare-year example; `docs/how-to, docs/reference`.
- [ ] `P04.S14` - Add a final repo-wide grep gate asserting zero 2026Q1 / YYYY-nT / period=YYYY usage in code, tests and docs outside the refusal-regression fixtures; `run the relevant suites green; `src/aeat, docs`.

### Phase `P05` - DEEP LAYER (outstanding): internal combined-token representation migration

Discovery: combined 2026Q1/2026-1T strings are load-bearing BELOW the operator surface — registry deadline-window TOML (period = 2026Q1 across every modelo), the WorkflowEngine period contract (workflow_period_for_work_unit emits 2026Q1/2026-1T, asserted across _workflow_gate, _resume and dozens of tests), and the source docstrings that honestly describe that token. Deleting the domain/period.py combined regexes is BLOCKED until this internal representation migrates to separated (filing_year, registry_token). High blast radius across the registry authoring tree in a shared worktree; tracked as outstanding follow-on, not completed this pass.

- [ ] `P05.S15` - OUTSTANDING — Migrate the registry deadline-window schema and every modelo deadline_windows TOML from a combined period string (period = 2026Q1) to a separated (filing_year, registry_token) shape, through the loader/compiler per aeat-registry-authority-flow; `src/aeat/_data/registry/aeat/modelos/**/deadline_windows, src/aeat/domain/calculations/registry`.
- [ ] `P05.S16` - OUTSTANDING — Replace the WorkflowEngine combined-token contract: have workflow_period_for_work_unit and the resume/gate paths carry (filing_year, registry_token) instead of composing 2026Q1/2026-1T, and migrate every dependent test assertion; `src/aeat/application/modelo/_workflow_gate.py, src/aeat/application/workflow/_resume.py`.
- [ ] `P05.S17` - OUTSTANDING — Once the deep layer is separated, delete the combined-input regexes from parse_canonical_period (unblocks P03.S08) and rewrite the source docstrings that cite 2026Q1 as the canonical token; `src/aeat/domain/period.py, src/aeat/application/workflow/_resume.py, src/aeat/domain/calculations/registry/_queries.py`.

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

<!-- State which Steps, Phases, or Waves can be executed in parallel and
which carry hard ordering. At `L1` and `L2`, parallelism is decided
per-Step or per-Phase. At `L3` and `L4`, Waves are sequenced by
default (one Wave must land before the next can begin); Phases
within a single Wave may be parallelised when they share no hard
interdependency. -->

## Verification

<!-- State the mission success criteria for this plan. Each criterion
should be a verifiable check (test passes, surface conforms,
reviewer signs off) rather than a free-form assertion.

The plan is complete when every Step in every Wave is closed
(`- [x]`). At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

For tier-specific verification cadence, see the convention ADR
authorising this plan via the `related:` frontmatter. -->
