---
tags:
  - '#plan'
  - '#modelo-200-semantic-crosswalk'
date: '2026-09-02'
tier: L3
related:
  - '[[2026-08-08-aeat-design-relayout-boundary-modelo-200-partition-adr]]'
  - '[[2026-09-02-modelo-200-semantic-crosswalk-research]]'
  - '[[2026-08-10-aeat-export-fragment-generator-authority-adr]]'
modified: '2026-09-02'
body_schema: body-v2
body_hash: 'sha256:2cc442e02cbb055c837689ab832a7e854695ec4259f00bb791b577f0763471aa'
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
     Replace modelo-200-semantic-crosswalk with a kebab-case feature tag, e.g. #foo-bar.
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

# `modelo-200-semantic-crosswalk` plan

<!-- One-line headline summary plan. -->

## Description

<!-- Briefly describe the proposed work. Reference `{adr}`s,
`{research}`, `{reference}`. Supporting documentation must be read prior to
writing the plan document. A plan may execute one ADR or a cluster; when
several feed it, state here which Wave or Phase each ADR governs. -->

## Steps

## Wave `W01` - establish the immutable 2024 reconciliation boundary

Freeze the exact pinned 2024 design as the sole target identity authority and record the full population before mutation.

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

### Phase `W01.P01` - freeze the declaration and source evidence census

Separate current declarations from semantic adjudications and bind every result to the exact 2024 source SHA.

- [ ] `W01.P01.S01` - Extend the deterministic census across 3,173 current declarations, 156 reconstructed candidates, 3,158 exact rebinds, 15 unmapped declarations, 185 identity mismatches, and legal gaps; `dev/registry/analysis/m200_2024_full_reconciliation.py`.
- [ ] `W01.P01.S02` - Prove census completeness, determinism, source-SHA binding, contamination visibility, and partition-drift refusal; `dev/registry/tests/test_m200_2024_full_reconciliation.py`.

### Phase `W01.P02` - remove non-authoritative historic semantic reuse

Prevent historical fragments, adjacent designs, and description similarity from becoming 2024 semantic or legal authority.

- [ ] `W01.P02.S03` - Retire historic-payload restoration as authority-producing behavior while retaining proposal-only diagnostics; `dev/registry/analysis/m200_2024_restoration_candidates.py`.
- [ ] `W01.P02.S04` - Detect target-description, semantic-role, legal-reference, and source-SHA mutations at the historic-restoration boundary; `dev/registry/tests/test_m200_2024_restoration_candidates.py`.

## Wave `W02` - derive physical reconciliation from the pinned design

Build deterministic tooling that changes only facts proven by the 2024 design and never infers semantic ownership from siblings.

### Phase `W02.P03` - program the exact source-reference rebind

Derive exact 2024-anchor rebinds while preserving every non-source authority fact byte-for-byte.

- [ ] `W02.P03.S05` - Implement the source-SHA-bound planner and canonical TOML mutation surface for 3,158 exact declaration rebinds; `dev/registry/analysis/m200_2024_full_reconciliation.py`.
- [ ] `W02.P03.S06` - Reject missing anchors, source drift, duplicate output, altered non-source payloads, and partial rebind application; `dev/registry/tests/test_m200_2024_full_reconciliation.py`.

### Phase `W02.P04` - classify mismatched and orphan target identities

Assign identity mismatches and source-map orphans to closed target-first dispositions without sibling fallback.

- [ ] `W02.P04.S07` - Implement target-anchor identity classification and explicit dispositions for every unmapped declaration; `dev/registry/analysis/m200_semantic_casilla_candidates.py`.
- [ ] `W02.P04.S08` - Prove identity ambiguity, segment qualification, non-casilla ownership, and orphan omission fail closed; `dev/registry/tests/test_m200_semantic_casilla_candidates.py`.

## Wave `W03` - adjudicate 2024 meaning and legal authority

Turn target-year evidence into reviewed semantic-map and legal authority after the identity worklist is closed.

### Phase `W03.P05` - close the legal catalogue worklist

Resolve legal-catalogue gaps against applicable 2024 authority before semantic rows become authoritative.

- [ ] `W03.P05.S09` - Derive the source-bound legal worklist with applicability-window and unresolved-reference evidence; `dev/registry/analysis/m200_2024_full_reconciliation.py`.
- [ ] `W03.P05.S10` - Author reviewed 2024-applicable legal catalogue entries and anchors for the closed worklist; `src/cadrumo/_data/registry/aeat/legal/`.
- [ ] `W03.P05.S11` - Enforce legal resolution, target-window coverage, anchor reachability, and rejection of later-year substitution; `dev/registry/tests/test_m200_2024_full_reconciliation.py`.

### Phase `W03.P06` - record closed semantic adjudication families

Resolve every candidate semantic through explicit reviewed target-year families and reviewer provenance.

- [ ] `W03.P06.S12` - Compile reviewed target-year authority for exact same-2024 template repairs; `dev/registry/mappings/modelo_200/2024/`.
- [ ] `W03.P06.S13` - Adjudicate uniquely proposed cross-revision candidates against official 2024 evidence; `dev/registry/mappings/modelo_200/2024/`.
- [ ] `W03.P06.S14` - Adjudicate conflicting cross-revision candidate sets against official 2024 evidence; `dev/registry/mappings/modelo_200/2024/`.
- [ ] `W03.P06.S15` - Author target-year authority for target fields with no applicable cross-revision candidate; `dev/registry/mappings/modelo_200/2024/`.

## Wave `W04` - materialize complete target authority and generate privately

Integrate reviewed declaration, legal, map, and render authority and regenerate into a fresh temporary root.

### Phase `W04.P07` - enforce complete semantic-map admission

Reject unresolved proposals, stale sources, incomplete legal grounding, and reciprocal export-reference drift.

- [ ] `W04.P07.S16` - Require reviewed target-year adjudication provenance and reject proposal-only semantic entries; `dev/registry/pipeline/_semantic_map_validation.py`.
- [ ] `W04.P07.S17` - Preserve source identity, parser-map bijection, qualified casilla ownership, and declaration admission in the semantic join; `dev/registry/pipeline/_semantic_map_join.py`.
- [ ] `W04.P07.S18` - Add positive and mutation coverage for adjudication, legal applicability, identity mismatch, and unresolved-anchor refusal; `dev/registry/tests/test_semantic_map_validation.py`.

### Phase `W04.P08` - generate and validate the private 2024 export tree

Render from the pinned design and reviewed authority into a temporary root without hand-authored coordinates.

- [ ] `W04.P08.S19` - Bind Modelo 200 2024 bootstrap generation to the exact target design and digest; `dev/registry/pipeline/generated_export_bootstrap_targets.toml`.
- [ ] `W04.P08.S20` - Generate the complete export package, provenance manifest, and reciprocal references through the canonical pipeline; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/export/`.
- [ ] `W04.P08.S21` - Prove temporary-root regeneration, whole-tree equality, provenance equality, and source-drift refusal; `dev/registry/tests/test_generated_export_trees.py`.

## Wave `W05` - publish filing-grade authority and independently verify it

Publish and promote only after the complete generated package passes the real fail-closed authority path.

### Phase `W05.P09` - publish only the validated generated package

Exercise canonical check and publish under established locks, receipts, and destination-identity contracts.

- [ ] `W05.P09.S22` - Exercise Modelo 200 2024 check and publish through the canonical pipeline authority path; `dev/registry/pipeline/cli.py`.
- [ ] `W05.P09.S23` - Reject target mutation, stale receipts, partial trees, reference asymmetry, and post-validation drift; `dev/registry/tests/test_generated_tree_publication.py`.
- [ ] `W05.P09.S24` - Promote the 2024 revision to filing grade only after committed generated-package validation; `src/cadrumo/_data/registry/aeat/modelos/200/revisions/2024/revision.toml`.

### Phase `W05.P10` - prove end-to-end registry and filing readiness

Verify loaded authority, generated export bytes, revision selection, focused gates, and independent review.

- [ ] `W05.P10.S25` - Prove the 2024 filing context selects filing-grade Modelo 200 through ValidatedRegistryAuthority; `src/cadrumo/domain/calculations/registry/tests/test_modelo_200_ejercicio_2024_resolves.py`.
- [ ] `W05.P10.S26` - Run focused crosswalk, generator, publication, loader, export-tree, and authority suites with separately attributed full-suite results; `dev/registry/tests/`.
- [ ] `W05.P10.S27` - Produce an independent formal review of semantic authority, legal grounding, generated publication, promotion, and evidence; `.vault/audit/`.

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
