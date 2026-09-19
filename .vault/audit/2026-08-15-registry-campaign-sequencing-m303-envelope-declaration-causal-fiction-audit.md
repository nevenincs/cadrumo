---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:00aa977f3a074bb25ebbe00e93de54629fd8e67da608c3aad1b2df97ccfdb2eb'
related:
  - "[[2026-08-14-registry-campaign-sequencing-preflight-test-vacuity-audit]]"
---

# `registry-campaign-sequencing` audit: `M303 filing-envelope declarations that describe behaviour they do not drive`

## Scope

Two fields on the Modelo 303 filing-envelope declaration -- `total_derivation` and
`product_identity_requirement` -- were reported as orphaned. They are not. The
audit establishes what they actually are, because the answer changes what should
be done with them, and because the same shape governs three sibling fields.

The investigation was prompted by a broader sweep for schema that no code reads.
That sweep produced two unrelated results: a family that was never built, recorded
separately, and this one, which is the opposite case and needs the opposite
treatment. The fields are left untouched; this is a report.

## Findings

### behaviour-exists-declaration-inert | medium | Both declared behaviours are implemented and enforced, but not from the declaration

`total_derivation` names an emitted-byte total, and the export path does enforce
exactly that: rendering refuses unless the envelope total is derived from the
emitted bytes. `product_identity_requirement` names an AEAT product/software
identity requirement, and Modelo 303 export refuses outright when no such identity
authority is supplied. Neither behaviour is missing, and neither casilla resolves
to a blank.

What is absent is the causal link. Production hardcodes the one sanctioned version
of each behaviour rather than dispatching on the declared token. Within the
shipped package the two fields appear only in test fixtures that construct them.
No registry authoring TOML declares the envelope at all; it is built by the
development-side generator.

This is why the case is not symmetrical with a never-built family. Deleting a
declaration nothing supports removes a false claim. Deleting these would remove a
description of behaviour that genuinely exists, which is a different and worse
trade.

### causal-fiction | medium | The defect is that a reader believes the declaration governs

The cost is not a runtime gap; it is a false belief about where authority lives. A
reader encountering a declared derivation token reasonably concludes that changing
it would change what the exporter does. It would not. The token is inert, and the
behaviour it names is fixed in application code some distance away.

That misreading is expensive in this codebase specifically, because the registry
is the declared authority for almost everything else. A field that looks like
registry-governed configuration, in a model whose whole purpose is to declare an
envelope grammar, is read as governing by default.

### unfireable-guard | high | The terminal case: a guard in the export path over a field that cannot vary

`closer_derivation` is the same shape carried one step further, and it reached
shipped code. The export path compared the declared closer derivation against its
only admissible value and raised on mismatch. The field is a required
single-valued literal on a frozen model, so the schema refuses any other value at
construction and the value cannot change afterwards. The comparison therefore
re-tested, at render time, a condition that was already unconstructible at build
time. The branch could never be taken.

It read as protection in the export path of a filed artefact. It was decoration,
and nothing in the surrounding code disclosed that.

Measured before acting: the field is required, its declared type admits exactly
one value, and construction with any other value is refused with an error naming
both the field and the sanctioned value. The guard was removed rather than made
fireable, because the alternative -- inventing a second vocabulary member so the
comparison could fail -- would fabricate a distinction the source design does not
have in order to justify a line of code. Rendering was confirmed byte-identical
across sixteen filing periods, and the invariant survives the removal, enforced
earlier and more strictly by the type.

### zero-bit-declarations | high | A single-valued literal cannot discriminate, so it cannot be a contract

Five axes share one root cause. Four of them -- two on the algorithm provider
family, two on the filing envelope -- are declared as single-valued literals, and
the fifth was until its guard was removed.

A field that admits exactly one value carries no information. It cannot record a
choice, cannot refuse a wrong one beyond what its own type already refuses, and
cannot select behaviour. It reads as a claim while functioning as a comment with a
type annotation. The determinism and side-effect-freedom markers on the algorithm
provider family are the clearest illustration: they are not constraints a provider
must satisfy, because they can only ever be written true.

The tests asserting these tokens shared the defect. Each compared a generated
declaration against the literal the generator emits, so it would pass equally if
the constant were changed on both sides. Those assertions were removed rather than
rewritten, after confirming that the type already refuses every one-sided change
and that the assertions therefore added nothing: a coordinated two-sided change is
the only thing they could have caught, and they passed under it.

## Recommendations

Leave both envelope fields in place. Whether the exporter should dispatch on the
declaration, rather than hardcoding the sanctioned version beside it, is a
decision about where authority lives for export grammar, and it belongs to the
owner of that boundary rather than to this audit.

A follow-on decision record, if this is pursued, must rule on one question: is the
filing-envelope declaration the authority for how the envelope is rendered, or is
it documentation of what the renderer independently guarantees. Both are
defensible; what is not defensible is the present state, where it reads as the
first and behaves as the second.

If the ruling is that the declaration governs, then a single-valued literal is the
wrong type for every one of these axes. The vocabulary needs a genuine second
member before any dispatch on it can mean anything, and that member must come from
the source design rather than be invented to make a comparison possible.

If the ruling is that the declaration documents, then say so where the field is
declared, so the next reader does not spend the same effort establishing that the
token is inert.

Treat a single-valued literal as a smell wherever it appears on a declaration
model. It is defensible as a schema-version pin or a discriminator awaiting its
second member, and indefensible as a contract term, because a term that cannot be
violated is not a term.
