---
tags:
  - '#plan'
  - '#startup-performance'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-10-13-startup-performance-operation-contract-manifest-adr]]'
modified: '2026-10-14'
body_schema: body-v2
body_hash: 'sha256:8af98a37346a21bf918f8b0e4f1e336b329c432edd0150ff6711d8ad07d65006'
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
     Replace startup-performance with a kebab-case feature tag, e.g. #foo-bar.
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

# `startup-performance` plan

Finish the generated operation contract manifest so contract readers stop composing every operation.

## Description

Approved 2026-10-14. Basis: the operator chose to finish the contract-manifest ADR on 2026-10-14 to clear the orphan gate.

The accepted ADR `2026-10-13-startup-performance-operation-contract-manifest-adr` governs every Step. Its manifest model and lazy registry already exist in `src/cadrumo/application/operations/contract_manifest.py` with no consumer, which fails `dev/quality/tests/test_production_scan_surface_has_no_orphans.py`. This plan delivers the rest of its Implementation: the composition group table and shared inputs at the composition seam (S01), the dev generator, the generated `src/cadrumo/_data/operations/contract_manifest.json`, the drift recipe and its tests (S02), the manifest-backed registry for the worker with the module-graph gate (S03), and the runtime and terminal interface consumers (S04). The finding it answers is `import-bloat-worker` in `2026-10-13-startup-performance-audit`. No new costly decision is involved; group granularity follows the ADR's one group per owning operation module.

## Steps

- [x] `S01` - Split the monolithic production registry builder (operation_composition.py:1033-2145) into named composition groups, one per owning operation module, each importing its builders inside its function; move the shared composition inputs into one lazily resolving inputs object and keep build_production_operation_registry composing every group eagerly; `src/cadrumo/entrypoints/operation_composition.py`.
- [x] `S02` - Add the dev generator that composes the eager registry and writes the manifest through OperationContractManifestV1.from_registry (contract_manifest.py:118-133), generate the shipped manifest, add the generate and check recipes beside generate-provider-catalog (justfile:537-546), a drift test in the owning package and a planted-defect test proving the check fails on a stale manifest; `dev/operation_contract_manifest/generate.py, src/cadrumo/_data/operations/contract_manifest.json, justfile, src/cadrumo/entrypoints/tests/test_operation_contract_manifest.py`.
- [x] `S03` - Compose a manifest-backed registry (ManifestOperationRegistry.from_manifest, contract_manifest.py:166-172) over the group table and make the worker's compose_operation_dependencies (operation_composition.py:2148-2262, called from runtime/operation_host.py:183) use it; prove stale-manifest refusal and pin with a module-graph gate that reading every contract imports no operation handler module; `src/cadrumo/entrypoints/operation_composition.py, src/cadrumo/entrypoints/tests/test_operation_contract_manifest.py`.
- [x] `S04` - Switch the runtime registry preparation (runtime/profile_connections.py:370) and the terminal interface registry door (tui/installed_session.py:336-343) to the manifest-backed registry, coordinating the runtime file with its active owner; `src/cadrumo/entrypoints/runtime/profile_connections.py, src/cadrumo/entrypoints/tui/installed_session.py`.

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

     For user-requested coordination across the program and its tracker,
     vaultspec-projectmanager owns that context and assignments; this
     plan remains the home of implementation sequencing.

     ## Wave `W01` - ...
     ## Wave `W02` - ...

     The ## Epic intent block is mandatory at L4 and absent at L1, L2,
     L3. The plan title (the level-one # heading at the top of the
     document) is the Epic title; no separate Epic heading is emitted. -->

## Parallelization

Sequential. S02 needs the group table from S01; S03 needs the generated manifest from S02; S04 needs the manifest-backed registry from S03. S04 edits `src/cadrumo/entrypoints/runtime/profile_connections.py`, which another worker owns; that edit is coordinated through the orchestrator.

## Verification

- `dev/quality/tests/test_production_scan_surface_has_no_orphans.py` passes, so `contract_manifest.py` has a consumer.
- `just check-operation-contract-manifest` passes on the committed manifest and a planted-defect test shows it fails on a stale one.
- The owning-package drift test composes the eager registry and matches the shipped manifest, fingerprints included.
- A stale manifest makes the manifest-backed registry refuse when the group is composed.
- A module-graph gate shows reading every contract through the manifest-backed registry imports no operation handler module.
- Existing composition tests, ruff, `just check-types`, `just check-import-boundaries`, regenerated import-load targets and `dev/quality/tests/test_no_git_cli.py` pass.
