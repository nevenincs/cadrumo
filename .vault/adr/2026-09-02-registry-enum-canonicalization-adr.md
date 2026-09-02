---
tags:
  - '#adr'
  - '#registry-enum-canonicalization'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8424bab265978f2ac600625b2074974fb32b94c092407dd8ea48096e38d45432'
related:
  - "[[2026-09-02-registry-enum-canonicalization-audit]]"
  - "[[2026-06-01-registry-period-code-union-cli-boundary-adr]]"
  - "[[2026-07-27-conformance-cli-adr]]"
---

# `registry-enum-canonicalization` adr: `Canonical enums are the single authority for registry value sets` | (**status:** `proposed`)

## Problem Statement

The registry ships 19,511 TOML files whose conformance-bearing scalars are read
back by a Python schema. That schema is meant to be the authority for every
value set it parses. It is not, in the ways catalogued in
`2026-09-02-registry-enum-canonicalization-audit`, and each way lets a value be
conformant against one reading of the schema and not another.

A decision is needed rather than a sweep of repairs, because the findings share
one shape and each has a plausible local fix that would leave the shape intact.
Collapsing the duplicate codec spellings repairs one comparison and teaches
nothing. Retyping one degenerate field repairs one field. Only a gate on where a
value set may be defined closes the class, and only a gate can hold it closed.

The record also settles a question the campaign would otherwise re-litigate per
field: whether provenance about how a file was produced belongs in data that
ships to users.

## Considerations

- The schema is the authority by intent: `BeforeValidator` coercion hops in the
  schema base run ahead of strict field validation, so an unknown token fails
  when the model is built rather than at a downstream branch. The loader's only
  pre-pass is structural discovery; no value-set check runs ahead of the hops.
- Enums are already the codebase's default answer, yet the registry schema
  annotates many model fields with multi-member string unions, a substantial
  minority of them reached through a named alias rather than spelled at the
  field. The campaign has measured this three ways under three predicates and
  no figure is quoted here: the gate's subject is a predicate, and the count is
  whatever that predicate returns on the day it runs.
- A vocabulary that cannot express its own negation cannot fail. One is
  established: the legal review status, read by 530 rows across two models.
  Three further one-member fields were examined and are unresolved rather than
  settled -- an extraction failure semantics and a runtime clean state, both of
  which read as assurance claims frozen at one value, against two evidence-tier
  declarations that restate their own model's identity and are correct. The
  campaign has misjudged this population twice, so it is adjudicated per field
  and never in bulk.
- The two enums that were byte-identical were reachable only by semantic search,
  not by name. Text matching does not find this class, so the campaign's
  discovery method is part of its design rather than an implementation detail.
- The cross-package private-import rule reached zero and is gated with no
  allowlist. That shape is the reason this campaign can end rather than ratchet.
- Registry validity must not depend on the loading machine, which is why the
  governance rules use fixed calendar bounds rather than the clock. Anything
  added here holds the same property.
- `2026-06-01-registry-period-code-union-cli-boundary-adr` is accepted and
  records a permanent exception to the typed-enum mandate for the period axis,
  which carries a regex member that cannot be enumerated. That axis is
  `Annotated[str, BeforeValidator]`, not a union, so it lies outside the subject
  of the gate proposed here and the two records do not conflict.

## Considered options

**Repair each finding locally.** Collapse the codec spellings, retype the
degenerate fields, deduplicate the twin enums. Cheapest, and leaves the class
open: the next inline vocabulary is admitted silently and nothing records why
the repairs were related.

**Validate the tree against a generated value catalogue.** Emit the permitted
tokens per key and check the tree against it. Rejected, but not on drift: the
project's generated-reference rule establishes that a generator plus a check
mode is a durable guarantee, so a regenerated catalogue would not go stale. It
is rejected because it leaves each value set with two definitions, the enum and
the emitted artefact, when the defect being repaired is precisely that value
sets have more than one.

**Require every closed vocabulary to resolve to a named enum the schema
imports, and gate the multi-member case.** Chosen. One definition per value set,
the tree validated against it by construction, and the gate derived from the
tree so a new multi-member union fails rather than accumulating.

**Move all build provenance out of shipped data.** Rejected as stated: it
discards facts legitimately about the shipped artefact. Narrowed to a
stamp-granularity rule below.

## Constraints

No frontier dependency; the mechanism is `StrEnum` and pydantic, both already
load-bearing. The blocking constraints are ordering and decidability.

A data sweep that removes the value un-swept rows depend on has no safe
intermediate state. The codec collapse demonstrated this the hard way: a sweep
matching one TOML quoting style left 141 declarations behind and the tree
stopped loading once the duplicate spelling was withdrawn. Either the two halves
land together, or the permissive half survives until the sweep is proven
complete against a deliberately broader reading of the tree than the sweep
itself used.

Retyping the degenerate review status is not uniformly costly. Of the 530 rows,
the 499 source blocks carry neither reviewer nor date and fall to the pending
member. Of the 31 legal-parameter blocks, 22 carry a reviewer token that maps
mechanically onto a reviewed member; the remaining 9 carry a qualified
attestation naming outstanding operator work and require a per-row reading. The
honest backlog is therefore at least 499, and those rows must read as unreviewed
rather than be cleared by stamping a value.

The gate's subject must be mechanically decidable. Multi-member string unions on
model fields are, provided the predicate resolves a field's annotation through
any alias chain first: a union moved into a named alias is the same union, and a
gate that reads only the field's own spelling can be satisfied by renaming.
One-member unions are not decidable at all: they split into legitimate scope and
shape pins and genuine degenerate claims, and no property of the annotation
separates those readings. Non-string unions cannot become string enum members.

Promoting a union to an enum is not a pure retype. Registry models validate
strictly, so an enum-typed field refuses the bare token every shipped row
carries unless the boundary coercion hop the schema base already provides is
added in the same change. Landing the enum without the hop makes the tree
unloadable, which is the ordering constraint above in a second form.

## Implementation

Three layers, in dependency order.

The value layer first. Every multi-member closed vocabulary on a registry schema
model field resolves to a named `StrEnum` in the domain, imported by the schema
rather than spelled at the field. Aliases collapse to one member, so a value has
one spelling as well as one definition, and the canonical spelling is the one
the existing encoding alias map already elects. A vocabulary genuinely open at
the boundary -- legal prose, party names, text quoted from an official design --
stays a plain string and is out of scope. Degenerate conformance fields are
repaired individually, by name and after adjudication, because they are defects
rather than a class.

The twin review-status enums merge to one. The revision-side enum survives
because its docstring carries the reasoning for the value set; both are hydrated
identically and both live in the core package, so neither hydration nor location
discriminates. The legal-side module is deleted in the same change rather than
left as a re-export, per the no-legacy-compatibility rule. The three token values
are byte-identical across both enums, so no shipped row changes and the merge has
no intermediate state.

The dev-side stamping narrowing is in scope rather than exempt. It is today a
second enum re-declaring two members with copied values, held correct by a
pinning test, which is the compensating-construct shape this campaign exists to
remove. It becomes a derived subset expressed over the canonical enum.

The provenance layer second, at stamp granularity rather than per field. The
four-scalar governance stamp is validated as a unit -- a reviewed status without
a reviewer is refused, and a reviewer under a pending status is refused -- so
splitting it would make its own coherence rule unenforceable. The stamp
therefore moves or stays whole, and it stays in registry data.

Closing its identity axis amends the conformance-CLI record, which specifies the
authorship scalar as non-empty free text; that amendment is made here explicitly
rather than by silent override. The reviewer field splits rather than narrows:
the declaring party becomes an enum, and the attestation narrative moves to a
separate declared free-text field. The split is required by the data. Of the
revision-level stamps, a substantial minority carry multi-paragraph attestations
naming digests of bundled sources, coverage figures and explicit self-review
disclosures, and an enum cannot hold any of it. Typing the field without
splitting it would discard grounding the calculation-grounding rule requires be
preserved, which is a worse defect than the one being repaired.

The dev-side conformance surface remains the owner of freshness questions, which
the registry may not ask because it may not consult the clock. That surface is a
private module already reached from outside its package by its own tests; the
promotion that owes is a pre-existing hygiene item, recorded here and not caused
by this campaign.

The gate layer last, and only once the multi-member count is zero: no
multi-member string union on a registry schema model field, derived from the
tree on every run, with no allowlist and no baseline. One-member unions and
non-string unions are outside its subject by construction rather than by
exemption, and the record says so here so a later audit does not read their
survival as a hole.

## Rationale

The knockout is falsifiability. A conformance field whose type admits one value
reports the same answer whether or not the underlying work was done, and two
such fields currently do. No local repair changes that property; only requiring
the vocabulary to have a negation does.

The enum wins over the generated catalogue on definition count rather than on
drift, which is the criterion that actually separates them and the one the
campaign has already applied once.

Scoping the gate to the mechanically decidable case is what makes the
no-allowlist promise keepable. A gate that also counted one-member unions would
need a list of permitted pins to reach zero, and that list is the mechanism this
campaign exists to remove.

The difference between a scope and an allowlist is real on maintenance and false
on coverage, and the record claims only the first. A predicate cannot go stale
and cannot be silently occupied by a future violation, where a list does both.
But the excluded population is known to contain instances of the very defect the
gate exists to close, which is why those are repaired by name here and why the
method that finds the next one is a schema read rather than the gate.

Keeping the governance stamp whole wins because its coherence rule is the only
thing currently making the stamp falsifiable, and the discriminator that would
have split it -- whether a user of the wheel could act on the fact -- gives
ambiguous answers on the stamp's own fields and on the retrieval date beside
them.

## Consequences

Value sets gain one definition each, so a member added in one place cannot leave
another copy validating the old set. Semantic duplication of the kind that hid
two identical enums becomes findable, because there is one name to find.

The honest cost is visibility of work not done. Retyping the degenerate stamp
converts 499 free certifications into an explicit backlog, and the tree will
report less assurance after this campaign than before it while being no less
correct. A reader who mistakes the new count for a regression will be wrong in a
way this record exists to prevent.

One-member and non-string unions remain unguarded. That is a deliberate limit,
not an oversight, and the degenerate conformance fields found so far were
found by reading the schema rather than by counting the tree -- so the method
that finds the next one is a schema read, not the gate.

The gate closes the class only for the registry schema. The same shape almost
certainly exists elsewhere in the codebase, and this record does not claim
otherwise; extending it is a later decision with its own evidence.
