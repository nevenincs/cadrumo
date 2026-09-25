---
tags:
  - '#plan'
  - '#filing-capability'
date: '2026-09-25'
tier: L2
related:
  - '[[2026-06-04-fichero-boe-export-layouts-adr]]'
modified: '2026-09-25'
body_schema: body-v2
body_hash: 'sha256:92f1e7c34376e48b4f9ad4fee6dae1cb2f95ece3f7f0af08a418b44348af651b'
---

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the
       related: field above.
     - The related: field carries governing ADRs, if any.
       Steps inherit their evidence transitively. Direct supporting
       evidence links are optional; per-row footers do not exist.
     - NEVER use [[wiki-links]] or markdown links in the
       document body. -->

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #plan) and one feature tag.
     Replace filing-capability with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     tier is mandatory for new plans. Allowed: L1, L2, L3, L4.
     L1 = Steps only. L2 = Phases above Steps. L3 = Waves above
     Phases above Steps. L4 = Epic above Waves above Phases above
     Steps; PM association required. Pre-existing plans without this
     field default to L2.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'. The related field
     carries governing ADRs; Steps inherit their evidence transitively.
     Direct supporting evidence links are optional. A decision-free plan
     records its coverage assessment in the Description.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->


<!-- HIERARCHY AND TIERS:
     Epic > Wave > Phase > Step. Step is the canonical leaf-row
     noun. Execution artifact: the plan's ledger.
     Tier is declared in frontmatter as tier: L1/L2/L3/L4
     (mandatory for new plans; pre-existing plans without the
     field default to L2 until `vaultspec-core vault check all --fix` adds it).
     The tier selects containers:
       L1 = Steps only.
       L2 = Phases above Steps.
       L3 = Waves above Phases above Steps.
       L4 = Epic above Waves above Phases above Steps; MUST declare
            a project-management association in the Epic intent
            block prose.
     Select the smallest hierarchy that clarifies coordination:
       L1 = a flat sequence of cohesive revisions, including broad changes.
       L2 = Phases clarify groups of Steps.
       L3 = Waves clarify dependencies between groups of Phases.
       L4 = an Epic coordinates a program with external tracking.
     Duration, file count, package count, or short parallel work alone
     never requires a higher tier.
     Between two tiers take the smaller and promote later.
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

<!-- COHESIVE GRANULARITY:
     One Step is one cohesive, verifiable commit. Coordinated repeated edits
     may share a row when scope and verification are explicit. Separate
     unrelated outcomes. Name the bounded files or area, expected creations,
     and intended result; avoid unspecified catch-all work. -->

<!-- VAULTSPEC-CORE VAULT PLAN CLI:
     The `vaultspec-core vault plan` CLI is the canonical surface for
     structural manipulation of this plan document. Writers and
     executors MUST use `vaultspec-core vault plan step add/insert/move/
     remove/check/uncheck/toggle/edit`,
     `vaultspec-core vault plan phase add/move/remove/edit`,
     `vaultspec-core vault plan wave add/move/remove/edit`,
     `vaultspec-core vault plan epic intent`, and
     `vaultspec-core vault plan tier promote/demote` for every
     identifier-affecting change; the `plan_edit` and `plan_progress`
     MCP tools reach the Step verbs only, and the above-Step verbs run
     through the CLI. Hand edits are forbidden and
     flagged by `vaultspec-core vault plan check`; canonical-identifier
     preservation is guaranteed only when a verb performs the mutation. Run
     `vaultspec-core vault plan --help` for the full subcommand
     surface. -->

# `filing-capability` plan

Close every authorable row of the filing capability worklist so each registry revision can emit its filing artifact.

## Description

Approved 2026-09-25. The operator answered the worklist decision with "filing yes": for each revision whose official record design is bundled, this application may claim filing authority, which the worklist gate requires beside the layout itself.

The gate is `dev/registry/tests/test_filing_capability_worklist.py::test_every_registry_revision_can_produce_a_filing_artifact`. On 2026-09-25 it listed 50 revisions across 25 modelos; 48 are authorable gaps and are the Steps below, one per revision, grouped by modelo. Two rows are terminal and stay out of scope because approval cannot supply what they lack: 136/2026 has no published authority to ground a layout on, and 036/2025-02-03-y-siguientes is filed on the AEAT sede and produces no fichero. They remain on the worklist until their own reconsideration conditions change.

Decision coverage: the fichero-BOE export layout decision governs how a layout is authored and emitted; no new costly decision is involved. The per-revision authority judgement is the operator approval above, recorded here.

A Step closes only when its revision has an export layout derived from its official record design through the canonical authoring path, its authority grade is promoted to filing with the record design as evidence, the registry gates (validity, runtime load, integrity) pass, the published authority is republished, and the revision no longer appears on the worklist. A revision whose record design is missing, ambiguous or self-contradicting is not forced: its Step records the evidence and it stays listed.

## Steps

### Phase `P01` - Modelo 036 filing capability

Author the export layouts Modelo 036's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.


<!-- The plan's tier (declared in frontmatter as `tier: L1`, `L2`, `L3`, or
`L4`) determines the structure under this section:

- `L1`: a flat list of Step rows (no Phase, Wave, or Epic).
- `L2`: one or more `### Phase` blocks each containing Step rows.
- `L3`: one or more `## Wave` blocks each containing Phase blocks.
- `L4`: a `## Epic intent` block, followed by Wave blocks. -->

<!-- Replace this scaffold with the tier-appropriate structure for your plan.
Format examples for each block type are embedded below as commented
templates. -->

<!-- Progress is recorded through the plan verbs (`plan_progress`,
     `vaultspec-core vault plan step check`), one Step at a time. -->

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

- [ ] `P01.S01` - Author and verify the 036/2023-hasta-2025-02-02 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/036/revisions/2023-hasta-2025-02-02/`.

### Phase `P02` - Modelo 038 filing capability

Author the export layouts Modelo 038's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P02.S02` - Author and verify the 038/2024-desde-06 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/038/revisions/2024-desde-06/`.
- [ ] `P02.S03` - Author and verify the 038/2025-y-siguientes export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/038/revisions/2025-y-siguientes/`.

### Phase `P03` - Modelo 136 filing capability

Author the export layouts Modelo 136's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P03.S04` - Author and verify the 136/2022-2025 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/136/revisions/2022-2025/`.

### Phase `P04` - Modelo 165 filing capability

Author the export layouts Modelo 165's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P04.S05` - Author and verify the 165/2013-2015 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/165/revisions/2013-2015/`.
- [ ] `P04.S06` - Author and verify the 165/2023-2025 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/165/revisions/2023-2025/`.

### Phase `P05` - Modelo 182 filing capability

Author the export layouts Modelo 182's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P05.S07` - Author and verify the 182/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2024/`.
- [ ] `P05.S08` - Author and verify the 182/2025 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/182/revisions/2025/`.

### Phase `P06` - Modelo 184 filing capability

Author the export layouts Modelo 184's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P06.S09` - Author and verify the 184/2015 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2015/`.
- [ ] `P06.S10` - Author and verify the 184/2016-2018 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2016-2018/`.
- [ ] `P06.S11` - Author and verify the 184/2019-2021 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2019-2021/`.
- [ ] `P06.S12` - Author and verify the 184/2022 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/184/revisions/2022/`.

### Phase `P07` - Modelo 185 filing capability

Author the export layouts Modelo 185's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P07.S13` - Author and verify the 185/2003-2025 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/185/revisions/2003-2025/`.

### Phase `P08` - Modelo 187 filing capability

Author the export layouts Modelo 187's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P08.S14` - Author and verify the 187/2022-y-siguientes export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/187/revisions/2022-y-siguientes/`.

### Phase `P09` - Modelo 188 filing capability

Author the export layouts Modelo 188's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P09.S15` - Author and verify the 188/2022 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2022/`.
- [ ] `P09.S16` - Author and verify the 188/2023-y-siguientes export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/188/revisions/2023-y-siguientes/`.

### Phase `P10` - Modelo 189 filing capability

Author the export layouts Modelo 189's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P10.S17` - Author and verify the 189/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/189/revisions/2023/`.
- [ ] `P10.S18` - Author and verify the 189/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/189/revisions/2024/`.

### Phase `P11` - Modelo 190 filing capability

Author the export layouts Modelo 190's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P11.S19` - Author and verify the 190/2022 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2022/`.
- [ ] `P11.S20` - Author and verify the 190/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/190/revisions/2023/`.

### Phase `P12` - Modelo 193 filing capability

Author the export layouts Modelo 193's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P12.S21` - Author and verify the 193/2022 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2022/`.
- [ ] `P12.S22` - Author and verify the 193/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/193/revisions/2023/`.

### Phase `P13` - Modelo 194 filing capability

Author the export layouts Modelo 194's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P13.S23` - Author and verify the 194/2019 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/194/revisions/2019/`.
- [ ] `P13.S24` - Author and verify the 194/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/194/revisions/2023/`.
- [ ] `P13.S25` - Author and verify the 194/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/194/revisions/2024/`.

### Phase `P14` - Modelo 200 filing capability

Author the export layouts Modelo 200's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P14.S26` - Author and verify the 200/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/`.

### Phase `P15` - Modelo 220 filing capability

Author the export layouts Modelo 220's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P15.S27` - Author and verify the 220/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2024/`.
- [ ] `P15.S28` - Author and verify the 220/2025 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/220/revisions/2025/`.

### Phase `P16` - Modelo 222 filing capability

Author the export layouts Modelo 222's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P16.S29` - Author and verify the 222/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/222/revisions/2023/`.
- [ ] `P16.S30` - Author and verify the 222/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/222/revisions/2024/`.

### Phase `P17` - Modelo 280 filing capability

Author the export layouts Modelo 280's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P17.S31` - Author and verify the 280/2022-2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/280/revisions/2022-2024/`.

### Phase `P18` - Modelo 296 filing capability

Author the export layouts Modelo 296's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P18.S32` - Author and verify the 296/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/296/revisions/2023/`.

### Phase `P19` - Modelo 308 filing capability

Author the export layouts Modelo 308's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P19.S33` - Author and verify the 308/2009-2011-junio export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/308/revisions/2009-2011-junio/`.
- [ ] `P19.S34` - Author and verify the 308/2011-julio-2015 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/308/revisions/2011-julio-2015/`.
- [ ] `P19.S35` - Author and verify the 308/2016-2018 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/308/revisions/2016-2018/`.

### Phase `P20` - Modelo 345 filing capability

Author the export layouts Modelo 345's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P20.S36` - Author and verify the 345/2022 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/345/revisions/2022/`.
- [ ] `P20.S37` - Author and verify the 345/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/345/revisions/2023/`.
- [ ] `P20.S38` - Author and verify the 345/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/345/revisions/2024/`.

### Phase `P21` - Modelo 390 filing capability

Author the export layouts Modelo 390's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P21.S39` - Author and verify the 390/2021 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/390/revisions/2021/`.

### Phase `P22` - Modelo 576 filing capability

Author the export layouts Modelo 576's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P22.S40` - Author and verify the 576/2007 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/576/revisions/2007/`.

### Phase `P23` - Modelo 721 filing capability

Author the export layouts Modelo 721's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P23.S41` - Author and verify the 721/2023 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/721/revisions/2023/`.
- [ ] `P23.S42` - Author and verify the 721/2024 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/721/revisions/2024/`.

### Phase `P24` - Modelo 763 filing capability

Author the export layouts Modelo 763's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P24.S43` - Author and verify the 763/2012-2014 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2012-2014/`.
- [ ] `P24.S44` - Author and verify the 763/2015-2017 export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2015-2017/`.
- [ ] `P24.S45` - Author and verify the 763/2018-1t-3t export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2018-1t-3t/`.
- [ ] `P24.S46` - Author and verify the 763/2018-4t export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2018-4t/`.
- [ ] `P24.S47` - Author and verify the 763/2019-y-siguientes export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/763/revisions/2019-y-siguientes/`.

### Phase `P25` - Modelo 840 filing capability

Author the export layouts Modelo 840's official record designs define and promote each revision to filing grade under the operator's approval, so every listed revision leaves the worklist.

- [ ] `P25.S48` - Author and verify the 840/2003-y-siguientes export layout from its record design and promote the revision to filing grade; `src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/`.

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

The plan is complete when every Step is closed (`- [x]`) and the final
cohesive review passes. At `L4`, the Epic-completion check additionally requires
the declared project-management association to report the Epic
complete.

Review follows the vaultspec system section. L1 has no Phase close;
coincident plan-close and handoff gates share one integrated review. -->
