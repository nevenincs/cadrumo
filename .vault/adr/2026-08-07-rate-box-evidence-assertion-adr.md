---
tags:
  - '#adr'
  - '#rate-box-evidence-assertion'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:a599754e03a39457281bbbd91d6433c74cd0c05817f7e324e4b6f3a7db932078'
related:
  - "[[2026-08-07-rate-box-evidence-assertion-research]]"
---

# `rate-box-evidence-assertion` adr: `an official box asserts only what the evidence determines; the return preserves the whole` | (**status:** `accepted`)

## Problem Statement

A casilla that both feeds a computed total and is exported to a rate-specific
AEAT box cannot serve either role correctly with a single binding. Modelo 390's
régimen-general tier casillas do exactly this today, and the consequence is a
filed artefact whose rate breakdown is false, established in
`2026-08-07-rate-box-evidence-assertion-research`.

A decision is needed now because the obvious repair is worse than the defect.
Narrowing the binding to the box's rate deletes every row whose rate was never
recorded, and the deleted amount leaves the declared total rather than moving to
another box. Two questions must be settled before any implementation, and
neither is an implementation detail:

What may an official box assert when the evidence underdetermines it? A ledger
row can record that a cuota exists without recording the rate charged. Placing
that row in a rate-specific box asserts a rate the operator never stated.

What may a return assert when its parts underdetermine its whole? If
underdetermined rows are kept in the total but excluded from every rate box, the
boxes sum to less than the total the return declares.

Both questions outlive Modelo 390. Every rate-keyed box on every modelo faces
them, including this form's four unmodelled régimen blocks.

## Considerations

Flow direction of error is not symmetric: a wrong breakdown misstates a
distribution, a wrong total misstates the amount owed. Project posture treats
silent under-declaration as the graver failure.

The application never files. It builds, validates and exports, and a human files
the artefact outside it, so a defect that survives export reaches the taxpayer
with no further gate behind it.

The underdetermined case already has a recorded decision against admitting it,
in the `applied_rates` docstring cited by the research. This record ratifies and
generalises that decision rather than making it fresh.

The intended architecture is also already described there: rate-blind bindings
serve totals, rate-specific bindings serve boxes, as complements. Modelo 390's
tier casillas were never split along that line.

The export contract already distinguishes a computed result that is blank
(a hard refusal, because the calculation failed to populate it) from an optional
operator input that is blank (a valid zero). Rate boxes are computed results.

The Modelo 390 to Modelo 303 reconciliation would fire as a shortfall under the
narrowing repair, for a reason nobody designed it for.

## Considered options

**Admit the underdetermined row into the tier's ordinary-rate binding.**
Cheapest, no new casillas, and it keeps every row in both the total and a box.
Rejected: it writes into an official box an assertion the operator never made,
and it is undetectable downstream because the box appears correctly populated.
This reverses a recorded decision rather than filling a gap.

**Narrow the existing tier bindings to their box rate, adding casillas for the
remaining rates in one atomic commit.** Fixes the breakdown for rows whose rate
is recorded. Rejected: every new binding is keyed on the same optional field, so
no casilla claims the underdetermined rows and they leave the total. Atomicity
cannot help, because the conflicting roles live inside one casilla.

**Split the roles: rate-specific casillas for the boxes, a rate-blind casilla
for the total.** Chosen. Fixes the breakdown, keeps every row in the total, and
asserts a rate only where the evidence determines one.

**Make the rate mandatory wherever a cuota exists.** Correct at source and
removes the underdetermined case entirely. Deferred, not rejected: it is a
data-model change over existing ledger rows carrying a backfill-or-refuse
question, and it does not repair rows already recorded. It belongs in its own
record.

**Leave the merge in place.** Rejected: the false breakdown reaches a filed
artefact in a return whose rate boxes AEAT reconciles.

## Constraints

The `applied_rates` selector axis already exists and discriminates correctly, so
no schema change is required for the rate-specific half. No mechanism exists to
express "this row's rate is unknown" as a selector; the rate-blind binding
covers that case by not discriminating, which is sufficient for this decision
and adds no new expressiveness.

The rate boxes depend on the registry rate catalogue for grounding, and that
catalogue currently resolves only 2024 while the Modelo 390 revision declares a
span beginning 2010. This does not block the decision, because the roles split
identically whatever the catalogue covers, but it bounds how far back the
rate-specific boxes can be populated. It is tracked separately and deliberately
not resolved here.

This record governs the Reg. ordinario block. The four unmodelled régimen blocks
are CANDIDATES to follow this decision, not inheritors of it: neither their box
sets nor the precondition in the amendment above have been measured for them.
Each must be checked for a rate-blind total before the two-layer shape is applied,
because where a block's tier boxes are themselves the operands of its total the
shape double-counts.

### Two vocabularies name the same slots, and nothing reconciles them

Modelo 390 addresses its export slots by semantic casilla id (`iva.anual.*`)
while the AEAT record design addresses them by official box number. The two sets
do not intersect at all: the bundled 2024 design yields 311 distinct box numbers
and the layout declares none of them. The correspondence exists only as a
position — the offset a field occupies inside an export record — and resolving
it requires also disambiguating which régimen segment the record belongs to,
because every position in that design appears twice, once under Reg. ordinario
and once under Recargo de equivalencia.

This is a keying mismatch between two naming systems, not a coverage gap, and it
has bitten from both directions already. Reading it from the casilla end, the
absence of a box number was mistaken for the absence of any mapping, which made
a live mis-declaration look latent. Reading it from the corpus end, a
number-keyed cross-check of the layout against the official design matches
nothing on this modelo and would report every one of its 311 boxes as missing.

This record does not solve the mismatch. It narrows it, because every box-layer
casilla it introduces carries its official box number explicitly rather than
leaving the correspondence implied by position, extending the partial numeric
layer that eight Modelo 390 casillas already carry. A consumer that needs the
full mapping still cannot derive it from the registry alone, and should expect a
bare-offset match to be ambiguous while looking conclusive.

## Implementation

Each rate-specific official box gains its own casilla, bound by a selector that
admits exactly that rate, carrying its official box number, and carrying the
export reference that writes it to its position in the record design. These
casillas are the box layer: they are populated only from evidence that
determines the rate, and a row that does not determine one never reaches them.
Stating the box number on the casilla is what keeps the mapping readable rather
than implied, so a later consumer need not re-derive it from offsets.

The existing tier casilla keeps its rate-blind binding and continues to feed the
devengada total, but loses its export reference. It becomes the total layer,
internal to the calculation, catching every row including those whose rate is
unknown. No official box is written from it.

Where the two layers disagree — that is, where the rate boxes sum to less than
the rate-blind total — the difference is exactly the underdetermined amount.
That difference is surfaced at two gates with different severity.

At calculate, a non-blocking advisory naming the unrated amount and its tier,
carried through the typed notice channel. Calculate must succeed, because the
operator needs to see the position in order to repair the ledger, and refusing
there would withhold the information the repair depends on.

At export, a refusal. A return whose rate boxes do not account for its declared
total is structurally incomplete in the same sense the export completeness gate
already refuses a blank computed result, and rate boxes are computed results
rather than optional operator inputs. The artefact is what a human files, so an
inconsistency that survives export costs the taxpayer a correction they cannot
make, where a refusal costs them a ledger repair they can.

## Rationale

The chosen option is the only one that leaves both quantities true. The
breakdown becomes accurate because each box draws only from rows that determine
its rate; the total stays whole because the rate-blind layer keeps every row.
The alternatives each sacrifice one to save the other.

The knockout against admitting the underdetermined row is not cost but
truthfulness at the filing surface. A box that says "charged at 10 %" on
evidence that says only "a cuota was recorded" is a fabricated assertion, and it
is worse than either defect it resolves precisely because it looks correct. The
research shows this shape was already rejected in code for the same reason,
which makes it a constraint rather than a preference.

The knockout against narrowing is that it trades a wrong breakdown for a wrong
total. The research measures the trade directly: a rate-blind binding returns
20.00 across a rate-recorded and a rate-unrecorded row, and the narrowed binding
returns 10.00, with the difference leaving the return rather than moving boxes.

Splitting the advisory and the refusal across two gates avoids a false choice.
The question is not whether an incomplete breakdown is acceptable, but where it
is actionable. During calculation it is information the operator can act on;
at export it is a defect about to leave the system.

## Consequences

The Modelo 390 rate boxes become individually trustworthy: a populated box
reflects rows that actually carried its rate, and an empty box means no such
evidence exists rather than that the money went elsewhere.

A taxpayer holding rate-unrecorded rows will be refused at export until the
ledger records those rates. This is a real cost and a new one — such a taxpayer
can export today, with a silently mis-allocated breakdown. The refusal is the
intended trade, and the calculate-time advisory exists so the refusal is never
the first notice.

The rate-blind total casilla becomes load-bearing in a way that is easy to
break: any later change narrowing it re-creates the deletion this record
forbids. That property needs an explicit regression, not a comment.

The Modelo 390 to Modelo 303 reconciliation keeps its role unchanged, since the
total layer preserves exactly the rows the quarterly bindings preserve.

The two-layer shape generalises to every rate-keyed box **whose modelo carries a
rate-blind total**, and is the expected pattern for the unmodelled régimen blocks
only where that precondition holds, which means the implementation should read as
a pattern rather than as a Modelo 390 special case.

**Amendment — the precondition, which this record originally omitted.** The
two-layer shape requires a total that is NOT the sum of the tier boxes. Where the
tiers themselves are the total's operands, the rate-blind layer is not a safety
net: it is a duplicate, and it double-counts into the total.

Modelo 303 is the measured counterexample. Its `[27]` total-cuota-devengada
formula enumerates the tier cuota boxes directly, including the RD-ley 4/2024
transitional rungs' `[155]` and `[167]`, so it has no rate-blind total for a
second layer to feed. Adding a rate-blind sibling alongside those tiers would add
the same money twice rather than catch a residue. The original claim that the
shape generalises to *every* rate-keyed box was therefore false as written, and
the failure was one of scope rather than of reasoning: the shape is right on
Modelo 390 precisely because Modelo 390's total is not the sum of its tiers.

Each modelo must therefore be TESTED against this precondition rather than
assumed to satisfy it. That is an instance of the standing rule that AEAT
surfaces do not transfer between modelos.

Making the rate mandatory at source remains open, and until it lands the
refusal at export is the only thing preventing an incomplete breakdown from
being filed.

A cross-check gate reading the bundled record designs is sequenced behind this
work. Such a gate would close the export contract's blind spot, where the set of
representable casillas derives entirely from the layout declaration with nothing
confirming it against the official record. It is currently blocked on the
vocabulary mismatch above: keyed by box number it matches nothing on Modelo 390
and would report all 311 of its boxes as absent. Every box-layer casilla this
record introduces states its official number, so each one is a slot that gate
can reconcile. Four tiers is not the whole mapping, and the gate should not be
built on the assumption that this record completes it.
