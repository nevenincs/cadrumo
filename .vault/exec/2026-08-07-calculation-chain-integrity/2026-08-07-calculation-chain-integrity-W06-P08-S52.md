---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:1745e6c23e81e231444b9a05e141daf40db613d66cefad315ac5755f3ec20d2f'
step_id: 'S52'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---

# Author corpus entries for the confirmed food-rate instruments before any rate record cites them, both the instrument that introduced the regime and the one that set the final step if they differ

## Scope

- `src/cadrumo/_data/corpus/normatives/html/`

## Description

- Bundle the consolidated BOE rendering under the normatives corpus.
- Generate the extraction sidecars the anchor resolver reads.
- Author the legal catalogue entry with per-figure required text.

## Outcome

The instrument is bundled rather than excerpted. Authoring an excerpt from
quoted sentences would have put one author on both sides of the evidence gate.

A first attempt bundled the diario rendering, which carries the operative text
but no element ids, so a citation could name the file and not the article.
Swapped for the consolidated rendering after comparing the two clause by clause.

The sidecars were the second blocker: the resolver reads the extracted JSON and
raises when it is absent, so the citation could not have resolved at all.
Generated with the same extractor the rest of the tree uses, so the sidecar
cannot disagree with what the next extraction pass would produce.

## Verification

```
Resolved through the live anchor resolver rather than by inspecting files:

  shared sentence prefix   -> 4 matches
  each figured form        -> 1 match each
  non-breaking-space form  -> 0 matches
```

## Notes

Two gate traps, both proved live rather than reasoned about. The four operative
sentences are identical apart from the figure, so a required text taken from the
common prefix passes whichever window the file happens to contain. And the
document separates each figure from the preceding word with a non-breaking
space while the gate normalises that to a regular space before comparing, so the
raw bytes and the matching surface disagree and only one of them does the
matching.

The first entry landed with a hyphenated kind value the schema rejects, which
made the whole registry unloadable for every consumer. The author verified the
TOML parsed and every required text matched, and never verified the registry
loads. Fixed by a peer.

The review-status field is typed as a single-value literal, so an honest pending
is not representable there; the provenance lives in the reviewed-by field until
an operator re-stamps it.
