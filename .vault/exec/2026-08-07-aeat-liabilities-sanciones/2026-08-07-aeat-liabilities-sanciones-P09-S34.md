---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:dd664a624a2878378cc9c561ca82a863138e3a541a022ee24833573c53fe3d1a'
step_id: 'S34'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---

# Make a document in which no label matches report explicitly unparsed and refuse to return a record of zeroes or a clean empty result, verified by a regression feeding an unrelated PDF and asserting the refusal, paired with the standing lesson that this reader has twice returned a silent zero against populated data

## Scope

- `src/cadrumo/adapters/inbound/notificacion/_sancion.py`

## Description

- Confirm a document in which no label matches refuses rather than returning a zeroed or empty record.
- Confirm the refusal names every missing, malformed and ambiguous field and is localised.
- Correct the payable selection so a printed zero is read as stated rather than discarded.

## Outcome

The refusal contract was already delivered and holds: an unreadable document names every failing field through a localised refusal, never a partial or zero-filled record, and the service preserves the refusal beside the retained bytes rather than swallowing it.

What this record adds is a defect found inside that contract during review. The payable was selected with a truthiness fallback, and a zero Decimal is falsy. Two consequences on a figure a taxpayer pays: a document printing a zero payable and no secondary line refused as unread though it had been read correctly, and a document printing both lines bound the payable to the secondary figure, inverting the precedence the record's own docstring states. The selection is now an explicit presence check, regressed in both printed layouts plus a secondary-only zero, with a companion test pinning that a genuinely absent payable still refuses - the fix widened what is accepted without relaxing the refusal.

## Notes

The zero-payable case is a real served act, not a synthetic one: a sancion whose reducciones absorb it entirely leaves nothing to pay. The regression fixture reconciles arithmetically rather than leaning on a zero base, so it exercises the reader rather than a degenerate shortcut.

Recorded retrospectively for the delivered half; the payable correction is this session's work.
