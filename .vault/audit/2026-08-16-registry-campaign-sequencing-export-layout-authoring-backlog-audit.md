---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-16'
modified: '2026-10-14'
body_schema: 'body-v1'
body_hash: 'sha256:733e79df4f6de704ec1f5035e7cf4b90ab06c9a32070cb01a67a9ebd6cc61642'
related:
  - "[[2026-08-16-registry-campaign-sequencing-designless-modelo-registry-membership-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `registry-campaign-sequencing` audit: `export layout authoring backlog`

## Scope

This audit follows registry revisions that refused build because they declared no export
layout, after the designless population had been resolved. The initial assumption—that
each refusal was straightforward authoring against a bundled design—was disproved. This
condensed record keeps the distinct findings, their later corrections, the campaign's
measured work, and the remaining blockers. The original entry is dated 2026-08-16 and was
last modified 2026-10-03; appended sections are kept in source order where individual
subsections do not carry a separate date.

The work concerns export-layout generation and registry authoring, not tax calculation
correctness. Generated trees remain CLI-owned. Their validation proves structural
coverage and declared wire facts; it does not by itself prove that a realistic taxpayer
value can be rendered correctly.

## Findings

### hand-authoring-an-export-tree-is-the-rejected-option | critical | Two layouts were authored by hand, then removed; the generator refuses that exact shape for a reason

Modelos 308 and 309 were manually given fixed-record trees, then those trees were removed.
Their designs classify M30800 and M30900 as variable envelopes. A fixed-width transcription
can look complete while asserting the wrong record kind. The accepted generator authority
requires a typed, evidenced composition contract for a variable envelope; it rejects
inferred totals and hand-edited generated TOML. The coverage validator alone compares a
layout with the same parse and cannot establish that a variable envelope was composed
correctly.

### what-the-backlog-actually-is | critical | One modelo is generatable today; eight are blocked on one shared contract

The initial IR survey treated eight refusals—151, 200, 202, 303, 308, 309, 322 and 353—as
one shared variable-envelope contract problem, not eight independent authoring tasks.
That was a historical snapshot, later refined into revision-level worklists. At that
stage 193 and 347 also lacked record-design epochs, and 296 and 360 had incomplete reads.
The epochs for 193 and 347 were subsequently declared from their sources' applies-from
windows. Parser work later made additional designs readable. Do not use the initial
generatable count as the terminal backlog.

### partial-reads-are-invisible-to-the-coverage-gate | high | The strongest argument for the generator over hand authoring

The layout coverage check can pass an incomplete design because both the expected and
measured sides shrink together. The original survey found skipped record bodies in 200,
202, 232, 296 and 360, including 45 skipped bodies in the 2010 and 2011 Modelo 200 designs.
The generator therefore requires a complete read before producing a tree. Later parser
and attribution work narrowed the corpus worklist; the refusal remains the right guard
against publishing a partial layout.

### one-registry-two-export-conventions | high | The scaffolder still creates the shape the ADR retired

The Modelo scaffolder still emitted manual export_layouts directories while the accepted
generator writes export plus provenance. At the initial survey, 210 and 303 had generated
trees and 34 models used manual trees. The scaffolder was identified as the source of
continued divergence; this audit did not itself authorize changing the convention.

### grade-and-design-scoping-of-the-refusal | medium | Two independent claims now scope the no-layout refusal, both proven both ways

The no-layout refusal was measured only for revisions that claim filing grade and models
that cite record_design evidence. Paired tests established both predicates in both
directions. Applicability-only revisions are not promised export capability, but the
runtime filing check independently refuses a filing snapshot whose layout is missing.
A form_spec is not a machine record design; Modelo 721's printable BOE annex therefore
does not trigger the design predicate. The scope evidence prevents a revision from
silencing a real missing layout by changing its own grade.

### modelo-184-is-authorable-and-its-hard-part-is-recoverable | medium | The desglose categories are in the source, keyed by position range

The early survey found 132 anchors in three fixed records and 44 bare ENTERO/DECIMAL
halves in two desglose groups. The category names are recoverable from the source by
matching each printed position range; 21 categories were identified. At that stage six
canonical owners existed for 132 anchors, and parent anchors still needed semantic
classification. Later work authored and published Modelo 184, then end-to-end export
probes exposed wire-value defects. The original “authorable” finding is not evidence of
correct filing output.

### modelo-296-parse-hole-is-a-missing-naturaleza | high | Root-caused: AEAT omitted the type token, and the parser correctly refuses to guess

The initial parser read left positions 413–432 of the Modelo 296 perceptor record
unclassified because the source line says “CÓDIGO LEI DEL PERCEPTOR” without an explicit
nature token. The current parser correctly refuses to guess: similar prose can restate
positions already claimed by a real row, and broad acceptance could invent fields across
218 designs. The proposed safe route was a second pass limited to unclaimed holes that
the declared total proves. Later parser work and authoring changed the worklist; this
initial diagnosis is retained as the reason a gap-fill rule needs a separate, mutation-
tested change. Modelo 360's unread body was not shown to share this exact shape.

### the-extractor-and-the-generator-disagree-about-desglose | critical | Containment overlap is a permitted AEAT shape to one authority and a refusal to the other

The original claim that the extractor accepted containment while the generator rejected
the same parsed components was corrected. Modelo 184's bare consecutive subfields are
not nested by the parser's dotted-ordinal rule; the 184 records carry no parsed components,
so the coverage validator's component handling is a no-op. Exact geometry still refused
184, but the evidence did not establish two authorities disagreeing over the same
component tree. The real open question became which positive source signal permits a
bare-ordinal parent to be reconstructed without wrongly nesting grouping headers or
visual extraction artefacts such as Modelo 038. Preserve this correction; do not repeat
the first diagnosis as current fact.

### the-generatable-set-is-now-six | high | Three parser fixes and the epoch declarations moved four modelos onto the generated path

After epoch declarations and parser fixes, the intermediate survey counted six models
with complete IR reads: 184, 193, 232, 296, 347 and 360. Five passed the generator's
contiguity check; 184 remained blocked on its desglose geometry. This was a dated
worklist snapshot, not the final capability set. Subsequent publication, splits,
source registration and revision-specific findings changed the remaining work.

### render-profile-eligibility-is-blind-to-pdf-designs | critical | A PDF-sourced tree would generate with every numeric wire fact unstated, and nothing would refuse it

The early Modelo 347 survey found zero eligible numeric anchors because eligibility
recognised workbook abbreviations Num/N and blank Contenido cells, while PDF designs
spell the naturaleza out and carry descriptive prose. All 19 numeric fields could
therefore have escaped required wire-fact declarations. The finding exposed an authority
question: when a PDF has no Contenido column, which source facts are official wire facts
and which require a reviewed render profile? It was not permission to infer numeric,
decimal, date, flag, identifier, digit-string or literal-default behavior.

### the-binding-selector-record-key-is-overloaded | critical | The first modelo to combine a source-sense binding with an export layout refuses, and six more will

Bindings use record for both an export record selector (for example page_01 with wire
coordinates) and a source row-set name such as perceptor or m347_declarante_summary.
The early Modelo 347 publication reached registry validation and refused the source-sense
binding because it lacked wire coordinates. Ten models used the key, with 727 export-
record occurrences in 131, 349 and 720 alongside source-row meanings. A shared selector
contract is required; source record names must not be mistaken for wire projections.

### modelo-347-state | high | Authored, rendering, and stopped inside the candidate's own validation

At the initial authoring milestone, Modelo 347 had 33 casillas, a 64-anchor semantic map,
a 19-rule render profile, generated tree, export references and an application link.
Publication still failed on the sello position, unresolved filing families and a registry
loader being refactored concurrently. Later repair corrected stale map/profile entries,
then revision splits and renewed source reading changed the scope. This finding is an
intermediate state, not a claim that every Modelo 347 revision is now fileable.

### the-sello-position-is-a-deliberate-conservatism-not-a-gap | high | Tried to make it omissible, reverted, and the reason is the better finding

The design says the electronic seal is reserved for AEAT and must be blank in other
presentations. A proposed prose-based omissibility rule was reverted: the accepted gate
reads evidence from the cell naming the field, not nearby explanatory content. A narrow
test would have reclassified 25 seal positions across 215,416 fields, but small blast
radius did not justify changing which evidence the gate trusts. Modelo 360 showed the
reservation in a PDF naming cell as well. Resolving the rule belongs to its owner, not an
individual layout author.

### modelos-193-and-296-share-one-parser-gap | high | Characterised exactly, with the fabrication hazard measured and the discriminator identified

The initial PDF read missed parenthesised foral subfield ranges in Modelo 193 and 296:
20 rows in 193 and 10 in 296. Accepting every parenthesised range would also treat six
Modelo 200 year ranges as byte positions, including a fabricated 90-byte span beginning
at 1923. The parent has no count word, so the separate gap-fill proposal would not apply.
This is a distinct parser hazard from Modelo 296's missing naturaleza. Any repair must
recognise the PDF row form while refusing the year-range control.

### modelo-232-writes-taxpayer-names-into-AEAT-reserved-bytes | high | a filing-correctness defect in a PUBLISHED tree

A published Modelo 232 tree emitted 32 reserved-name casillas across the 2016–2017 and
2018-onward revisions. The taxpayer supplies the related-party NIF; AEAT owns the
reserved name bytes. The map and generated tree therefore risked writing taxpayer data
into AEAT-reserved positions behind a valid digest. The reserved-write checker was
already reporting the condition. This was flagged for correction across both revisions;
this audit does not record a verified repair.

### a-published-tree-cannot-export-any-real-value | critical | 33 casillas in Modelo 184 refuse every realistic value, and the gates cannot see it

A later field-by-field probe of published layouts found 33 of 45 multi-field Modelo 184
casillas refuse realistic values: 30 money, two ratio and one split date. The same whole
casilla value is sent to both integer and decimal leaves, but no value policy selects a
part. Structural map/profile validation cannot see this. The earlier “published and fully
implemented” claim was therefore true only of structural validation, not wire behavior.
No source-grounded split-value policy or end-to-end proof is recorded here.

### every-value-policy-refused-an-absent-optional-casilla | critical | the blank fill was unreachable on exactly the fields this campaign generates

All ten tested value policies refused None on an optional slot, although AEAT requires
empty numeric fields to be zero-filled and required fields to refuse. Projection happened
before the absence check, making the blank-fill path unreachable for policy-bearing
generated fields. This affects the campaign's generated layouts directly. Together with
the split-value defect, it meant Modelo 184 could export neither realistic values nor
legitimate absences. No verified fix is recorded in this audit.

### modelo-347-repaired-and-the-gate-that-was-never-watching-it | high | the map went stale because 347 was published without a drift row

The published Modelo 347 map/profile were repaired against current parser output. A
stale parent was split into telephone and name fields; another into integer and decimal
parts. The eligibility count moved 19 to 22, and regenerated trees changed source-evidence
hashes. The changes were checked against the correct semantics for each pair. Later work
split revisions and extended per-field reading; older revisions still require their own
grounded review.

## Recommendations

### Close shared and source-dependent authoring blockers

The original eight-modelo variable-envelope cohort is historical. Keep the composition
contract as shared work: do not hand-author a fixed record or infer a total. Re-measure
each revision after the contract lands rather than carrying the old eight-modelo list
forward unchanged.

Resolve PDF wire-fact authority before treating an empty PDF render profile as complete.
Keep PDF descriptive prose distinct from explicit wire facts, and require reviewed
profiles wherever the design does not state the wire representation.

For Modelo 184, establish the source signal that distinguishes a true bare-ordinal
desglose from grouping headers and extraction artefacts; regression-test the 038 control.
Then prove split-part values and optional absence through the shipped codec before
describing the published tree as filing-ready.

Keep the selector semantics explicit for source row-sets and export records. Repair the
Modelo 232 reserved-name writes across every affected revision. Read earlier Modelo 347
revisions independently; a current revision's map and profile do not establish parity
for its predecessors.

### Preserve corrected worklist and terminal open status

The closing audit leaves eight standing registry failures. Do not count unrelated
peer edits or transient partial-tree test runs as campaign failures. The remaining work
was partitioned by evidence:

- 78 revision spans lack corpus proof and require official design acquisition. Examples
  include Modelo 036's 2025-02-03-y-siguientes, Modelo 038's 2002-y-siguientes and
  Modelo 100's 2020 and 2021.
- 24 year-coverage divergences split into 12 deadline-window semantics questions and
  12 genuine source gaps. The first class needs a ruling on whether design windows
  represent exercise governed or legal-force/presentation reach. The second needs source
  acquisition; Modelo 126's 2019 revision citing only the 2020 design is an example.
- Fifteen unattributed design titles remain after two were grounded from AEAT's own
  titles; 37 designs remain unregistered. Do not infer an era from an orden year or an
  “actualizado” date. The two Modelo 036 editions named “2021 y siguientes” have
  different layouts and remain refused pending evidence.
- Modelo 200's split has a proven locale-move command for shared keys, but translation
  remains open: 3,219 shared casillas can move as one operation; 185 2024-only boxes
  still need English, Catalan and Hungarian labels. An earlier test of 145 boxes found
  no safe year-substitution composition. A separate 104-label locale backlog remains
  translation-blocked.
- Modelo 347's earlier revisions still need per-field source reading.

The last remeasurement reports eight failures, 5,384 passes and a clean authority load
on a quiet tree. Other runs included peer in-flight edits and are not comparable. The
registry's 78 unproven spans and unresolved year-window semantics are not repaired by
passing package tests.

## Chronology and corrections

The log below condenses the append-only work in source order. Counts are retained with
their stage because later passes corrected earlier conclusions. A claim stated as closed,
withdrawn or superseded reflects the later control described here, not deletion of its
history.

### Initial generator survey and 347/184 publication work

The first IR survey identified the variable-envelope cohort, missing epochs and partial
reads. The early recommendation prioritized one composition contract over per-modelo
manual authoring. Modelo 347's map, profile and tree were then authored; its first
publication attempt exposed the seal, filing-family and concurrent-loader blockers.
Modelo 184 was later reported published with zero generator validation failures. That
was a structural milestone only: later realistic-value and absence probes found the
two critical codec defects recorded above.

The campaign's registry failure count moved from 88 to 70 in an intermediate measurement.
A subsequent snapshot reported five clean models and two generated publications (347 and
184), while later validation snapshots ranged through 73 and then 30 failures. These
are stage-specific counts, not one monotonic series. Several family-only closures were
dispositions rather than new authoring: Modelo 720's verification predicates were
declined for informative casillas, Modelo 115's schedule and ledger-backed predicate
were authored, and Modelo 111's family work was measured separately.

### Queue closure, parser and gate repair

The append-only queue work repeatedly measured the six initial queue items, corrected
wrong joins and false positives, and closed each only after the relevant control ran.
The later entries withdraw findings where a source or revision view had been misread;
they do not treat a green assertion as evidence if its fixture or predicate was inert.
Work included repairing generated-tree and casilla tallies, adding mutations for gates
that had stopped biting, fixing reviewability and newline sensitivity, and restoring
tests whose imports or fixtures had gone stale.

A second measurement wave corrected 369 and 390 gap counts that had used raw source
positions instead of derived layouts; the actual derived data coverage had no such
gaps. The 193/720 short-record family, 2022 orden handling, Modelo 303 reserved-byte
work and other defects were adjudicated against their source controls. Modelo 296's
early parse-hole diagnosis was later superseded by parser/authoring work; its end-to-end
layout ultimately covered five records and 136 entries. Models 136 and 721 were removed
from the record-design backlog because neither revision claimed record_design evidence.

### Locale labels and revision splits

The Spanish label backlog was remeasured at 1,798, not the earlier count of 50.
Later work authored the 309 labels across all four catalogues, then 308, 151 and 322;
a 322 join defect had hidden 419 labels. Reachability was tested separately from
suitability, and the method was not generalized where it would infer labels without
source support. Models 184 and 193 recovered labels from grounded block headings and a
small glossary. Further corrected joins resolved the remaining 190/200/202/322 label
groups; locale parity eventually reached zero.

Revision boundaries were then grounded and executed for Modelo 184 at 2025, 322 at
2023/2024, and 347 at 2024/2025. A proposed 200 split was built in halves, including
its semantic map and render profile, but publication was reverted when the source was
not fully registered or locale parity was incomplete. Modelo 210's 2026 split was the
first of four to land, proving the cutover path; 322 later landed after a rollback and
a corrected detector. Modelo 347's evidence exposed a second relayout and a signal the
prior detector could not see. Modelo 200's later publication was again reverted because
publication alone was not the contract; localization and old-revision reading remained.

### Source registration, coverage and terminal remeasurement

The registration campaign repeatedly corrected epoch attribution from AEAT titles and
ordenes. Ten designs were registered in one pass and seven refused; later title review
grounded two of 17 unattributed designs (111 and 763), leaving 15. A later full title
sweep of 39 returns found only the already-known two 036 candidates; the distinct-layout
control kept them refused. Do not convert design revision dates or orden names into
governed years.

Every parser-recoverable source was eventually read whole, including Modelo 200's
position-10 and later-page rows. Follow-up controls found that some supposed holes were
wrong joins, duplicate evidence or source artefacts; the parser worklist was reduced to
unrecoverable or genuinely unavailable source evidence. The 24 year-coverage lines were
finally divided into 12 semantic-window questions and 12 acquisition gaps. The 78
unproven spans remain a separate acquisition population.

The final section holds the registry failure count at eight. It closes the locale move
CLI work after independent parity and split-routing checks, but leaves Modelo 200
translations open. It also records 15 unattributed designs, 37 unregistered designs,
the Modelo 347 earlier-revision reading, 78 unproven spans and the two 12-item
year-coverage classes. This is the terminal status for this audit; none of those
worklists is converted into a success by the existence of a tool or a passing subset.
