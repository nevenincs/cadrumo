---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:c06f862bf1d6fd6ef6a4308b288d876a9de39b7319c4d10e32338c8245f2f395'
step_id: 'S14'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Handle the ambiguity refusal in the registry describe and bindings query

## Scope

- `src/cadrumo/domain/calculations/registry/_queries.py`

## Description

- Establish the true caller set and the existing handling before changing anything.
- Route the remedy through the raiser rather than the shared message.
- Verify the untouched path is unchanged, not only that the new path works.

## Outcome

**No code change was needed, and establishing that is the row's result.** This row was re-pointed here from the profile inspect surface after measurement showed that surface does not call the year-only selector at all and already refuses on this error. The query resolver was the genuinely unguarded caller and one of the three the sub-year record names.

Measured rather than read: the resolver calls the selector bare at `_resolve_revision_for_year`, and it treats `NoRevisionForPeriodError` the same way - it does not catch that either. So propagating the ambiguity IS "handling it the way it already handles a missing revision for a period", which is exactly what the decision record requires. The two refusals are consistent, not one guarded and one leaking.

**What makes propagation the right answer here rather than a gap** is that the refusal is typed, registered and instructive. It carries an error code, `ERROR_CALCULATIONS_REGISTRY_AMBIGUOUS_REVISION`, in the CLI error registry, so it reaches the operator as a coded localised refusal rather than a traceback. Exercised rather than inferred: resolving the error through the production message resolver renders the localised sentence naming the modelo and both candidate revision ids, with the raiser's suggestion attached.

**One honest limitation, recorded rather than smoothed over.** The localised sentence carries the modelo and the candidate ids but NOT the filing year or the reason, because its catalogue template predates them and adding a placeholder would mean editing four catalogues. The filing year reaches the operator through structured context and the suggestion instead. Whether the localised prose should name it is a separate decision to be made once, not a side effect of this row.

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
