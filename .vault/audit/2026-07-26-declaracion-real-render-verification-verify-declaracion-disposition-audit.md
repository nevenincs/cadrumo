---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - '[[2026-07-26-declaracion-real-render-verification-plan]]'
---

# `declaracion-real-render-verification` audit: `verify_declaracion disposition evidence`

## Scope

Evidence for plan step `P04.S18`, which asks for the disposition of
`verify_declaracion` — a modelo-agnostic comparison mechanism the campaign
observed has no callers outside its own tests.

This record gathers the evidence the decision needs and does **not** take the
decision. The step belongs to a campaign whose agent is mid-run; deleting or
enrolling a verification capability on its behalf would substitute an outsider's
judgement for the owner's on a product question. What was missing was the
measurement, and that is what this supplies.

Written by a different campaign, working the reconcile and evidence surfaces,
which is how the overlap surfaced. Semantic search was unusable throughout — the
code index held roughly 68 sections against roughly 4,546 source files while
reporting itself healthy — so every claim rests on direct reads and `rg`.

## Findings

### no-operator-surface | high | the capability is unreachable, not merely unused

Stronger than the caller count, and the fact that reframes the step: **no CLI
surface consumes `InboundDeclaracionObservation` at all**. So there is no
operator path into this mechanism, and none can be opened by wiring an existing
verb — the input type itself never arrives from an entrypoint. "Zero callers" is
a symptom; the absent operator surface is the condition.

### three-comparison-mechanisms | high | the distinction it claims is untested by use

Three mechanisms compare declaracion values against expectations, and the
package docstring is explicit that this one is neither of the others: it is not
the persisted verification-report catalogue, and not filed-state reconciliation,
which "stays with `verify_filed_state`". The third is
`_reconcile_declaracion_casillas` on the live reconcile path.

The claimed distinction is real on its face — this mechanism verifies an
**imported draft against registry expectations before any filing exists**, while
both live siblings operate post-filing. But the distinction has never been
exercised, because nothing calls it. A boundary asserted in a docstring and
never crossed in production is the shape that produces parallel authorities in
this codebase.

### caller-free-confirmed | medium | nothing outside the package's own tests calls it

`verify_declaracion` is referenced only by its own definition, its package
facade, two docstring cross-references, and its test module. No production
consumer exists in any other package.

### capability-is-genuine | medium | it is not simply dead code

Pre-filing validation of an imported declaration is a capability neither live
sibling provides. Whoever decides this should not read "zero callers" as
"redundant": on the evidence it is unreachable rather than duplicated, and those
two conditions have opposite remedies.

## Recommendations

Decide between two dispositions, both defensible on this evidence, and record
which and why.

**Enrol it** — build the operator surface that supplies an
`InboundDeclaracionObservation`, making the capability reachable. Correct if an
import-declaracion verb is intended, since the mechanism is then waiting for a
surface rather than lingering past one.

**Delete it** — a mechanism no operator can reach is dead capacity, and its
claimed boundary against the two live comparison paths is unverified precisely
because nothing exercises it. `no-dormant-source-resolvers` codifies the same
either-or for source resolvers ("enrolled in the live mesh or deleted"), and the
principle transfers even though the rule's scope does not.

What should **not** happen is closing the step with the mechanism left as-is.
That preserves a third comparison authority whose distinction from the other two
rests on prose no execution tests, which is the accretion this repository has
spent several campaigns unwinding.

One caution for whoever takes it: if deletion is chosen, confirm no in-flight
work in this campaign's own parser and profile steps intends to call it. This
record was written from a clean read at a moment when the campaign's source
areas carried no uncommitted changes, but four of its exec records were
untracked and its plan stood at 8 of 20.
