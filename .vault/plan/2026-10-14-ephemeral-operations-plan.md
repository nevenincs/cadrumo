---
tags:
  - '#plan'
  - '#ephemeral-operations'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-08-11-tui-architecture-adr]]'
modified: '2026-10-14'
body_schema: body-v2
body_hash: 'sha256:56d5985d7f02b1ac77569c13cc68cbb889b2ab0b8cf1eee3e1c2c942724eb47d'
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
     Replace ephemeral-operations with a kebab-case feature tag, e.g. #foo-bar.
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

# `ephemeral-operations` plan

Run no-effect reads without durable journaling, as the accepted operation-envelope decision already permits.

## Description

Approved 2026-10-14. Basis: operator directive 2026-10-14 to address every failing test, relayed by the orchestrator; the plan implements accepted `2026-08-11-tui-architecture-adr` D5.

Each page of a profile view is its own durable read operation. Every page takes the profile's one journal root lock about 25 times, writes a journal file and keeps it. Under host load the 60 s whole-view budget (`src/cadrumo/adapters/local_runtime/frontend_profile_view_client.py:183`) expired across four pages, with one journal lock held 7.4 s. The docs-sequence profile-view test under `-n 2` and the packaged TUI overview read both failed this way. Widening the budget is excluded by the startup-performance audit's widened-deadlines finding.

D5 lets an operation declare `EPHEMERAL` durability when lost observation cannot conceal an effect requiring reconciliation. The capability model enforces that declaration (effect `NONE` only, no replay, no conflict scope; `src/cadrumo/application/operations/capabilities.py:98-104`). No operation declares it, though, and the supervisor journals every operation through the same durable ports. This plan routes ephemeral operations to an in-memory store behind those same ports. Supervision, receipts, observation and result release therefore behave as before, and each ephemeral operation exists only for the life of its worker. The terminal receipt stays exact-profile and no-effect, as rule 12 requires. An ephemeral read lost with its process is answered as an unknown operation; D5 accepts that loss for an operation with no effect. Only `user-profile.view` is declared ephemeral here; other reads can follow on the same mechanism.

Decision coverage: `2026-08-11-tui-architecture-adr` D5 governs. No new costly decision is involved.

## Steps

- [x] `S01` - Add an in-memory operation store implementing the journal, event-stream, observation-reader, lease and secure-reference ports (application/operations/persistence/journal.py:387-520) with the durable adapter's create, commit, settlement, replay and observation semantics (adapters/persistence/operations/journal.py:270-384, _journal_validation.validate_advance), keyed per operation so ephemeral leases never contend; `src/cadrumo/adapters/persistence/operations/ephemeral_store.py, its owning tests`.
- [x] `S02` - Route each operation to the in-memory store or the durable journal by its definition's declared durability at create, and by operation id afterwards; keep recovery inventory and idempotency durable-only, and compose the router where the worker builds its supervisor (entrypoints/operation_composition.py:3213-3235, application/operations/composition.py:240); `src/cadrumo/adapters/persistence/operations/durability_router.py, src/cadrumo/entrypoints/operation_composition.py`.
- [x] `S03` - Serve frontend observe and result-page reads of an ephemeral operation through the composed router, which the observation and result services already read (application/operations/composition.py:297-298), and prove that an operation lost with its process answers both as the typed unknown-operation refusal; `src/cadrumo/adapters/persistence/operations/tests/test_durability_router.py`.
- [x] `S04` - Declare user-profile.view EPHEMERAL with effect NONE only, no replay and no conflict scope (capabilities.py:98-104; user_profile/operations.py:156), and regenerate the operation contract manifest; `src/cadrumo/application/user_profile/operations.py, src/cadrumo/_data/operations/contract_manifest.json`.
- [ ] `S05` - Prove it: an ephemeral page read takes zero journal-lock acquisitions and writes no journal file; a durable read is unchanged; a worker ended mid-read leaves no record and no effect and the frontend gets unknown-operation; the docs-sequence profile-view test and the packaged TUI overview read pass under -n 2 with the 60 s view budget unchanged; `src/cadrumo/adapters/persistence/operations/tests, src/cadrumo/entrypoints/runtime/tests, dev/docs/sequences/tests/test_runner.py`.

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

Sequential. S02 routes to the store S01 adds; S03 serves what S02 routes; S04 declares the first ephemeral operation only once S01-S03 can carry it; S05 proves the whole path.

## Verification

- An ephemeral profile-view page acquires the journal root lock zero times and leaves no journal file, counted through the real adapter.
- A durable operation's journal behaviour is unchanged, shown by the existing operations and supervisor suites.
- A worker ended mid-read leaves no record and no effect, and the frontend receives the typed unknown-operation refusal.
- `dev/docs/sequences/tests/test_runner.py::test_sequence_profile_view_uses_fresh_runtime_proof_and_exact_profile` and the packaged TUI overview read pass under `-n 2`, with the 60 s view budget unchanged.
- `just check-types`, `just check-import-boundaries`, the contract-manifest drift check and ruff pass on the touched files.
