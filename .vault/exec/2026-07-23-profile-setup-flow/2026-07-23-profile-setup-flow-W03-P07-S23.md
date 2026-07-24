---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S23'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

# Add the descendant repeating group emitting the exact renta_family.descendiente fact shape and aggregates through descendant_facts_from_list, descendant NIFs validated by core.identity

## Scope

- `src/cadrumo/application/wizard/_catalogue.py`

## Description

- Author the descendant group in the substrate's first-class repeating-group vocabulary in `src/cadrumo/application/wizard/_descendant_group.py`: a `descendientes-count` integer page gated to natural persons drives a `FlowRepeatingGroup` with per-descendant birth-date, adoption-date, disability-grade, convivencia, custodia-compartida, meses-madre-trabajo, gastos-guardería, and optional NIF pages; splice post-bridge via `attach_descendant_group`, the same decoration seam as the format hints.
- Project answers to the `renta_family.descendiente.{n}.*` facts and aggregates through the canonical `descendant_facts_from_list`; the new code only maps answers to `DescendantInfo`. Validate descendant NIFs through `cadrumo.core.identity`, blank allowed for minors.
- Guard every domain constraint as a verdict before persist: month-range and non-negative-amount per-answer validators leave a failing value uncommitted; adoption-versus-birth registers as a flow-scope cross-field validator blocking submit on both interactive and scripted completion paths; the model constraints stay as defence in depth.
- Replace the descendant namespace at the persist seam: `descendant_clearing_facts` emits the store's canonical `value=None` clears for every on-record `renta_family.descendiente.*` path and stale aggregate the fresh projection does not set, co-committed with the upserts in one `set_active_fields` write, guarded on the count page being answered.
- Add seventeen real-behaviour tests: thirteen engine-level (fact shape, count gating, verdict refusals, splice idempotency) and four persistence-boundary (fact weaving, no-drop re-persist, count-shrink clearing, count-zero clearing) against the real encrypted store.

## Outcome

Landed as `89da268e38` (group, projection, tests) and `248733ff4d` (verdict guards, namespace-replace clearing, persistence tests); locale values for the twenty minted keys landed through the coordinator's catalogue lane. Two review passes: the first returned revision-required (unguarded constraints; stale-linger desync on count shrink); the re-review returned a clean pass with every finding closed on file-line evidence and no new critical or high defects. The count-shrink hazard — stale higher-index descendant facts inflating the mínimo por descendientes — was upgraded from a deferral candidate to a fixed-in-revision item because it becomes reachable the moment the group is spliced into the live definition.

## Notes

- Adoption-token drop at checkpoint save is reviewed BENIGN with the why recorded: only an invalid adoption date is normalised to `None` during checkpoint projection (a valid pair projects verbatim), the flow-scope validator force-corrects it before any submit on either completion path, and resume re-collects the group. The verdict is conditional on the definition splice landing; until then the whole descendant surface is dormant by construction.
- Descendant facts survive a resume that does not re-answer the group: the persist path is a per-path upsert and a group-less answer map projects zero descendant facts, touching no persisted row — the no-drop question raised at review is closed with that mechanism, pinned by a round-trip test.
- Deliberate deviation from the authoring reference: a count question drives the group because the substrate's repeating-group contract requires a count source page; the reference sketched an add-from-review interaction. Reconcile the reference at the honesty review.
- The `attach_descendant_group` splice into the live definition build ships with the non-interactive migration step, which owns `src/cadrumo/application/wizard/_commands.py` in that window; descendants become operator-visible at that landing.
- Resume and modify seeding of group instance answers remains unwired (`checkpoint_answers_from_record` re-projects top-level questions only) — scoped to the descendiente-door step; the count-shrink clearing makes the reachable shrink path safe in the interim.
- One test-labeling correction from re-review: three of the four persistence tests are real-store round-trips; the weaving test is a projection-composition unit test.
- The executor's suite claim was corrected by the re-review to 301 passed / 4 failed on the dirty working tree: three localization reds belong to the concurrent scripted-driver migration WIP and one is the tracked modify-honesty red that migration's acceptance gate closes.
