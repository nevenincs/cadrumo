---
tags:
  - '#plan'
  - '#crossperiod-filing-deadlock'
date: '2026-06-21'
modified: '2026-06-21'
tier: L2
related:
  - '[[2026-06-19-crossperiod-filing-deadlock-adr]]'
  - '[[2026-06-19-crossperiod-filing-deadlock-research]]'
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
     Replace crossperiod-filing-deadlock with a kebab-case feature tag, e.g. #foo-bar.
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

# `crossperiod-filing-deadlock` plan

### Phase `P01` - Decision A - admit late local work file for closed-window targets

Resolve the FILE-gate obligation schedule in the target period's filing year so a genuinely-existing but closed-window obligation is admitted as a late LOCAL filing (extemporanea, con recargo), seeding the next period's cross-period carry observation; a target that never had an obligation still refuses NO_PENDING_OBLIGATION.


<!-- One-line headline summary plan. -->

- [x] `P01.S01` - Re-scope the FILE-gate obligation schedule to the target period's filing year for an explicit FILE target, leaving the as-of-today projection on today.year; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S02` - Guard the target-year compute against NoDeadlineWindowsError so a year with no registry windows degrades to NO_PENDING_OBLIGATION rather than UNHANDLED_EXCEPTION; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S03` - Admit an explicitly-targeted overdue obligation as a late local filing, stamping the extemporanea marker on the COMPUTING_DEADLINES step details instead of aborting DEADLINE_PASSED; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S04` - Skip the submission filing-window preflight for the local FILE purpose alongside VERIFY; `src/aeat/application/workflow/_engine.py`.
- [x] `P01.S05` - Update the workflow engine tests to Decision A semantics (targeted overdue admitted, closed-window FILE no longer aborts DEADLINE_PASSED); `src/aeat/application/workflow/tests/test_engine.py`.

### Phase `P02` - Decision B - within-year local-chain export with a disclosing advisory

Admit a same-filing-year app_filing local chain whose only blockers are the official-evidence delta to verify and export, clearing those blockers and surfacing a non-blocking advisory; cross-year priors, operator_manual sources, and value/revision divergence stay blocking.

- [x] `P02.S06` - Add the non_official_local_chain_advisory facet on CrossPeriodDependencyEvidence and the has_non_official_local_chain_advisory verdict property; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `P02.S07` - Add _relax_same_year_local_chain admitting a same-year app_filing dependency whose blockers are a subset of the official-evidence-delta set, clearing those blockers and stamping the advisory facet; `src/aeat/application/calculations/_cross_period_clean_state.py`.
- [x] `P02.S08` - Emit the non-blocking WARNING non-official-local-chain advisory finding from the cross-period clean-state findings builder; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `P02.S09` - Attach cross-period dependency legal grounding (LGT art 119/120, LIVA art 99 for compensacion, RGAT art 9 for activity-start) to every cross-period and iva-wallet finding; `src/aeat/application/modelo/_verification_actions.py`.
- [x] `P02.S10` - Reconcile the local cross-period carry tests to admit-with-advisory for same-year chains while keeping the cross-year prior blocking and preserving the app_filing-non-official invariant; `src/aeat/application/modelo/tests/test_local_cross_period_carry.py`.
- [x] `P02.S11` - Ratchet the owned _cross_period_clean_state.py SPLIT-CANDIDATE size budget from 1265 to 1300 for the feature addition; `src/aeat/tests/test_codebase_size_budgets.py`.

## Description

Backfill plan for the cross-period filing deadlock remediation (campaign finding C0). The authorizing ADR decomposes the deadlock into two cooperating gates and resolves each with a bounded change; the research frames the campaign mandate (make every correctly-computed filing reachable, replacing silent or over-strict refusals with evidence-disclosing, locally-completable paths). The engine arithmetic for every cross-period aggregation (M130 quarter-to-quarter pago-fraccionado carry, M303 1T-to-2T IVA compensacion carry, M100 M130-fold-in) is already correct; the deadlock made it operationally unreachable for any late filing or prior-year reconstruction, so a taxpayer could export only the first period of a chain.

Phase `P01` (Decision A) corrects the literal year-derivation bug in the FILE-gate obligation schedule: an explicit FILE target resolves its obligation in the target period's filing year, so a genuinely-existing but closed-window obligation is recognised as OVERDUE and admitted as a late LOCAL `work file` (extemporanea, con recargo) that persists the `app_filing` carry observation the next period reads. `NO_PENDING_OBLIGATION` still refuses a target for which no obligation ever existed; the as-of-today projection keeps its `today.year` basis, preserving the single-producer invariant.

Phase `P02` (Decision B, same-year scope) admits a same-filing-year `app_filing` local chain whose only remaining blockers are the official-evidence delta to verify and export, clearing those blockers and surfacing a non-blocking WARNING advisory that discloses the non-official basis (`no-silent-under-declaration`). The scope is deliberately narrow: a cross-YEAR non-official prior still blocks (the anti-laundering gate `local-filed-observations-are-non-official-evidence` was authored to protect), `operator_manual` sources and value/revision divergence stay blocking, the `app_filing` source kind stays out of `_OFFICIAL_SOURCE_KINDS`, and only the LOCAL verify/export path is relaxed, never an AEAT-acceptance assertion.

This plan is a retroactive backfill: the implementation landed on `chore/eliminate-shims` in commits `6e635f566` (Decision A) and `84add274d` (Decision B) before this plan was authored. Each Step's execution record names the landing commit; the companion code-review audit is the closure evidence.

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

Phase `P01` (Decision A) and Phase `P02` (Decision B) are end-to-end independent in code but ordered in effect: Decision A alone unblocks the carry value while leaving the dependent verify blocked on official evidence, and Decision B alone has nothing to be clean about because no observation is ever written. Neither phase alone delivers the end-to-end exports the campaign demands, so both are required for the feature. Within `P01`, steps `S01`-`S04` all touch `_engine.py` and were landed in one atomic commit; `S05` (the test update) rides the same commit. Within `P02`, steps `S06`-`S07` (clean-state facet plus relaxation), `S08`-`S09` (advisory emission plus legal grounding), `S10` (test reconciliation), and `S11` (size-budget ratchet) were landed in one atomic commit. The two phases landed as two separate commits and could in principle have been split across two sessions; in practice Decision B was authored after Decision A's reds were confirmed green.

## Verification

The plan is complete when every Step is closed and the C0 test surface is green. Mission success criteria, each a verifiable check:

- Decision A: `src/aeat/application/workflow/tests/test_engine.py` is 47/47 green, including `test_gate_aborts_when_projection_lacks_the_target` (never-existing obligation still refuses `NO_PENDING_OBLIGATION`), `test_deadline_passed_via_run_for_period`, and `test_verify_reaches_done_for_a_closed_filing_window`.
- Decision B: `src/aeat/application/modelo/tests/test_local_cross_period_carry.py` is 5/5 green, asserting (a) a same-year `app_filing` chain is admitted with the non-official-local-chain advisory, (b) a cross-year non-official prior is NOT relaxed and still blocks, and (c) `app_filing` stays absent from `_OFFICIAL_SOURCE_KINDS`.
- Cross-period clean-state boundary pins: `src/aeat/application/calculations/tests/test_cross_period_clean_state.py` is green, holding `operator_manual`, value/revision divergence, missing observation/filing, and group-member gaps BLOCKING.
- End-to-end reachability: `src/aeat/application/modelo/tests/test_e2e_ledger_m130_quarters_to_m100_annual.py` drives the M130 1T-to-4T chain through the real `work file` path and folds into M100, and `test_verify_gate_blocks_chain_carrying_non_official_prior_year` (the cross-year anti-laundering canary) stays green.
- Owned size-budget ratchet for `_cross_period_clean_state.py` (SPLIT-CANDIDATE) is satisfied at 1300.
- The companion code-review audit signs off the safety boundary (the locally-clean vs genuinely-unclean partition) and confirms no official-evidence laundering.

Known external state: at the time of authoring, 54 reds in the C0-adjacent test files are caused entirely by an unrelated peer campaign's in-flight registry edit (the M100/2024 mixed-income construct `renta-2024-mini-model-actividades-economicas-directa` and its new ledger bindings `0021`-`0025`, with an incomplete construct legal-grounding sweep). Those reds are registry-load failures owned by the mixed-income campaign, not this feature's surface; the C0 logic surfaces (`test_engine.py`, `test_local_cross_period_carry.py`) carry zero failures. See the companion audit for the owner-distinguished triage.
