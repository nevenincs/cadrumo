---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:30c98b794fadf27c58ac9f8534e2e63d9ce361b3fd39a557b6e706d009c9aa1b'
step_id: 'S128'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Correct the prose claiming the place-of-supply articles are unbundled

## Scope

- `src/cadrumo/domain/iva`

## Description

- Verify the claim before correcting it, rather than trusting the row. Confirm the three place-of-supply articles are bundled and that legal catalogue entries exist for them with their required text pointing at those anchors.
- Correct the supply-nature prose to describe the citation shape that is actually used.
- Leave the citation shape alone. The articles are cited as anchors into the whole consolidated law rather than as per-article extract files, and that is the shape the grounding rule PREFERS over hand-authoring a duplicate.

## Outcome

The docstring described a gap that had already closed, and would have sent the next reader fetching text the repository already ships.

This is the second time this exact misreading has cost the campaign work. A sibling row was retired for the same reason: a coordinator's inventory counted only the per-article extract shape and read the absence of that one form as the absence of the text. Both the retirement and this correction come down to the same discipline — a citation can take more than one shape, and counting one shape is not measuring coverage.

**What this excludes.** This corrects PROSE only. It adds no grounding, changes no citation, and makes no claim that the place-of-supply mapping is complete — the mapping rows own that. A reader should take from this only that the articles are present and catalogued, not that everything downstream of them is finished.

## Verification

Landed as:

    9b7afb7903  docs(iva): correct the place-of-supply corpus claim
    src/cadrumo/domain/iva/_supply_nature.py | 15 +++++++-----

Prose-only change to a single module, with no production behaviour on the diff.

Gate run requested from the single test-run authority rather than executed here.

## Notes

Executed by this lane's Tier-2 worker under the lead's dispatch.

Worth carrying: the row was one of four dispatched together and was deliberately ordered FIRST because it was the cheapest. The previous worker on this tranche exhausted its context on a different row and delivered nothing else, so ordering the cheap certain rows ahead of the expensive uncertain one is what got this landed at all.
