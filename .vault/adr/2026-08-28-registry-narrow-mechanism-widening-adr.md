---
tags:
  - '#adr'
  - '#registry-narrow-mechanism-widening'
date: '2026-08-28'
modified: '2026-08-28'
body_schema: 'body-v2'
body_hash: 'sha256:cdb39e100641040577bb6c66eeb84e09569d51562308817561e8f54e0b094661'
related:
  - "[[2026-08-28-registry-narrow-mechanism-widening-research]]"
---

# `registry-narrow-mechanism-widening` adr: `widen three narrow registry mechanisms by declaration, never by matcher` | (**status:** `accepted`)

## Problem Statement

Three registry mechanisms were each written deliberately narrow, each says so in its own
docstring, and each has now met a real defect it cannot express. A decision is needed now
because the cheap remedy in every case is to loosen a matcher until the red clears, and
that readmits precisely the failure the narrowness prevents. One of the three was
attempted that way and had to be reverted, so this is an observed hazard rather than a
predicted one.

The evidence, including the measurements bounding each widening, is in
`2026-08-28-registry-narrow-mechanism-widening-research`. This record decides only what
each mechanism may admit and on whose authority.

## Considerations

- All three mechanisms guard the same thing: that a filing artifact's bytes are proven,
  not assumed. Loosening any one converts a proof into a plausible guess.
- Two of the three defects are latent rather than active. Modelo 165's era carries no
  export layout, and Modelo 303's coverage verdict is unproven rather than wrong. Modelo
  720's is live: an unanswered prompt emits blanks AEAT cannot parse.
- The narrowness in each case encodes a real discrimination problem, not caution. A
  single position with no naturaleza is genuinely indistinguishable from numbered prose;
  41 bundled designs open a description with the field's own range.
- Widening by matcher is unbounded and silent. Widening by DECLARATION is bounded by what
  someone wrote down and can be audited later.
- `2026-06-26-binding-source-kind-taxonomy-unification-adr` is accepted and already
  settles HOW a source kind is added; decision C is an instance of that procedure, not a
  competing rule.
- `2026-08-19-registry-export-layout-coverage-adr` governs whether a revision may claim
  the `filing` rung. It does not touch join or fallback mechanics, so nothing here
  contradicts it.

## Considered options

- **Widen each matcher until its case passes.** Rejected, and the reason is measured. For
  the row parser, "no position range means prose" would have dropped 8 legitimate
  single-position `BLANCOS` rows. For the constant sweep, treating all 46 diseño
  "Constante" fields as defects would have broken Modelo 714's correct fillers and
  hard-coded one branch of Modelo 369's genuine either/or. A matcher wide enough for the
  defect is wide enough for the false positives beside it.
- **Leave all three and let the ratchets carry them.** Rejected. Modelo 720's is a live
  blank-emission path, and the join ratchet exists to shrink; a permanently unshrinkable
  entry makes it decorative, the same failure the non-blocking CI guards were criticised
  for.
- **Widen by explicit declaration, per instance, with the declaration carrying its
  evidence.** Chosen. Each admission names its subject and cites the AEAT text that
  justifies it, so the set of admitted cases is enumerable and reviewable.
- **Route Modelo 720 through an inline literal.** Rejected on evidence: it violates the
  contract that three tests pin, and was reverted after being tried.

## Decision

**A narrow registry mechanism widens only by an explicit, evidence-carrying declaration
naming its subject. No mechanism widens by relaxing a matcher, a shape test, or a
predicate.**

Concretely, three admissions:

**A. A fourth `RecordDesignCorrection` kind for a mis-declared range start.** It names the
sheet, the wrongly-declared start, the corrected start, and the sibling editions that
evidence the correction. It is admissible only where no field is described in the vacated
span in ANY edition, so it can move a filler boundary and can never invent or displace a
data row. Modelo 165's `02-165-orden-hap-2455-2013.pdf` is the first subject.

**B. The auxiliary-envelope header contract stops pinning slots that are not
structural.** AMENDED TWICE on 2026-08-28, and the second amendment matters more than the
first: the REMEDY below is right and has already paid off, but the SUBJECT this decision
was written for turned out to need nothing at all.

Modelo 303's `DP30300` is **not an auxiliary envelope header and never was**. It is a
VARIABLE envelope: a 328-byte prefix, then a `Variable` body at offset 329 carrying "el
contenido de las páginas correspondientes a la declaración", then a
`"</T3030AAAAPP0000>"` relative closing. The parser classifies it correctly as such, and
`_build_sheet` skips the auxiliary path precisely BECAUSE a variable envelope was found.

It also never reached the fallback this decision set out to rescue it from. `DP30300` is
declared as the layout's `filing_envelope`, so the coverage check sets `is_envelope_sheet`
and answers from the envelope contract, DELIBERATELY skipping the join -- the code records
why: an envelope opens with the same `<T` and modelo bytes its page records do, so it
agrees with every one of them and would "join" a page whose fields sit at unrelated
offsets, which Modelo 353 demonstrated. Both the parser and the checker were already
right about Modelo 303. What was wrong was a ratchet inventory that counted "the join did
not fire" without enumerating the branches where the join is not attempted.

The first amendment's diagnosis of the CONTRACT still stands, and the remedy still earns
its place -- on a subject nobody predicted. Slots 0/1/2 differ across AEAT's own designs
only in SPELLING, and slot 4's `ANNUAL_PERIOD` role was pinned to the literal `"0A"`,
which made the contract annual-only by accident. Unpinning it admitted **Modelo 131's page
zero across all four revisions**, which had been rejected by exactly that accident and now
reaches the correct branch. That is the decision's real value: it was found by measuring
what the change actually did, not by reasoning about the case that prompted it.

The contract's over-specification, which is what this decision fixes, was measured on
`DP30300` before its true classification was known -- the reading holds regardless:

* Slots 0, 1 and 2 differ only in SPELLING. AEAT writes `Constante "<T"` in Modelo 390's
  design and a bare `"<T"` in Modelo 303's; likewise `Constante "0"` against `"0"`, and
  the modelo constant. Both spellings assert the identical constant. This is the same
  variance the row parser already tolerates for naturaleza tokens, whose own docstring
  records that a closed alternation "turns every variant into a SILENTLY dropped row".
* Slot 4 differs SEMANTICALLY, and this is the real blocker. Its role is named
  `ANNUAL_PERIOD` and it is pinned to the literal `"0A"`. Modelo 390 is an annual return
  so its period slot is that constant; Modelo 303 is quarterly and monthly, so its slot
  reads `"01"..."12" o "1T"-"4T"` -- a range, not a constant.

So the defect is an ACCIDENTAL PIN, not a missing declaration, and this codebase has
already fixed one instance of exactly this class. The comment beside
`_AUXILIARY_ENVELOPE_HEADER_MODELO_INDEX` records that pinning the modelo slot "made this
header contract single-modelo by accident: every other structural check -- roles, lengths,
rows, ordinals, extent -- is already modelo-neutral, so the literal was the only thing
rejecting an identical header on another form." The period slot is the remaining instance
of that same accident, one axis over.

The decision is therefore: the header contract asserts STRUCTURE -- roles, lengths, rows,
ordinals, extent, and the tag constants that make it an envelope -- and stops asserting
the filing CADENCE of the modelo that happens to carry it. The period slot accepts the
period vocabulary a revision's own selector already declares, exactly as the modelo slot
accepts any three-digit modelo. Spelling variance on a constant slot is read through the
constant, not the prose around it.

Declaring `DP30300` an exception is REJECTED twice over: it would have recorded a
spelling and cadence difference as a bespoke carve-out AND declared a variable envelope to
be an auxiliary header, which it is not. A declaration is right for a genuinely
exceptional subject and wrong both for a contract that was merely over-specified and for a
subject that was never exceptional.

THE DURABLE LESSON, and it cost four corrections to learn: an inventory built from "the
check did not fire" must enumerate every reason it might not have fired. The join ratchet
counted `_join_record(...) is None` and successively over-reported auxiliary headers,
sheets whose constants ride on bindings, and declared filing envelopes -- three distinct
branches where the join is deliberately not attempted. Each looked like debt and none was.

**C. A constant-supplying `BindingSourceKind` member.** It carries the constant's value
and is resolved without operator input, so a structural constant can stay a binding --
preserving Modelo 720's inline-representation contract -- while no longer being
answerable-blank. Added per the accepted taxonomy ADR's procedure: canonical core enum,
value equal to the stored token, an enrolled resolver or an explicit deferral, and the
registry-versus-enum parity gate.

## Constraints

- No frontier risk. All three are typed-schema and enum work over strict pydantic and
  StrEnum surfaces.
- **C has the wide blast radius.** A new `BindingSourceKind` member must reach every mesh
  resolver's `owned_sources`, the owned/deferred frozensets, and the parity gate in one
  coherent state before anything depends on it.
- **B must not disturb Modelo 232.** Its `DR23200` is already correctly classified in both
  revisions and reaches the correct branch; the widening adds a declaration path and
  changes no existing classification.
- **A must not become a general position editor.** The no-field-in-any-edition precondition
  is the whole guard; without it the kind degrades into arbitrary corpus rewriting.
- Modelo 184's export tree is GENERATED. Any equivalent fix there changes the mapping and
  republishes through `dev/registry`'s own check and publish authority; the committed tree
  is never hand-edited.

## Implementation

Each admission lands as schema plus declaration plus gate, in that order, and none is
useful without its gate.

A adds the correction kind to the discriminated union feeding
`RecordDesignExtraction.corrections`, so the existing worklist keeps treating "corrected"
as distinct from "complete" with no per-kind branch. The precondition is enforced at
extraction, not asserted in prose.

B adds a registry declaration consulted by `_auxiliary_envelope_header` alongside the
existing shape test, and the coverage module's header branch is reached by either route.
The generic fallback remains for genuinely unclassifiable sheets.

C adds the enum member, its resolver enrolment, and the M720 binding re-source. The
existing M720 contract tests stay untouched and must stay green: they are the proof the
fix preserved the design rather than routing around it.

Every admission is enumerable, so each gets a gate asserting its declared set is non-empty
and that every member still needs its admission -- the same both-directions ratchet the
provenance-only design exclusion already uses.

## Rationale

The knockout criterion is that a declaration is auditable and a matcher is not. When
Modelo 165's correction is declared, a reviewer can ask whether the sibling editions
really say 102 and whether the vacated span is really empty. When a matcher is loosened to
admit the same case, nothing records what else it now admits -- and the two measurements
in the research show that "what else" is large and includes correct behaviour.

The secondary criterion is that widening by declaration keeps each mechanism's original
guarantee intact for every case nobody declared. The narrow gates stay narrow; they simply
stop being the only door.

## Consequences

Modelo 720's live blank-emission path closes, and its two ratchet entries close with it --
by fixing the registry rather than reclassifying, which is the standard the ratchet was
built to hold. Modelo 303's coverage verdict becomes a real per-record proof across all
five revisions instead of the weaker any-record question. Modelo 165's authoritative
source stops carrying an undescribed span before its era acquires a layout.

The cost is three declaration surfaces to maintain, each of which can go stale. That is
why each carries a both-directions gate: an admission that no longer describes a real case
must be deleted, not left standing.

The pathway this opens is the one to watch. A declaration mechanism invites use, and the
research records the discrimination that must survive: only an UNCONDITIONAL constant on a
blank-capable channel is a defect, and `filler` for "Constante. Blanco" and a conditional
`[blanco | constante "C"]` are correct as they stand. If these admissions start absorbing
those, the widening has failed.

Not settled here: whether Modelo 303's `DP30300` is an auxiliary envelope in the same
sense as Modelo 390's page zero, or a third shape. Decision B declares it one because the
coverage branch is right for it; if it later proves a distinct shape, B's declaration is
the place that records the assumption.
