---
tags:
  - '#research'
  - '#cli-testimonial'
date: '2026-05-20'
modified: '2026-05-20'
related:
  - "[[2026-05-20-cli-testimonial-findings-inventory-audit]]"
  - "[[2026-05-20-testimonial-driven-cli-verification-playbook-reference]]"
  - "[[2026-05-12-cli-workflow-redesign-adr]]"
---

# CLI state-architecture research

The testimonial-driven verification surfaced a cluster of defects that
look unrelated at the symptom layer but are one architectural problem.
This document triages them past the symptoms into the architecture,
and proposes considerations for a follow-up ADR.

## The failure cluster

| Symptom | Persona | State fact underneath |
|---|---|---|
| `profile rename` -> `missing_profile_record`; source already gone | Carmen | secure-object key is `user-profile:{bucket_id}:{profile_id}` - record identity embeds physical location |
| original rename left a ghost profile | Pablo | registry mutated before filesystem; no cross-store transaction |
| `overview status` reports "no saved drafts" after `calculate` produced work units | Rosa | `overview` reconstructs state from a different store set than `modelo work` writes |
| Modelo 303 / 130 calculate to all-zero casillas with classified ledger entries present | Quim | the ledger store and the calculation bindings are not wired - `ledger_iva_aggregation` does not resolve from the ledger; `borrador_capable=False` |
| `ledger allocate` exits 0 but `business_pct` invisible in `ledger view` | Quim, Carmen | writer and reader of the same datum disagree |
| `auth test` returned an empty profile while `auth status` did not | Raul | two readers each rebuild "active profile" from a different subset of stores |
| `auth status` `configured:True` vs `health_summary:"not configured"` | Raul | "configured" derived from one signal, health from another - no single readiness model |
| `verify` -> `NO_PENDING_OBLIGATION`, nothing creates the obligation | Elena, Teo | the workflow state machine has a state with no producer |
| `modelo readiness:ready` while `verify` blocks | Terese | two readiness assessments, two answers |
| auth lock at repo-root `.tokens/`, outside `AEAT_LOCAL_STORAGE_ROOT` | (coordinator) | state scattered across independently-rooted locations |

## Diagnosis - what the cluster actually is

These are not ten bugs. They are one architecture: **a logical entity's
state is fragmented across many physical stores, with no aggregate that
owns it, no transaction boundary across the stores, and every reader
re-deriving "truth" from a different subset.**

A single "profile" is, concretely, all of:
1. a bucket directory on disk,
2. a manifest file (`_manifest_io`),
3. an encrypted record in a per-bucket SQLite secure-objects table,
4. a plaintext active-profile pointer file (`_bucket_pointer`),
5. a manifest-scan *computed view* (after `WorkflowState.profiles`
   was retired - this removed a store and added a derivation),
6. and, for auth, lock/token files under a separately-rooted
   `.tokens/` directory.

A "workspace" likewise spans `WorkflowState`, per-bucket transaction
catalogues, invoice catalogues, modelo work units / drafts, and the
bucket-event-history catalogue.

### 1. There is no single source of truth

`WorkflowState` + `workflow_state_repository` looks like a central
store, but it is *one of* the stores, not *the* store. Profile
membership is a manifest-scan derivation; the profile record is in
secure-objects; the active pointer is a separate file. No object owns
"the profile" across all six locations. So a mutation is correct only
if it remembers to touch every store - and `rename` did not.

### 2. Identity is coupled to physical location

The smoking gun: the secure-object key `user-profile:{bucket_id}:
{profile_id}`. The *same logical record* is addressed differently
depending on which bucket directory it sits in. Move the directory and
the record becomes unaddressable. A stable entity must have a
location-independent identity; here it does not.

### 3. No transaction boundary across stores

`rename` mutates the DB record, then moves the directory, then
rewrites the manifest, then the pointer. Any step can fail mid-way -
the original ghost (registry ahead of filesystem) and the broken-record
(record keyed to the old location) are both partial-write states.
There is no unit-of-work spanning SQLite + filesystem + pointer.

### 4. Readers each reconstruct truth independently

`overview`, `auth status`, `auth test`, `modelo readiness`, and
`verify` each load a different subset of stores and compute their own
view. So they disagree: `overview` cannot see work units `calculate`
wrote; `auth test` and `auth status` answered differently; `readiness`
said ready while `verify` refused. There is no single canonical
read-projection that all surfaces consume.

### 5. State *domains* are not integrated

The deepest symptom (Quim): you classify six transactions into the
ledger, then `calculate` Modelo 303/130 and every casilla is zero.
The ledger domain and the calculation domain each have coherent
internal state, but the binding layer that should aggregate ledger
facts into modelo casillas does not resolve from the ledger
(`borrador_capable=False` on every IVA binding). Two state islands
with no bridge - the user's data never reaches the computation that
needs it.

### 6. Events are an audit log, not the state model

There is a real event system (`bucket-event-history`,
`BucketEventType`, `append_bucket_event`). But events are *appended
alongside* state writes as an audit trail - they are not the source
of state. This is event-logging, not event-sourcing. Consequence:
the events cannot enforce consistency (they are a parallel write that
can itself drift - cf. the apex ADR's R20 "three event types absent
from the enum"), and rebuilding state from events is not possible.

## Answering the explicit questions

- **Why isn't state applied consistently?** Because no aggregate owns
  a logical entity across its physical stores; each operation writes
  the stores it happens to know about. Consistency is by convention,
  not by construction.
- **Is there no centralized state management system?** There is a
  *partial* one (`WorkflowState`). It is not authoritative: manifest,
  secure-objects records, pointer files and the token dir live outside
  it. Retiring `WorkflowState.profiles` moved profile membership *out*
  of the central store into a derivation - the opposite of
  centralising.
- **Is this an event issue?** No - or rather, the event system is
  mis-cast. Events here are audit, not truth. An event-sourced design
  (events are the source; state is a projection) would dissolve the
  multi-store-drift class entirely; the current design gets the cost
  of an event system without the consistency benefit.

## Actionable architecture considerations (for a follow-up ADR)

1. **Define the aggregate boundary.** A `Profile` (and a `Workspace`)
   is one aggregate with one repository that owns *all* its physical
   stores. Every mutation goes through it; no surface writes a store
   directly.
2. **Location-independent identity.** Drop `bucket_id` from the
   secure-object key (or make the key a stable UUID). A record's
   identity must not change when its directory moves.
3. **A unit-of-work across stores.** Rename / configure / create must
   be atomic across SQLite + filesystem + pointer, or carry a defined,
   tested rollback. The rename fix's ad-hoc rollback should become a
   general mechanism, not a per-command patch.
4. **One canonical read-projection.** A single function builds the
   profile/workspace view; `overview`, `status`, `readiness`,
   `verify`, `auth status` all consume it. No surface re-derives.
5. **Bridge the ledger and calculation domains.** The binding layer
   must actually resolve modelo casillas from ledger/invoice facts;
   `borrador_capable` should be true once the bridge exists. This is
   the highest-user-value gap - without it the product computes
   nothing from the user's own data.
6. **Decide event-sourcing vs event-log explicitly.** Either commit
   to events-as-source (state becomes a rebuildable projection -
   consistency by construction) or keep events as audit and give the
   mutable stores their own integrity guarantees (a cross-store
   validator run at read time, generalising `assess_active_profile_
   health` to every state type).
7. **One state root.** `AEAT_LOCAL_STORAGE_ROOT` must root *every*
   store including the token/lock dir, or the isolation contract -
   relied on by tests and by the persona harness - is silently false.

## Next step

This research should produce an ADR (`state-architecture` /
`state-consolidation`) under the vaultspec pipeline, cross-referenced
from the apex CLI ADR. The aggregate-boundary and ledger-to-calculation
bridge (considerations 1 and 5) are the load-bearing decisions and
should be sequenced first.
