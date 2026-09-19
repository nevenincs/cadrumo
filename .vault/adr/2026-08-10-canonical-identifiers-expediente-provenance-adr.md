---
tags:
  - '#adr'
  - '#canonical-identifiers'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:89d9c26b268c33fcac7d480080c02a3e5bd3979e5779d60c2fc38a58fb5ebb99'
related:
  - "[[2026-08-07-canonical-identifiers-adr]]"
  - "[[2026-08-07-canonical-identifiers-reference]]"
---

# `canonical-identifiers` adr: `IVA compensation expediente provenance` | (**status:** `accepted`)

## Problem Statement

The parent decision record enrolled three AEAT-issued identifier namespaces
onto typed aliases and left one field behind: `expediente_id` on the Modelo 303
compensation period state. An earlier attempt to retype it onto the tighter
alias was reverted on the finding that the loose bound is load-bearing, and the
field has stood since as the one un-enrolled member of an otherwise-closed
taxonomy, carrying `min_length=1` with no stated reason.

"The loose bound is load-bearing" is true and is not a decision. It records
that the field admits two populations without saying which, whether both belong
there, or what a reader is entitled to conclude from a value found in it.
`2026-08-10-canonical-identifiers-expediente-provenance-reference` measures
those populations. A decision is needed now because every remaining enrollment
Step in the parent plan treats this field as deferred rather than decided, and
a deferral with no stated release condition is an abandonment.

## Considerations

- The field is supplied by five production paths, and only one of them supplies
  an AEAT-issued value. The other four mint local markers - grounding
  reference, "The five supplying paths".
- Two of the five do not construct the model at all; they pass a bare `str`
  through a shared conduit pair, so the two provenances are already
  indistinguishable at the point the field is set - grounding reference, same
  section.
- The codebase already names the polymorphism in prose, in the local-filing
  helper's own docstring and in its caller's parameter documentation. What it
  does not do is represent it - grounding reference, same section.
- Provenance is already encoded twice more, informally: as a prefix convention
  inside `source_observation_key`, and partially in `status`. Nothing validates
  either, and neither can be parsed back reliably - grounding reference,
  "Provenance is already encoded, informally, in two other fields".
- Each of the four non-AEAT markers carries strictly less information than the
  `source_observation_key` written beside it at the same site - grounding
  reference, "Every non-AEAT marker is strictly redundant".
- The compensation-history storage key is derived from the period and does not
  fold this field, so a representation change orphans no persisted record. The
  namespace that does fold an expediente belongs to the sede adapter and holds
  a different record type - grounding reference, "The storage key does NOT fold
  this field".
- **The field has zero production readers.** It is written by five paths,
  persisted, and read by nothing outside tests. This is the consideration most
  likely to be misread, and it is treated under Rationale rather than taken at
  face value here.
- Two neighbouring fields in the same model each document exactly which absent
  case their `None` represents; the polymorphic one documents nothing.
- The parent record's own rejected shape-only resolver applies here: the four
  markers are not a closed vocabulary and cannot be reliably told apart from an
  AEAT value by inspection.

## Considered options

1. **A discriminated pair: `AeatExpedienteId | None` plus a closed provenance
   enum (chosen).** The field becomes optional and typed, carrying a value only
   where AEAT issued one; a separate required enum carries which of the five
   paths produced the row. Costs a new required field on a persisted model and
   a change at all five supplying sites.
2. **Delete `expediente_id` from the model and rely on
   `source_observation_key`.** Cheapest, and the redundancy measurement
   genuinely supports it for all five paths, the AEAT one included. Rejected:
   it promotes an opaque composite string to sole carrier of a filing-evidence
   identifier, recoverable only by splitting on a delimiter no type enforces,
   and it discards the provenance axis entirely rather than representing it.
3. **Keep `min_length=1` and add a field description declaring the
   polymorphism.** Rejected: it documents the defect rather than closing it.
   Nothing validates a description, and a consumer still cannot tell an
   AEAT-issued expediente from the literal `manual-seed` without knowing the
   four minting conventions by heart.
4. **Retype to `AeatExpedienteId` outright and have the four non-AEAT sites
   mint AEAT-shaped values.** Rejected outright, and named here because it is
   the option a mechanical enrollment sweep would reach for. It manufactures
   values that impersonate AEAT-issued filing evidence, which is a strictly
   worse failure than the loose bound it would close.
5. **Infer provenance from the marker string's shape at read time.** Rejected
   on the parent record's own reasoning against shape-only namespace inference,
   and additionally because the four markers are an open convention rather than
   a closed set.

## Constraints

- No production code lands from this record. It is followed by Steps in the
  parent plan, each gated on its own verification.
- The new enum is a closed value set and lands in `core/` per the standing
  architecture rule, not beside the model. The sibling lifecycle enum already
  declared in the same domain module is inconsistent with that rule; this
  record does not rule on the sibling and does not use it as precedent.
- The provenance field is REQUIRED with no default. A default would let a new
  supplying path omit it and inherit a provenance it did not declare, which is
  the same silent-default hole this campaign has already closed elsewhere.
- Both conduit functions must take the provenance explicitly alongside the
  expediente. Adding the enum to the model alone cannot work: the two conduit
  callers are indistinguishable by the time the model is constructed.
- The change requires a strict roundtrip with every defaultable field populated
  non-default plus an anti-tautology proof, per the standing quality-gates
  rule. The anti-tautology proof deletes the persisted provenance and asserts
  refusal.
- **The close condition is a control, not the new refusal.** The refusal firing
  on `manual-seed` proves only that the constraint exists. The Step does not
  close until the wallet-balance, binding-prefill and carry-ingress paths are
  shown still to construct and load every legitimate row. A refusal correctly
  shaped can still be wrongly sized.
- Test corpora carrying non-AEAT-shaped literals are updated to the new shape
  in the same commit. They are fixtures, not persisted operator data, and this
  tree is pre-release, so no upgrader is written and none may be.

## Implementation

A closed `StrEnum` in `core/` names the five supplying paths, one member each,
with no catch-all member: an unlisted future path must be added to the enum
rather than absorbed. The names distinguish an AEAT capture, a local filing, a
casilla reconstruction, an operator seed and an operator correction, matching
the five paths the grounding reference enumerates.

The period-state model gains that enum as a required field and narrows
`expediente_id` to the typed AEAT alias or `None`. The two are constrained
against each other by a model validator, so the pair cannot express a state the
domain does not have: an AEAT-capture row must carry an expediente, and a row
of any other provenance must not. That validator is the whole point of the
pair - two independent optional fields would permit an operator-seeded row
carrying an AEAT expediente, which is the impersonation this record exists to
prevent.

The two conduit functions take the provenance as a required parameter beside
the expediente, so each of their callers declares its own. The three direct
construction sites declare theirs inline and drop their markers. Nothing is
lost by dropping them: each is a lossier duplicate of the
`source_observation_key` written at the same site.

What this record does NOT do: it does not touch the sede observation store or
its key grammar, it does not alter `source_observation_key`, and it does not
reconcile `status`, which remains a partial third encoding of the same axis.
That reconciliation is a separate question and is named here as excluded rather
than left unmentioned.

## Rationale

The knockout is the zero-readers measurement, read correctly rather than at
face value.

A field with no production readers looks like an argument for deleting it, and
option 2 is the honest expression of that reading. But zero readers is evidence
about the symbol and never about the capability. The reason no surface reads
this field is that no surface *can*: a consumer holding one of these values
cannot tell whether it is an AEAT expediente that would resolve at AEAT's
expediente-detail endpoint or the literal string `manual-seed`. The
polymorphism did not merely fail to help a reader; it suppressed the readers.
Deleting the field on a no-readers argument would therefore delete a capability
the defect was hiding, and would do it while citing the defect's own symptom as
the justification.

Option 1 wins because it is the only option under which a consumer can act on
the value. With the pair in place, a surface that wants to link an operator to
the AEAT expediente behind a filed period reads one typed field and one enum
and knows, without convention, whether it holds filing evidence. Option 3
leaves that consumer exactly where it is. Option 4 gives it a value it can act
on and is wrong to trust. Option 5 asks it to re-derive by shape what the
producer already knew and threw away, which the parent record already ruled
against.

The cost side is unusually cheap for a persisted-model change, and that is
measured rather than assumed: the storage key does not fold this field, so
nothing orphans, and every marker being dropped is strictly redundant against a
field written beside it. Those two facts are what make the pair affordable
here and would not transfer to another field without being re-measured.

## Consequences

**Gains.** The provenance distinction becomes representable, validated and
queryable instead of being carried three times by string convention. The four
local markers that currently sit in a field named for an AEAT identifier stop
impersonating one. The parent taxonomy closes over its fourth namespace rather
than carrying one permanently-deferred member.

**Difficulties.** A required field with no default on a persisted model means
every construction site changes in one commit, including test corpora, and the
conduit signature change reaches two application packages. The alternative -
a default - is the hole this record refuses.

**Pathway opened.** The five-member enum gives any future supplying path an
explicit enrollment point instead of a free-text convention, and gives an
operator surface the discriminator it needs to link a filed period to its AEAT
expediente for the first time.

**Pitfall.** The seam this record draws is specific to this field, and the
reasoning does not generalise. It holds because the storage key does not fold
the value and because every dropped marker is redundant against a neighbour.
Any attempt to apply the same pair to another identifier field must re-measure
both, and a reader treating this record as a template for the other AEAT
namespaces will get the storage-orphaning question wrong at the sede store,
where the key grammar does fold the expediente.

**Unmeasured, stated rather than buried.** Whether this polymorphic-slot shape
recurs on any other model was not swept - the grounding is scoped to this one
field. And the claim that the four minted values are not AEAT-issued rests on
their construction sites rather than on an AEAT publication of what it issues.

## Amendment (2026-08-10): a prior provenance taxonomy exists, and `status` already leaks into it

Caught by the implementing lead's discovery pass **before any code was written**,
which is the only reason this is cheap. Three things needed ruling and this
record answers all three, because a ruling that answers only the obvious one
creates the duplicate it was meant to close.

### What the original record missed

Neither this record nor its grounding reference mentions
`ObservationSourceKind`, a five-member `StrEnum` at
`application/calculations/_observations_repository.py` carrying `APP_FILING`,
`OPERATOR_MANUAL`, `AEAT_SEDE_JUSTIFICANTE`, `AEAT_SEDE_LIVE_CAPTURE` and
`AEAT_CSV_REGISTER`, plus an `is_official_aeat` property that decides
filing-grade authority. Both documents were grepped and it appears in neither.

Worse, the grounding reference already recorded that `status` is "a third
partial encoding of the same axis" and did not follow it one step further. It
is not a partial encoding. **The local-filing path stamps
`APP_FILING_SOURCE_KIND` into `status`, which is literally
`ObservationSourceKind.APP_FILING`** — so that taxonomy is already being written
into this model, through a field this record proposed to leave alone.

### Ruling 1 — the two taxonomies COEXIST, and here are the grounds

Coexistence is defensible on subject grounds and indefensible if nobody states
them, because a later reader finding two provenance enums with no recorded
reason will merge them or add a third. So the grounds are recorded rather than
assumed:

- **Different subjects.** `ObservationSourceKind`'s own docstring says it
  classifies the origin of a persisted calculation OBSERVATION.
  `IvaCompensationPeriodState` is not an observation; it is a derived
  per-period compensation row.
- **One member has no counterpart.** `CASILLA_RECONSTRUCTION` builds a state
  from casilla values with no observation at all, and that site documents
  itself as computational scaffold that is never persisted.
- **One distinction is destroyed by the alternative.** `OPERATOR_SEED` and
  `OPERATOR_CORRECTION` are separate paths; `ObservationSourceKind` has a
  single `OPERATOR_MANUAL`. The current `status` field already destroys this
  distinction by writing the same literal for both, which is evidence for
  keeping it rather than against.
- **Reuse would import a filing-authority predicate.** `is_official_aeat`
  decides which provenances establish filing-grade cross-period readiness. A
  compensation row must never confer filing authority, and the standing rule
  keeping `app_filing` out of the official set exists precisely because that
  confusion is available. Importing a taxonomy whose property *decides*
  officialness onto this model invites it.

### Ruling 2 — `status` is NOT left untouched, and this is the larger half

Adding a provenance field beside a `status` that already holds `app_filing` on
one path would leave the model **self-contradicting by construction on four of
five paths**: two fields answering "where did this row come from", disagreeing
structurally. That ruling would have created the duplicate rather than closed
it.

Measured, `status` currently carries three incompatible subjects:

| path | `status` written | subject |
| --- | --- | --- |
| AEAT capture | the captured register status | an AEAT-printed external fact |
| local filing | `APP_FILING_SOURCE_KIND` | provenance, from the other taxonomy |
| casilla reconstruction | a `"filed"` literal | app lifecycle, on a never-persisted row |
| operator seed | the seeded literal | app lifecycle |
| operator correction | **the same** seeded literal | app lifecycle, indistinguishable from seed |

`status` cannot simply be deleted: the domain lot builder branches on the
seeded literal to surface a seeded opening balance as an available lot even at
zero generated amount, and the wallet CLI emits `status` to the operator in both
its JSON and its text form. So the operator today sees a register status, a
source-kind token and two app literals in one field, and cannot tell an operator
seed from an operator correction at all.

**Ruling:** once the provenance field exists, `status` narrows to `str | None`
carrying ONLY the AEAT-printed register status, `None` on every other path. The
seeded-literal branch re-expresses against the provenance member, which is what
it was really asking. The reconstruction path's literal disappears with it — that
row is never persisted and the literal never meant anything. The operator surface
emits provenance and register status as separate fields.

**This lands in the SAME commit as the provenance field.** Split across two, the
tree carries a model with two disagreeing provenance carriers, which is the
state this amendment exists to prevent.

### Ruling 3 — the population control was satisfiable against the wrong field

`W02.P02.S65` was written as a population measurement so it could not pass
vacuously. With `status` still carrying provenance, an implementer could satisfy
its disconfirming clause by reading provenance off `status` — **a control that
can pass against the wrong field is vacuous in a way its author cannot see**, and
this author did not see it.

The control now asserts against the new field AND asserts that `status` is `None`
on every non-AEAT path. That second half is a claim only the ruled design can
satisfy, so the control cannot be met by the shape it exists to reject.

### Unchanged, and load-bearing for all three rulings

Two of the five provenances reach the model through the conduit pair, which takes
a bare `str`, so they are indistinguishable where the model is built. **Whichever
enum wins, the conduit signature must carry the provenance**, or two of five
members are unassignable at the only place they could be set. That was the
original record's finding and no part of this amendment relaxes it.
