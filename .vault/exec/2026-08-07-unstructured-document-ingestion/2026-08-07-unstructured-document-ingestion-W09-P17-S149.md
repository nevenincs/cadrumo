---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:18f4aa10e26cd2bdc890d8ec3557608728e9fe91003530585199cf46efbea011'
step_id: 'S149'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# The exact-structured origin note: premise false, and no live surface carries it

## Scope

- `src/cadrumo/application/ledger`

## Description

- Check the row's two factual claims at HEAD before correcting anything.
- Find the enum member declared, find the accepted-origin set referencing it, and find the PRODUCER the row says is missing.
- Find the producer is no longer missing either: a production site constructs the exact-structured origin today.
- Search the live source for a note carrying the false claim, and find none.
- Locate the two surviving stale sentences, establish where they live, and decide deliberately whether to rewrite them.

## Outcome

Nothing was changed, and that is the correct outcome rather than a shortfall.

The row exists because a note read as "the taxonomy is missing a member", which would have sent a lane to the taxonomy owner for a change nobody needed — one lane nearly took that route before measuring. At HEAD the framing is doubly obsolete: the member was always there, and the producer the row correctly identified as the real gap has since landed. So the note cannot mislead anyone about a missing member, because the situation it described in either reading no longer exists.

**The correction the row asked for already exists in the right place.** A sibling execution record names the gap as a missing producer rather than a missing member. That is the authoritative statement, it is in the record that owns the finding, and it predates this row's execution.

**Two stale sentences survive, in historical execution records, and they were deliberately NOT rewritten.** An execution record states what was done and believed at the time it was written. Editing one retroactively to match a later tree does not correct the record — it destroys the record's only value, which is being a fixed account of a moment. The campaign's whole method for distinguishing delivered from delivered-narrower depends on those accounts staying fixed. So the stale sentences stay, and the correction lives forward in the sibling record and in this one, where a reader arrives by following the row.

**What this excludes.** This closes the note. It does NOT add or verify the producer, and it makes no claim about whether exact-structured origins are stamped correctly everywhere they should be. A reader wanting that should start from the producer site, not from here.

## Verification

Read directly from HEAD:

    origin=FieldOrigin.EXACT_STRUCTURED        application/ledger/_grounding_anchor.py:611
    the enum member declared                   core/_field_origin.py:40
    accepted-origin set referencing it         application/ledger/_grounded_reading.py:70

Live-source sweep for the false claim across the owning package: no match.

Surviving stale sentences, both inside historical execution records rather than source, left intact by design.

Gate run not requested: no file changed.

## Notes

Executed by this lane's Tier-2 worker under the lead's dispatch, and reported as a skip with its evidence rather than as a completion, which is the honest shape for a row whose premise expired.

This is the eighth row in this campaign found already-delivered or premise-false at HEAD. The rate is high enough that verifying the premise is now the first action on every row rather than a preliminary, and it has twice prevented a change that would have been actively wrong rather than merely unnecessary.
