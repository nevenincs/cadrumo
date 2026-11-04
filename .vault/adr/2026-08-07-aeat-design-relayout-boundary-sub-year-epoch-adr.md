---
tags:
  - '#adr'
  - '#aeat-design-relayout-boundary'
date: '2026-08-07'
modified: '2026-11-04'
body_schema: 'body-v1'
body_hash: 'sha256:da79154c851180fd7adc4997b2ca746cb6631d394de383d05fd092c33f67642c'
related:
  - "[[2026-08-07-aeat-design-relayout-boundary-adr]]"
  - "[[2026-08-07-aeat-design-relayout-boundary-research]]"
---
# `aeat-design-relayout-boundary` adr: `a design epoch narrower than a filing year is expressed by period-token partition` | (**status:** `accepted`)

## Problem Statement

The accepted `2026-08-07-aeat-design-relayout-boundary-adr` rules that no
registry revision may span an AEAT design re-layout, and authorises splitting
Modelo 303 and Modelo 390 accordingly. It assumes throughout that every boundary
falls between filing years. One does not: AEAT declares a Modelo 303 boundary in
its own published filenames at periods 09 and 3T of one filing year, mid-year. The
authorised split is therefore unauthorable for that year until this record settles
whether the revision model can express an epoch narrower than a filing year, and
by what mechanism.

This record decides only that question. It does not supersede or amend the
accepted boundary record, whose property, refusal posture and
prescripcion-bounded scoping all continue to govern; it supplies the one
mechanism that record's implementation needs and does not name.

The question is live in two directions and neither is an offset error. Inside the split year,
the later design adds boxes the earlier one has no room for, so a 3T or 4T filing
written under the earlier layout cannot declare them at all. For the transition into the latest design, four fixed slots change which box they carry while staying at the
same offset and length, so a filing written under the earlier semantics is
byte-valid, length-valid and digest-valid while declaring the wrong quantities.
No offset check, length check or digest detects either.

## Considerations

- The epoch structure was re-measured for this record against the bundled
  `.xlsx` workbooks through the shipped `extract_record_design_workbook`, keyed
  on the bracketed AEAT box number at each sheet, offset and length slot rather
  than on positional index or on free-text description. Across the five designs
  `2023-y-siguientes` claims, labelled in order D1 (the opening design), D2 (the
  early design of the split year, through period 08 and 2T), D3 (the late design
  of the split year, from period 09 and 3T), D4 (the following year's design) and
  D5 (the latest design): D1 to D2 is identical (0 slot meaning flips,
  0 boxes moved, 0 boxes added, every sheet total unchanged) -- **REFUTED, see the
  amendment below**; D2 to D3
  adds 8 numbered boxes (108, 111, 165 through 170) with 0 flips and 0 moves and
  every sheet total unchanged; D3 to D4 shows 0 numbered-box movement but
  grows sheet DP30302 from 1706 to 1900 positions; D4 to D5 flips 4 slots,
  moves 128 boxes and grows sheet DP30305 from 1523 to 1528. Three boundaries,
  so `2023-y-siguientes` spans FOUR design epochs: D1 and D2 as one, then D3,
  then D4, then D5 onward.
- **AMENDMENT (measured 2026-08-08): the D1-to-D2 identity above is FALSE
  and the epoch count is FIVE, not four.** Four real fields are RETIRED into
  reserved space between those two designs, all on sheet DP30302 in the Régimen
  Simplificado block: the employee-count and maximum-employee-count slots for
  Actividad 1 at offsets 1110 and 1116, and the same pair for Actividad 2 at
  offsets 1236 and 1242. Each reads as a live field in D1 and as
  `Reservado para la AEAT` in D2.
  The two passes this record ran are **structurally incapable** of seeing that
  class, which is why the reading was honest and still wrong: the reserved block
  absorbs the freed bytes exactly, so no offset shifts and no sheet total grows.
  Re-running both passes reproduces this record's figures exactly -- 0 of 174
  shared boxes moved, 0 added, 0 removed, every sheet total unchanged. The error
  was not a mismeasurement but inferring layout identity from two signals blind to
  the change that occurred; the occupancy pass this record never ran is the only
  one that reports it. That pass is now a shipped signal in the span gate.
- No single signal finds all three boundaries, and this record initially got that
  wrong. The box-number key alone reports D3 and D4 as one epoch, because
  DP30302's growth is entirely in unnumbered modulos fields; the page-length
  signal alone reports D2 and D3 as one epoch, because that transition
  displaces nothing. Each finds a boundary the other cannot see, and only their
  UNION is the epoch set. This is the accepted boundary record's own
  union-of-two-signals doctrine, and taking one instrument's verdict for the
  whole answer is the error that doctrine exists to prevent.
- The instrument matters and both weaker ones mislead. An index-keyed diff
  compares unrelated fields the moment either side inserts, and produced a
  retracted reading of 56 fields relocating across 17 shift magnitudes. A
  description-keyed diff cannot separate a rename from a semantic flip, and
  reports the D1-to-D2 wording refresh (`discapacitados` becoming
  `personas con discapacidad`, at identical offsets) as change. Only the
  box-number key discriminates. It has its own blind spot, stated next.
- The box-number key is blind to slots carrying no bracketed number, and two such
  slots do flip meaning between D2 and D3: a one-byte flag and the
  thirteen-byte reference beside it change from `Declaracion complementaria` and
  its prior-filing receipt number to `Autoliquidacion rectificativa` and its
  identifying receipt number. That flip is real, this record's primary instrument
  cannot see it, and it was found only by the description-keyed pass. Neither
  instrument alone is sufficient.
- Revision selection is year-first. `select_revision` filters on
  `period_selector.includes_year(filing_year)`, then narrows by period token,
  then applies an optional `on` date against `valid_from` and `valid_to`.
  `PeriodSelector` carries `years`, `year_from`, `year_to` and `periods`, and has
  no within-year narrowing field.
- A period-token partition already selects correctly with no schema change, and
  this was measured rather than reasoned: two synthetic revisions covering the split year
  built from the live Modelo 303 definition, one declaring the early tokens and
  one the late tokens, resolve 2T and 08 to the early revision and 3T and 09 to
  the late one through the production `select_revision`.
- The `on` date is already threaded end to end, through
  `ValidatedRegistryAuthority.snapshot`, `build_validated_snapshot` and both
  selectors, and one production caller already derives one from filing context
  rather than accepting it from an operator: the foreign-asset threshold resolver
  passes the last day of the filing year. A date derived from filing year and
  period is therefore a derived fact of the same kind, not an injected selector,
  and does not offend `revision-resolution-is-law-determined`. The unscoped period
  query refuses an as-of date explicitly rather than accepting and ignoring it, so
  the mechanism is honest where it is unavailable.
- `PeriodSelector` is a cross product of years and period tokens, not a set of
  year-and-period pairs. It cannot express every period of the opening year plus the
  early periods of the split year. This is the constraint that separates the options, and it makes
  revision count exceed epoch count under any mechanism that does not add a schema
  axis.
- Every mechanism leaves the year-only surface ambiguous, so that cost is shared
  rather than a discriminator: measured, two revisions covering the split year resolve
  through `select_revision_for_year` to `AmbiguousRevisionSelectionError` unless an
  on-date is supplied. Its callers are the binding-readiness discovery helper, the
  registry describe and bindings query, and the revision diff command. The
  readiness helper catches only `NoRevisionForPeriodError`, so the ambiguity
  propagates from it today.
- The corpus already knows the boundary the selector cannot express: the
  `2023-y-siguientes` manifest names both `aeat-dr-303-2024-early` and
  `aeat-dr-303-2024-late` in its `source_refs`, alongside the opening, following-year and
  latest designs.
- The landed span gate cannot see a mid-year boundary at all, for a reason
  independent of this decision: its design inventory keeps one design per year via
  a setdefault over a filename sort, so of the two split-year workbooks whichever sorts
  first wins and the other is discarded. Its silence about the split year is therefore not
  evidence.
- The landed span gate was re-run for this record once an unrelated Modelo 202
  export-layout defect stopped blocking registry load, and its verdict corroborates
  this record while demonstrating the blindness above. It reports
  `2023-y-siguientes` as spanning 2 re-layouts and needing 3 revisions, naming
  the D3/D4 and D4/D5 boundaries. Those are two of the three boundaries
  measured here, and it names them from the same evidence: sheet DP30302 growing
  1706 to 1900, and sheet DP30305 growing 1523 to 1528 alongside a large box
  relocation. It does not name the mid-year boundary, exactly as its one-design-per-
  year inventory predicts. The gate therefore understates this revision's split by
  one boundary and one revision, and a future reader must not take its count as the
  answer.
- The gate and this record's instrument agree on the fact of the D4-to-D5
  relocation but not on its exact size: the gate reports 125 of 174 shared boxes
  moved, this record's pass 128 of 183 numbered slots, because the two extract the
  box number from a field description by different conventions. The disagreement is
  in the denominator, not in the finding, and neither figure should be quoted as
  precise without re-deriving it.

## Considered options

- **Partition the period tokens between two same-year revisions (chosen).** Pro:
  works today with no schema change, no selector change and no new validation,
  measured against the production selector, and declares the boundary in exactly
  the vocabulary AEAT used to publish it. Con: because the selector is a cross
  product, an epoch covering a whole year plus part of the next needs two
  revisions, so Modelo 303's four epochs need five revisions, one pair of which is
  layout-identical.
- **Discriminate two same-year revisions by on-date alone, both declaring the full
  token set.** Rejected: measured to be ambiguous without the date, and dependent
  on every call site supplying a derived one, so a single caller that omits it
  silently gets whichever revision the tie-break returns rather than a refusal. It
  converts a structural property into call-site discipline, and the call sites are
  exactly what a future author forgets.
- **Add a within-year narrowing axis to `PeriodSelector`, a period-from field or
  an explicit year-and-period pair set.** Rejected for now, and it is the honest
  runner-up: it would express four epochs in four revisions with no duplicate
  layout, a genuine advantage over the chosen option. Rejected because it adds a
  schema axis, its validator, and a second way to say what the existing `periods`
  field already says, buying a reduction in authoring duplication and nothing in
  correctness, while giving the non-overlap property the resolver depends on two
  independent sources that can disagree.
- **Accept the residue for one half of the split year and refuse export there.** Rejected as
  the general answer, since the boundary is expressible and refusing an expressible
  year is a self-inflicted gap. Retained as the correct behaviour for any period no
  bundled design covers, which is the accepted boundary record's existing ruling
  and is unchanged by this one.

## Constraints

- The epoch set stated here is data, not a constant, and no one signal produces it.
  Re-derive it at implementation time as the UNION of three passes over the bundled
  `.xlsx` workbooks: a box-number-keyed comparison for movement and slot meaning, a
  per-sheet total-positions comparison for growth the numbered key cannot see, and a
  description-keyed pass for unnumbered slot flips. Taking any one of the three for
  the whole answer understates the boundary set, which this record did on its first
  pass.
  Do not copy the three-epoch figure, and do not read the extracted markdown or
  extracted json siblings: they are one extraction pass in two envelopes, so
  neither is a control on the other, and across this corpus twenty-five xls and
  xlsx extraction pairs are byte-identical, meaning the markdown cannot
  discriminate even its own source format.
- The span gate must be made able to see a mid-year boundary before it can certify
  this split, since it currently keeps one design per year. Until then a green gate
  is not evidence that a mid-year epoch is modelled.
- The year-only selector surface must be given a defined answer for a split year
  before the split lands, or three read-only surfaces begin raising an ambiguity
  error they do not catch.
- Every revision id change reaches every carried cross-year observation stamped
  against the old id, per `carried-observations-stamp-their-revision`; the split is
  not export-layout-only and the carry paths must be re-confirmed, as the accepted
  boundary record already constrains.
- The transitional rate rungs pinned to the split year belong to the revisions
  covering it only. Copying them into every post-split revision is the obvious and wrong
  resolution.

## Implementation

Express a sub-year design epoch by giving each covering revision a
`period_selector` that declares the AEAT-published token partition: for Modelo
303's split year, one revision declaring the quarterly and monthly tokens through period
08 and 2T, and one declaring 3T, 4T and 09 through 12. Because the selector is a
cross product of years and tokens, an epoch spanning a whole year plus part of the
next needs two revisions, so Modelo 303's four design epochs are authored as five
revisions: the opening year in full together with the early split-year periods
(believed to share a layout, split only because the selector cannot express one
epoch crossing the year boundary), then the late split-year periods, the
following year in full, and the latest design onward.

**AMENDED: the claim this paragraph originally made -- "Exactly one pair carries an
identical export layout by construction, which is the accepted cost of not adding
a schema axis" -- is REFUTED.** No pair shares a layout. The opening and early
split-year designs differ by the four retired Régimen Simplificado slots recorded in the
Considerations amendment, so the five revisions cover five distinct design epochs
and each must parse its OWN design. The revision count of five is unchanged; the
pairing behind it is not, and a reader must not conclude from the stable count
that the correction was cosmetic. Copying one revision's export fragment tree into
its neighbour -- which the original wording invited, since a duplicate layout "by
construction" reads as licence to copy -- would write declared values into space
AEAT marks reserved.

Each revision still declares its own `source_refs` naming the specific AEAT design
it encodes, which is unchanged.

**The MECHANISM this record decides is untouched and still governs.** The
period-token partition, its rejection of date-only discrimination, and its
rejection of a within-year schema axis all stand; only the layout-identity
observation falls. This amendment rules on code and is not self-executing: it is
implemented by Steps `S15` and `S16` of
`2026-08-08-aeat-design-relayout-boundary-plan`, which author the opening and
early split-year revisions from their own designs, and by `S64`, which re-derives each
revision's total-formula operand lists rather than copying the newest backwards.
`S66` records the divergence in the campaign audit.

The revision count of five has now survived TWO corrections of the epoch count,
and that is coincidence twice over rather than corroboration. Under this record's
first, wrong three-epoch pass the five arose as two layout-identical pairs; under
four it was described as one pair plus a distinct late split-year epoch; under the
measured five it arises as five distinct epochs and no pair at all. A reader who
re-derives the epochs and expects the count to have moved should not read its
stability as a sign the correction was cosmetic, and a reader comparing this
record against its own earlier revisions should not read the unchanged number as a
sign nothing changed. A count that holds while the structure under it changes
three times is the clearest possible warning not to use it as a check.

Selection then needs no code change on the period-scoped path, since the
production selector already resolves each token to exactly one revision. The
year-only path does need one. Give `select_revision_for_year` a defined answer for
a year covered by more than one revision, refusing instructively, naming both
candidate ids and stating that the year carries a mid-year design boundary so the
caller must supply a period or a date, and make its three callers handle that
refusal the way they already handle a missing revision for a period. A year-only
answer for a split year is wrong in whichever direction it is given, so a refusal
is the only honest return; all three callers are read-only discovery surfaces
where a refusal is recoverable and a silently arbitrary pick is not.

Extend the span gate to read every bundled design rather than one per year, keying
its inventory on the design file rather than on the year parsed from its name, so
a mid-year boundary is visible to it at all. Give it the box-number key as its
comparison and a companion check for unnumbered slots whose meaning changes at a
fixed offset, since the numbered key alone would pass the complementaria to
rectificativa flip.

For a filing period falling in an epoch no bundled design covers, the behaviour is
unchanged from the accepted boundary record: no revision claims it,
`select_revision` raises its existing refusal naming the unmodelled period, and
nothing is exported. That ruling extends to sub-year epochs without amendment, a
period being as legitimate a unit of non-coverage as a year.

## Rationale

The knockout is that the period-token partition needs nothing built. AEAT
published the boundary as period tokens, the registry already speaks period
tokens, and the production selector was measured resolving the partition correctly
with no schema change, no selector change and no new validator. Every alternative
buys a smaller revision count or a tidier schema by adding a mechanism, and none
buys correctness the chosen option lacks.

The date-only option fails on a safety property rather than on cost. Under a token
partition, a caller that supplies no date still gets the right revision on the
period-scoped path, because the tokens are disjoint; under date-only
discrimination the same caller gets an arbitrary one. Making correctness depend on
every call site remembering to derive a date is the shape that produced the defect
this record exists to close.

The schema-axis option is genuinely better on authoring economy and worse on
authority. Two independent ways to declare which periods a revision covers means
the non-overlap property every consumer relies on has two sources that can
disagree, and the resolver would have to reconcile them. Duplicated layout data
generated from the corpus is cheaper to hold correct than a duplicated notion of
coverage.

Refusal for an uncovered epoch is retained rather than re-decided: the accepted
boundary record already ruled that a visible refusal beats a silently wrong
artefact on a byte-exact surface, and nothing about the unit of coverage shrinking
from a year to a period changes that reasoning.

## Consequences

- Modelo 303 gains five revisions where one exists, covering **five** design
  epochs, **no pair of which carries an identical export layout** -- the original
  wording of this entry, "covering four design epochs, one pair of which carries an
  identical export layout", is withdrawn per the amendments above. Anything
  treating revision count as a proxy for design count is still wrong and must be
  swept; the companion warning against assuming distinct revisions imply distinct
  layouts no longer applies to this modelo, because here they do.
- The year-only selector becomes a refusing surface for split years. That is a
  behaviour change for binding-readiness discovery, the registry describe and
  bindings query, and the revision diff command; the readiness helper's existing
  catch is too narrow and will propagate the error until widened.
- The two halves of the split year stop being interchangeable, which is the point: a 3T or 4T
  filing in that year gains the eight boxes the earlier design cannot express, and the
  complementaria and rectificativa slots stop being declared under the wrong
  meaning.
- The transition into the latest design is the higher-severity half of this work and is
  current rather than historical: 128 boxes move and four slots change meaning at
  a fixed offset, in the filing year now open. Sequencing the split
  oldest-to-newest would leave that exposure standing longest.
- Nothing here reduces the exposure until the split lands. This record makes the
  boundary expressible; it does not express it. A reader who takes the mechanism
  as the fix will believe the split year and the latest design are modelled when they are not.
- The gate stays untrustworthy on this axis until it reads more than one design
  per year, so a green gate must not be cited as evidence that a mid-year epoch is
  covered.
- Sub-year epochs become expressible for every modelo, not only Modelo 303. That
  is a gain and also an invitation to model boundaries that are not real; the
  epoch set should keep coming from a re-run measurement over the bundled corpus,
  never from a revision author's judgement.
