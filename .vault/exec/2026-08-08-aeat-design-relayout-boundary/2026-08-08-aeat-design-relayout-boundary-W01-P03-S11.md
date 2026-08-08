---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:ce089ec8a6bd3c68f43d469949f4b9b16fef7f1c484b8943abacc13722b4a10b'
step_id: 'S11'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Make the year-only revision selector refuse instructively

## Scope

- `src/cadrumo/domain/calculations/registry/_temporal.py`

## Description

- Establish the true caller set and the existing handling before changing anything.
- Route the remedy through the raiser rather than the shared message.
- Verify the untouched path is unchanged, not only that the new path works.

## Outcome

The typed error, its sorted `candidate_ids` tuple and the raise itself all already existed. What was missing was the **remedy**: the message read `modelo 303: ambiguous revision selection: <ids>` and never said what to do about it. That is the same defect as the operator-reachable refusals that carry no suggestion, and this is one instance of it rather than a special case.

**The remedy rides on the raiser, not in the shared message, and the reason is correctness before convenience.** Two selectors raise this error. For the year-only one the fix is to supply a period or an as-of date; for the period-scoped one the caller has already supplied a period, and that advice would send an operator to redo what they just did. No single string can be right for both, so each raiser passes its own remedy through the base error's existing `suggestion` channel. Keeping out of the four locale catalogues was a consequence, not the argument.

The filing year is now named in the fallback text and carried in structured context, because "two revisions match" only becomes actionable once the reader knows WHICH year is doubly covered.

**Measured both ways, and the second is the one that mattered.** The year-only raiser now produces `modelo 303 filing year 2024: ambiguous revision selection: 2024-early, 2024-late -- this filing year carries a mid-year AEAT design boundary, so more than one revision covers it and no year-only answer is correct`, with the suggestion attached and `filing_year` in context. The period-scoped raiser is **byte-identical to before**: same message, no suggestion, same two context keys. That is the whole risk of touching a shared error, and it was proved rather than reasoned.

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
