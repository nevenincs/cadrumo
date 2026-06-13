---
tags:
  - '#plan'
  - '#first-filer-attestation'
date: '2026-06-13'
tier: L2
related:
  - '[[2026-06-13-first-filer-attestation-adr]]'
  - '[[2026-06-12-first-filer-attestation-research]]'
  - '[[2026-06-05-cross-period-filing-clean-state-adr]]'
  - '[[2026-06-05-cross-period-calculation-guards-adr]]'
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
     Replace first-filer-attestation with a kebab-case feature tag, e.g. #foo-bar.
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

# `first-filer-attestation` `operator-declared activity-start scoping of cross-period requirements` plan

### Phase `P01` - Typed no-prior-obligation provenance vocabulary

Introduce the typed no-prior-obligation evidence facet on CrossPeriodDependencyEvidence carrying the activity-start date that scoped a requirement out, the provenance kind (operator-declared vs censo-corroborated), and an optional censo snapshot id, plus the application-layer scoping predicate over a declared activity-start date. The registry stays pure; the facet is the auditable, non-silent record the accepted ADR requires.


<!-- One-line headline summary plan. -->

- [ ] `P01.S01` - Add the NO_PRIOR_OBLIGATION_PRE_ACTIVITY provenance facet kind enum to the cross-period clean-state vocabulary while gate-proving it never enters _OFFICIAL_SOURCE_KINDS; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [ ] `P01.S02` - Add the typed NoPriorObligationProvenance model carrying activity_start_date, provenance kind (operator-declared vs censo-corroborated), and optional censo snapshot id; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [ ] `P01.S03` - Add the suppressed no_prior_obligation facet field plus its clean-property treatment to CrossPeriodDependencyEvidence so a scoped-out requirement is explicit and non-silent; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [ ] `P01.S04` - Add the pure period-strictly-before-activity-start predicate over a declared date routed through Period boundary authority, unit-testing that the alta-containing period is NOT before-start; `src/aeat/application/calculations/_cross_period_clean_state.py`.

### Phase `P02` - Application-layer activity-start scoping in requirement derivation

Scope cross-period dependency requirements whose period falls strictly before the operator-declared activity_start_date out of the derived graph inside _cross_period_clean_state.py, generalising the existing M130 absent-by-design vocabulary from calendar-position to activity-start boundary. Apply the scoping uniformly to both previous_filing bindings and relation_source_requirements, stamp suppressed anchors with the provenance facet, and resolve the binding value to a provenance-marked zero. Never weaken _OFFICIAL_SOURCE_KINDS.

- [ ] `P02.S05` - Apply the activity-start scoping filter to previous_filing-origin requirements in cross_period_dependency_requirements so a period strictly before the declared alta is dropped from the derived graph; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [ ] `P02.S06` - Apply the same activity-start scoping filter to registry-relation-origin requirements so the suppression is uniform across both previous_filing and relation_source_requirements origins; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [ ] `P02.S07` - Stamp each suppressed requirement with the no-prior-obligation provenance facet and resolve its binding value through the existing absent-by-design path to a provenance-marked Decimal zero rather than an unstamped carry; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [ ] `P02.S08` - Thread the declared activity_start_date parameter into evaluate_cross_period_clean_state and cross_period_dependency_requirements without letting callers pass an ad hoc dependency set, preserving registry-derived guard semantics; `src/aeat/application/calculations/_cross_period_clean_state.py`.

### Phase `P03` - Caller plumbing and non-blocking advisory

Thread the operator-declared activity_start_date from the workflow profile through the verification-action caller into evaluate_cross_period_clean_state, reusing the exact field the deadline engine consumes. Emit the non-blocking advisory finding when suppression rests on a declared-but-uncorroborated date, fail closed (block, prompt to record the date) when no activity_start_date exists at all, and keep the first local filing persisting under the non-official app_filing source kind.

- [ ] `P03.S09` - Thread workflow_profile.activity_start_date from the verification-action caller into _cross_period_clean_state_verdict_for_work_unit and onward to evaluate_cross_period_clean_state, reusing the exact field the deadline engine consumes; `src/aeat/application/modelo/_verification_actions.py`.
- [ ] `P03.S10` - Emit a non-blocking advisory verification finding when a suppression rests on an operator-declared-but-uncorroborated activity-start date, mirroring the existing unstamped-revision advisory severity that keeps the grant path open; `src/aeat/application/modelo/_verification_actions.py`.
- [ ] `P03.S11` - Fail closed with a blocking finding that prompts the operator to record the activity-start date when the profile carries no activity_start_date at all, so the gate never silently opens; `src/aeat/application/modelo/_verification_actions.py`.

### Phase `P04` - Real-behavior verification gates

Prove the design with real-storage tests: the empty-pre-activity-span (absent-by-design = no blocker) case, the alta-containing-period stays in scope, uniform application across both requirement origins, the no-activity-start fail-closed case, the advisory surfaces, and an anti-tautology proof that a REAL prior filing post-dating the declared alta still blocks.

- [ ] `P04.S12` - Add a real-storage test proving an empty pre-activity span produces no cross-period blocker (absent-by-design) and verify completes on current-period merits for a genuine first filer; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
- [ ] `P04.S13` - Add a real-storage test proving the alta-containing period stays in scope as the first obligation and is NOT suppressed; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
- [ ] `P04.S14` - Add a real-storage test proving the activity-start scoping applies uniformly to both previous_filing and relation_source_requirements origins; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
- [ ] `P04.S15` - Add an anti-tautology proof that a REAL prior filing post-dating the declared alta still produces a cross-period blocker and still demands official AEAT evidence; `src/aeat/application/calculations/tests/test_cross_period_clean_state.py`.
- [ ] `P04.S16` - Add a real-storage test proving the gate fails closed when the profile carries no activity_start_date and that the non-blocking advisory surfaces when a declared date scopes a requirement out; `src/aeat/application/modelo/tests/test_cross_period_clean_state_gates.py`.
- [ ] `P04.S17` - Add a regression asserting no_prior_obligation provenance never enters _OFFICIAL_SOURCE_KINDS and the first local filing still persists under the non-official app_filing source kind; `src/aeat/application/modelo/tests/test_cross_period_clean_state_enforcement.py`.

## Description

This plan implements the accepted `2026-06-13-first-filer-attestation-adr`:
scope a genuine first filer's pre-activity cross-period dependency anchors out
of the clean-state requirement graph using the operator-declared
`activity_start_date`, with declared (non-AEAT) provenance and a non-blocking
advisory until an AEAT censo snapshot can corroborate it. The defect, mapped in
`2026-06-12-first-filer-attestation-research`, is that the cross-period
clean-state gate demands official AEAT evidence of prior-period filings that
never legally existed for a first filer, closing the verify-export-file loop with
no legitimate offline exit.

The grounded surfaces. The requirement-derivation and evaluation logic lives in
`src/aeat/application/calculations/_cross_period_clean_state.py`
(`cross_period_dependency_requirements`, `evaluate_cross_period_clean_state`, the
`CrossPeriodDependencyEvidence` facet, and `_OFFICIAL_SOURCE_KINDS`). The
operator-declared `activity_start_date` already reaches the deadline engine at
`src/aeat/domain/deadlines/_engine.py` (it suppresses any obligation whose
`closes_on < activity_start_date`) fed from `src/aeat/domain/deadlines/_profiles.py`,
so the field and its pre-start suppression semantics are precedented, not novel.
The verification-action caller in
`src/aeat/application/modelo/_verification_actions.py` already threads the
`TaxpayerProfile` (`workflow_profile`) and projects profile rosters into the
clean-state contract via `_cross_period_expected_member_sets_from_profile`, which
is the exact precedent for threading `workflow_profile.activity_start_date` into
the gate.

The design honours the accepted defaults verbatim: the alta-CONTAINING period is
the first obligation and only STRICTLY-prior periods are suppressed (routed
through `Period` boundary authority per `period-filter-single-boundary-authority`);
the narrowing is an application-layer filter over the derived requirements (the
registry stays pure, the declared date is a grounded input, not an ad hoc per-call
shrink — preserving the `2026-06-05-cross-period-calculation-guards-adr` registry-
derived-graph constraint); the suppression is recorded as an explicit typed
no-prior-obligation evidence facet (NOT a silent omission); the scoping applies
uniformly to both `previous_filing` bindings and `relation_source_requirements`;
and censo-corroboration is deferred — the declared date is the authority now with
a non-blocking advisory. `_OFFICIAL_SOURCE_KINDS` is never weakened, and the first
local filing still persists under the non-official `app_filing` source kind, so a
later dependent period still demands real AEAT evidence of that filing.

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

The Phases carry hard ordering and are NOT parallel. P01 (the typed provenance
vocabulary) is a precondition for P02 (the scoping that stamps the facet), which
is a precondition for P03 (the caller plumbing and advisory that surface it),
which P04 (the verification gates) proves. Within a Phase the Steps share the
same file and must land in id order.

CONTENTION RISK — peer WIP in the worktree. At plan-authoring time
`src/aeat/application/calculations/_cross_period_clean_state.py`,
`src/aeat/application/modelo/_verification_actions.py`, and the test files this
plan touches (`test_cross_period_clean_state.py`,
`test_cross_period_clean_state_gates.py`,
`test_cross_period_clean_state_enforcement.py`) all carried uncommitted peer
modifications (` M`), and an untracked peer file `_dt12_advisory.py` exists in the
same package. The executor MUST run `git status --short -- <file>` and
`git diff -- <file>` before the first edit to each file and abort on non-authored
WIP per `aeat-swarm-orchestration`. Re-read HEAD immediately before acting on any
Step in case a peer fix landed between authoring and execution. Because every
P01/P02 Step and the P03 caller-plumbing Steps share two heavily-contended files,
serialise execution behind a single coder per file rather than fanning out.

## Verification

The plan is complete when every Step is closed (`- [x]`) with a matching
`.vault/exec` record per `plan-closure-requires-exec-records`, and the following
verifiable gates pass:

- The genuine-first-filer real-storage test (P04.S12) proves verify completes on
  current-period merits with zero cross-period blocker for an empty pre-activity
  span (absent-by-design).
- The boundary test (P04.S13) proves the alta-containing period stays in scope as
  the first obligation and is not suppressed.
- The uniformity test (P04.S14) proves the scoping applies to both
  `previous_filing` and `relation_source_requirements` origins.
- The anti-tautology proof (P04.S15) proves a REAL prior filing post-dating the
  declared alta still produces a cross-period blocker and still demands official
  AEAT evidence — the gate is not vacuously open.
- The fail-closed-plus-advisory test (P04.S16) proves the gate blocks when no
  `activity_start_date` exists and surfaces the non-blocking advisory when a
  declared date scopes a requirement out.
- The honesty regression (P04.S17) asserts the no-prior-obligation provenance
  never enters `_OFFICIAL_SOURCE_KINDS` and the first local filing still persists
  under non-official `app_filing`.
- Every test uses real storage (no mocks/stubs/skips/xfail) per
  `aeat-quality-gates` and `aeat-roundtrip-discipline`, and the
  `_cross_period_clean_state.py` and `_verification_actions.py` focused suites
  plus the full `src/aeat` collect-only gate stay green (owner-triaged per
  `full-tree-gate-must-distinguish-owner` if peer churn reds the full tree).
