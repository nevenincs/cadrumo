---
tags:
  - '#exec'
  - '#current-schema-only-purge'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:42290cb8ef17bd34c9aa9cc678bf716af58a2bed893562882c979c2bc4a13a5d'
step_id: 'S12'
related:
  - "[[2026-08-10-current-schema-only-purge-plan]]"
---

# Require explicit current encrypted-bundle envelope payload and KDF markers

## Scope

- `src/cadrumo/application/user_profile/_bundle_encryption.py`

## Description

- Drop the defaults from all three transport markers so each is required.
- Stamp every marker explicitly at the encryption writer.
- Replace the transport envelope's ceiling check with exact equality.
- Name the payload-model and KDF literals as constants instead of repeating
  them at the writer and again at each gate.

## Outcome

Landed in `7ad5cc3` with its proof step.

The row named the envelope version, and the same defect turned out to sit on two
sibling fields of the same record: `payload_model` and `kdf` each carried a
default equal to the value their own gate compares against, so each gate was
blind to an envelope omitting its key. Closing one of three would have left the
record in a state where the reason the fix was needed still applied to it. All
three were closed together.

The transport version gate moved from a ceiling to exact equality, and the reason
it differs from the PAYLOAD gate a few lines away is the substance of this step.
The payload version is checked against a floor-to-current range that carries a
per-hop upgrader chain, so an older payload has a defined route forward and the
range is built to widen once the floor freezes; it is single-valued today only
because the floor still equals the current version. The transport envelope has no
floor, no upgrader chain and no lineage enrolment, so nothing could carry an
older layout forward -- accepting one means reading bytes under a structure this
build does not implement. A ceiling admitted every older envelope, which is the
direction with no recovery behind it.

## Notes

The payload-lineage machinery was confirmed untouched: the supported-version set,
the durability floor, the current-version constant, the upgrader registry and the
unreadable-version refusal are all forward-only controls the governing
compatibility decision keeps, and the file that owns them is not in this commit.
That set membership LOOKS like a pre-current tolerance is precisely why it was
checked rather than assumed.

`kdf_version` was deliberately NOT gated. It routes nothing -- the derivation
reads the salt and the cost parameters and never consults the version -- so a
gate would need the Argon2 version promoted onto the master-key package facade
first. That is a real gap and it is rowed separately rather than taken here,
because reaching into the KDF parameter record is the owner-gated boundary two
other rows of this plan are already held on.
