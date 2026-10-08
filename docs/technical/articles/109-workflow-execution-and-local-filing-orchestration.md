# Workflow execution and local filing orchestration

[Technical overview](../architecture.md) · [Article index](catalogue.md) · [Snapshot and reading guide](../reading-guide.md)

> This page describes the analyzed source snapshot. Its findings and limitations are not a certification of the current branch.

**Report:** `STAGE-2-109` · **Topic:** [Operations, profiles and workflows](../topics/operations-profiles-and-workflows.md)

<!-- preserved:article -->
## Scope and method

This chunk contains 19 workflow application modules, totaling 5,615 lines, 222,233 bytes, and 44,424 measured `o200k_base` proxy tokens. I read every assigned line range across all eight bounded helper pages. The report distinguishes local orchestration from live reads and from actual submission. This is static analysis only; external service behavior and legal correctness were not tested.

## Workflow execution

`WorkflowEngine` coordinates a staged local filing pipeline: load the typed taxpayer profile, compute/select an obligation, optionally inspect notifications and prior filings, load inputs and build a registry-backed draft, check identity/schema alignment and findings, then run local preflight. The engine accepts narrow Protocol collaborators for deadlines, data inputs, drafts, auth provider descriptions, and live reads. A successful result records a draft and terminal stages, while `submission_id` remains `None`: this chunk orchestrates validation and local filing work, it does not itself transmit a declaration to AEAT. engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) protocols.py (`src/cadrumo/application/workflow/protocols.py`) protocols.py (`src/cadrumo/application/workflow/protocols.py`) protocols.py (`src/cadrumo/application/workflow/protocols.py`)

Deadline selection shares the domain schedule producer used by state projections. `FILE` requires a matching open obligation for the ordinary next-work path; an explicitly targeted late period can continue as a locally marked extemporaneous workflow, while an absent or closed untargeted obligation aborts. `VERIFY` treats the filing window as informational and can build against a synthetic `NOT_APPLICABLE` obligation when no calendar row matches its explicit target. More than one exact schedule match is an integrity failure rather than an application-level choice. engine.py (`src/cadrumo/application/workflow/engine.py`) _deadline_stage.py (`src/cadrumo/application/workflow/_deadline_stage.py`) _deadline_stage.py (`src/cadrumo/application/workflow/_deadline_stage.py`)

When wired, the inbox stage blocks on formal `notificacion` rows not marked read; absent session/source is represented as a skip. The prior-expediente probe is likewise conditional on the session and source and blocks a matching already-filed year. Draft construction uses bucket-scoped input providers, then checks draft profile tax ID, modelo, period, and current registry schema version. It rejects non-ready states and ERROR findings before submission preflight. These sources may perform AEAT-side reads when a production host supplies them, even though this engine has no submission stage. engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) protocols.py (`src/cadrumo/application/workflow/protocols.py`) protocols.py (`src/cadrumo/application/workflow/protocols.py`)

Preflight records certificate provider state and expiry severity when a bundle is present, and can abort on unavailable, expired, or critically near-expiry credentials. Its local submission-engine call skips deadline and auth-readiness flags for both VERIFY and FILE because these are local workflows. There is a scope question worth verifying: `_stage_running_preflight` still calls `_resolve_certificate_preflight` before that skip, so a present but invalid certificate bundle can block VERIFY/FILE; a missing bundle is merely recorded as not wired. Also, inbox and already-filed reads can still be contacted when their optional sources are supplied. Confirm which local workflow modes are intended to remain independent of configured credentials and external reads. engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) engine.py (`src/cadrumo/application/workflow/engine.py`) protocols.py (`src/cadrumo/application/workflow/protocols.py`)

Each outcome is a typed sequence of stage records with closed abort reasons, timestamps, bounded finding codes, and fact-based precondition verdicts. Site-health and unexpected component failures become structured step failures and include a site-health alert with the same computed run ID; aborts become results rather than exceptions unless a caller explicitly opts into exception behavior. abort.py (`src/cadrumo/application/workflow/abort.py`) engine_recording.py (`src/cadrumo/application/workflow/engine_recording.py`) engine_recording.py (`src/cadrumo/application/workflow/engine_recording.py`) engine.py (`src/cadrumo/application/workflow/engine.py`)

## Profile state, persistence, and recovery

Active-profile discovery resolves only committed capsule summaries. It distinguishes no capsule from an unreadable discovery source, refuses ambiguous labels, and does not read manifests or encrypted facts just to list profiles. Active-record resolution then requires an authenticated profile session and the caller's pinned decode context; it returns typed reasons for unavailable record, absent capsule, or misaddressed session. profile_bucket_scan.py (`src/cadrumo/application/workflow/profile_bucket_scan.py`) profile_bucket_scan.py (`src/cadrumo/application/workflow/profile_bucket_scan.py`) active_profile.py (`src/cadrumo/application/workflow/active_profile.py`) active_profile.py (`src/cadrumo/application/workflow/active_profile.py`)

The health projection carefully separates a committed but locked profile from a dangling pointer, missing/unreadable record, unreadable capsule, and incomplete profile. It is observational and never unlocks or creates credentials. It keeps the resolved label as a private in-process witness, excluding it from serialized health output while allowing the correct login/edit action to be resolved. Confirmed pointer repair takes the pointer transaction and re-assesses eligibility under lock before clear, then re-assesses the result. profile_health.py (`src/cadrumo/application/workflow/profile_health.py`) profile_health.py (`src/cadrumo/application/workflow/profile_health.py`) profile_health.py (`src/cadrumo/application/workflow/profile_health.py`) profile_health.py (`src/cadrumo/application/workflow/profile_health.py`)

Workflow state and run history are persisted through an explicitly composed encrypted secure-object port. State supports optimistic revision checks, bounded retries, and transactional sibling writes such as bucket events. Run records are stored in the secure backend rather than the nominal `runs_dir`; loads verify the requested run identity. Reset fingerprints read metadata and readability, append a plaintext-free bucket event before deleting only the workflow-state row, and retain recoverable state if event emission fails. persistence.py (`src/cadrumo/application/workflow/persistence.py`) persistence.py (`src/cadrumo/application/workflow/persistence.py`) persistence.py (`src/cadrumo/application/workflow/persistence.py`) persistence.py (`src/cadrumo/application/workflow/persistence.py`) persistence.py (`src/cadrumo/application/workflow/persistence.py`) persistence.py (`src/cadrumo/application/workflow/persistence.py`) events.py (`src/cadrumo/application/workflow/events.py`) events.py (`src/cadrumo/application/workflow/events.py`)

One confirmed documentation mismatch: `reset_workflow_state` says its fingerprint includes a hash of the deleted state, but the typed fingerprint and emitted payload contain only optional schema version, write time, byte length, reason class, and recovered bucket ID. No content hash is computed in these modules. Align the description with actual fields or add the promised digest if downstream audit relies on it. persistence.py (`src/cadrumo/application/workflow/persistence.py`) events.py (`src/cadrumo/application/workflow/events.py`) events.py (`src/cadrumo/application/workflow/events.py`)

## Resume and assessment

Resume first captures an exact persisted run and permits a fresh attempt only when it is terminally aborted, has an obligation and an abort reason, and is not a designed terminal case (`NO_PENDING_OBLIGATION`, `ALREADY_FILED`, `USER_CANCELLED`). Selectors support exact run ID, work-unit ID, calculation-revision ID, or a complete visible modelo/year/period target. Model work-addressing remains the authority for revision and period resolution; multiple natural-key candidates are shown as an ambiguity rather than guessed. resume.py (`src/cadrumo/application/workflow/resume.py`) resume.py (`src/cadrumo/application/workflow/resume.py`) resume.py (`src/cadrumo/application/workflow/resume.py`) resume.py (`src/cadrumo/application/workflow/resume.py`) resume.py (`src/cadrumo/application/workflow/resume.py`)

The registered resume-context operation binds run and calculation readers to the requested profile, verifies the active profile and selected-period scope, captures success/refusal/ambiguity without starting a workflow, and stores the result as a secure operand. Its effect is explicitly `NONE`; release requires a terminal receipt matching definition, profile subject, terminal condition, and refusal references. The frontend receives typed candidate data to choose an exact attempt. resume_operation.py (`src/cadrumo/application/workflow/resume_operation.py`) resume_operation.py (`src/cadrumo/application/workflow/resume_operation.py`) resume_operation.py (`src/cadrumo/application/workflow/resume_operation.py`) resume_operation.py (`src/cadrumo/application/workflow/resume_operation.py`)

Strengths include the separation between local draft workflow and actual submission, typed collaborators, exact draft identity checks, distinguishing benign locked state from damage, CAS state updates, and refusal rather than guess on ambiguous resume. Main follow-ups are to validate the certificate behavior for local purposes, resolve the promised-but-absent reset digest, and trace the production host's optional live-source wiring and access scope. This chunk contains no executed tests or external adapter behavior, so atomic storage, actual network touchpoints, and resume-to-engine wiring remain to be checked elsewhere.

## Complete assigned-file coverage

- __init__.py (`src/cadrumo/application/workflow/__init__.py`)
- _deadline_stage.py (`src/cadrumo/application/workflow/_deadline_stage.py`)
- _identity.py (`src/cadrumo/application/workflow/_identity.py`)
- abort.py (`src/cadrumo/application/workflow/abort.py`)
- active_profile.py (`src/cadrumo/application/workflow/active_profile.py`)
- adapters.py (`src/cadrumo/application/workflow/adapters.py`)
- engine.py (`src/cadrumo/application/workflow/engine.py`)
- engine_helpers.py (`src/cadrumo/application/workflow/engine_helpers.py`)
- engine_recording.py (`src/cadrumo/application/workflow/engine_recording.py`)
- errors.py (`src/cadrumo/application/workflow/errors.py`)
- events.py (`src/cadrumo/application/workflow/events.py`)
- persistence.py (`src/cadrumo/application/workflow/persistence.py`)
- profile_bucket_models.py (`src/cadrumo/application/workflow/profile_bucket_models.py`)
- profile_bucket_scan.py (`src/cadrumo/application/workflow/profile_bucket_scan.py`)
- profile_health.py (`src/cadrumo/application/workflow/profile_health.py`)
- protocols.py (`src/cadrumo/application/workflow/protocols.py`)
- resume.py (`src/cadrumo/application/workflow/resume.py`)
- resume_operation.py (`src/cadrumo/application/workflow/resume_operation.py`)
- review_models.py (`src/cadrumo/application/workflow/review_models.py`)
<!-- /preserved:article -->
