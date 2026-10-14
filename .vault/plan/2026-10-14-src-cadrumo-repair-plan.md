---
tags:
  - '#plan'
  - '#src-cadrumo-repair'
date: '2026-10-14'
tier: L1
related:
  - '[[2026-07-01-import-centralization-adr]]'
  - '[[2026-08-14-test-harness-sanity-successor-adr]]'
  - '[[2026-06-05-test-topology-refactor-adr]]'
  - '[[2026-07-25-bucket-event-payload-bounding-adr]]'
modified: '2026-10-14'
body_schema: body-v2
body_hash: 'sha256:1c98cc6df8b0d857391d77700d84ad81533e1efd50ade42e31c6eacbafe630a5'
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
     Replace src-cadrumo-repair with a kebab-case feature tag, e.g. #foo-bar.
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

# `src-cadrumo-repair` plan

<!-- One-line headline summary plan. -->

## Description

Approved 2026-10-14

Authorization: the user requested continued fixes to src/cadrumo after the source-scoped unit run recorded 50 failures and 41 errors. Repair root causes and necessary ownership references while retaining behavioral coverage and protective gates. Preserve concurrent changes and the completed registry-wire and actor-bound fixes.

Existing accepted import-centralization, test-topology and test-harness-sanity decisions govern S01-S02: canonical defining modules, inert namespaces, user-confirmed TUI ownership inside cadrumo and separate runtime package ownership, narrow fixture ownership and complete fail-closed collection. The accepted bucket-event-payload-bounding decision governs S05. S03-S04 are routine repairs within existing diagnostic and storage contracts; no costly new decision is involved. S06 verifies the integrated result and owner-generated manifests. No legal-data rewrite, taxpayer filing, compatibility shim or broadened test exclusion is authorized.

Baseline evidence is .logs/test-runs/src-cadrumo-unit-20261014-232926-839/unit.log and its summary. Reconcile current source before each repair because another writer has corrected the malformed profile patch header and moved several formerly failing modules. Discover actual current failures rather than reconstructing removed paths.

The user corrected role conflation on 2026-10-15 and authorized continued repairs and mixed Luna max and Sol 6.1 medium agents. TUI remains a tax-product frontend in cadrumo; runtime is separate. A fixture dependency alone does not determine test ownership. Packaging/distribution inclusion, generic runtime authority and tax persistence paths must be assessed separately. Reassess earlier moves against the behavior each test proves before applying further ownership repairs.

## Steps

- [ ] `S01` - Restore source parsing and resolve moved test and fixture ownership without compatibility imports; `src/cadrumo/entrypoints and affected application tests, canonical runtime or harness-owned destination tests where relocation is required`.
- [ ] `S02` - Reconcile complete source inventories, canonical references and operation surface coverage with current ownership; `src/cadrumo core and cross-cutting source audit tests, shared inventory helpers and affected source docstrings`.
- [x] `S03` - Restore consistent diagnostic logging format and side-effect-free import behavior; `src/cadrumo/core/logging.py, diagnostic_log.py and their owning tests`.
- [ ] `S04` - Repair storage setting enrollment, documented environment controls and producer liveness receipts; `src/cadrumo/core storage configuration and taxonomy modules, .env.example and storage policy tests`.
- [ ] `S05` - Prove bounded optional decimal event payloads without weakening payload refusal; `src/cadrumo/application/ledger/actions_common.py and actions_lifecycle.py, domain/buckets/tests/test_payload_value_bounding.py`.
- [ ] `S06` - Run focused and complete product verification, regenerate affected owner-generated contracts and review the integrated repair; `src/cadrumo unit selection, affected canonical destination tests, configured code gates and repair evidence`.
- [x] `S07` - Separate corpus evidence from Python controls and republish verified authority; `dev/registry compiler and receipt tests, dev/quality/tests/test_corpus_provenance.py, src/cadrumo/_data/corpus/tests, src/cadrumo/adapters/outbound/aeat/sede/tests/test_groi_check.py, .authority/authority.current.json`.
- [x] `S08` - Resolve IVA evidence duties against the filing frame and enforce canonical IVA names; `src/cadrumo/application/aggregation/evidence_advisory.py, application/aggregation/tests/test_calculation_revision_iva_evidence_authority.py, application/tests/test_reference_catalogue.py, application/tests/test_apoderado_scopes_payload.py, tests/test_spanish_iva_stem_conformance.py`.

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

S01 implementation was assigned to Sol 6.1 medium ownership_review: restore the TUI to cadrumo.entrypoints.tui, update its callers and launch paths, and restore tax CLI assertion modules using explicit neutral fixture ports while keeping concrete runtime setup/lifetime in host providers. Root owns storage and source-gate files excluded from that assignment.

S02 docstring and canonical symbol-reference repairs were assigned to Sol 6.1 medium doc_reference_repair, including the two doc-reference resolvers and the reported defining-module references. The disjoint 18-row central TUI error-enrollment repair was assigned to Luna max unit_coverage, limited to the existing declaration table and registration callers. Root serializes shared vault records, generated inventories and integration.

Root owns S03 logging, S04 storage scope and shared AST detector, S05 bounded payload and registry evidence behavior. Luna max unit_run owns the complete src/cadrumo unit run and focused checks; Luna max unit_summary owns the configured just check-code aggregate. Sol may prepare the integrated review read-only once a concurrency slot is free. Source writers are frozen during final checks, outputs are separate, and no worker stages or overwrites concurrent edits.

## Verification

Reproduce each owning failure and check success and refusal boundaries. Prove source parsing and clean affected collection after ownership changes. Retain moved tests at canonical owners, preserve markers and fixture lifetime, and remove dangling references rather than adding aliases or ignores. Static inventories remain complete and live, with existing planted-defect controls intact.

Run focused logging, storage, payload and source-audit tests and Ruff checks for changed files. Finish with the exact offline unit selector over src/cadrumo including calculation and revision-registry tests, affected moved tests at canonical destinations and configured code quality gates. Regenerate operation metadata only through its owning CLI and prove fresh currency. Record actual counts and unresolved conditions in the ledger and integrated review. Preserve unrelated index and worktree changes; never stage or commit another writer's unreviewed work.
