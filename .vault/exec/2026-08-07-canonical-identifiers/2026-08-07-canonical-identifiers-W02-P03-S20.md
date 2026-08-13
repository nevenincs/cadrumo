---
tags:
  - '#exec'
  - '#canonical-identifiers'
date: '2026-08-13'
modified: '2026-08-13'
body_schema: 'body-v1'
body_hash: 'sha256:9beabf4c66dcdb8ff9b8bdbd765be79a30757cc6909d04de5b11fc283e749098'
step_id: 'S20'
related:
  - "[[2026-08-07-canonical-identifiers-plan]]"
---

# unify CSV normalisation to one form across the verify adapter and the calendar-evidence consumer, matching whichever form `W02.P03.S13` proved correct

## Scope

- `src/cadrumo/application/overview/_calendar_evidence.py`

## Description

- Route the evidence-reference cleaner through the module's existing canonical
  CSV key function instead of stripping only.
- Delete the five casefold calls in the conflict-merge comparison, which
  becomes plain equality once both sides are normalised once.
- Record in the cleaner's docstring why one form is required and what the
  second form used to cost.

## Outcome

The change is confined to `src/cadrumo/application/overview/_calendar_evidence.py`,
in `_clean_reference_id` and `_merged_conflict_reference_ids`.

The row asked which of the two surfaces carried the correct form. The verify
adapter was already correct: it normalises through the shared uppercase
comparison form and then applies the shape predicate. The uppercase form is
the correct one on the merits, not merely by precedent, because the adopted
bound is uppercase alphanumeric, so a lowercase normal form fails the very
contract it normalises toward.

There was genuinely something to unify, so this is not an adjudicated close.
The calendar-evidence consumer carried BOTH forms at once. Its justificante
lookup key already delegated to the shared uppercase form, but the
conflict-merge path independently stripped and then casefolded at each of five
comparisons. Casefold produces lowercase and additionally transliterates, so
the module held two keys for one identifier depending on which branch compared
it, and the transliterating variant is unsafe for a value that must round-trip
to the cotejo endpoint byte for byte.

The correct outcome was one authority rather than two agreeing
implementations, so the cleaner now delegates to the same key function instead
of gaining its own copy of the transform. The module ends with exactly one
normalisation authority, reached by two named roles: the key function for
required values and the cleaner for optional ones. Emptiness handling is
preserved, since a blank input still normalises to blank and yields nothing.

Case-insensitive matching of one CSV against another is a deliberate,
named capability of this surface and is preserved: the overview suite's
lower-case evidence fixtures still match, because normalising once up front
makes the subsequent equality checks case-insensitive by construction.

Focused verification: the overview suite passes apart from two failures
outside this surface, covering agenda cohort partitioning and profile-fact
projection. Both fail identically without this change. Lint and format are
clean.

## Notes

One behavioural consequence is worth stating rather than leaving to be
discovered. The emitted conflict reference identifiers are now uppercase,
because the values placed into that tuple are the normalised ones. In practice
the emitted set is unchanged: the sibling retype puts the source field on the
canonical alias, which normalises at the model boundary, so the values arriving
here are already uppercase. The function's own docstring always described its
result as normalised, so this makes the code agree with its stated contract.

Two further casefold comparisons of the same identifier survive in the
cross-period clean-state application module. They are the same defect class and
outside this row's named scope, so they were left in place rather than swept
silently. They are worth a successor row.

The first overview suite run aborted during collection because a peer was
writing the registry tree while the loader was fingerprinting it. The run was
repeated sequentially and completed.
