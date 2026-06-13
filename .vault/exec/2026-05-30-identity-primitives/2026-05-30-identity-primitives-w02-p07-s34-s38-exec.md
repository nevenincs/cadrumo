---
step_id: S34
tags:
  - '#exec'
  - '#identity-primitives'
date: '2026-05-30'
modified: '2026-05-30'
related:
  - '[[2026-05-30-identity-primitives-plan]]'
  - '[[2026-05-30-identity-primitives-adr]]'
---

# identity-primitives W02.P07.S34-S38 — promote AttachmentId

## Scope

Declare the hex-64 `AttachmentId` alias in
`src/aeat/domain/attachments/_ids.py` per ADR Rule 6 owner-domain
placement, and lift the canonical `attachment_id` BaseModel field on
`domain/attachments/_models.Attachment` onto the alias.

## Outcome

`AttachmentId = Annotated[str, StringConstraints(min_length=64,
max_length=64, pattern=r"^[0-9a-f]{64}$")]` declared in
`src/aeat/domain/attachments/_ids.py` with an `__all__` export.

Promoted BaseModel fields:

- `src/aeat/domain/attachments/_models.py`:
  `Attachment.attachment_id`.

The `Attachment.sha256` field stays bare-str under Rule 7 (content
fingerprint, not a referential identity). The
`_enforce_attachment_id_matches_sha256` post-validator continues to
pin the equality invariant.

Real-behavior tests added at
`src/aeat/domain/attachments/test_ids.py` cover acceptance of a
canonical sha-256 hex digest, rejection of uppercase hex, rejection
of wrong-length values, and rejection of non-hex characters.

## Genuine non-canonical fields skipped

- `src/aeat/application/ledger/_models.py` (`attachment_ids: tuple[str, ...]`
  on `ManualLedgerTransactionCommand`, `ManualLedgerTransactionPatch`,
  `LedgerTransactionPayload`, `LedgerTransactionReviewPayload`,
  `LedgerTransactionRemovalReport.cascaded_attachment_ids`) — tuple
  collections of attachment references, not the canonical mint.
  Operator-supplied identifiers entering these tuples are not always
  pre-validated hex-64 (CLI input flow); the existing
  `_normalise_identifier_tuple` validator strips and dedupes without
  pattern-enforcing. Promoting `tuple[str, ...]` to
  `tuple[AttachmentId, ...]` would reject CLI input paths whose
  values arrive through the field validator's normalisation rather
  than as canonical mints. Genuine non-canonical reference family;
  skipped per the brief's "reference vs mint" discriminator.
- `src/aeat/application/evidence/_models.py` carries no
  `attachment_id` BaseModel field. The evidence bundle records
  attachments by transitive bucket-event-object references, not by
  a direct `attachment_id: str` field.

## Verification

- `uv run --no-sync pytest src/aeat/domain/attachments/test_ids.py`
  returns `4 passed`.
- `uv run --no-sync pytest src/aeat/domain/attachments/` reports
  one pre-existing failure
  (`test_blob_and_manifest_round_trip_without_plaintext_files` —
  privacy / encryption regression unrelated to type aliases,
  inventoried in the W01.P03.S14 record).

## Plan steps closed

`W02.P07.S34`, `S35`, `S36`, `S37`, `S38`. S36 (`application/evidence/_models.py`)
and S37 (`application/ledger/_models.py`) landed as no-ops — neither
surface carries a singular `attachment_id` BaseModel field; the
attachment-references they expose are tuple-typed collections
captured above as genuine non-canonical references. S38 standalone
roundtrip test would duplicate the existing
`domain/attachments/test_repository.py` coverage that already
exercises `Attachment` persistence; the typed alias is now in force
on every test that constructs an `Attachment`.
