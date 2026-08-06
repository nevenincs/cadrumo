---
tags:
  - "#adr"
  - "#google-optional-adapter-boundary"
date: '2026-07-14'
related:
  - "[[2026-07-14-google-optional-adapter-boundary-research]]"
  - "[[2026-07-14-google-optional-adapter-boundary-reference]]"
  - "[[2026-07-14-google-oauth-audit]]"
  - "[[2026-07-12-google-oauth-adr]]"
  - "[[2026-06-30-bucket-custody-completeness-adr]]"
  - "[[2026-06-10-ledger-evidence-enforcement-adr]]"
  - "[[2026-06-26-binding-vocabulary-cli-cohesion-adr]]"
  - "[[2026-06-03-modelo-export-workbook-parity-adr]]"
  - "[[2026-07-04-google-sa-impersonation-adr]]"
  - "[[2026-05-14-ledger-transaction-lifecycle-adr]]"
supersedes:
  - '2026-06-04-ledger-google-live-export-adr'
modified: '2026-07-17'
body_hash: 'sha256:5b7bc6c874b88b838fed87a77edd851036cc5c452da85a728cf7e62cb91b29c7'
---
# `google-optional-adapter-boundary` adr: `Google integration authority boundary and legacy-scope reconciliation` | (**status:** `accepted`)

## Problem Statement

Six Google architecture decision records (ADRs) accepted in May assigned
independent responsibilities to the optional Google integration. Those
responsibilities included key custody, restore, watched ingestion, domain
export, reverse-merge taxonomy, and persisted calculation mutation. The shipped
system instead composes Google access over existing local authorities. Without
a successor, those formerly accepted descriptions turn obsolete mechanisms
into apparent implementation backlog and invite duplicate repositories,
recovery formats, and write paths.

This ADR decides the shared authority question. It does not approve six
replacement features or treat historical plan structure as a product mandate.
An open Google plan row is genuine work only when it closes a verified gap in
the constrained adapter role established here.

## Considerations

- OAuth Desktop and service-account impersonation already exist. The secure
  repository persists OAuth client, token, and session records plus the
  per-profile credential-source selection. The provider factory mints
  impersonated access tokens per use. Another authentication, session, or
  provider layer would duplicate shipped code.
- The Drive mirror uploads ciphertext and reads remote objects and manifests to
  verify integrity and revision lineage. It is non-authoritative, not
  write-only.
- Complete recovery is already owned by the provider-neutral sealed
  full-custody archive. Google-specific key escrow and row-by-row restoration
  are absent and would duplicate that mechanism.
- `ledger doclink` and `ledger pull-folder` already acquire operator-selected
  Drive bytes and persist them through canonical encrypted attachment custody.
  Only `doclink` also delegates to the ledger evidence linker. A broad claim
  that Google never causes a local write would therefore be false.
- Calculation Sheets already supports export, parity verification, typed pull,
  and shared-engine computation. Pull returns typed input; compute persists
  nothing and does not make Google Sheets authoritative for calculation or
  filing.
- Ledger correction already uses `ledger update` and the canonical application
  writer, including its lineage and bucket-event behavior.
- The related Reference binds these findings to the audited implementation.
  The related research and audit distinguish implemented value from obsolete
  mechanism choices.

## Considered options

1. **Complete every legacy Google phase.** Rejected because it would create a
   second recovery architecture, watched-ingestion coordinator, and parallel
   domain mutation paths.
2. **Edit only the plan and leave every old ADR accepted.** Rejected because the
   contradictory architecture would remain authoritative and recreate the
   false backlog.
3. **Adopt one optional-adapter authority boundary and supersede the conflicting
   records.** Accepted because one decision resolves the shared authority error
   while preserving useful shipped behavior under its canonical owners.
4. **Write separate Google recovery, inbound, ledger, and calculation-mutation
   replacements.** Rejected because those would imply four new product
   initiatives where the evidence supports one scope reconciliation.

## Constraints

- Google integrations are opt-in interoperability adapters. Each profile uses
  its approved credential source: OAuth Desktop or service-account
  impersonation. The local encrypted bucket, calculation registry,
  provider-neutral sealed full-custody archive, and canonical application
  services remain authoritative under this decision unless a later ADR
  explicitly supersedes it.
- A Google command may persist data only by delegating to the existing canonical
  owner. This permits the secure OAuth store and explicit evidence acquisition;
  it prohibits an independent Google domain writer.
- Remote manifest reads, ciphertext inspection, conflict detection, and
  integrity comparison remain permitted. The remote mirror does not own
  restoration, key custody, or local writes.
- `doclink` and `pull-folder` remain explicit, byte-bearing evidence acquisition
  paths. This ADR does not mandate a watched Drive inbox, automatic filename
  router, plaintext staging pipeline, or rejection-sidecar subsystem.
- Calculation `pull` remains typed readback, and `compute` remains
  non-persistent computation through the shared engine. Persisting pulled Sheet
  input requires a separate ADR and delegation to the canonical calculation
  writer.
- Ledger mutation remains Google-independent and uses the canonical ledger
  lifecycle.
- This ADR neither approves nor rejects provider-neutral watched ingestion,
  remote transport of the sealed full-custody archive, bulk correction, or
  worksheet adoption. The owning domains must decide those features instead of
  inheriting them from the Google plan.
- The related accepted ADRs own credential selection, the remote manifest
  mirror, the sealed full-custody archive, encrypted evidence, workbook parity,
  typed binding transport, and ledger mutation. These shipped implementations
  provide the interfaces and authority boundaries this decision depends on.
  This ADR does not replace them.
- This ADR authorizes no production-code addition, compatibility shim, new
  repository, command, recovery format, or write path.

## Implementation

This ADR reconciles the architecture corpus and Google plan to one boundary.
Google may use the approved per-profile credential source, export ciphertext
and typed projections, inspect remote integrity state, acquire
operator-selected evidence bytes, and return typed worksheet input. Domain
persistence must pass through the canonical service that owns that data.

The following implemented behavior remains in scope:

- existing OAuth Desktop with secure client, token, and session storage;
- persisted per-profile credential-source selection, ephemeral service-account
  impersonation, and provider composition;
- ciphertext push plus remote manifest and object integrity reads;
- explicit `doclink` and `pull-folder` acquisition through canonical attachment
  custody, with `doclink` also using the ledger evidence linker;
- calculation export, verification, typed pull, and non-persistent shared-engine
  compute; and
- canonical `ledger update` for transaction correction.

This ADR retires the following Google-owned mechanisms from architectural
scope:

- Google key escrow, per-row restore, or a second recovery format;
- a watched `_inbound` workflow and its routing or rejection machinery;
- a Google-owned per-domain export/reverse-merge taxonomy or corrections
  namespace;
- parallel ledger writers; and
- Sheet-to-work-unit or Sheet-to-calculation-revision persistence.

This ADR supersedes these records in whole while restating their surviving
outcomes through the current canonical owners:

1. `2026-05-13-google-oauth-snapshot-adr`, “Snapshot, backup, and restore with
   encryption boundary”.
2. `2026-05-13-google-oauth-inbound-adr`, “Incoming-bucket ingestion semantics”.
3. `2026-05-13-google-oauth-taxonomy-adr`, “Per-domain export taxonomy”.
4. `2026-05-13-google-oauth-calc-sheets-adr`, “Calculation-to-Sheets visual
   verification surface”.
5. `2026-05-13-google-oauth-twoway-adr`, “Two-way Sheets sync feasibility
   verdict”.
6. `2026-05-14-google-oauth-adr`, “schema-to-sheet engine and parity guarantee
   for bidirectional modelo sheets”.

The current decisions for the remote manifest, sealed full-custody archive,
evidence enforcement, workbook parity, binding vocabulary, and canonical ledger
remain in force. Supersession of the older calculation records does not remove
visual review, typed readback, or non-persistent compute.

## Rationale

The retired mechanisms share one error: they treat Google as a second
application architecture rather than as an adapter. Existing adapters already
provide optional Drive egress, integrity observation, and explicit evidence
acquisition. The provider-neutral sealed full-custody archive owns recovery.
Calculation review, typed worksheet experimentation, and canonical domain
writers retain their current responsibilities.

One authority decision removes duplication without implementing historical
mechanism choices or inventing replacement ADRs. If a future proposal persists
Sheet edits, automates ingestion, or uses Drive to transport the sealed
full-custody archive, the owning domain must issue a new ADR. That ADR must cover
the affected data and safety contract.

## Consequences

- The legacy Google plan may retire obsolete rows without claiming that their
  designs were implemented.
- Existing Google authentication and constrained workspace behavior remain
  unchanged.
- `sync push` is not a recovery workflow; complete recovery remains the sealed
  full-custody archive.
- Automatic Drive ingestion and direct remote-to-local mirror restoration are
  unavailable under this decision.
- Sheets remains useful for review, typed input, and what-if computation but
  is not authoritative for calculation or filing.
- The owning domains may reconsider provider-neutral ingestion, sealed
  full-custody archive transport, bulk correction, and worksheet adoption.
- The immediate work is architecture-corpus and plan reconciliation. No
  production-code implementation follows from this ADR.
