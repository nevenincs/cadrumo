---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:9133f0c3ad51fdfec1bba60b82294d147b9b20c845371f2675506193980c6216'
step_id: 'S13'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Handle the ambiguity refusal in the registry revision diff surface

## Scope

- `src/cadrumo/application/registry/_diff.py`

## Description

- Establish the true caller set and the existing handling before changing anything.
- Route the remedy through the raiser rather than the shared message.
- Verify the untouched path is unchanged, not only that the new path works.

## Outcome

The diff resolved each bare filing year through the year-only selector and handled only the no-match case. It now refuses on ambiguity too, through the same `RegistryApplicationInputError` and the same translated key its no-match path uses, listing the candidate revisions in `available_revisions` and passing the selector's own suggestion through.

A silent pick would have been the worst available outcome here specifically: diffing is a two-revision operation, so choosing either side of a mid-year boundary produces a plausible report of the wrong pair, and nothing downstream would contradict it.

## Verification

    uv run --no-sync ruff check <changed files>   All checks passed!
    uv run --no-sync ty check <changed files>     All checks passed!
    uv run --no-sync pytest src/cadrumo/domain/calculations/registry/tests/ -p no:randomly -n0 -q
      -k "temporal or error or ambiguous or revision_selection"
    70 passed, 3803 deselected

    resolve_error_message(AmbiguousRevisionSelectionError(...))
      -> "Mas de una revision del registro coincide con el modelo 303: 2024-early,2024-late."
      suggestion -> "supply the filing period, or an as-of date"

## Notes

**The remedy is surfaced, never restated.** Each caller quotes the selector's own `suggestion` and `candidate_ids` rather than composing local advice, so there is one sentence of guidance in the tree and no second copy to drift from it.

**Attribution.** A peer bare whole-index commit took this change into HEAD alongside roughly fifty-seven files of the fleet's work under a subject describing unrelated changes. The working tree was byte-identical to HEAD afterwards, so the state tested is the state that shipped.
