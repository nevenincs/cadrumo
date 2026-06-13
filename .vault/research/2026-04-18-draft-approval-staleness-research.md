---
tags:
  - "#research"
  - "#draft-approval-staleness"
date: "2026-04-18"
modified: '2026-04-18'
related:
  - "[[2026-04-17-export-first-adr]]"
  - "[[2026-04-17-export-first-roadmap-plan]]"
---

# draft-approval-staleness research: draft approval persistence + deterministic stale detection

Research note for issue #230. Scope is limited to persisted draft approval
state and deterministic stale detection across filing/review/submission and the
transaction/category state surfaces already present on this branch. This note
documents the current branch behavior, the main change vectors that can invalidate
an approved draft, candidate detection strategies, and the recommended direction.

## current branch state

`src/aeat/application/filing/_schema.py` defines `FilingDraftStatus` with `DRAFT`,
`VALIDATED`, `READY_TO_SUBMIT`, `SUBMITTED`, `ACKNOWLEDGED`, `REJECTED`,
`AMENDED`, and `CANCELLED`. `FilingDraft` persists `draft_id`, `modelo`,
`period`, `profile_tax_id`, `status`, `values`, `findings`, timestamps,
`schema_version`, and `notes`. There are no approval fields such as
`approved_at`, `approved_by`, `approval_basis`, or `review_checksum`.

`src/aeat/application/filing/_schema.py` also makes `draft_id` content-addressed over
`(modelo, period, profile_tax_id, schema_version, values)`. This is stable for
the draft payload itself, but it is intentionally narrower than the full review
surface: it does not capture transaction catalogue state, category-profile
state, or formula/ruleset state outside the stamped `schema_version`.

`src/aeat/application/filing/_builders/modelo_130.py`,
`src/aeat/application/filing/_builders/modelo_303.py`, and
`src/aeat/application/filing/_builders/modelo_390.py` stamp `schema_version` from the
casilla collection and derive the `draft_id` from the built values. This means
builders already expose one deterministic version vector for the filing schema,
but they do not persist any explicit review basis beyond the draft payload.

`src/aeat/application/filing/_validator.py` validates a draft and emits findings. The
validator can warn on schema-version mismatch, but it does not persist approval
state and it does not mark an existing draft as stale. `apply_validation`
currently promotes drafts only through the pre-approval path
`DRAFT -> VALIDATED -> READY_TO_SUBMIT`.

`src/aeat/entrypoints/cli/filing/__init__.py` persists drafts as JSON under
`Settings.aeat_drafts_dir`. `src/aeat/application/filing/_complementaria.py` reloads the
original draft from the same JSON directory when building an amendment. Any
approval persistence scheme therefore has to survive plain JSON round-trips and
remain usable by amendment reload paths.

`src/aeat/adapters/outbound/aeat/export/_preflight.py` requires `READY_TO_SUBMIT` and checks only
error findings, deadline window, and certificate load. There is no approval
gate and no stale-approval gate. `src/aeat/adapters/outbound/aeat/export/_protocols.py` keeps a
submission-local `DraftStatus` shim with only `DRAFT`, `INCOMPLETE`, and
`READY_TO_SUBMIT`, and `src/aeat/application/workflow/_engine.py` assumes the same
`READY_TO_SUBMIT` hand-off. Approval support is therefore not yet threaded
through the submission and workflow boundary types.

`src/aeat/adapters/outbound/aeat/export/_confirm.py` computes a live-submission checksum from the
current draft payload, including status and findings, and uses it only to build
the operator confirmation phrase for a live AEAT write. This checksum is
submission-specific and is not stored as review provenance.

`src/aeat/domain/financial/transactions/_models.py` gives transactions a
content-addressed `transaction_id` derived from raw transaction fields.
Classification updates in `src/aeat/domain/financial/transactions/_service.py` mutate
semantic classification state and also touch `classified_at` and
`classified_by`. The catalogue is persisted as JSON via atomic save/load
helpers, but there is no catalogue-level fingerprint or review snapshot.

`src/aeat/domain/financial/categories/_registry.py` and
`src/aeat/domain/financial/categories/_corpus.py` expose category-profile mappings.
The public loader currently returns `CATEGORY_PROFILES_2025` for 2025. Filing
builders already stamp the casilla-schema version, but there is no separate
fingerprint for the category mappings that drive transaction-to-casilla
aggregation.

The product direction already expects this gap to close. The export-first ADR,
the revise/review audit, and `ROADMAP.md` all call for persisted approval
metadata and an `APPROVAL_STALE` path when transactions, profiles, formulas, or
other filing inputs change after review.

## change vectors that can invalidate an approved draft

The branch already exposes four distinct change vectors that matter for issue
#230:

- Draft payload changed: the filing values themselves differ because the user
  rebuilt the draft, edited inputs, or loaded a different draft instance for
  the same modelo and period.
- Transaction catalogue changed: new transactions arrived, raw transaction
  fields changed, or transaction classifications changed in a way that affects
  aggregation.
- Category-profile state changed: the category registry or public loader now
  maps the same transaction set differently into AEAT casillas.
- Schema or formula context changed: the casilla collection version moved, or
  formula logic changed without the currently persisted approval record being
  refreshed.

These vectors are not equivalent. A useful approval record has to identify
which surface moved, not just that "something" changed.

## candidate stale-detection strategies

### strategy A: single global ledger timestamp

Persist one "last reviewed at" timestamp on the draft and compare it against one
global "ledger updated at" timestamp gathered from the local state.

This is operationally simple, but it is the weakest option on this branch.
There is no single monotonic state owner across `src/aeat/filing`,
`src/aeat/domain/financial/transactions`, `src/aeat/domain/financial/categories`, and the
formula/schema surfaces. A timestamp approach becomes correct only if every code
path that can affect review validity remembers to bump the same clock. The
current branch does not have that invariant.

It also cannot explain why a draft went stale. A changed transaction catalogue,
an updated category registry, and a formula revision all collapse into the same
"timestamp moved" result. That makes review diffing and debugging weak. It is
also prone to false positives from metadata-only writes and false negatives when
versioned files change without updating the chosen timestamp source.

### strategy B: reuse the live-submission checksum

Reuse `src/aeat/adapters/outbound/aeat/export/_confirm.py:compute_draft_checksum()` as the stored
review checksum and compare it during review/export.

This is stronger than a single timestamp because it is deterministic, but it is
still weaker than the approval problem requires. The live-submission checksum is
explicitly designed for operator confirmation of the current filing draft. It
normalizes the current draft status, values, and findings. It does not capture
the transaction catalogue, category profiles, or a dedicated schema/formula
basis outside what already made it into the current draft payload.

That means it misses important stale vectors. A transaction catalogue can
change, or category mappings can change, before the draft is rebuilt. In that
state the approval should be stale, but the live-submit checksum of the old
draft payload would still match. The checksum is also coupled to
submission-oriented fields such as `status` and `findings`; once approval adds
new statuses or review-only metadata, the meaning of the checksum becomes noisy
and self-referential.

### strategy C: persist a decomposed approval basis with separate fingerprints

Persist approval metadata on `FilingDraft`, including an `approval_basis`
object that stores independent fingerprints for:

- draft payload
- transaction catalogue
- category profiles
- schema/formula context

Then derive `review_checksum` from the canonical serialized `approval_basis`
object rather than from the live-submission payload.

This is the strongest option because it matches the actual invalidation
surfaces already present on the branch. It is deterministic, explainable, and
compatible with JSON persistence. It also gives the future review surface a
natural way to say exactly what changed: payload, catalogue, profiles, or
schema/formulas.

Its main cost is that the project must define stable normalization functions for
each fingerprint. That is real work, but it is the right work for issue #230:
the problem is not "compute a hash somewhere", it is "persist the exact basis
Kent approved and compare it against the same basis later".

## tradeoffs and design notes

The recommended direction should keep `draft_id` stable and separate from review
provenance. `draft_id` already answers "is this the same filing payload?" It
should not be overloaded to answer "is this approval still valid?" because
approval validity depends on more than the filing payload.

The transaction-catalogue fingerprint should be semantic, not merely bytewise
over the saved JSON file. On this branch, JSON persistence also carries audit
fields such as `classified_at` and `classified_by`. The fingerprint should be
defined over the state that can change filing meaning, not over incidental file
ordering or save timestamps. The branch already gives a good starting point:
`transaction_id` is content-addressed from raw transaction fields, and manual
classification state is explicit.

The category-profile fingerprint should be separate even though builders already
stamp `schema_version`. The current `schema_version` comes from the casilla
collection. Category mappings are a different change surface. A profile change
can invalidate the aggregation basis even when the casilla schema does not move.

The schema/formula fingerprint should remain separate from the category-profile
fingerprint. This branch already distinguishes between the filing schema
collection and the financial category registry. Future formula-rule changes may
need to invalidate approvals even when the category registry stays fixed.

A decomposed approval basis is also better for branch compatibility. The
existing workflow and submission code still assume `READY_TO_SUBMIT`, so issue
#230 should persist review provenance first and let later review/export work
thread new statuses through `src/aeat/adapters/outbound/aeat/export/_protocols.py` and
`src/aeat/application/workflow/_engine.py`. Persisted basis data is useful immediately and
does not require `draft_id` churn.

## recommended direction

Persist approval metadata directly on `FilingDraft`. The minimum persisted shape
should include:

- `approved_at`
- `approved_by`
- `approval_basis`
- `review_checksum`

`approval_basis` should be a structured object with four independent
fingerprints:

- `draft_payload_fingerprint`
- `transaction_catalogue_fingerprint`
- `category_profiles_fingerprint`
- `schema_formula_fingerprint`

`review_checksum` should be derived from the normalized `approval_basis`
serialization, not from the live-submit checksum and not from a global timestamp.
That gives one deterministic top-level token for review approval while retaining
the per-surface breakdown needed for stale diagnostics and future `review diff`
output.

The branch-compatible rule is:

- Build and validate drafts exactly as today through `READY_TO_SUBMIT`.
- Persist approval metadata after review as a separate concern from draft
  construction.
- Recompute the current approval basis on review, export, and any explicit
  "check stale" surface.
- Mark the approval stale whenever any stored fingerprint differs from the
  current fingerprint for the same surface.

This recommendation is stronger than a single ledger timestamp because it does
not rely on one mutable global clock and it tells the user which review surface
moved. It is stronger than reusing the submission live checksum because it
captures upstream transaction, profile, and schema/formula changes even before a
draft rebuild happens, and it keeps review provenance decoupled from
submission-only confirmation behavior.

## conclusion

Issue #230 should be treated as a persisted provenance problem, not as a UI-only
approval toggle. The branch already has deterministic identifiers for drafts and
transactions, JSON persistence for local state, and explicit roadmap pressure to
detect stale approvals. The missing piece is a persisted approval basis that
matches the real invalidation surfaces.

The recommended direction is therefore:

- persist approval metadata on `FilingDraft`
- store an `approval_basis` object with separate fingerprints for draft payload,
  transaction catalogue, category profiles, and schema/formula context
- derive `review_checksum` from that basis

That gives deterministic stale detection, clear future diff semantics, and a
path that remains compatible with the branch's current `READY_TO_SUBMIT`
handoff while review/export work is still being threaded through the workflow
and submission boundaries.
