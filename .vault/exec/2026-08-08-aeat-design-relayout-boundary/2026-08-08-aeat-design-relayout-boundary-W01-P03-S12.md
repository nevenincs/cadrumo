---
tags:
  - '#exec'
  - '#aeat-design-relayout-boundary'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:318163da659e15fa3924295bbf6a45842460e36c73a8eaac1e26582ffb030ba9'
step_id: 'S12'
related:
  - "[[2026-08-08-aeat-design-relayout-boundary-plan]]"
---
# Widen the binding-readiness helper's refusal handling

## Scope

- `src/cadrumo/application/modelo/_binding_readiness.py`

## Description

- Establish the true caller set and the existing handling before changing anything.
- Route the remedy through the raiser rather than the shared message.
- Verify the untouched path is unchanged, not only that the new path works.

## Outcome

The helper caught only `NoRevisionForPeriodError`, so the ambiguity refusal propagated out of a read-only discovery surface whose whole contract is reporting readiness. It now catches both and answers the same way for each: `None`, meaning undetermined, which is the contract it already had.

**This was not hypothetical.** The first filing year covered by two revisions would have raised out of a helper that only reports whether profile bindings are resolvable, turning a discovery question into an operator-facing error from a surface that had been working. Modelo 303's 2024 split creates exactly that year, which is why the sub-year decision record sequences this before any split.

The debug log names the candidate revisions and quotes the error rather than composing its own advice, so the remedy has one home.

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
