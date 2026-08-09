---
tags:
  - '#exec'
  - '#unfalsifiable-test-sweep'
date: '2026-08-09'
modified: '2026-08-09'
body_schema: 'body-v1'
body_hash: 'sha256:d4f6d136de5a5348195f7e42d2a7d9502f8891409ab00d1a0d860369c53ac1e3'
step_id: 'S01'
related:
  - "[[2026-08-09-unfalsifiable-test-sweep-plan]]"
---
# Floor the dev UTF-8 corpus so a walk returning nothing fails instead of passing silently

## Scope

- `src/cadrumo/tests/test_utf8_enrollment_inventory.py`

## Description

- Added `test_the_dev_corpus_is_not_empty`, asserting the dev walk returns more files than a collapse floor.
- Set the floor an order of magnitude below the live count rather than near it.

## Outcome

The dev bare-UTF-8 scan can now fail when its corpus collapses. Before this it could not, under any circumstances.

That was not a latent risk but a live one, and the proof is direct: emptying only the dev walker at runtime produced three passes and nothing anywhere noticed. The scan raises only when it finds a violation, so a walk matching no files reports precisely what a clean tree reports.

Its sibling scan is protected as a side effect of the inert-ratchet check. The dev scan has no such accident available to it, because `_DEV_KNOWN_VIOLATING` is already an empty frozenset - the dev ratchet has fully drained. So the dev side had already arrived at the end state the production side is still travelling toward.

The floor is set at 20 against 228 live files. A floor near the live count would fail on ordinary deletions, and a constant that fails for benign reasons gets edited rather than read - which is how a floor stops protecting anything. This one is asking whether the walk COLLAPSED, not whether the tree grew.

## Verification

    uv run --no-sync pytest src/cadrumo/tests/test_utf8_enrollment_inventory.py -n 0 -q
    5 passed in 4.21s

Mutation, applied at runtime from outside the repository so no tracked file was modified, emptying only the dev walker:

    FAILED test_the_dev_corpus_is_not_empty
    1 failed, 4 passed in 3.70s

The identical mutation produced `3 passed` before this Step.

## Notes

The dev accessor returns an empty list when the dev root is not a directory, so a collapsed walk degrades silently rather than raising. That is the concrete path by which this would have happened.
