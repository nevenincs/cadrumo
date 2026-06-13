---
tags:
  - '#adr'
  - '#draft-approval-staleness'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-research]]'
  - '[[2026-04-17-export-first-adr]]'
---

# `draft-approval-staleness` adr: `persist status-level draft approval and derive stale transitions from approval-basis fingerprints` | (**status:** `accepted`)

## Problem Statement

Issue #230 requires Kent to approve a draft and later trust that the system will
detect when that approval is no longer valid. The current branch persists filing
drafts in JSON, but it does not persist review approval metadata and it has no
deterministic way to invalidate an approval when the underlying transaction
catalogue, category mappings, or schema/formula context change.

## Considerations

The existing `draft_id` in `src/aeat/application/filing/_schema.py` is intentionally scoped
to the filing payload. It is stable and useful, but it is not broad enough to
represent the full review surface. The live-submit checksum in
`src/aeat/adapters/outbound/aeat/export/_confirm.py` is likewise deterministic but remains
submission-oriented and draft-local.

The branch already exposes the upstream state surfaces that can invalidate an
approval:

- filing payload identity and validation outcome in `src/aeat/filing`
- transaction catalogue content and semantic classification state in
  `src/aeat/domain/financial/transactions`
- category profile mappings in `src/aeat/domain/financial/categories`
- casilla schema and formula/ruleset context in `src/aeat/filing` and
  `src/aeat/formulas`

The review decision therefore needs a persisted provenance object that can be
recomputed against those same surfaces later. The resulting stale signal must
remain compatible with current JSON draft persistence, existing
`READY_TO_SUBMIT` flows, and later review/export work already called for in the
roadmap.

## Constraints

Drafts are persisted as plain JSON files under `Settings.aeat_drafts_dir`, so
the new review state must serialize cleanly without database migration support.
Existing drafts on disk must keep loading after the change. The solution must
avoid coupling the new review state to any live-write surface; stale detection
belongs to review and draft inspection only on this branch.

Tests must exercise real draft and transaction behaviour without mocks or
tautological state manipulation.

## Implementation

Approval provenance is embedded directly on `FilingDraft` rather than stored in
a sidecar file. `FilingDraftStatus` is extended with `APPROVED` and
`APPROVAL_STALE`, and `FilingDraft` gains these persisted approval fields:

- `approved_at`
- `approved_by`
- `review_checksum`
- `approval_basis`

`approval_basis` is a structured object with canonical component digests:

- `draft_payload_fingerprint`
- `draft_review_fingerprint`
- `transaction_catalogue_fingerprint`
- `category_profiles_fingerprint`
- `schema_formula_fingerprint`

The canonical fingerprints are defined over semantic state, not incidental file
bytes or timestamps. In particular, the transaction-catalogue fingerprint is
computed from a normalized projection of the transactions and their filing-meaningful
classification state rather than from raw JSON bytes or mutable audit fields
such as operator timestamps.

`draft_review_fingerprint` is defined only from the pre-approval validation
surface: the normalized machine filing status together with the sorted
validation findings that existed before approval. It must exclude approval
metadata, approval state, review checksums, and any stale marker so the stale
check cannot become self-referential.

`schema_formula_fingerprint` is defined from stable provenance for the active
casilla collection plus the resolved formula/ruleset identity used for the
draft's `modelo` and period. `schema_version` alone is insufficient.

Machine validation continues to derive the pre-review statuses `DRAFT`,
`VALIDATED`, and `READY_TO_SUBMIT` exactly as today. Review then adds two
explicit lifecycle transitions:

- `aeat review approve` transitions `READY_TO_SUBMIT -> APPROVED`
- any approval-basis mismatch transitions `APPROVED -> APPROVAL_STALE`

`aeat review unapprove` removes the approval fields and restores the machine
validation status implied by the current findings. Staleness is defined exactly
as any approval-basis fingerprint mismatch against the current recomputed basis
for the same draft, including the case where the current validation surface no
longer implies `READY_TO_SUBMIT`. `review_checksum` is the digest of the
canonical serialized `approval_basis`, and it exists as the single top-level
approval token. It is not reused from the live-submit checksum.

Existing JSON drafts receive no backfill. Missing approval fields deserialize as
`None` and therefore behave as unapproved. They must never be auto-upgraded into
an approved state by validation or load paths. Re-approving the draft writes a
full approval record using the current basis and replaces any stale approval
record.

Verification must cover:

- approval persistence round-trip through JSON draft storage
- stale detection after transaction catalogue mutation
- stale detection after category or schema/formula basis changes
- preservation of existing non-approval validation flows
- filing/review CLI visibility of stale approvals without any write-path
  integration

## Rationale

Embedding approval provenance on `FilingDraft` keeps the review decision tied to
the persisted artifact that operators actually inspect and submit. A sidecar
file would introduce lookup and coherence problems without solving any real
branch constraint.

Using explicit `APPROVED` / `APPROVAL_STALE` lifecycle states satisfies the
issue #230 and umbrella #202 contract directly, keeps the CLI observable state
simple for Kent, and still preserves the machine-validation meanings of
`DRAFT`, `VALIDATED`, and `READY_TO_SUBMIT` for non-review flows.

Using a decomposed approval basis is stronger than a single ledger timestamp
because it does not depend on one globally maintained clock and it can explain
which review surface drifted. It is stronger than reusing the live-submit
checksum because it captures upstream state changes even when the draft payload
has not yet been rebuilt.

## Consequences

The implementation must add stable normalization helpers for every approval-basis
surface and thread review-state checks into the filing/review CLI surfaces. This
is more work than a timestamp flag, but it is the minimum needed for
deterministic stale detection.

Because stale state is derived from approval-basis mismatch, any command that
surfaces approval validity must recompute the current basis before trusting a
stored approval record. That adds predictable read-time work, but it avoids
silent drift and keeps stale detection correct.

Existing drafts remain usable without migration, but they will load as
unapproved until explicitly approved on the new branch. Future review work can
build on the same approval-basis model without redefining the filing identity
model or changing `draft_id`.
