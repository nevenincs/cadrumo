---
tags:
  - '#adr'
  - '#tuimodelo'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:08372fc220272c83d23b8b08e49b98e077e279546f7ff78e05c27f0ef2465cb6'
related:
  - "[[2026-09-07-tuimodelo-reference]]"
  - "[[2026-08-05-arch-remediation-registry-format-casilla-section-order-adr]]"
  - "[[2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr]]"
  - "[[2026-08-24-tui-modelo-workspace-interface-adr]]"
  - "[[2026-08-10-casilla-schema-read-model-adr]]"
  - "[[2026-08-24-tui-registry-api-gate-adr]]"
  - "[[2026-09-07-tuimodelo-adapter-migration-adr]]"
  - "[[2026-09-07-tuimodelo-reconcile-verify-adr]]"
---

# `tuimodelo` adr: `declared form projection for schema-derived declaration surfaces` | (**status:** `proposed`)

## Problem Statement

The declaration surfaces must be generated rather than hand-built. There are 58 modelos over
128 revisions and 29,678 casillas; hand-authoring a screen per modelo does not scale, will
not track revisions, and is the reason the current editor renders every casilla as an
identical unlabelled text box (`2026-09-07-tuimodelo-reference`).

Generation needs an ordering and a grouping that the registry does not carry: there is no
order, page, row or column field on a casilla, and the section tuple is untranslated and far
finer than the printed form (`2026-09-07-tuimodelo-reference`). The obvious candidate —
deriving order from fixed-width export offsets at runtime — is measurably right where it
applies and measurably absent where it does not.

An accepted decision has already treated section order as an ungated presentational concern
and, when it considered how a presentation sequence should be expressed, pointed at explicit
data on the casilla or its export layout rather than an inferred one
(`2026-08-05-arch-remediation-registry-format-casilla-section-order-adr`). That record was
addressing fragment filenames and authoring conventions rather than runtime reads, so it
constrains the shape of an answer without dictating one; this record decides the runtime
question it left open.

A decision is needed before any editing, review or reconcile surface is built, because all
of them render the same projection and none can be specified until its shape and its
coverage are settled.

## Considerations

- Offset order tracks the official form closely where offsets exist, and section-plus-declaration
  order does not. A probe against the official record design shipped in the corpus reported a
  perfect rank correlation for modelo 303 in 2025 against a near-zero one for the alternative.
  An independent pass could not reproduce the probe's casilla population, so the exact
  correlation figure is not yet established and this record does not rest on it; re-measuring it
  is an open item. The qualitative ordering — offsets close, declaration order uncorrelated — is
  corroborated separately by section contiguity at every modelo measured
  (`2026-09-07-tuimodelo-reference`).
- Declaration order is a filename sort. Modelo 390 compiles as 716, 717, 683, 684, 21, 22
  and modelo 303 similarly; it works for two modelos by naming accident
  (`2026-09-07-tuimodelo-reference`).
- Offsets place 11,268 of 29,678 casillas. Of the 18,410 unplaced, only 97 carry any
  classification, so 61.8 per cent would vanish with no diagnostic across 101 of 128
  revisions (`2026-09-07-tuimodelo-reference`).
- Modelo 100 declares an export layout with zero records, zero fields and zero offsets on all
  six revisions, and no casilla carries an export reference. The flagship consumer form gets
  total fallback (`2026-09-07-tuimodelo-reference`).
- Modelo 100 nevertheless has a better source already in the tree: RentaWeb dictionaries and
  schema definitions covering 2,215 of 2,249 casillas with a deep path tree and a large set of
  official group headings. Those dictionaries are already production inputs — the registry
  treats them as layout authority evidence and carries a dictionary-path override mechanism
  against them — but nothing reads them for presentation order or grouping, and that override
  seam is the natural home for the seed this record proposes
  (`2026-09-07-tuimodelo-reference`).
- The official section headings exist and are joinable. The record-design corpus is 749 files
  across 58 modelo directories, 56 of them carrying extracted sidecars, and a large majority of
  casillas join to a verbatim official description; the extraction module is production code,
  not a development script. The precise join rate is an open measurement
  (`2026-09-07-tuimodelo-reference`).
- An accepted decision names explicit data on the casilla or its export layout as the
  sanctioned way to express a presentation sequence, and records that the official record
  design is number-keyed rather than section-contiguous
  (`2026-08-05-arch-remediation-registry-format-casilla-section-order-adr`).
- A single modelo work review read model is already accepted as the one read model for this
  surface, and its problem statement warns against re-deriving a second one
  (`2026-08-10-casilla-schema-read-model-adr`).
- Label honesty and the disclosure of an untranslated fallback are already owned by an
  accepted amendment and are not reopened here
  (`2026-08-24-tui-registry-api-gate-adr`).
- Flattening repeated blocks into per-slot scalars is forbidden
  (`2026-06-13-m303-form-vs-semantic-casilla-dual-keying-adr`), which is exactly what naive
  offset ordering does to row-bearing records.
- 812 casillas in modelo 200 are addressed on between two and eleven pages, and 1,062 resolve
  to multiple export fields corpus-wide (`2026-09-07-tuimodelo-reference`).
- Hiding computed and internal casillas does not reduce the surface at scale: modelo 200's
  input surface is 3,452 of 3,462 (`2026-09-07-tuimodelo-reference`).
- Casilla labels are complete — all 29,678 resolve in all four locales — but a shipped
  workspace path bypasses the continuity tier and degrades them to bare identifiers, at 97 per
  cent on the two worst modelo 303 revisions and 74 per cent across that modelo overall
  (`2026-09-07-tuimodelo-reference`).
- The value parser returns raw text for 12 of 19 data types, so 4,715 filing-bound casillas
  including identity and bank-account fields accept any string, and the declared
  unsupported-kind refusal is constructed nowhere
  (`2026-09-07-tuimodelo-reference`).
- Constraints are absent on 96.9 per cent of casillas and default to none, so a generator
  cannot distinguish unconstrained from unmeasured (`2026-09-07-tuimodelo-reference`).
- Presentation must be a typed application read model, not registry schema interpreted into
  widgets in the frontend (`2026-08-24-tui-modelo-workspace-interface-adr`).

## Considered options

1. **Runtime offset interpretation.** Rejected on coverage and diffability, not on governance:
   it silently drops 61.8 per cent of casillas, produces nothing at all for modelo 100, leaves
   the form free to reshuffle between revisions with no gate able to notice, and infers row
   structure from slot and offset semantics that the dual-keying decision deleted. It also sits
   awkwardly with the accepted preference for explicit data, though that record was not ruling
   on runtime reads.
2. **Section tuple plus declaration order.** Rejected: declaration order is a filename sort,
   and the ordering it produces is uncorrelated with the official form.
3. **Constructs as the grouping layer.** Rejected on measurement: 109 of 128 revisions
   declare exactly one construct for the entire modelo, and modelo 200's single construct
   holds 3,215 casillas.
4. **Hand-authored screens for the modelos that matter, generated fallback elsewhere.**
   Rejected: it reintroduces per-modelo screens for exactly the forms that change most, and
   creates two mechanisms whose behaviour diverges.
5. **A declared presentation family, generated at development time from official sources,
   human-reviewed, shipped as data, and read at runtime.** Chosen: it satisfies the accepted
   explicit-data requirement, uses offsets and the official record-design corpus as seeds
   rather than as runtime authority, gives modelo 100 a first-class second source, and makes
   coverage an auditable fact rather than a silent gap.

## Constraints

- Bound by the accepted dual-keying decision forbidding flattening of repeated blocks, so row
  groups must be first-class rather than slot-scalars, and the generator may not reintroduce
  the slot-and-offset inference that decision deleted.
- Bound by the accepted workspace interface decision: the projection is an application read
  model and the frontend renders what it is given.
- Bound to extend the accepted modelo work review read model rather than introduce a second
  one. A parallel read model is the failure that record was written to prevent.
- The declaration is a published artefact and must have a stated load path, a validator and a
  cache identity that includes its source state. Without those it becomes a second runtime
  authority beside the validated registry, which the registry authority flow forbids, and it
  reproduces the stale-digest hazard the parent record documented.
- Row groups are required by this decision but the row-group type is referenced by no
  interface module today, so the type and its rendering are prerequisites rather than
  assumptions.
- Undeclared revisions must fail closed to inspection-only. On today's corpus that is a large
  fraction, and that fraction is the honest coverage number, not a defect to be papered over.
- The value parser and the unsupported-kind refusal are prerequisites: an editor generated
  over the current parser would accept arbitrary text into identity and bank fields.
- The label continuity defect is a prerequisite for any surface showing casilla names.
- The registry carries no applicability signal at record level — every record is required and
  there are no discriminators — so the projection cannot yet say which pages apply to a
  given taxpayer.
- Visual geometry is not available: printed forms exist for two of fifty-nine modelos. The
  projection reproduces structure and order, never pixel layout.
- Generated presentation data is a generated artefact and belongs to its generator; it must
  not be hand-edited in place.

## Implementation

A declared presentation family becomes generated registry data, one declaration per modelo
revision. It names an ordered tree of pages and sections, assigns every casilla a placement
within it, carries an official heading for each node, and declares repeated blocks as row
groups with their cardinality.

It is published and loaded through the validated registry authority, alongside the revision it
describes, and never read from disk by a consumer. It is compiled and validated with that
revision, so a declaration referencing a casilla the revision does not define, or omitting one
it does, fails before publication rather than at render time. Its cache identity includes the
source state it was generated from, so a stale declaration cannot be served against a changed
revision. This keeps one runtime authority rather than two.

The declaration is produced by a development-time generator, not at runtime. The generator
seeds order from export field offsets within record order where a fixed-width layout exists,
and takes headings from the official record-design corpus, whose casilla join rate is high but
is recorded as an open measurement rather than an established figure. For modelo 100, which has
no offsets and no export
references, the generator seeds from the RentaWeb dictionary and schema path tree instead;
this is a second seed into the same declaration format, not a second mechanism. Output is
reviewed by a person before it ships, because the seeds are strong but not authoritative
about presentation.

Placement is a closed typed axis with an explicit unplaced arm carrying a reason. A casilla
that the generator cannot place is declared unplaced with cause, never omitted. This is the
single most important property of the design: the current candidate mechanism would have
dropped eighteen thousand casillas with no diagnostic, and the project's standing rule
forbids exactly that kind of silent absence.

Casillas addressed at more than one position declare a primary placement and its aliases, so
the operator edits one value in one place while the surface can still show where else the
same box appears on the official form.

Row-bearing structures are declared as typed row groups over the detail-row model rather than
flattened into per-slot scalars. The slotted records already resolve into rectangular tables
mechanically, so this is a declaration of what the data already is.

The runtime read model exposes the declaration joined to live values, provenance and
diagnostics, and carries a discriminator naming which source produced its presentation, so
the source can never switch between revisions of a modelo without the change being visible.
A revision with no declaration resolves to an inspection-only projection that states why it
is not editable, rather than degrading to an arbitrary order.

Control selection derives from data type, input kind and constraints. Absent constraints
render as bound-not-declared rather than as unconstrained, an unsupported kind renders the
declared refusal view rather than a text box, and the value parser gains real per-type
parsing before any of this is exposed for editing.

Two gates hold the design. A coverage gate reports declared versus undeclared revisions and
placed versus unplaced casillas, so coverage is a published number. A stability gate diffs a
revision's declaration against its predecessor and requires a reviewed acknowledgement when
placements move, so an operator never silently finds the form rearranged.

Delivery is ordered by ascending difficulty and descending confidence: the small
fixed-width forms first, then the mid-size ones, then the largest, then modelo 100 on its own
seed.

## Rationale

Coverage is the knockout, not governance. Runtime offset interpretation is the option the
evidence most flatters — the closest match to the official design of anything measured — and it
still fails, because offsets place barely a third of the corpus by casilla
weight, place nothing at all for the flagship consumer form, and would drop the remainder with
no diagnostic. An ordering mechanism that is exact where it applies and silent where it does
not is not a mechanism for a filing-grade product.

The accepted preference for explicit data points the same way without being decisive on its
own: that record treated section order as an ungated presentational concern and was addressing
authoring conventions rather than runtime reads. It is corroboration, not a prohibition, and
this record should not be read as claiming otherwise. What the measurement shows is that
offsets are exactly the right seed, and a generator is where a seed belongs.

Declaring also fixes what runtime derivation could not. It gives modelo 100 a projection at
all, by admitting a second seed into one format. It makes the 61.8 per cent unplaced
population visible as declared unplaced-with-reason rather than as absence. It lets a
stability gate exist, because two declarations can be diffed while two runtime derivations
cannot. And it satisfies the dual-keying decision, because row groups can be declared as row
groups instead of being inferred away.

The alternative that most tempts is hand-authoring the four modelos that matter. It is
rejected because those four are the forms that change most often, and a hand-authored screen
is precisely what fails to track a revision. Curated content still has a home here — a human
reviews and corrects every declaration — but it is authored in the same format the generator
emits, so there is one mechanism and one renderer.

The prerequisites in this record are unusually heavy for a presentation decision, and that is
deliberate. A generated editor over a parser that accepts any string for a bank account is
worse than no editor, and a generated form over labels that render as bare numbers is worse
than the command line. Both are cheap to fix and both must precede the surface.

## Consequences

Presentation becomes an auditable artefact. Coverage is a number the project publishes rather
than a property that emerges, and a revision either has a reviewed declaration or is honestly
inspection-only.

The campaign inherits a generator and a review obligation. Someone must look at each
declaration before it ships, which is real cost, concentrated on the largest forms. The
compensation is that the review is once per revision rather than once per screen, and that
the seeds are good enough that review is correction rather than authorship.

Coverage will start narrow and visibly so. On today's corpus a majority of revisions would
begin undeclared, including the flagship consumer form until its own seed is built. Stating
that plainly is the point; the rejected option would have shown a form for every modelo and
quietly omitted most of the boxes.

Three defects are promoted to blocking prerequisites: the value parser, the unsupported-kind
refusal, and the label continuity resolution. None is large, all three are already located,
and none may be deferred past the first editable surface.

Multi-position casillas gain a concept the product did not have. The alias model is new
vocabulary and will need care in the editor so that editing an aliased box is obviously one
edit and not several.

The registry still cannot say which pages apply to a taxpayer. Until it can, the projection
shows the whole declared form and relies on the operator to skip inapplicable pages, which is
a real usability gap on the largest modelos and a candidate for a later decision.
