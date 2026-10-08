---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:dd292cc25e99573c40f27900a9bb76f11be9038288f0f3da1a08810166f4560d'
related:
  - "[[2026-08-11-tui-architecture-adr]]"
  - "[[2026-08-24-tui-operation-observation-adr]]"
  - "[[2026-08-24-tui-operation-observation-research]]"
---

# `tui-architecture` audit: `S119 public observation service review`

## Scope

Independent review of `W02.P19.S119` against the accepted operation architecture, its rejected observation-staging provenance, the observation research, and the canonical plan. Focused Ruff and pytest checks passed: 84 tests across observation, public contracts, facade, and the real persistence journal.

## Findings

### cancellation-availability | high | The projection advertises cancellation during an irreversible section

The canonical executor guard keeps irreversible-section depth only in `_Cancellation._irreversible_section_depth` at `src/cadrumo/application/operations/_execution_context.py:51` and does not place that fact in the atomically observed snapshot. Consequently a cooperatively cancellable operation that is currently inside its irreversible mutation boundary remains `RUNNING` with no cancellation request and is projected as cancellable. This contradicts accepted D7 and the census-operation clause requiring `cancellable_now` to become false in the atomic apply section, so S119 cannot yet supply authoritative control availability.

### interaction-contract-binding | high | Pending interaction projection does not prove the checkpoint belongs to the registered interaction contract

REVIEW projection substitutes the current registry's response schema without validating the checkpoint's `response_schema_ref`, while every INPUT or CHOICE checkpoint is projected as unsupported even when the definition never declared that kind. The journal validates interaction identity and revision but not the definition's interaction declaration or response-schema binding. A mismatched durable checkpoint can therefore cross observation as a plausible current public interaction instead of producing a safe definition-contract refusal, violating the exact registered schema and definition-digest boundary.

### conformance-coverage | medium | S119 tests leave most public mapping and failure behavior unproved

The test suite does not drive log, effect, notice, reconciliation, diagnostic, interaction, or terminal rows through the public observation service; does not exercise REVIEW and unsupported pending-interaction projection; does not prove terminal-condition and effect combinations independently; and does not inject reader or projection failures to prove raw exceptions collapse to `observation_unavailable`. The implementation branches appear renderer-neutral, and semantic plus exact searches found no second production projector or progress fold, but the acceptance surface is not executable at the required fixed point.

## Recommendations

- Add one canonical operation-state fact for current cancellation availability or irreversible-section occupancy, transition it under supervisor authority with the same observation anchor, and derive `cancellable_now` from that fact rather than a lifecycle heuristic.
- Bind pending interaction kind and response schema to the exact registered definition at publication or hydration, then have observation refuse mismatches. Replace the unstructured response-schema reference in the current-only cutover rather than retaining a compatibility translation.
- Add real-model, no-mock service tests for every internal event variant, every supported/unsupported pending interaction, independent terminal/effect projection, raw exception collapse, bounded reconnect, and service-level expiry/compaction resynchronization with sentinel non-retention assertions.
## Re-review disposition

The remediation resolves the original two high findings and the medium conformance finding. `cancellation_deferred` is now a required current-schema snapshot fact, supervisor-owned irreversible entry and exit persist it with nested and cancellation-race handling, validation excludes impossible terminal and acknowledged states, and public observation requires it to be false before advertising cancellation. Pending interaction projection now refuses undeclared kinds and requires the checkpoint's REVIEW response reference to exactly reproduce the registered response schema identity. Real filesystem-backed tests exercise the held irreversible section, all nine public event variants, REVIEW and unsupported interactions, definition mismatch, secret-bearing checkpoint non-retention, corrupt persistence collapse, terminal state, bounded reconnect, and deterministic resynchronization projection. Focused Ruff and type checks pass; 98 focused tests and 292 operations/persistence tests excluding the independently stale facade inventory pass.

### schema-reference-redeclaration | medium | One production interaction producer still hand-builds the canonical schema reference

This duplicates the canonical formatting rule in a production REVIEW producer and can drift from the schema identity that later production registry composition supplies. Under the project's no-redeclaration rule, this is the sole remaining review finding; the S119 observation logic itself is otherwise conformant.

## Re-review recommendation

- Give the censal response schema one domain-owned `OperationSchemaIdentityV1` fact and derive its interaction checkpoint reference through `operation_public_schema_reference`; production registry composition must reuse that same identity rather than restating its ID, version, fingerprint, or formatted reference.
## Final approval

The schema-reference redeclaration finding is resolved. Facade and executor parity tests prove the binding-to-model identity and the durable pending checkpoint's reference after a real supervisor start and restart reconciliation.

Semantic and exact producer censuses now find one formatter definition, one domain binding, and two intended production consumers: the censal producer and observation validator. No production hand-built `schema:<id>.v<version>` response reference, duplicate formatter, alternate binding, projector, or progress fold remains. Ruff and operation-surface type checks pass; 58 focused registry, facade, observation, and censal tests plus the final 10-test censal/observation cluster pass. A broader direct type check of the censal module still reports the pre-existing unchanged `Unknown` return from the lazy live import in `_pull_censal_datos`; it is outside the S119 diff and does not affect this approval.

No open S119 findings remain. `W02.P19.S119` is approved.
