---
tags:
  - '#adr'
  - '#ledger-classify-queue'
date: '2026-11-20'
modified: '2026-11-20'
body_schema: 'body-v2'
body_hash: 'sha256:02270f0d0065e0b813b9068af01ef7631c3999cbfce60d39c9fa8e908fef19ae'
related:
  - "[[2026-10-25-agent-owned-models-adr]]"
  - "[[2026-10-04-desktop-shell-adr]]"
  - "[[2026-10-16-idle-churn-adr]]"
  - "[[2026-10-17-idle-churn-operation-observation-adr]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - "[[2026-10-13-agent-attachments-adr]]"
  - "[[2026-06-15-llm-classification-workflow-adr]]"
  - "[[2026-10-19-provider-settings-tax-model-runs-adr]]"
  - '[[2026-11-20-ledger-classify-queue-reference]]'
---

# `ledger-classify-queue` adr: `ledger classification jobs, task-kind models and revision cues` | (**status:** `accepted`)

Accepted 2026-11-20 on the operator's binding requirements of 2026-11-20, relayed by PRIME in the LEDGER-CLASSIFY brief:

- cadrumo-agent is the single provider source, and each task kind gets its own default provider, model and effort from an agent setting, falling back to the picker.
- Off-host classification needs the accepted consent path and is never refused silently.
- Classification runs through a real backend queue.
- Progress is visible.
- A typed completion signal is sent, with the desktop-shell amendment "authorised 2026-11-20 by demand".

The commitments below restate those requirements. Text marked as a hypothesis may change within them.

## Problem Statement

Classifying ledger movements with a model is a blocking action, one movement at a time. Each ask holds the profile serial lock for up to 90 s. "Pedir para cada" is a hidden sequential loop over at most 20 rows, and its results live only in the open component. Nothing tells the window when background work finishes. Every task uses the one picked model, with no effort setting. On an off-host lane every classification is refused before dispatch, and the window shows only "the model is unavailable". The operator requires a persisted queue, visible progress, a typed completion signal, per-task model defaults and an explicit consent path. Evidence: `2026-11-20-ledger-classify-queue-reference`.

## Considerations

- This requirement reverses the one-picked-model rule for task defaults (`2026-10-25-agent-owned-models-adr`, constraint 6 and its 2026-10-27 amendment).
- Cues are advisory and carry no private fact; authority stays in typed reads (`2026-10-16-idle-churn-adr`, `2026-10-17-idle-churn-operation-observation-adr`). A revision-only cue already exists (`2026-11-15-desktop-shell-console-environment-adr`).
- Off-host reading needs a person-granted, digest-bound consent. Its three scopes are once, agent session and remembered (`2026-06-10-llm-evidence-classification-adr`, 2026-10-13 amendment; `2026-10-13-agent-attachments-adr`, constraint 7 and its 2026-10-25 amendment).
- Model output is a proposal, never an applied fact, and regulated amounts are derived. `ledger list --status pending` remains the movement review queue (`2026-06-04-llm-ledger-classification-adr`, `2026-06-15-llm-classification-workflow-adr`).
- The window holds no domain data or logic (`2026-10-04-desktop-shell-adr`, 2026-10-27 amendment).
- The supervisor already offers cooperative cancel, resumable checkpoints and leases without a deadline. The AEAT run queue lives in host memory and is lost on restart (reference, section "Long-running operations and storage").

## Considered options

- **Host-memory loops, as in the AEAT run.** Rejected: they do not survive a restart, and their state lives outside the backend.
- **One long operation per job, with state only in the operation checkpoint.** Rejected: `operation_secure_references` is process-local and holds one review. A job of 1000 items needs its own state that can be queried.
- **A persisted job record in its own secure namespace, worked by a resumable cooperative operation.** Chosen: the backend owns the queue, items, proposals and revision; the host only starts, follows and signals.
- **A payload-carrying event with job progress.** Rejected: it breaks the cue rule. The cue carries an opaque revision, and the window reads the data.
- **Per-task model choice stored in Cadrumo.** Rejected under constraint 1 of `2026-10-25-agent-owned-models-adr`. The task setting lives in the agent service record, and its vocabulary comes from cadrumo-agent.

## Constraints

1. **Task-kind model defaults.** cadrumo-agent's catalogue serves the task kinds it accepts (at least classification and extraction) and the effort values a lane's background runs accept. The person may set a lane, a model and an effort per task kind in the agent's settings. The agent service stores this in its `model-role-selections` record under a new schema version, keeping the existing version-read rule. A task resolves to its task setting, or else to the picked reading model. The capability refusals of `2026-10-25-agent-owned-models-adr` constraint 10 apply unchanged, and no other model stands in. Cadrumo names no model, effort or default.
2. **Effort on background runs.** Background requests gain an `effort` option, honoured only when the lane's catalogue entry declares it. cadrumo-agent delivers the field first. Cadrumo consumes it after a re-pin in the same window and never pins an unpushed commit.
3. **Jobs are backend records.** A classification job holds:
   - a scope: one movement, a selection or a period;
   - the lane, model and effort it is bound to;
   - a consent reference;
   - items, each pending, running, proposed, failed with a typed cause, cancelled, or stale (its movement changed after the proposal);
   - a monotonic revision.

   The record lives in its own FINANCIAL, bucket-local, full-custody secure namespace, with revision-guarded writes. Registered operations enqueue, run, cancel, retry failed items, dismiss and read jobs. Their contracts are generated and enrolled in the operation contract manifest.
4. **The job never applies a proposal.** An item's result is a proposal bound to the movement's revision. The person accepts, edits or rejects each item through the existing ledger review and apply path. Every value stays manually editable.
5. **Restart safety.** A job survives process and window restarts. A run interrupted mid-item leaves that item `UNKNOWN` until it is reconciled, never done. Remaining pending items resume when the profile is next open. Cancel is cooperative: an in-flight model run settles before the item is marked cancelled.
6. **Consent.** A job on a lane whose catalogue entry sets `reads_off_host` needs a person-granted consent before it runs. The scope is once (this job), agent session, or remembered for that lane and model, and the person can revoke it. Each dispatch is recorded in `EvidenceConsentLedger`, under the gestor bar and the deployment opt-in. Without consent, enqueue refuses with a typed cause and two remedies: authorise, or switch to a local lane. That refusal is rendered with its cause, never as "unavailable".
7. **Typed revision cue.** When a background job's record changes, the host sends the window a cue `{family, profile_id, job_id?, revision}` on one subscribed channel.
   - `family` is a closed vocabulary that starts with `ledger_classification`. Other background operations join by adding a family.
   - `revision` is the opaque revision the backend serves.
   - The cue carries no private fact and grants nothing.
   - The window re-reads through the typed read operation, gated on revision. It also re-reads on subscribe and on window focus.
   - Cues never replace a read, and no periodic polling is added.
8. **Visible state.** The shell shows a background-task indicator: the count, each job's progress, failures with their causes, and cancel and retry. The Libro shows each affected row as classifying, proposed or failed. Every control either changes visible state or shows a typed notice, and is logged.
9. **Measured speed.** A change to batching, concurrency, prompt prefix or warm-up is adopted only with before-and-after numbers on synthetic data. The numbers are the time to the first result for one movement, and the throughput for 100 and 1000 movements. Concurrency stays within the lane's declared capability.

## Implementation

We will add:

- a persisted queue of ledger classification jobs in the backend, worked by a cooperative, resumable registered operation through cadrumo-agent background runs;
- per-task-kind model and effort defaults, owned by cadrumo-agent and the agent service;
- a typed, revision-gated background-task cue from the host to the window;
- a shell indicator, per-row state, and per-row "Preguntar al agente" actions that enqueue jobs.

Hypotheses within the constraints:

- The host starts the run operation after an enqueue, and on profile open when pending items exist. It follows the run outside the profile serial lock, as AEAT capture does. It maps runtime `RecordsChanged` to one coalesced read of the jobs' revision, and emits the cue only when that revision changed.
- The run classifies a small batch of items per model request, with bounded concurrent requests and a shared system prefix. It commits each batch's proposals as one revision-guarded write.
- "Open in agent conversation" hands the movement to the agent panel as an attachment under `2026-10-13-agent-attachments-adr`, where the person approves it.

## Rationale

Only a backend record gives restart safety and per-item proposals while letting the window read the queue without holding domain state. Reusing the supervisor's cooperative cancel and checkpoint reconciliation keeps `UNKNOWN` honest. A revision-only cue keeps the idle-churn rule intact, because cues stay advisory and reads stay authoritative. Re-reading on subscribe and on focus delivers the operator's "never miss an update". Task-kind defaults stay where models are owned, so Cadrumo still names no model.

## Consequences

- `2026-10-25-agent-owned-models-adr` constraint 6 ("There is no per-task choice") is amended. The person may set a per-task-kind default in the agent settings, the picker remains the fallback, and the person still sees no internal role.
- `2026-10-04-desktop-shell-adr` gains the typed background-task cue channel. Under `2026-10-16-idle-churn-adr` and `2026-10-17-idle-churn-operation-observation-adr`, a window cue may name an opaque job identifier and a revision, and still carries no private fact.
- The 20-row cap of "Pedir para cada", and holding its results in the component, are retired in favour of jobs.
- Accepted cost: a new namespace, new operations with generated contracts, and a cadrumo-agent catalogue change with a re-pin.
- Reconsider if the supervisor gains a native job facility, or if cadrumo-agent offers batch runs natively.
