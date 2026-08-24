---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:34d9ad723a1301bc32ee2b05dd21ad30ec82b5be6a02fea6d0803e759d455f9b'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-24-tui-operation-observation-adr]]"
  - "[[2026-08-24-tui-operation-observation-research]]"
  - "[[2026-08-11-tui-architecture-plan]]"
---
# `tui-architecture` audit: `S119 public observation service review`

## Scope

Independent review of `W02.P19.S119` against the accepted operation architecture, its rejected observation-staging provenance, the observation research, and the canonical plan. The review covered `src/cadrumo/application/operations/_observation.py`, its sole facade export, `src/cadrumo/application/operations/tests/test_observation.py`, the atomic observation materialization introduced by the preceding steps, and semantic/exact searches for competing folds and projectors. Focused Ruff and pytest checks passed: 84 tests across observation, public contracts, facade, and the real persistence journal.

## Findings

### cancellation-availability | high | The projection advertises cancellation during an irreversible section

`OperationObservationService._project` derives `cancellable_now` only from the definition's declared cancellation capability, a broad lifecycle allowlist, and absence of an already-recorded request at `src/cadrumo/application/operations/_observation.py:154`. The canonical executor guard keeps irreversible-section depth only in `_Cancellation._irreversible_section_depth` at `src/cadrumo/application/operations/_execution_context.py:51` and does not place that fact in the atomically observed snapshot. Consequently a cooperatively cancellable operation that is currently inside its irreversible mutation boundary remains `RUNNING` with no cancellation request and is projected as cancellable. This contradicts accepted D7 and the census-operation clause requiring `cancellable_now` to become false in the atomic apply section, so S119 cannot yet supply authoritative control availability.

### interaction-contract-binding | high | Pending interaction projection does not prove the checkpoint belongs to the registered interaction contract

`_project_pending_interaction` at `src/cadrumo/application/operations/_observation.py:225` does not verify that the persisted request kind is present in `contract.interaction_kinds`. REVIEW projection substitutes the current registry's response schema without validating the checkpoint's `response_schema_ref`, while every INPUT or CHOICE checkpoint is projected as unsupported even when the definition never declared that kind. The journal validates interaction identity and revision but not the definition's interaction declaration or response-schema binding. A mismatched durable checkpoint can therefore cross observation as a plausible current public interaction instead of producing a safe definition-contract refusal, violating the exact registered schema and definition-digest boundary.

### conformance-coverage | medium | S119 tests leave most public mapping and failure behavior unproved

`src/cadrumo/application/operations/tests/test_observation.py:232` exercises only phase and progress rows from the real adapter. The test suite does not drive log, effect, notice, reconciliation, diagnostic, interaction, or terminal rows through the public observation service; does not exercise REVIEW and unsupported pending-interaction projection; does not prove terminal-condition and effect combinations independently; and does not inject reader or projection failures to prove raw exceptions collapse to `observation_unavailable`. Expiry and compaction at `src/cadrumo/application/operations/tests/test_observation.py:323` call the private `_project` method with a fabricated materialization rather than observing through the public service. The implementation branches appear renderer-neutral, and semantic plus exact searches found no second production projector or progress fold, but the acceptance surface is not executable at the required fixed point.

## Recommendations

- Add one canonical operation-state fact for current cancellation availability or irreversible-section occupancy, transition it under supervisor authority with the same observation anchor, and derive `cancellable_now` from that fact rather than a lifecycle heuristic.
- Bind pending interaction kind and response schema to the exact registered definition at publication or hydration, then have observation refuse mismatches. Replace the unstructured response-schema reference in the current-only cutover rather than retaining a compatibility translation.
- Add real-model, no-mock service tests for every internal event variant, every supported/unsupported pending interaction, independent terminal/effect projection, raw exception collapse, bounded reconnect, and service-level expiry/compaction resynchronization with sentinel non-retention assertions.
