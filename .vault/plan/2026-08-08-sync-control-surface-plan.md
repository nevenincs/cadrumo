---
tags:
  - '#plan'
  - '#sync-control-surface'
date: '2026-08-08'
modified: '2026-08-12'
body_hash: 'sha256:fd075f18788369267d0388c13992315eb01025c6f4019f51739fbea8ecae94a3'
tier: L2
related:
  - '[[2026-08-08-sync-control-surface-adr]]'
  - '[[2026-08-08-sync-control-surface-reference]]'
---

# `sync-control-surface` plan

## Description

Executes the `sync-control-surface` ADR. That record rules on the shape of sync
controls across the Google Sheets calculation export and the AEAT filed-history
sweep; none of it is implemented, and this plan is the row set that carries the
implementation debt the ruling created.

The ADR is a ruling on code and is not self-executing. Without these rows the
record reads as in force while HEAD carries none of it, and a later reader
believes it shipped. Grounding for every Step — the exact modules, the existing
differs to relocate, and the write mechanics — lives in the feature's reference
document.

Phase `P01` is independent of the ruling and should not wait for it: it closes a
live defect that can empty an operator's workbook today.

## Steps

### Phase `P01` - Close the Sheets torn-write window

An interruption between the batch clear and the batch update empties the operator's workbook today. This is a live defect and the precondition for any cancellation affordance.

- [x] `P01.S01` - gate the ordering property offline - the whole-tab clear is gone and the stale set never names a written cell - since an interruption between two live Sheets calls cannot be reproduced without a forbidden online write; `src/cadrumo/adapters/outbound/google/tests/test_calc_sheets_apply_no_empty_window.py`.
- [x] `P01.S02` - make the tab surface survive an interruption between the two calls, so a partial apply never leaves the operator's workbook empty; `src/cadrumo/adapters/outbound/google/_calc_sheets_apply.py`.

### Phase `P02` - Dry-run on both sync surfaces

One flag spelled the same way on both mutating verbs, with the preview payload declared per write shape: cell-level for the Sheets overwrite, record-level for the filed upsert.

- [x] `P02.S01` - relocate the recapture divergence computation to run BEFORE the upsert instead of after it, preserving the existing notice; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P02.S02` - add the dry-run short-circuit to the filed sweep, returning the divergence set the upsert would introduce without writing; `src/cadrumo/application/live/_filed_data_capture.py`.
- [x] `P02.S03` - expose the filed sweep dry-run flag and carry its state as primary result data on the envelope, never as a notice; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [x] `P02.S04` - reuse the verify parity comparison to build the export preview, rather than growing a second differ; `src/cadrumo/application/storage/calc_sheets/_parity_harness.py`.
- [x] `P02.S05` - add the dry-run short-circuit and flag to the Sheets export, reporting the ranges it would clear and the cells that would change; `src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`.
- [x] `P02.S06` - prove a dry-run writes nothing on either surface, by asserting the store and the remote plan are byte-identical across a preview run; `src/cadrumo/application/live/tests/`.
- [x] `P02.S08` - REVERT the FiledRecaptureDivergence redeclaration introduced by P02.S02 at 86a9002581. The model at application/live/_remote_state_models.py:112 is a fifth carrier of a concept that already has a canonical home - CasillaDivergence at application/modelo/_reconcile_casilla.py:73 carries a typed CasillaId, a closed CasillaDivergenceKind, computed_value, filed_value and delta, whereas this one carries changed_casillas as a bare tuple of str with no values, no kind and no delta. It is not a different concept at a different granularity, it is the same concept carried worse and wrapped in filing identity. Three reasons revert rather than carry. First it has NO CONSUMER - P02.S03 is unbuilt, so this is a design-only shell of exactly the kind the architecture rule bars, because a shell accretes consumers before anyone re-examines it, and the dry-run short-circuit that is the real value of 86a9002581 does not depend on it. Second, the per-casilla comparator cluster is already unruled at four members on the synced-history-consumption plan, and arriving at that ruling with five, one of them strictly weaker, clarifies nothing. Third and load-bearing, reverting does NOT prejudge that ruling while folding WOULD. THIS ROW IS NOT A FOLD AND MUST NOT BE READ AS ONE - folding this carrier onto CasillaDivergence requires choosing between a comparator that returns bare strings with no tolerance and one that returns CasillaDivergence with a 0.01 default, which is precisely the open pair the other plan demands be ruled first, whereas removing a member is not choosing a comparator. Scope is therefore delete the model, delete its export from the application live facade, drop the recapture_divergences field from BulkFiledDataCaptureReport and from the capture accumulator, and keep both the dry_run short-circuit and the single-traversal shape of recapture_divergence_notices intact. Verified as a self-contained deletion rather than assumed - the only consumer is the report field this row also removes. Gate - the model and its facade export are gone, the dry-run short-circuit still returns a report and still writes nothing, the recapture advisory still fires on the notices channel unchanged, and no new carrier is introduced in its place; `src/cadrumo/application/live/_remote_state_models.py, src/cadrumo/application/live/_filed_data_capture.py, src/cadrumo/application/live/__init__.py`.

### Phase `P03` - Last-sync provenance and scope honesty

A local typed sync-run record replacing the remote developer-metadata stamp as the provenance authority, plus a truncation notice so a limited sweep cannot read as complete coverage.

- [x] `P03.S01` - Define the typed sync-run record carrying surface, resolved scope, completion instant, unit counts and divergence count. SCOPE CORRECTION, one finding rather than three notes. This row's scope clause was authored against an ASSUMED layout and is wrong in three places, so a builder following it lands in an illegal home. The surface axis is a new closed value set, so it is a StrEnum in core rather than a Literal local to the storage package. The atomicity the sibling row requires reaches the secure-object batch writer under adapters persistence, so the record model may live in application while the co-write cannot. And application storage is a namespace container whose own facade states it re-exports nothing by design because exporting there would couple callers to the internal subpackage layout, so a private module directly under it admits only a cross-package private import or a re-export its docstring forbids. The record therefore lives in an application storage subpackage with its own public facade, matching the calc sheets sibling. Two model decisions carry reasons rather than conventions. The success flag is not redundant against the divergence count and inferring either from the other inverts both cases, because a run can finish cleanly having found divergences and can fail partway having found none precisely because it never got far enough to look. And the divergence count is refused at construction when it exceeds the unit count, because a unit the run never reached cannot have been found to diverge. Both counts describe what the run REACHED and never what it intended to reach; `src/cadrumo/core and src/cadrumo/application/storage/sync_runs and src/cadrumo/adapters/persistence/storage`.
- [x] `P03.S02` - Persist the sync-run record on completion of each surface, on partial failure as well as success, with a strict roundtrip through the real encrypted store. Partial failure means a run that TRIED to write and got partway, which is a different event from a run that declined to write by design, so the clause binds the real path at full strength and does not reach the preview branch. A DRY RUN WRITES NO RECORD and that absence is declared rather than accidental. A preview reads the remote surface and persists nothing, so it has no last-sync provenance because nothing was synced, and a provenance record is itself a persist that would defeat the guard whose entire purpose is leaving no trace. Delivered in ONE commit with the sibling row and one exec record covering both, because a typed record whose persistence is unwritten is the design-only implementation shell the architecture rules prohibit and its roundtrip is what proves the field types are right. The co-write uses the secure-object batch save with the record repository and the catalogue repository bound to the SAME repository instance so both writes share one session scope, which is the canonical pattern rather than a per-repository wrapper method, and the surface-level event is emitted IN ADDITION to the primitive's lifecycle event rather than instead of it. The roundtrip populates every defaultable field with a non-default value and carries an anti-tautology proof that mutates the on-disk payload and asserts refusal; `src/cadrumo/application/storage/sync_runs and src/cadrumo/application/live and src/cadrumo/application/storage/calc_sheets`.
- [x] `P03.S03` - emit a truncation notice when a sweep is limited, so a partial run cannot read as complete coverage; `src/cadrumo/entrypoints/cli/_app_live.py`.
- [x] `P03.S07` - Introduce the application-layer export service the workbook-export CLI calls, so the sync-run record can be persisted on that surface at all. This row exists because the sibling persistence row assumed both surfaces have an application-layer completion point and only one does. The filed sweep completes inside the application layer with the bucket id already in scope, so its record is one call. The workbook export completes inside the CLI handler, which calls the outbound Google adapter directly, and there is no application function between them. Persisting from the entrypoint would make it the first CLI site writing to a secure-object namespace, and persisting from the adapter would have an outbound adapter reach back into application storage and invert the dependency direction, which is a cycle rather than a layering preference. Both are refused outright rather than weighed. The remaining option is to move plan build and apply orchestration into an application service the CLI then calls, which touches a shipped verb's path and is why this is its own row rather than a clause inside persist the record on completion. Note additionally that failure on this surface RAISES rather than returns, so recording on partial failure as well as success needs the write in the failure path too, and doing that from the CLI would put the partial-failure semantics of a persistence contract inside an entrypoint. The record and its writer already exist and are verified, so this row introduces no new storage concept and only gives the second surface a legal place to call from; `src/cadrumo/application/storage/calc_sheets and src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py`.
- [x] `P03.S09` - RETROACTIVE ROW for a correctness defect shipped by P03.S02 and closed across four commits, opened after the fix rather than before it so the history does not live only in a chat message. WHAT SHIPPED WRONG. The filed sweep fed the record's bounded count pair from two different populations. A recapture advisory is raised once per observation ABSORBED, while the count it was paired against was observations successfully ENROLLED. Enrolment narrows twice against absorption, by the latest-per-period collapse in select_latest_filed_observations_in_history_order and by a BEST_EFFORT enrolment failure diverting its observation into failures. So divergence_count could exceed unit_count and the record refused ITSELF at the very end of a real sweep, after every unit had already been fetched and persisted, destroying the partial-run report and failing worst precisely when the run went worst. A second quieter bug rode with it. unit_count silently meant enrolled rather than reached, against its own field docstring, so a run that reached ten and enrolled three recorded three and was indistinguishable from a run that reached three. That is the partial-reads-as-complete lie inside the store built to stop it. HOW IT WAS FOUND, which is the reusable part. Not by a gate. By re-reading HEAD before starting the next row. A peer's revert at 3612f729fa landed AFTER db8c87fd52, deleted the redeclared carrier, and correctly repointed this writer onto a same-shaped but differently-bounded field. It compiled and type-checked clean, because nothing static owns this class. The revert row's own verification claim, that the only consumer is the report field it also removes, was true when authored and FALSE when executed, because db8c87fd52 added a second consumer in between. The executor re-ran it and caught the drift. A row's verification claim is re-run at execution time, never trusted from authoring time. SECOND REUSABLE LESSON, a misread by this row's own author. The behavioural gate was first reported unbuildable offline on the strength of the sibling capture test's docstring. That docstring records that CAPTURE FROM AEAT is unreachable, because per-row capture fetches the cotejo PDF through context.request where route interception never runs. What the gate needed was a PERSISTED OBSERVATION, which is separable and which persist_filed_calculation_observation seeds directly. A negative claim inherits the scope of the thing actually checked and then travels at full width. Structural-only coverage would have shipped behind a disclosure reading as honest and complete. CLOSED BY four commits. 2b10626f59 repoints both counts onto the accumulator's canonical reached-tally, which already drives the sweep limit and is the only counter incremented in every mode. 22a7262ba6 makes the invalid pair unrepresentable, because record_sync_run now takes a SyncRunCoverage derived through coverage_of which reads BOTH numbers off ONE source, so pairing two populations requires an object that misreports itself rather than a call site that pairs two numbers, and it adds an AST floor requiring every production writer to derive while asserting a non-empty call-site floor before checking offenders. e9d49e0a08 adds the behavioural gate reproducing the defect state through production code with a positive control. f3eb0f3c6e adds the vacuity floor so a collapse of enrolment to zero cannot satisfy the narrowing assertion. The bound deliberately lives in two places. SyncRunCoverage guards CONSTRUCTION where the invalid pair is authored, and SyncRunRecord guards LOAD where a corrupted payload never passed through coverage at all. Gate is unrun by the author and verification belongs to gatekeeper; `src/cadrumo/application/storage/sync_runs and src/cadrumo/application/live/_filed_data_capture.py and src/cadrumo/application/live/tests/test_recapture_divergence_coverage.py`.

## Parallelization

Phase `P01` carries no dependency on the other two and should be executed first
and independently; it closes a live defect.

Phases `P02` and `P03` share no hard interdependency and may run in parallel.
Within `P02`, the filed-sweep chain (`S01` through `S03`) and the Sheets chain
(`S04`, `S05`) are independent of each other; `S06` depends on both.

`P02.S01` must land before `P02.S02`: the dry-run has nothing to report until
the divergence computation runs ahead of the write.

## Verification

- The window is closed structurally rather than by reproduction: no code path
  clears a bare tab range, and the stale set is derived from what the write
  returned so it can never name a cell the write covered. An interruption
  reproduction is deliberately absent -- it would need a write-shaped online
  test against a real account, which is forbidden here -- so nothing in this
  plan should be read as claiming one exists.
- A dry-run on each surface leaves the observation store and the remote
  spreadsheet byte-identical, asserted against the real store rather than a
  mock.
- The dry-run state is present as primary result data on both envelopes and
  absent from the notices channel, per the CLI envelope contract.
- A sync-run record exists after both a successful and a partially-failed sweep,
  and survives a strict roundtrip with every defaultable field populated
  non-default.
- A limited sweep emits the truncation notice; an unlimited one does not.
