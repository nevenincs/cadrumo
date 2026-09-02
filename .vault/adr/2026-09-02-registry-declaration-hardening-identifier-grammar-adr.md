---
tags:
  - '#adr'
  - '#registry-declaration-hardening'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:0eb87a549160221991c79a1af31eef0f1955ca446ef9a56450c87f5eb1c4eadf'
related:
  - "[[2026-09-01-registry-temporal-coverage-live-remeasurement-adr-regrounding-audit]]"
  - "[[2026-09-02-registry-declaration-hardening-declaration-kinds-adr]]"
  - "[[2026-09-02-registry-declaration-hardening-plan]]"
---

# `registry-declaration-hardening` adr: `A modelo declares the identifier grammars it permits and what each one means` | (**status:** `proposed`)

## Problem Statement

A casilla identifier is the name every other declaration reaches the casilla by. Formulas target
it, bindings resolve to it, export fields address it, continuity chains assert identity across
revisions with it. Nothing constrains its shape.

Five grammars are in use across the corpus's 29522 casillas: numeric at 19990, dotted at 5622,
page-qualified at 2009, kebab at 1745, and bare token at 156. Twenty-one modelos use more than
one. After the grammar set was completed against the corpus, no identifier is unclassified, so
the five are a closed and complete description of what exists today.

An earlier account of this condition was wrong in both directions: it named three grammars and
twelve mixing modelos. Two shapes were missing from it. Kebab, a hyphenated form carrying no dot,
is the third most common in the corpus and its first segment is sometimes numeric.
Page-qualified is not a grammar at all but a compound, a page or block reference joined by a
colon to a tail that is itself one of the other shapes, so classifying it has to recurse into the
tail. A rule that checked only the head would accept any tail whatever and hide an unrecognised
identifier behind a valid prefix.

A restated identifier sits beside the identifier: a number field duplicates the numeric id, and
an alias field is used by no casilla at all.

## Considerations

The mixing is not obviously accidental. The largest cases are strongly asymmetric in a way that
suggests two roles rather than two conventions: one modelo carries 11272 numeric identifiers
beside 85 of other shapes, another 6516 numeric beside 119 page-qualified, another 1037 kebab
beside 8 dotted. Several are near balanced, which weakens the reading that the minority is always
an accident: one carries 60 numeric against 56 kebab, another 365 kebab against 190 dotted.

A numeric identifier in this registry is the official box number as the form prints it. A dotted
or kebab identifier names a domain concept the form does not number. Those are different kinds of
thing, and a rule of one grammar per modelo would force either inventing numbers for concepts the
authority never numbered, or abandoning the official numbers for boxes that have them. Both are
worse than the mixing.

A field that would have made the roles explicit is effectively dead: a form number is set on 138
of 29522 casillas. For numerically identified casillas the identifier already is the official
number, which is why the field is redundant, and it cannot serve as the discriminator.

Cross-revision continuity was expected to be the pressing risk here and is not. Measured across
the corpus, 1294 chains span 6090 casillas and not one crosses a grammar, and no evolution record
names a chain no casilla carries. The two decisions are therefore independent and this one does
not gate continuity work.

## Considered options

**Document the grammars and enforce nothing.** Costs nothing and protects nothing. The next
authored casilla can pick any shape, and the closed set stops being closed the moment somebody
writes a sixth.

**Declare one grammar per modelo and refuse a mixed modelo.** Simple to state and simple to
enforce. It requires re-identifying the minority side in twenty-one modelos, which for several is
not a minority, and it collides with the observation above: it would force a modelo carrying both
official box numbers and unnumbered domain concepts to give up one or the other.

**Declare the permitted grammars per modelo as a set, each bound to what it means.** A modelo
declares that it uses, for example, numeric for officially numbered boxes and dotted for domain
concepts the form does not number. The loader refuses an identifier whose shape is not in the
declared set, and refuses a shape used for a role the modelo did not declare it for. Mixing stays
legal where it is meaningful and becomes a declaration rather than an accident.

## Constraints

The grammar set is closed. An identifier matching no named grammar is a refusal, not an occasion
to widen a grammar until it matches. A sixth shape appearing in the corpus means the set, and any
contract written against it, no longer describes the registry.

A compound grammar classifies by its parts. A page-qualified identifier is permitted only when
its tail is itself a permitted grammar, so widening what may appear before the colon can never
silently admit an unrecognised identifier after it.

A modelo may not declare a grammar it does not use, and may not use one it has not declared.
Both directions are refusals, because a declaration that is merely permissive would drift back
into describing whatever happens to be there.

Re-identifying a casilla is an identity change, not a rename. Continuity chains, previous-filing
selectors, export field references and record row mappings all key on the identifier and move in
the same change, with an operator-reviewed preview before it lands.

## Implementation

Add the permitted-grammar declaration to the modelo definition, carrying for each grammar the
role it serves. Enforce it in the loader, consistent with the declaration-kinds decision, because
a warm load skips validator modules.

Seed the declaration from measurement rather than from intent: each modelo's current grammar
usage is what it declares initially, so enforcement begins by pinning the present state. That
turns the existing mixing into recorded fact and makes any future drift a refusal, without
requiring any re-identification to land first.

Retire the restated number field and the unused alias field under the declaration-kinds contract.
The number is derivable from a numeric identifier and is authored nowhere else useful; the alias
field has no users.

Re-identification, where a modelo's usage turns out to be genuinely accidental rather than
role-driven, is separate follow-on work per modelo and is not authorised by this record.

## Rationale

One grammar per modelo was the obvious rule and measurement argued against it. The registry
carries both official box numbers and domain concepts the authority never numbered, and a single
grammar cannot express both honestly. Declaring the permitted set with roles keeps the
information that mixing carries instead of destroying it.

Seeding from measurement rather than from a target state is chosen so that enforcement can land
before any data migration. The alternative sequencing, deciding the ideal grammar per modelo
first, leaves the registry unprotected for as long as that takes and invites the drift the record
is meant to stop.

The continuity argument that would have made this urgent was tested and did not hold, so this
record is sequenced on its own merits rather than as a prerequisite for continuity work.

## Consequences

The five grammars become a declared contract rather than an observation, and a sixth shape refuses
at load rather than passing unnoticed.

Mixing stops being ambiguous. A reader of a modelo can tell which shapes it uses and why, which is
information the registry does not currently carry anywhere.

Twenty-one modelos declare more than one grammar, and that is the recorded outcome rather than a
backlog. Any that are genuinely accidental surface as candidates for re-identification, but the
record does not presume which.

Two fields are retired: a restated number on every numerically identified casilla, and an alias
field with no users.

The cost is a declaration on every modelo definition and a loader refusal on a load-bearing path.
Seeding from current usage keeps the initial change data-only and behaviour-preserving, which is
what makes it safe to land before the re-identification questions are answered.
