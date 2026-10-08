# Work lifecycle, review, wizard, and workflow gate

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-086` · **Topic:** [Modelo work and revision lifecycle, part 2: verification, workbench and workspace](../topics/modelo-work-and-revision-lifecycle-part-2.md)

<!-- preserved:article -->
**Scope:** 15 files under `src/cadrumo/application/modelo`, totaling 4,979 lines, 201,485 bytes, and 41,816 measured proxy tokens. All eight bounded-reader pages were read in sequence. This report is based on static inspection; no application execution or tests were run. Token count is the manifest's `o200k_base` proxy.

## Capabilities and mechanisms

The work lifecycle service creates, lists, renames and discards work units while leaving target selection, calculations, filing records and applicability policy to their owning modules. Creation rechecks period/year consistency, profile readiness, registered model/period/revision, law-selected revision, applicability and superseded census ownership before insertion. Work-unit IDs are derived from profile, model, filing year, period and revision, so attempting to recreate a discarded target resolves to the same ID and is refused; a supersede/recreate transition is not implemented here. New work and its creation event are committed together with a catalogue revision guard. Creation gates and co-commit (`src/cadrumo/application/modelo/work_lifecycle.py`), superseded census refusal (`src/cadrumo/application/modelo/work_lifecycle.py`)

Renaming and discarding load a revisioned catalogue, check the repository's bucket scope and, when supplied, compare the currently stored unit with the operator-approved snapshot. Both update metadata/state and append their event as one guarded write. Discard is durable, not deletion: the unit remains available to history, default listing hides it, and repeated discard refuses. Lookups against another profile's unit return not-found rather than reveal that foreign unit exists. Rename (`src/cadrumo/application/modelo/work_lifecycle.py`), discard (`src/cadrumo/application/modelo/work_lifecycle.py`), bucket-scoped lookup (`src/cadrumo/application/modelo/work_lifecycle.py`)

Lifecycle continuations encode the only next action (or an explicit terminal/operator-decision outcome) from observed evidence. Argument bindings must be resolved and exactly match values in that evidence, leaving frontends to render rather than invent a target or recovery. The standalone pure selector supports full IDs, 12-character operator IDs, and natural model/year/period targets. It checks optional coordinate assertions against exact IDs, refuses ambiguous short or natural targets, and limits active-natural mode to draft roots. Continuation invariants (`src/cadrumo/application/modelo/work_lifecycle.py`), captured-catalogue work selection (`src/cadrumo/application/modelo/work_selection.py`)

Deadline posture uses the shared registry window and business-day resolver, exposing nominal and effective close dates, holiday-coverage status, and exactly one remaining/overdue count. When late, it may include a rate-only Article 27 recargo preview, always marked `unassessed`; it supplies no assessed amount, eligibility decision or actual presentation date. A separate M210 path resolves result-qualified windows from the calculated disposition and persisted official renta-type code, returning no window when the result is unresolved. Deadline and unassessed preview (`src/cadrumo/application/modelo/work_plazo.py`), result-qualified M210 window (`src/cadrumo/application/modelo/work_plazo.py`)

The canonical work review projects one row per registry casilla in registry order, including value/origin, semantic role, constraints, concrete bindings/formula lineage, relation consumption, official state and blockers. It distinguishes origin anomalies and absent-by-design values, and reports progress only against a registry-authored completeness manifest; undefined progress carries no fabricated counts. A capture helper observes versioned work-unit and calculation catalogues, a digest of the verification catalogue, and the pinned registry generation, enabling a later pass to detect a stale multi-source review. Review rows and manifest progress (`src/cadrumo/application/modelo/work_review.py`), currentness capture (`src/cadrumo/application/modelo/work_review.py`)

The registered review read requires one exact profile and work-unit identity, verifies the profile-bound repositories and current registry revision, then returns a compact projection: lifecycle and verification states, measured progress, casilla count, findings, blockers and row-source-fingerprint count. It does not return the detailed casilla values. Scalar finding facts retain explicit type tags and are revalidated before projection. The public result must match the successful, no-effect terminal receipt and exact work-unit subject. Compact review snapshot (`src/cadrumo/application/modelo/work_review_operation.py`), worker read and result projector (`src/cadrumo/application/modelo/work_review_operation.py`)

Wizard discovery draws manual casillas and promptable manual/profile bindings or relation inputs from the pinned registry, attaches legal/source grounding, and omits computed and ledger-fed values. Each live run owns a UUID-scoped copy table whose entries are removed on close; both CLI and TUI use the same frontend-neutral flow, with checkpoints disabled. Follow-up questions are created only for recognized missing-input errors and binding IDs. This discovery function receives a work unit rather than the current calculation/operator layer, so it enumerates registry manual casillas without independently filtering already-entered values; confirm whether that is intentional for each caller. Step discovery and grounded follow-up (`src/cadrumo/application/modelo/work_wizard.py`), run-scoped copy and flow (`src/cadrumo/application/modelo/work_wizard.py`), typed missing-input classification (`src/cadrumo/application/modelo/work_missing_input.py`)

Workbench operations provide five authenticated reads for a human CLI/TUI session: form plus edit admission, casilla help, baseline renewal, staged-edit preflight and one-time retrieval of a refused Apply's named calculation prerequisite. They are recorded as no-effect reads, run under the worker's pinned authority, and resolve access from the persisted work unit's exact period. Disclosure permissions distinguish operation metadata from profile and tax values; the policy requires a human. The prerequisite operation consumes a retained projection once before deriving source boxes, so interruption after consumption but before result capture is a recovery edge to check against its read/idempotency contract. Five operation definitions (`src/cadrumo/application/modelo/workbench_operations.py`), human/period-scoped access (`src/cadrumo/application/modelo/workbench_operations.py`), one-time prerequisite read (`src/cadrumo/application/modelo/workbench_operations.py`)

The workbench public mirror preserves typed decimals, periods, findings and form fields, then restores the canonical read and requires exact equality before releasing it. Its excluded-field inventory is explicitly empty, so a newly excluded canonical field fails review instead of silently disappearing. The read admits an edit baseline alongside the exact calculation/verification identity shown by the form, so the next action is judged against the same revision. Public mirror and round-trip check (`src/cadrumo/application/modelo/workbench_projection.py`), form read and baseline admission (`src/cadrumo/application/modelo/workbench_read.py`)

The workflow gate replays an immutable revision into a filing draft, approves a ready draft locally, and persists that approved draft before returning it. It uses the bucket's own transaction catalogue fingerprint for review evidence. `VERIFY` runs validation independently of filing-window dates; `FILE` retains local filing-window and late-filing policy. Every workflow result is persisted before return, and an aborted run raises so callers must not update verification or filing state. This module does not own those lifecycle mutations; verification and filing callers do so only after a successful gate. Draft builder and persistence (`src/cadrumo/application/modelo/workflow_gate.py`), purpose and durable run result (`src/cadrumo/application/modelo/workflow_gate.py`), required workflow persistence ports (`src/cadrumo/application/modelo/workflow_gate_ports.py`)

## Knowledge, safety, and implementation assessment

The work layer depends on pinned registry facts, profile readiness, work-unit and calculation repositories, verification reports, filing/ledger evidence, deadline calendars and typed operator attestations. It keeps regional-rate previews explicitly conditional, refuses unsupported lifecycle transitions, and uses guarded co-commits for work state and events. The profile object carries one decrypted profile record and its decode context through the call chain to avoid multiple reads. No external network behavior is established by this chunk; despite the workflow's submission-preflight dependency, its local filing record is written by a separate caller.

The strongest security boundaries are bucket-scoped repository checks, exact profile/work-unit request binding, human-only workbench access, compact review output, strict typed projections and evidence-derived continuations. Two conditional recovery questions merit synthesis: workbench prerequisite retrieval consumes its private one-time value before source-box resolution and final result capture, so a later exception may make retry return no prerequisite; and wizard discovery cannot itself distinguish already-entered manual values because its input contains no revision. Also verify that workflow draft persistence and workflow-run audit storage use the expected encrypted adapters. No assigned tests were present, so the atomicity, capture freshness, draft approval and operation retry behavior remain unexercised.

## Dependencies and follow-up

Connect the lifecycle and selector paths to their concrete repository implementations and to work-address capture. Trace review capture through producer-currentness checks and the source assembly module. Confirm wizard callers intentionally prompt the discovered set and that a missing profile-resolution read does not create misleading prompts. Review prerequisite-store take semantics with operation interruption handling. Finally, relate the workflow engine's VERIFY/FILE stages to the outer verification and local filing transitions; static code here does not certify any remote submission outcome.

## Complete assigned-file coverage

All 15 assigned files were read completely through pages 1–8.

- work_lifecycle.py (`src/cadrumo/application/modelo/work_lifecycle.py`)
- work_lifecycle_ports.py (`src/cadrumo/application/modelo/work_lifecycle_ports.py`)
- work_missing_input.py (`src/cadrumo/application/modelo/work_missing_input.py`)
- work_plazo.py (`src/cadrumo/application/modelo/work_plazo.py`)
- work_profile.py (`src/cadrumo/application/modelo/work_profile.py`)
- work_review.py (`src/cadrumo/application/modelo/work_review.py`)
- work_review_operation.py (`src/cadrumo/application/modelo/work_review_operation.py`)
- work_selection.py (`src/cadrumo/application/modelo/work_selection.py`)
- work_unit_repository.py (`src/cadrumo/application/modelo/work_unit_repository.py`)
- work_wizard.py (`src/cadrumo/application/modelo/work_wizard.py`)
- workbench_operations.py (`src/cadrumo/application/modelo/workbench_operations.py`)
- workbench_projection.py (`src/cadrumo/application/modelo/workbench_projection.py`)
- workbench_read.py (`src/cadrumo/application/modelo/workbench_read.py`)
- workflow_gate.py (`src/cadrumo/application/modelo/workflow_gate.py`)
- workflow_gate_ports.py (`src/cadrumo/application/modelo/workflow_gate_ports.py`)
<!-- /preserved:article -->
