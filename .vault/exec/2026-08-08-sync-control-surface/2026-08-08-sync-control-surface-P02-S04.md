---
tags:
  - '#exec'
  - '#sync-control-surface'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
step_id: 'S04'
related:
  - "[[2026-08-08-sync-control-surface-plan]]"
  - "[[2026-08-08-sync-control-surface-adr]]"
  - "[[2026-08-08-sync-control-surface-reference]]"
---

# Reuse the verify parity comparison to build the export preview

## Scope

- `src/cadrumo/application/storage/calc_sheets`

## Description

- Read what the verify path DOES before reusing it, rather than reusing the
  function the decision record names.
- Establish that the comparison is already pure and that only its callers are
  not, so the change is a move rather than a rewrite.
- Lift the row model, the row builder, the divergence predicate and the verdict
  resolver into a sibling module that takes no snapshot and no scenario.
- Repoint the harness at the extracted functions.
- Promote the row model to the package facade instead of leaving it re-exported
  from the harness.
- Land the move, the consumers, the facade and the test in one commit.

## Outcome

The comparison is now reachable without the write path, which is the property
the export preview needs and did not have.

WHY THE OBVIOUS READING OF THE RULING WOULD HAVE FAILED. The decision record says
the export preview reuses the parity machinery the verify verb already owns. Read
literally that means calling `verify_modelo_parity`, and that function cannot be
called by a preview: its own documented side effects are creating or updating the
spreadsheet, writing the scenario's operator inputs into `Entradas` and relations
into `Tarifas`, and reading `Cálculos` back. A dry-run built on it would write on
every invocation, which is the one thing the dry-run row exists to forbid. The
reusable unit is not the verb, it is the comparison underneath it.

WHAT MADE THIS A MOVE RATHER THAN A REWRITE. The comparison was already pure —
the row builder, the divergence predicate and the verdict resolver take mappings
and produce rows, and touch no I/O. Only their position was wrong: they sat in a
module whose import surface drags the Google discovery boundary. So nothing was
reimplemented and no behaviour was restated; the three pairwise flags, the two
divergence rules and the verdict precedence are carried across unchanged.

TWO SIGNATURES WERE RESHAPED, DELIBERATELY. The row collector previously took a
registry snapshot and an operator-input scenario. It used exactly two things from
them: the revision's casilla definitions and the scenario's expected values. A
preview holds neither object, so leaving those parameters in place is precisely
what would have forced a second differ into existence for the preview's benefit —
the outcome this row exists to prevent. It now takes a casilla sequence and an
AEAT-values mapping.

THE ROW MODEL MOVED TO THE FACADE rather than staying re-exported from the
harness. A module listing a sibling's symbol in its own `__all__` is a re-export
bridge, and the adapter that will consume this comparison is in another package,
so the promotion is a precondition of that consuming change rather than a
follow-up to it.

## Notes

THIS ROW IS NARROWER THAN THE DECISION RECORD'S PREVIEW, and the exclusion is
stated rather than implied. The record describes the Sheets preview as answering
three things: the per-tab cell ranges the plan would clear, the count of cells
whose value would change, and any foreign content the apply would refuse on.
Only the second is delivered here. The other two are not deferred out of
convenience — they cannot correctly live in this layer.

The reason is in the adapter's own written rationale. The clear step derives its
stale set from the addresses the write payload actually covered, and the module
that computes it states plainly that re-deriving that extent from the plan would
be a second implementation of the layout the payload builders already encode,
that the two would drift, and that the drifted set would then name cells the
write did cover — blanking live content. So a preview that computed
ranges-to-clear from the plan in the application layer would reintroduce exactly
the data-loss shape the write-then-clear ordering was changed to remove. The
ranges-to-clear and foreign-content halves therefore belong inside the adapter,
immediately before the batch calls, and are carried by the Sheets dry-run row.

A CONSEQUENCE FOR THE NEXT ROW, recorded here so it is not rediscovered: the
Sheets dry-run short-circuit cannot sit in the CLI or the application layer. It
has to sit in the adapter, at the point where the payload exists and the write
has not yet happened.

CORRECTION, ADDED AFTER THIS ROW WAS CLOSED: THE RELOCATION SHIPPED BROKEN, and
the paragraph above claiming behaviour is unchanged was false when written. The
row model's `Decimal` annotation was left imported under `TYPE_CHECKING` while it
types three pydantic FIELDS. With postponed annotations those become strings,
pydantic resolves them when it builds the model, and the class was left undefined
— so every instantiation raised while the module still imported. The three
pairwise flags and two divergence rules were carried across correctly; the model
carrying them could not be constructed.

WHY THE CLAIM SURVIVED REVIEW, which is the transferable part. Every check
available before a test body runs passed: the module imports, collection
succeeds, and the linter actively recommends the narrower type-checking import
that causes it. A behaviour-preserving relocation is exactly the change where an
author is least likely to instantiate anything, because nothing about the
behaviour changed. Fixed by importing at module scope, with the reason written
into the model's own docstring so a later tidy-up does not narrow it back and
reintroduce the defect wearing a lint fix. The full directory then ran green,
which additionally establishes that nothing else was depending on the broken
state.

The row stays closed. Its deliverable — one comparison, reachable without the
write path — was delivered and is sound. This correction is here because a
record claiming behaviour preservation, left standing beside a defect that
broke every consumer of the moved model, would misinform the next reader about
what that claim is worth.

VERIFICATION WAS NOT RUN BY THE AUTHOR. The suite authority holds that role. The
request named the two new files and the two modified ones, and additionally asked
for any calc-sheets test exercising the harness to be treated as in scope,
because the row model was removed from the harness's exported names and a stale
importer of the old path would be a regression owned by this change rather than
by whoever trips it.
