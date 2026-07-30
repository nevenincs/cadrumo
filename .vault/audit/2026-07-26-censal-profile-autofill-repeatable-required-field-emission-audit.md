---
tags:
  - '#audit'
  - '#censal-profile-autofill'
date: '2026-07-26'
modified: '2026-07-26'
related:
  - "[[2026-07-25-censal-profile-autofill-plan]]"
---

# `censal-profile-autofill` audit: `repeatable required field emission`

## Scope

Why a required field declared on a repeatable profile section binds for nobody,
and why every arrangement that would make it bind is blocked. Written because
the work is blocked on infrastructure rather than effort, and the measurements
below are expensive to re-derive and easy to get wrong in a way that looks
right.

Audited: the required-field emission helper and its consumers, the conditional
completeness helper and its consumers, and the two routes from a flat value
mapping to the legally-grounded economic-activity predicate.

## Findings

### repeatable-emission | high | The required declaration binds for no taxpayer at all

A repeatable section is validated per row, and a section with no rows yields no
rows to validate, so the emission helper produces nothing for it. Measured
against the shipped schema with an employee-only natural person, and separately
with a taxpayer declaring actividad economica, and with a legal entity: all
three return only the IVA regime path. The activity description is emitted for
nobody.

The consequence is worse than the field going unenforced. The same silence also
covers the taxpayer who declares economic-activity income and never names the
activity, which is the case the requirement exists to surface. A profile in that
state reads as complete today.

### suppression-direction | high | A call-site filter can only subtract, so the fix cannot live there

Because nothing is emitted, a guard composed at the consuming call site can only
remove paths from a set that never contained the one in question. Making the
declared case loud requires an addition, which means the emission helper itself.
A gate built at the call site is correct and complete and permanently inert, and
nothing in it shows that: it compiles, its tests pass, and an anti-tautology arm
that flips the section's repeatability in memory passes too, because that arm
proves the guard would fire given input and cannot prove anything supplies it.

### blanket-emission | high | Emitting unconditionally regresses a defect closed the same day

Measured by simulating the naive change - emit every required field of a
zero-row repeatable section - against an employee-only natural person. The
result is thirteen missing fields rather than one: attribution socios,
attribution received, usage ratios, and the activity description. Every one of
those sections is correctly silent when empty, since a taxpayer with no
properties and no attribution entities owes nothing for them. That output is the
displayed-completeness defect closed hours earlier, reproduced verbatim.

So a per-section applicability condition is load-bearing rather than a
refinement. Without it the change is a straight regression.

### consumer-split | high | The two completeness helpers serve different surfaces, and the cheaper one is blind where it matters

Enumerated by callers, which is closed by construction and therefore a proof
rather than a sample.

The required-field helper has two production consumers: the validation service
and the profile overview. That pair is deliberate - the enforcing surface and
the displayed surface read one helper so they cannot drift apart, which is the
fix a prior finding landed.

The conditional-requirement helper has four: validation, preflight, key
validation, and the filing baseline. It does not include the overview.

This makes the attractive route a trap. Extending the conditional helper needs
no new symbol and reaches four surfaces for free, and it leaves the overview
blind - reopening the enforcing-versus-displayed drift by fixing this. Neither
module states the split; only enumerating consumers reveals it.

### named-symbol-terminus | medium | Every arrangement terminates in a new named symbol

The condition must live where both the enforcing and displayed surfaces see it,
which is the emission helper. Emitting there and suppressing at each call site
requires the same suppression in two places, so it must be shared, so it must be
named. Placing the condition inside the helper is a per-section applicability
lookup, which is likewise named. The schema offers no third home: its complete
key set carries no conditional-requirement mechanism, only a bare boolean.

### predicate-access | high | Reaching the canonical predicate from a value mapping has no safe route

The policy is settled and routes through the shipped, legally-grounded predicate
rather than a new one. That predicate takes the deadline-domain taxpayer
aggregate; the completeness helpers hold a flat mapping of path to rendered
string. The one sanctioned coercion from mapping to aggregate is strict: it
validates through the setup-answer model and raises on any undeclared token.

A surface whose purpose is untrusted input cannot depend on a strict projection
of that input. Wiring it into the validation service converted a reportable
defect into an exception on exactly the input the validator exists to catch, and
five existing tests said so. The emission helper is a worse host still, because
it also serves the display, so a raise there removes the operator's view as well
as the check.

Reading the predicate shows it consults only the income categories and, by the
second arm of the policy, the entity type - both already plain strings in the
mapping. Consuming them directly is nonetheless a further restatement of a
concept that already has three, which the routing decision exists to prevent.

### adjacent-concept | medium | A fourth statement of the same taxpayer concept sits in another layer

The setup wizard already carries a per-question applicability condition for this
exact taxpayer: legal entity, or income categories containing economic activity,
with a comment naming the salaried taxpayer and the pensioner who must not be
made to invent an activity. It is a per-question mechanism rather than a
per-section one, in a different layer, modelling the same distinction.

Any search for an existing applicability mechanism must reconcile against it. It
is also why the open question below cannot be closed by a symbol sweep: a
mechanism of that kind can be named anything, and this one shares no vocabulary
with the helpers it would serve.

## Recommendations

Treat the emission change and the predicate-access change as one decision
requiring an architecture decision record, not as an amendment to the helper.
The record must decide two things together: where a per-section applicability
condition is declared and consumed, and how a flat value mapping reaches the
canonical predicate without a strict coercion. Deciding emission alone licenses
roughly a third of the change and leaves the surface that would host it holding
a predicate it cannot call.

Do not land a call-site gate ahead of the emission change. It is inert, and
nothing in a passing suite distinguishes an inert guard from a working one.

Do not extend the conditional-requirement helper as the cheap route without
first deciding what the overview consumes; as it stands that trades this finding
for the displayed-completeness one.

Before any of it, one question stays open and cannot be closed by search: does a
per-section applicability mechanism already exist outside the completeness
module. Three concepts in this campaign were found under names nobody had
searched, one of them in the adjacent conditional layer of the same file, and
the wizard condition above is a live near-miss. Answering it needs semantic
discovery over the code corpus, which is the infrastructure the work is blocked
on.
