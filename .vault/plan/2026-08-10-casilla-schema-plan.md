---
tags:
  - '#plan'
  - '#casilla-schema'
date: '2026-08-10'
modified: '2026-08-11'
body_hash: 'sha256:d7e7066fd3e5b6e1a4c37b1abb96891e3812f93d68c436ffac83c4e26d187168'
tier: L3
related:
  - '[[2026-08-10-casilla-schema-read-model-adr]]'
  - '[[2026-08-10-casilla-schema-canonical-derivations-adr]]'
  - '[[2026-08-10-casilla-schema-blocker-spine-adr]]'
  - '[[2026-08-10-casilla-schema-dead-surface-adr]]'
  - '[[2026-08-10-casilla-schema-research]]'
---

# `casilla-schema` plan

Build the read side of the modelo surface in dependency order: stabilise the base, correct the registry data, land the canonical derivations and the blocker spine, assemble the one review record, retire the dead surfaces, then render the TUI review screen.

## Description

This plan executes the four-ADR cluster of the `casilla-schema` feature and is the campaign's single backlog: work exists if and only if it is a Step row here. Wave-to-authority mapping: W01 is governed by the research findings (base stabilisation plus the Category-A registry corrections that are hard preconditions of truthful derivations); W02 executes `2026-08-10-casilla-schema-canonical-derivations-adr` and `2026-08-10-casilla-schema-blocker-spine-adr`; W03 executes `2026-08-10-casilla-schema-read-model-adr`; W04 executes `2026-08-10-casilla-schema-dead-surface-adr` and delivers the TUI review screen the feature exists for; W05 is the standing intake and close wave.

How to enter this campaign (any session, any agent): run `vaultspec-core status casilla-schema`, read the next open step here, and `git log --grep` for it before starting - a peer may have landed it. The full session ritual and the campaign's hard prohibitions live in the always-on rule `.vaultspec/rules/casilla-schema-buildout.md` (generated copies under each provider's rules directory). Every closed step gets an execution record under `.vault/exec/2026-08-10-casilla-schema/` named by its display path, scaffolded through `vaultspec-core vault add exec`.

Governing disciplines, from the research and the campaign rule: shared answers land as importable, facade-exported code BEFORE their first consumer; each landing is one atomic commit that retargets or deletes its duplicates in the same change; every session enters through this plan's next open step, never through memory or chat history; and no step closes without its verification gate green plus an exec record, or a recorded carry-forward.

Owner rulings recorded 2026-08-10 and binding on this plan: progress counts are permitted only against the named manifest denominator (UNDEFINED when absent, never a bare percentage, never a forbidden field name per the P07 gate); manifest authoring is prioritised in three tranches - IRPF, retencion and IVA first, informative annual declarations second, remainder last; dead-surface semantics are re-homed case by case with no legacy surface ever maintained and all superseded code removed.

Append protocol - how this plan grows without losing precision. The plan is append-only by construction: step ids are immutable, gaps are never reused, and every addition routes through the plan verbs (the `plan_edit` tool or `vaultspec-core vault plan step add` and `step insert`), never a hand-edited row. Step actions must not contain semicolons - the row grammar reserves the semicolon for the scope separator. Three standing append gates: (1) step S08 expands into one manifest-authoring step per manifest-less revision, appended to P02 in the owner-ruled tranche order; (2) phase P11 is the intake gate for every mid-campaign discovery - audit findings, honesty-review items, regressions the campaign's own activity touches, adjudication follow-ups - each appended with its own scope and verification gate; a discovery whose subject phase is still OPEN may instead be inserted beside its siblings there; (3) a scope change is recorded as an appended step plus a note beside it stating what the standing goal still asks for that the narrowing excludes, never by silently rewording an existing row. Appending is expected and unbounded; widening an existing step silently is forbidden.

## Steps

## Wave `W01` - stabilise the base and correct the registry data

Deliver a base that imports cleanly and registry data whose derivations can be trusted. W02 depends on this wave: two of its derivations are only truthful on the outlier revisions after the parser and M720 corrections land. Governed by the research findings.

### Phase `W01.P01` - base stabilisation

The tree imports and a measurement reference point exists.

- [x] `W01.P01.S01` - land the NoRecoveryOutcome import fix via the apply-cached drive (the file carries unrelated peer WIP) and prove the tree imports with a clean collect-only run; `src/cadrumo/application/modelo/_preconditions.py`.
- [x] `W01.P01.S02` - confirm the registry restructure (91 to 94 revisions, the M303 split) is committed, pin that commit as the measurement SHA, and re-take the six basis-tracked numbers (registry revisions, relation pairs, relation-declaring revisions, export-exemption casillas, manifest-bearing revisions, manifest-less revisions) with a bundled-authority probe, recording the command and outputs in the exec record; `src/cadrumo/_data/registry/aeat/`.

### Phase `W01.P02` - registry data corrections

The Category-A data oversights are corrected so derivations are truthful on the outlier revisions.

- [x] `W01.P02.S03` - widen the xml dictionary casilla-id parser beyond digits-only and regression-test the 2024 and 2025 M100 id conventions; `src/cadrumo/domain/calculations/registry/_export_parse.py`.
- [x] `W01.P02.S04` - run binding-field derivation before every casilla-keyed export scan so M720's binding-derived boxes become visible, with an M720 regression; `src/cadrumo/domain/calculations/registry/_export.py`.
- [x] `W01.P02.S05` - normalise the completeness-manifest authoring tree to one on-disk shape and add a shape gate; `src/cadrumo/_data/registry/aeat/modelos/`.
- [ ] `W01.P02.S06` - remove the phantom constant_value source kind from its four production sites; `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`.
- [ ] `W01.P02.S07` - reconcile the M200 multi-segment manifest internal-only inconsistency and correct the false single-segment comment; `src/cadrumo/domain/calculations/registry/_record_design_coverage.py`.
- [ ] `W01.P02.S08` - derive the manifest-less revision worklist from the loaded snapshots after S05, assign each modelo to the owner-ruled tranches from its registry legal domain and title (tranche 1 is IRPF, retencion and IVA including M145, tranche 2 is the informative annual declarations, tranche 3 is the remainder), and record the assignment for owner confirmation before appending one manifest-authoring step per revision to this plan; `src/cadrumo/_data/registry/aeat/modelos/`.

## Wave `W02` - canonical derivations and the blocker spine

Deliver the shared answer-functions and the operator action spine as importable, facade-exported code before any consumer exists. W03 depends on every phase of this wave. Governed by the canonical-derivations and blocker-spine ADRs.

### Phase `W02.P03` - binding-to-casilla joins

One forward join, one reverse join, one relation grouping; duplicates retargeted in the same commits.

- [ ] `W02.P03.S09` - add casillas_by_binding to the registry bindings module as the exact dual of bound_casilla_binding_ids, facade-export it, and retarget the rate-box partition helper in the same commit; `src/cadrumo/domain/calculations/registry/_bindings.py`.
- [ ] `W02.P03.S10` - replace the last-write-wins target-casilla mapping on the M390-M303 adjustment path with the canonical reverse join, covering alternate bindings with a regression; `src/cadrumo/application/modelo/_calculation_modelo_adjustments.py`.
- [ ] `W02.P03.S11` - add relations_by_target_binding as the one relation grouping and retarget the two registry query loops and the relation-prefill loop in the same commit; `src/cadrumo/domain/calculations/registry/_queries.py`.

### Phase `W02.P04` - relation consumption

The four-channel consumption predicate becomes importable production code.

- [ ] `W02.P04.S12` - promote the consumption predicate from the consumption test into facade-exported registry functions, adding the alternate_bindings channel the test omits as an explicit deliverable, and re-point the test at the production functions; `src/cadrumo/domain/calculations/registry/_handoffs.py`.
- [ ] `W02.P04.S13` - record the consumption channel on relation handoff records and retarget the relation-prefill unresolved partition onto the promoted index; `src/cadrumo/application/calculations/_relation_prefill.py`.

### Phase `W02.P05` - official-box classification

The three-state official-box answer, truthful on the outliers.

- [ ] `W02.P05.S14` - add the three-state OfficialBoxStatus enum to core; `src/cadrumo/core/`.
- [ ] `W02.P05.S15` - add classify_official_boxes composing the fixed-width, binding-derived and xml-dictionary mechanisms after derivation, facade-export it, and regression-test M720, M100 2024 and M349; `src/cadrumo/domain/calculations/registry/_export.py`.

### Phase `W02.P06` - operator action spine

One small action vocabulary with total, import-asserted projections; the duplicate enum retired.

- [ ] `W02.P06.S16` - add the OperatorActionAxis StrEnum to core seeded from the blocker-spine ADR's provisional member list, amending members as the projection mapping steps demand; `src/cadrumo/core/`.
- [ ] `W02.P06.S17` - declare a total import-asserted spine projection for the 21 cross-period clean-state blockers; `src/cadrumo/application/calculations/_cross_period_models.py`.
- [ ] `W02.P06.S18` - declare total import-asserted spine projections for the verification finding kinds and for the modelo.readiness payload's three lists (missing, missing_bindings, ledger_issues); `src/cadrumo/domain/modelos/_verification_report.py`.
- [ ] `W02.P06.S19` - declare total import-asserted spine projections for IvaLedgerAggregationIssueReason on the preflight path and for ConfirmationBlockReason beside its core enum; `src/cadrumo/application/ledger/_preflight.py`.
- [ ] `W02.P06.S20` - reconcile DiscrepancyCause (application verification schema) and VerificationDiscrepancyCause (registry verification schema) into one enum, sweep every consumer, and delete the loser in one commit, coordinating with the P09 package deletion that owns one of the two homes; `src/cadrumo/domain/calculations/registry/_schema_verification.py`.
- [ ] `W02.P06.S21` - copy finding message_facts into Notice context on the envelope emission path so blocker codes reach the wire as data; `src/cadrumo/entrypoints/cli/_modelo_work_verification_cli.py`.

## Wave `W03` - the review read-model

Deliver the one assembled review record, its envelope, and the readiness fix. Requires all of W02 so the record joins canonical answers instead of minting duplicates. Governed by the read-model ADR.

### Phase `W03.P07` - assemble the review record

ModeloWorkReview, its producer, its envelope, and the findings attribution sweep.

- [ ] `W03.P07.S22` - promote resolve_calculation_binding_channels to the application modelo facade; `src/cadrumo/application/modelo/__init__.py`.
- [ ] `W03.P07.S23` - add the frozen ModeloWorkReview model and its single producer build_modelo_work_review, law-resolving the revision and asserting any stored stamp; `src/cadrumo/application/modelo/`.
- [ ] `W03.P07.S24` - sweep all finding construction sites that leave casilla_id unset (26 sites across 18 files, with _verification_cross_period.py carrying 9 including the never-populating cross-period kind) and populate it wherever a casilla exists to name, recording the grep-derived site list in the exec record; `src/cadrumo/application/modelo/`.
- [ ] `W03.P07.S25` - implement the owner-ruled progress counts: typed state plus counts against the named manifest denominator, UNDEFINED when no manifest exists, never a bare percentage; `src/cadrumo/application/modelo/`.
- [ ] `W03.P07.S26` - register the modelo.work.review envelope wrapping the record, with the spine axis and machine facts riding Notice context; `src/cadrumo/entrypoints/cli/_modelo_payloads.py`.
- [ ] `W03.P07.S27` - widen the modelo.requires classifier to bucket previous_filing, relation_prefill and live_observation sources, read alternate bindings, and surface unbucketed sources as an advisory; `src/cadrumo/application/modelo/_data_inventory.py`.

### Phase `W03.P08` - readiness reads verification

Pipeline health consumes the persisted verification outcome; INCOMPLETE is visibly distinct.

- [ ] `W03.P08.S28` - re-point pipeline health readiness at the persisted verification outcome and render INCOMPLETE distinctly from never-verified, with a parity regression; `src/cadrumo/application/overview/_pipeline_health.py`.

## Wave `W04` - deletions, wiring, and the TUI review screen

Retire the dead surfaces, wire the export self-check, and render the TUI review screen against the settled record. Governed by the dead-surface ADR and the read-model ADR.

### Phase `W04.P09` - dead-surface dispositions

Three deletions and one wiring, each per the dead-surface ADR.

- [ ] `W04.P09.S29` - adjudicate verify_declaracion against the live reconcile flow and record the overlap outcome in the exec record; `src/cadrumo/application/verification/`.
- [ ] `W04.P09.S30` - delete the application verification package, its tests and the registry application-links consumer rows in one commit, absorbing any missing semantics into reconcile first; `src/cadrumo/application/verification/`.
- [ ] `W04.P09.S31` - delete the strict resolve_bound_inputs_by_casilla_id and both of its facade exports; `src/cadrumo/domain/calculations/registry/`.
- [ ] `W04.P09.S32` - wire verify_export into export_draft as a post-write self-check requiring a MATCH verdict; `src/cadrumo/application/filing/_export.py`.
- [ ] `W04.P09.S33` - delete the entrypoints binding-source readiness dict and derive the readiness wording from a total, import-asserted mapping over BindingSourceKind in the application layer, localised through the locale catalogues; `src/cadrumo/entrypoints/cli/_modelo_discovery_cli.py`.

### Phase `W04.P10` - TUI review screen

The review screen renders the record; filtering rides the closed axes; the campaign closes with a fresh-context honesty review.

- [ ] `W04.P10.S34` - build the TUI review screen consuming the review record through the application modelo facade; `src/cadrumo/adapters/inbound/tui/`.
- [ ] `W04.P10.S35` - add faceted filtering over the record's closed axes; `src/cadrumo/adapters/inbound/tui/`.

## Wave `W05` - rolling intake and campaign close

A standing, deliberately open-ended wave. P11 is the single intake gate for everything discovered mid-campaign: audit-swarm findings, honesty-review items, in-scope regressions, and follow-ups from adjudication steps. Items enter ONLY as appended Step rows through the plan verbs, each with a scope and a verification gate; nothing is tracked in chat, memory, or side files. P12 closes the campaign and retires the campaign rule. This wave never blocks W01-W04; its close phase requires all of them.

### Phase `W05.P11` - discovery intake (append here)

Open-ended by design: every mid-campaign discovery lands here as an appended Step. A discovery that belongs to an earlier phase's subject matter is still appended HERE if that phase already closed; open phases may take insertions instead.

- [ ] `W05.P11.S37` - reconcile the stale export-exemption docstring describing M720 design positions 5-8 against the layout whose records carry zero inline fields; `src/cadrumo/domain/calculations/registry/_validate_export_exemption.py`.
- [ ] `W05.P11.S38` - adjudicate the dormant enum members (profile_schedule, UNRESOLVED_BINDING, INVALID_WAIVER, and the two unused exemption reasons): wire each, pin it dormant with a stated reason, or delete it; `src/cadrumo/core/`.
- [ ] `W05.P11.S41` - correct this plan's standing collect gate to name the selection it actually measures - a bare `pytest --collect-only -q` inherits the unit-lane marker expression from pyproject.toml addopts, deselects 4334 tests and never reaches three of the 21 rule-named gates, so the gate must either pass an empty marker expression or state in terms that it measures the unit lane only; `.vault/plan/2026-08-10-casilla-schema-plan.md`.

### Phase `W05.P12` - campaign close

The close gates: honesty review, rule retirement, and the final all-steps-accounted check.

- [ ] `W05.P12.S36` - run the fresh-context honesty review of the campaign close and record it as a vault audit with every finding actioned or deferred; `.vault/audit/`.
- [ ] `W05.P12.S39` - retire the casilla-schema-buildout campaign rule and sync the provider copies in the same action as the closing review; `.vaultspec/rules/casilla-schema-buildout.md`.
- [ ] `W05.P12.S40` - confirm every step in this plan is checked with an exec record or formally deferred with a follow-up reference, and only then declare the campaign structurally complete; `.vault/plan/2026-08-10-casilla-schema-plan.md`.

## Parallelization

Waves are sequenced: W01 before W02 before W03 before W04; W05.P12 (close) requires all of them, while W05.P11 (intake) is explicitly exempt from wave sequencing and accepts appends at any moment of the campaign. Within W01, P01 lands first; the P02 corrections may be authored in parallel but their gates verify only against the pinned base from S02, and S05 (manifest shape normalisation) must land before S08 derives the worklist - the worklist's predicate depends on the normalised shape. Within W02, the three derivation phases (P03, P04, P05) and the spine phase (P06) are independent tracks that may run in parallel; steps inside each phase are ordered. Cross-wave dependency: S20 shares subject matter with S30 - one of the two discrepancy enums lives inside the package S30 deletes - so S20 lands first, and if its loser is the one in the doomed package, S20's deletion half may be satisfied jointly with S30 in one commit, recorded in both exec records. W03 requires all of W02; inside it S22 precedes S23, S24 through S27 may proceed in parallel once S23 exists, and P08 is independent of P07. Within W04, P09 steps are mutually independent except that S29 (adjudication) precedes S30 (deletion); P10 requires P07 for the record and P09 only insofar as the screen must not reference deleted symbols.

Manifest authoring (the S08 expansion) is owner-prioritised (2026-08-10): the tranche-1 revisions (IRPF, retencion and IVA, including M145) land before W03 completes, so the ruled progress counts are meaningful on the important forms the moment the record ships; the informative annual declarations (tranche 2) land before P12 opens; the tranche-3 remainder is explicit backlog that does not block the close, provided each remaining revision's appended step is formally deferred with a follow-up reference at close (the S40 criterion). Manifest authoring is grounded tax work (legal refs and identity checks, per the calculation-grounding rule), so it proceeds in parallel with W02 and W03 without blocking them - the record renders missing manifests honestly as not measurable in the meantime.

## Verification

Global gates, holding for every step: the tree imports and `uv run --no-sync pytest --collect-only -q` is clean before and after every relocation commit; a canonical landing leaves zero non-test references to its retired duplicates, with the grep proof cited in the exec record; every new gate is proven to bite once (break the production code deliberately, preferably by a runtime patch from outside the repo, observe the red, restore); no mocks, stubs, skips, xfail or tautological assertions anywhere; registry values stay in TOML, never inlined; and a step closes only through the plan verbs with a matching exec record or a recorded deferral.

Per-phase exit gates:

- P01: `cadrumo.application.modelo` imports cleanly at the pinned SHA; the pinned SHA contains the committed registry restructure (94 revisions, the M303 split), so the measurement basis matches the corpus every other gate assumes; the six basis-tracked numbers are re-measured at that SHA with the bundled-authority probe and recorded, command and outputs, in the S02 exec record.
- P02: M100 2024 and 2025 casilla ids parse, with one regression per id convention; M720 boxes are visible to the casilla-keyed scan; exactly one manifest authoring shape exists on disk behind a shape gate; zero production references to `constant_value`; the M200 false comment is corrected; the S08 worklist exists as appended steps in tranche order with the tranche assignment recorded for owner confirmation.
- P03: `casillas_by_binding` is facade-exported and defined via `bound_casilla_binding_ids`, with a regression proving the refusal on a BOUND casilla without a binding; the enumerated duplicate set is retargeted in the same commits (the rate-box helper, the M390-M303 adjustment mapping with its alternate-bindings regression, the two registry query grouping loops, the relation-prefill grouping loop); a grep recorded in the exec record finds no remaining non-test binding-to-casilla or relation-to-binding grouping outside the canonical module.
- P04: the promoted consumption index covers all four channels including `alternate_bindings`; a regression exercises an alternate-binding-fed relation so the gate reds if the fourth channel is dropped; the consumption test imports the production functions; handoff records carry their consumption channel.
- P05: `classify_official_boxes` returns the three-state answer with named regressions on M720, M100 2024 and M349, and UNDEFINED on a layout-less revision.
- P06: every spine projection asserts totality at import, and a deliberately unmapped member reds the import (proof recorded, restored same session); the 21-member cross-period blocker enum is mapped in full; exactly one discrepancy-cause enum remains with zero references to the deleted one; blocker codes reach `Notice.context` as data, not prose.
- P07: `modelo.work.review` passes the envelope schema conformance gates; every finding construction site with a casilla to name populates `casilla_id`; progress renders the typed state plus counts against the manifest denominator, named on the payload by a denominator field whose value identifies the completeness manifest and its revision, UNDEFINED where no manifest exists; a payload-scoped gate forbids the seven ratio tokens (percent, percentage, fraction, ratio, pct, coverage_rate, completeness) in FIELD NAMES on the review payload - values may name the manifest; the requires classifier buckets previous_filing, relation_prefill and live_observation and surfaces unbucketed sources as an advisory.
- P08: a revision whose verification is INCOMPLETE renders distinctly from a never-verified revision, locked by a parity regression.
- P09: zero references to the deleted symbols remain in facades, registry TOML consumer rows, or the agent-harness documents under `src/cadrumo/_data/agent/`; the export self-check reds on a deliberately byte-tampered file; the API-reference stubs are regenerated with `python -m dev.docs.apidocs scaffold` in the deleting commits.
- P10: the review screen renders the outlier set (M720, M200 2024, M100 2024 and 2025, M349) truthfully, each behind a named regression; filtering covers every closed axis of the record.
- P11: never declared done, only empty; each intake step carries its own verification gate assigned at append time.
- P12: the fresh-context honesty review is persisted as a vault audit with every item closed or formally deferred with a follow-up reference; the campaign rule is retired and the provider copies synced in the same action; every step in this plan is checked or formally deferred.

The plan is complete when every Step is either closed or formally deferred with a follow-up reference (the S40 criterion - the tranche-3 manifest backlog is the sanctioned deferral class), P11 holds no open steps, and the P12 gates hold. Completion is measured against the decision statements of the four related ADRs, quoted in the close audit, never against a paraphrase or a narrowed reading.
