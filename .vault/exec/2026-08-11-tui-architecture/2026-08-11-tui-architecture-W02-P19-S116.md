---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:bb8ce40a24f68987631d70df5ffa5472c32474c6b5a803cccc3b518efd9628e8'
step_id: 'S116'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---
# Define the strict current-only operation observation, public projection, event-page, REVIEW-projection, response-control, cancellation, detach, and Workspace-refresh request, success, and typed refusal DTO families with independent V1 dispatch axes

## Scope

- `src/cadrumo/application/operations/_public.py`
- `src/cadrumo/application/operations/_registry.py`
- `src/cadrumo/application/operations/_models.py`
- `src/cadrumo/application/operations/__init__.py`
- `src/cadrumo/application/operations/tests/test_public_contracts.py`
- `src/cadrumo/application/operations/tests/test_facade.py`

## Description

- Ground the DTO boundary in accepted D0, D2, D7, and D10 clauses and the live S115 schema-contract implementation.
- Define strict unspecialized endpoint version headers plus current-only request, success, and closed typed-refusal families for observation, safe REVIEW projection, response-control availability, cancellation, detach, and Workspace refresh.
- Define a renderer-neutral anchored public projection, safe event-row union, bounded event page, progress record, and closed pending-interaction union.
- Keep endpoint version axes independent and exclude response bearers, private interaction checkpoints, custody material, raw journal records, raw events, lease evidence, callbacks, and frontend types.
- Enforce terminal, pending-interaction, cancellation, deadline, contract-declaration, progress, replay, and resynchronization consistency at the DTO boundary.
- Remove serializer-driven digest normalization from the S115 public definition contract and preserve deterministic digests through one explicit canonical value builder, allowing validation and serialization schemas to remain identical.
- Reuse the canonical terminal result/refusal invariant from `_models.py` instead of redeclaring it in the public terminal event.
- Export the DTO family only through the canonical `cadrumo.application.operations` facade and extend its topology gate.
- Construct public projection fixtures only through a real immutable operation registry, public definition registration, schema bindings, and contract set; exercise anchor, lifecycle-terminal-pending, timeline, deadline, cancellation, and contract-axis refusals adversarially.
- Run post-edit semantic and exact-symbol censuses for shadow observation, REVIEW, response-control, cancellation, detach, refresh, terminal, and digest authorities.

## Outcome

The sole canonical public DTO home is `_public.py`. Its closed unions preserve independent lifecycle, terminal-condition, and effect truth; bind observation pages to one anchor; enforce contiguous replay and resynchronization cursors; specialize REVIEW and refresh successes by exact registered models; and expose response availability without a bearer. Minimal headers support endpoint-specific unsupported-version dispatch without accepting retired exact request shapes. The facade remains the only public import path.

Every exported S116 Pydantic model, including the full projection, nested pending interactions, and every safe event variant, now passes the strict frozen closed-model graph and exact schema fingerprint gates. S115 contract digests remain deterministic without a field serializer or a second normalization authority. Projection conformance uses no direct test `model_construct` path.

Verification passed: 255 selected unit tests and 61 integration tests across the complete operation package, Ruff, basedpyright, Python compilation, and the repository import-hygiene scanner. Semantic fixed-point censuses and exact symbol sweeps found no second production declaration of any new DTO family; the one duplicated terminal invariant they exposed was deleted in favor of the canonical `_models.py` function.

## Notes

The existing facade still exports private supervisor-era snapshots, raw events, replay records, interactions, journal ports, and lease contracts. They remain live implementation authorities in this step and are mandatory S121/S122 cutover/deletion work; S116 does not create aliases for them or widen into service deletion. Supervisor aliases and direct manager execution doors remain mapped to S119-S122, S76-S78, and S157. The import-hygiene scan also reports unrelated standing tree findings outside this step; it exited successfully and found no new production cross-package private import or re-export bridge from S116.

## Remediation attestation

### Ordered implementation and remediation commit tuple

The reproducible code tuple is `66e4a30d48a694175b9f8e61b75cf340afd400cb` (initial public boundary), then `1778e2f7285037d68e6c88bf3367d2c0e660a996` (public-model and registry wiring), then `4967ef8220080aa4de32ab753f3b7679f37301ee` (S116 invariant remediation and direct witnesses captured as a shared S120 antecedent). The earlier documentation-only `7b9085e7b35beb570c9c7a0119d5c7c7a2e754bf` predates that tuple and is not treated as producing evidence.

The present finalization changes only control-flow type narrowing in the same public validator; it preserves the remediated semantics and has no additional DTO, registry, service, or frontend authority.

### Source-tree and verification evidence

The remediated source hashes are SHA-256 `1BB5D9FB690E244A0AD58BF950E5010AF9B5CCCA30F399AB9A5690E3E0DBDA23` for `src/cadrumo/application/operations/_public.py` and `AAA319F1ADD45E30C08A3F65C7C9F71B57800200E988AB51F1B70E4BCA363510` for `src/cadrumo/application/operations/tests/test_public_contracts.py`.

The public boundary now refuses a caught-up page whose requested, anchor, and next cursors disagree; any event row newer than its projection; progress whose phase differs from the current phase; pending interactions outside the waiting lifecycle, at a stale revision, or absent from the definition contract; and cancellation availability after request or during settlement. Direct adversarial witnesses cover every relation.

Scoped evidence passed: Ruff; basedpyright with zero errors; `test_public_contracts.py` (60 passed); the observation, projection-service, facade, and registry slice (58 passed); and the complete operation package suite (271 passed). A fresh Vaultspec RAG-plus-exact declaration census found `_public.py` remains the sole public DTO/invariant home, while `_model_contract.py` remains the sole strict-model graph authority. The independent follow-up review accepted the remediation with no new finding.
