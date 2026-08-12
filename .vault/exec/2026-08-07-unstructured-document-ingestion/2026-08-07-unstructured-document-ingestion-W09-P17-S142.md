---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-11'
modified: '2026-08-12'
body_schema: 'body-v1'
body_hash: 'sha256:b7162ba97ab5477d2b561d3afbb54f378205df381dac279d773e57e6b58c0648'
step_id: 'S142'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

# Let a postal field carry role evidence, since the role-evidence flag derives from the tax-identifier form and the validator refuses a role-evidence instruction on any other form, so the two identity fields each get a key asking the model to quote the printed heading proving whose they are while the two postal fields structurally cannot and their party attribution rests on prose alone. A transposition produces a fully valid draft with both fields grounded and every gate green, and once the consumer lands both parties get a confident wrong territory. Either widen the flag to a declared per-contract axis or record in the ADR rather than only the exec record that postal party attribution is anchor-reviewed rather than evidence-anchored, and make that a stated precondition on the consumer row

## Scope

- `src/cadrumo/llm`

## Description

- Confirm the row's mechanism against the contract model: role evidence is
  derived from the tax-identifier form and refused on any other.
- Implement the row's first option, widening the flag to a declared per-row
  axis with the postal fields declaring it.
- Run the suite, meet the gate that forbids exactly that, read its reasoning,
  and revert.

## Outcome

PREMISE SUPERSEDED. The row's second option was already taken, and its first
option is forbidden by a shipped gate that exists to forbid it.

The row's mechanism is real and unchanged: the flag derives from the form, so
the two identity fields ask the model to quote the printed heading proving
whose they are and the two postal fields structurally cannot. What is false is
the conclusion drawn from it -- that postal party attribution therefore "rests
on prose alone".

It does not. Address values are attributed DETERMINISTICALLY IN CODE, by
co-location from the document's own layout, precisely so the reader is never
asked for more. That is a stronger answer than the row's first option, not a
weaker one: it reads the document's structure rather than asking a model to
quote a heading and then trusting the quote.

The decision is gated, and the gate says so in its own words -- it asserts the
widening "the record refused", as a property rather than a tally: every
role-evidence-bearing field must name a party identity, no attributed address
field may carry one, and the RENDERED prompt is checked too, because a contract
table can stay honest while a template hardcodes an extra instruction. The
reasoning is a context budget: the design target is a lowest-bound vision model,
so every added key costs the fields already in the prompt, and a key with no
consumer buys review surface rather than safety.

Implemented anyway, before reading that. The change passed its own reasoning
and failed seven assertions across three modules, four of which exist
specifically to refuse it. Reverted; the suite is back to sixty-three green
with no diff.

WHAT THE ROW STILL ASKS FOR: nothing. CORRECTED after this record was first
written -- the claim below was wrong. It said the disposition wanted an ADR
line it did not have, and a row was opened for that. The governing ADR already
carries it as its sixth amendment, which renames the axis to party
attribution, rules that non-identity attribution is deterministic co-location
rather than more prompt, gives the context-budget reason, names the
transposition fixture as its gate, and states the interim as a visible
precondition. The row opened for it is closed as an error.

The correction sharpens this record rather than softening it: the amendment
says in terms that the role-evidence keys do NOT widen from two to six, and
the change attempted here would have widened them from two to four. So it was
ADR-refused as well as gate-refused, and reading either surface first would
have prevented it.

## Notes

THIS IS THE HAZARD THE PLAN PREAMBLE NAMES, and I walked into it rather than
around it. The row is wrong in a way its executor can fully satisfy: nothing
about widening the flag announces difficulty, the mechanism it describes is
accurate, and the implementation was clean. Had the gate not existed I would
have shipped a change that undid a deliberate design decision, added two keys
to a context budget that was argued down, and left the deterministic
attribution in place but unexplained beside a prompt now asking for the same
fact.

The gate caught it in one run. That is what a property-gated decision buys
over a decision recorded in prose, and it is the argument for the shape the
row's own second option asked for.
