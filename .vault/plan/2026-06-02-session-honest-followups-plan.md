---
tags:
  - '#plan'
  - '#session-honest-followups'
date: '2026-06-02'
tier: L2
related:
  - '[[2026-06-02-suite-redgreen-2026-06-02-plan]]'
  - '[[2026-06-02-m303-parser-engine-totals-impedance-adr]]'
  - '[[2026-06-01-m303-form-vs-semantic-casilla-dual-keying-adr]]'
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
     Replace session-honest-followups with a kebab-case feature tag, e.g. #foo-bar.
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

# `session-honest-followups` `Session-honest follow-ups and substrate hardening` plan

### Phase `P01` - Architectural blockers untracked

Capture and drive M303 chain, entrypoints cluster, M721 887 grounding to closure via teammate dispatch


<!-- One-line headline summary plan. -->

- [x] `P01.S01` - Verify M303 Route A landing closes 47 verification_chain reds; `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.
- [x] `P01.S02` - Dispatch peer adjudication on M151/M714/M721 stub-refusal trio post Phase-A registry landing; `src/aeat/entrypoints/cli/test_modelo_{151,714,721}_stub_refusal.py`.
- [x] `P01.S03` - Fix wizard-catalogue startup ordering for cli_runner.invoke path; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P01.S04` - Adjudicate bare-invocation bucket-session gate per ADR; `src/aeat/entrypoints/cli/test_profile_output_language.py`.
- [x] `P01.S05` - Ground orden-hfp-887-2023:art-3 via BOE OR update test_explain_721 assertion; `src/aeat/entrypoints/cli/test_overview_explain_verb.py`.

### Phase `P02` - Today fragile fixes regression risk

Re-verify the 9 commits landed this session for sibling regressions and silent coverage shrinkage

- [x] `P02.S06` - Verify M210 Phase-1 consumer modules exist; `check aeat.application.review et al; `src/aeat/_data/registry/aeat/modelos/210/revisions/2025/application_links/0001-application_links.toml`.
- [x] `P02.S07` - Author source_citations for modelo-200-base-imponible and -previa formulas; `src/aeat/_data/registry/aeat/modelos/200/revisions/2024-y-siguientes/records/formulas.toml`.
- [x] `P02.S08` - Confirm M151 WT-only fix landed in peer M151 commit; `re-stage when peer dir tracked; `src/aeat/_data/registry/aeat/modelos/151/revisions/2015-y-siguientes/workbook_parity_refs/0001-workbook_parity_refs.toml`.
- [x] `P02.S09` - Add non-zero BIN coverage test for M200 base-determination chain; `src/aeat/application/filing/test_decimal_inputs_routing.py`.
- [x] `P02.S10` - Add non-zero BL-negativa coverage test for M100 renta taxation_comparison; `src/aeat/application/modelo/test_taxation_comparison.py`.
- [x] `P02.S11` - Re-strengthen attachment_id persistence proof; `src/aeat/adapters/persistence/storage/test_attachment_store_roundtrip.py`.
- [x] `P02.S12` - Verify ErrorCode ModeloIvaWalletReconciliationBlocked locale strings against regulatory tone; `src/aeat/locales`.
- [x] `P02.S13` - Verify default_suggestion aeat app ledger iva wallet view CLI verb exists; `src/aeat/entrypoints/cli`.

### Phase `P03` - Substrate and infrastructure health

xdist collection skew, bash environment, synthetic-PDF generator gap, encrypted-column round-trip, wizard-catalogue startup ordering

- [x] `P03.S14` - Diagnose xdist collection-skew root cause and add deterministic test discovery gate; `pyproject.toml`.
- [x] `P03.S15` - Restore bash interpreter or formalize PowerShell mandate for this worktree; `CLAUDE.md`.
- [x] `P03.S16` - Document robust background-pytest capture pattern; `replace Tee Select-Object -Last 5 antipattern; `.claude/rules`.
- [x] `P03.S17` - Extend synthetic-PDF generator with M303 primitive form-field support; `src/aeat/tests/fixtures/justificantes/_generate.py`.
- [x] `P03.S18` - Clarify EncryptedString str-vs-bytes round-trip on object_key column; `src/aeat/adapters/persistence/storage/sql/_orm.py`.
- [x] `P03.S19` - Fix wizard-catalogue startup ordering for cli_runner.invoke path; `src/aeat/entrypoints/cli/__init__.py`.
- [x] `P03.S20` - Add structural gate linking _COMPUTED_CASILLAS_M303 to actual M303 formula registry; `src/aeat/adapters/inbound/declaracion/test_verification_chain.py`.
- [x] `P03.S21` - Audit plan exec-record Step-ID renumber-after-tier-promote drift across all 20 plans; `.vault/plan`.

### Phase `P04` - Deferred from existing plans

P04.S10 / P04.S12 / P07.S25 / M390 autoconsumo plus plan triage parents 143-147

- [x] `P04.S22` - Drive P04.S10 catalogue verification to closure; `src/aeat/domain/calculations/registry/test_catalogue_verification.py`.
- [x] `P04.S23` - Drive P04.S12 modelo parity coverage to closure; `src/aeat/domain/calculations/registry`.
- [x] `P04.S24` - Drive P07.S25 M303 golden SHA recompute with DR ground truth; `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py`.
- [x] `P04.S25` - Drive task #154 M390 autoconsumo asymmetry closure or formal defer; `.vault/audit`.
- [x] `P04.S26` - Drive #143 plan-triage parent and child triage tasks #144-#147 to resolution; `.vault/plan`.

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
