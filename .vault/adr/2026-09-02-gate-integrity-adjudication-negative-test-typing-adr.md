---
tags:
  - '#adr'
  - '#gate-integrity-adjudication'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:15bd2911a96bd2aa6b5802ff8b7ddc2e49b60a09ee7ba12e31cb0a24cc426d8d'
related:
  - "[[2026-09-02-gate-integrity-adjudication-tui-entrypoint-contracts-adr]]"
  - "[[2026-09-02-registry-enum-canonicalization-adr]]"
---

# `gate-integrity-adjudication` adr: `no suppression policy: the deliberate-wrong-type population is empty` | (**status:** `accepted`)

## Problem Statement

The type gate reports a large `invalid-argument-type` population. A share of it
was believed to be tests that deliberately pass a wrong-typed value to prove
runtime validation refuses it, where the type mismatch is itself the assertion
and typing it away would delete the test's purpose. That belief calls for a
suppression policy: a per-site ignore, a typed invalid-payload seam, a cast at
the injection point, or a per-file relaxation for negative-test modules.

A decision is needed before any of those is applied, because every one of them
permanently blinds its sites to real type erasure. If the population is smaller
than believed, or empty, the policy would buy nothing and cost the gate its
reach over the exact modules where refusal behaviour is proven.

## Considerations

- The reported figure counts diagnostics, not sites. The checker emits one
  diagnostic per candidate parameter when a mapping is splatted into a typed
  constructor, so a single call site can report dozens of times. Measured on the
  live tree, the `invalid-argument-type` diagnostics collapse to substantially fewer
  unique file, line and column sites.
- Of those unique sites, only a small minority sit within reach of a `pytest.raises`
  or validation-error assertion at all. Every one of them was read against its
  surrounding assertion.
- In not one case is a wrong type the thing being refused. Every refusal asserted is a
  value or constraint refusal on a well-typed value: an empty string against a
  non-empty label, a negative integer against a non-negative bound, a malformed digest
  against a format constraint, an out-of-set token against a narrowed enumeration, an
  empty or incomplete tuple against a completeness rule, contradictory operands against
  a coherence rule.
- The diagnostics at those sites come from separate mechanical causes that are
  independent of the assertion: a payload builder declared as a mapping of `object`
  splatted into a typed constructor; a dynamic splat whose key is a loop or
  parametrize variable, which makes the checker union every candidate field; a bare
  string literal standing in for an enum member in a fixture and relying on coercion;
  an over-broad `object` annotation on a helper parameter or return; and mapping
  value-type invariance, where a status-enum value is not accepted for a declared
  integer.
- The value constraints those tests assert are carried by annotated string and
  numeric types whose static form is the plain base type. A bad digest and a good
  digest are the same type to the checker, which is why the refusal is invariably a
  runtime concern and never a typing one.
- Several candidate sites already carry a suppression comment in another checker's
  dialect, which the active checker does not honour. Those are inert and prove nothing.

## Considered options

**A per-site ignore with an inline reason.** Rejected. It would annotate sites whose
diagnostic is not about the assertion at all, permanently hiding the payload and
annotation erasure that actually produced it.

**A typed helper constructing deliberately-invalid payloads behind one seam.** Rejected
because the premise fails. The payloads are not invalid; they are well-typed values that
violate runtime constraints. A seam advertising invalidity would misdescribe every
caller, and the honest version of that helper is simply the correctly typed payload
builder these sites already need.

**A cast at the injection point.** Rejected as the worst of the three. It launders the
mismatch into an assertion no reader can see, so a future reader cannot tell a
deliberate injection from an accident, which is precisely the property that would have
had to justify it.

**A per-file relaxation for negative-test modules.** Rejected. It is the broadest
instrument for the narrowest claim, and the project's gate discipline forbids a
file-level exemption where the condition is neither uniform nor per-site classified.

**No suppression policy; close the sites by typing.** Chosen. The sites carry ordinary
type erasure whose remedy is the same typed payload, annotation and enum-member work
already under way for the rest of the population, and closing them that way leaves every
refusal assertion intact and still proving refusal.

## Constraints

- Correcting these sites means editing modules inside an active typing lane that is
  closing the wider population. One writer owns a file; this record decides the policy
  and hands the classified sites to that lane rather than editing alongside it.
- The bare-string-for-enum sites are the subject of a separate proposed record on
  canonical enums as the single authority for registry value sets. They are closed by
  that campaign's remedy, not by a second one invented here.
- No correction may alter the asserted refusal. Typing a payload builder is permitted;
  changing an injected value, a bound, or an expected error is not, because the value is
  the test.

## Implementation

Nothing is suppressed, and no suppression mechanism is adopted. The population the
policy would have served does not exist, so the correct implementation is the absence of
one.

The candidate sites are handed to the typing lane already classified by cause, so they
need no re-derivation: give the payload builders a precise mapping type rather than a
mapping of `object`; replace an over-broad `object` parameter or return annotation on a
test helper with the type its callers require; unroll or type the dynamic splats so the
checker sees one field rather than a union of all of them; spell enum members rather
than their string forms in fixtures; and widen or correct the declared value type where
the only defect is mapping invariance.

Inert suppression comments in a checker dialect the active checker ignores are removed
as they are encountered rather than translated, since a comment that suppresses nothing
is a false record of a decision nobody made.

The general rule this record sets, for the next time the question arises: a refusal
assertion is evidence about values, and a type diagnostic at the same line is evidence
about the shape of the payload that carried them. They are separate defects, and the
presence of the first is never on its own a reason to silence the second.

## Rationale

The knockout is measurement. The policy was to be justified by a population of sites
where the mismatch is the assertion, and read against their assertions, that population
is empty. Every candidate turned out to assert a value refusal, which the type system
correctly regards as well typed, while its diagnostic came from an unrelated erasure in
the payload or the annotation.

That inversion also explains why every suppression option fails the same way rather than
differently. Each one would attach an exemption to a line whose diagnostic has nothing to
do with the reason offered for the exemption, so the reason would be false at the moment
it was written and would stay false permanently.

Closing by typing costs nothing the tests need. Because the constraints are carried by
annotated types whose static form is the base type, a correctly typed payload still
admits the empty string, the negative count and the malformed digest, and the validator
still refuses them at runtime. The gate keeps its reach and the tests keep their teeth.

## Consequences

The type gate retains full coverage over the modules that prove refusal behaviour, which
is where losing it would have mattered most. Nothing is added to the tree that a future
reader would have to evaluate and re-justify.

The candidate sites do not close in this record, and the gate stays red on them until the
typing lane reaches them. That is a slower path to green than a suppression sweep and it
is the honest one, because the diagnostics are reporting real erasure.

The classification is durable beyond these sites. The five causes recur wherever tests
build payloads dynamically, so the same reading applies to sites this measurement did not
reach, and a future report of deliberate wrong typing can be checked against it rather
than accepted.
