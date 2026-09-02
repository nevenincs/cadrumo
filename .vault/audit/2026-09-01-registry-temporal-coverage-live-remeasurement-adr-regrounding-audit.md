---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-09-01'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:106eedc5c8c931cdb03fb6fcc0b518722e8f2365a9be3b076c996ed57d3bf316'
related:
  - "[[2026-08-14-registry-temporal-coverage-authority-grade-coverage-adr]]"
  - "[[2026-08-14-registry-temporal-coverage-adr]]"
  - "[[2026-06-10-period-revision-resolution-adr]]"
  - "[[2026-08-31-period-revision-resolution-ad-hoc-operation-date-axis-adr]]"
---

# `registry-temporal-coverage` audit: `Live remeasurement of the registry coverage surface and the re-grounding the proposed coverage ADR now needs`

## Scope

A read-only remeasurement of the shipped registry and its development tooling, begun against the
live worktree on 2026-09-01 while an import-centralisation refactor was in flight and uncommitted,
and continued across the days following. Two independent passes opened it: an orchestrating session
and a separate agent instructed to derive every figure blind and return a verdict on the first
pass rather than inherit it.

Its original question was whether the evidence underneath this feature's proposed coverage decision
still held. It does not, and that finding stands. The audit then widened as measurement went on,
and the findings below are a rolling log rather than a single assessment: later entries correct
earlier ones, and several withdraw them outright. A reader should take the last entry on a subject
as the current position and read the earlier ones as the path to it.

The audit now covers the temporal declaration surface and its site agreement, revision identity,
identifier grammar, cross-revision continuity, the resolved export surface, wire types and monetary
scale, capability grade, provenance consistency, and the filing-export proof channel. It does not
review the correctness of any tax figure against AEAT, and it makes no claim about any value the
calculation engine produces.

One class of finding is different in kind and worth separating. Almost everything here measures the
registry against itself. Four findings instead compare it to the official AEAT record designs, and
those four settled questions the internal measurements could only raise: they confirmed a wire type
the internal reading called suspicious, corrected a defect count downward twice, and established the
one proven filing-correctness defect this audit contains. The tooling built alongside this audit
cannot produce findings of that kind. It locates candidates; the authority decides them.

## Findings

### adr-premises-overtaken-by-refactor | critical | The proposed coverage ADR rests on three premises that the live tree no longer exhibits

The proposed grade-bound coverage decision states three measured premises: that one
modelo carries private schema divergence through a named field and a modelo branch in
generic authority construction; that the applicability rules of 27 modelos live as Python
literals; and that an ungoverned coverage ledger assesses each revision at exactly one
representative year. All three were re-probed against the live tree. The modelo-specific
annual-orden field and its construction branch return no match in either the schema or
the authority module. The applicability module now carries a single modelo identifier as
a literal, not 27. The coverage module's own prose states that the matrix removes the
representative-coordinate defect. The premises appear to have been substantially resolved
by work that landed after the record was drafted. A decision accepted on this problem
statement would authorise work that is already done, and would misattribute the remaining
problem.

### adr-cites-renamed-private-modules | high | Every source path the proposed ADR cites has been renamed and no longer resolves

The proposed coverage decision cites five leading-underscore module paths under the
registry package. None of them exists in the live tree. Each has a public counterpart at
the same location with the underscore removed, consistent with the completed
import-centralisation work and with the architecture rule that requires canonical
definitions in semantically named non-underscore modules. The citations are therefore
unresolvable as grounding, and any reviewer following them to verify the record's claims
reaches nothing.

### stale-population-figures | high | The revision and modelo populations underneath the proposed decision have moved materially

The proposed coverage decision reports a measured population of 97 revisions across 73
modelos, 66 of them open-ended. Direct measurement of the live tree gives 128 revisions
across 58 modelos, with 49 open-ended. Both the direction and the magnitude differ: the
revision count rose while the modelo count fell, which means the shape of the corpus
changed rather than merely growing. A coverage horizon argued from the earlier figures
does not describe the current corpus.

### filing-export-proof-channel-unenrolled | critical | The two-channel filing-export proof is fully built and contains zero enrolled coordinates

The development filing-export proof module declares its canonical live proof entries and
its canonical conformance vectors as empty tuples. Both were confirmed empty at the
committed head as well as in the working tree, so this is not an artefact of the in-flight
refactor. The surrounding apparatus is complete: a generator verifier, the production
filing writer, and a byte comparison between them. Nothing is enrolled in it. The offline
closure report returns one satisfied revision against 127 refused, is not release
eligible, and refuses the filing-export limb for all 68 filing-grade revisions. No
exported byte has been proven against an official record design for any revision.

### generated-provenance-verifier-raises | high | The generated-source verifier calls a method its source type does not define

The corpus catalogue invokes an applicability method on the static generated artefact
source type, which does not define it. The call raises, which prevents the generated
provenance path from verifying. The defect is present at the committed head and is
therefore pre-existing rather than introduced by the refactor. It compounds the preceding
finding: even were coordinates enrolled, this path could not currently verify them.

### conformance-tool-unrunnable-and-ungated | high | The registry conformance tool cannot run as documented and no standing regression gate remains

The conformance package imports a revision-persistence module under its former private
name; the module has been renamed by the refactor, so the documented entry point fails to
import. Separately, the baseline-ratchet audit command and its committed baseline have
been deleted, and the replacement closure command is not wired into the justfile or CI.
The contributor runbook, the justfile target, the development README, and a gate test all
still name the deleted command. Dead baseline and ratchet classes remain in the manager
module. The registry consequently has no standing regression gate while a large refactor
moves through it. Restoring the deleted ratchet is not the remedy: the project's quality
rule holds that frozen corpus counts and baseline-only ratchets do not prove completeness.

### temporal-fact-declared-on-six-axes | high | The same temporal fact is declared at six or more sites reconciled by agreement validators

A revision's temporal validity is expressed through the revision directory name, an
explicit valid-from and valid-to pair, a period selector carrying its own year bounds,
per-year deadline windows numbering 843 across the corpus, source-reference applicability
bounds, legal-reference effective dates, a global horizon, and the enrolled years in the
authorisation manifest. Three agreement validators reconcile these after the fact. Every
additional declaration site is a place a maintainer can omit, contradict, or silently
drift, and the reconciliation is detective rather than preventive. The feature's proposed
coverage decision already frames the underlying problem as one selector answering three
distinct questions; this finding records the measured breadth of the fragmentation, not a
competing decision.

### revision-directory-names-misstate-their-windows | medium | Directory names are read as temporal facts and several of them are wrong

Several revision directory names do not describe the window the revision actually
declares. Two named for 2025 and later begin in 2023 and in 2026 respectively, the second
carrying an in-tree annotation recording the discrepancy as noted but not fixed. One named
for a 2013 start begins in 2012. One named as a 2008 to 2022 span declares 2022 only. Two
named for a single year 2024 are open-ended. Because the directory name is also the
revision identifier used in prose, tooling output, and review stamps, each of these is a
standing invitation to reason from a false window.

### open-ended-revisions-claim-unbounded-future-validity | high | Forty-nine revisions assert validity for years no evidence covers

Forty-nine revisions are open-ended, 27 of them filing-grade and all of those carrying
fixed-width layouts. The oldest load-bearing filing-grade example begins in 2010.
Selection for a filing year far beyond any evidenced year returns such a revision without
diagnostic. The registry cannot presently distinguish valid until superseded from verified
valid for a given year, which is precisely the distinction the no-silent-under-declaration
rule requires be preserved.

### revision-selection-can-be-ambiguous | medium | Selection ignores declared validity bounds unless an operation date is supplied

Temporal selection does not consult a revision's declared validity bounds unless an
operation date is passed. Across 1729 probed coordinates, 1727 resolve and 2 refuse as
genuinely ambiguous, both on one modelo at filing year 2011. A proposed decision on the
operation-date axis in the sibling period-revision-resolution feature already targets this
case; recorded here only to confirm it reproduces on the live tree and to bound its scale
at two coordinates.

### scheme-axis-occupies-the-revision-slot | medium | One modelo encodes a scheme rather than a period in its revision identifier

One modelo's three revisions are named for schemes rather than periods and are
disambiguated only by period-token namespace. They share a validity start, and the support
matrix consequently reports one of them as the latest revision on that tie. The revision
slot is carrying a non-temporal axis, which the surrounding temporal machinery cannot
represent honestly.

### raw-fragment-reads-understate-export-wiring | medium | Two earlier findings were measurement artefacts of reading authored fragments instead of derived layouts

Export fields are derived from bindings when a revision loads, so counting field kinds in
the authored fragments understates layout wiring severely. A first pass using that method
reported one modelo at zero per cent wired across three schemes and another as carrying
only filler fields. Measured through the binding-derivation entry point, those figures are
88.8, 88.9 and 93.4 per cent, and 95.6 per cent. Both earlier findings are withdrawn. One
revision's own review stamp warns of exactly this hazard. A separate low figure of 17.4
per cent on one modelo survives the corrected method and stands. The methodological point
generalises: authored fragments are a diagnosis surface only, and any coverage figure
taken from them without derivation is unsafe.

### cross-pass-figure-discrepancies | low | Two independent passes disagree on three counts, all resolved in favour of the second

The two measurement passes disagree on three figures: revisions carrying both a
fixed-width layout and calculation grade, reported as 57 across 25 modelos and as 62
across 28; bound casillas, reported as 730 and as 720; and the count of explicitly
out-of-scope obligations, reported as roughly 95 and as 94. The second pass derived each
through the loaded authority rather than by fragment inspection and is preferred.
Recorded because the first-pass figures were circulated before correction.

### closure-predicate-does-not-ship | high | The release-eligibility predicate lives in contributor tooling, not in the application

The application registry package's closure module is 157 lines of pydantic models and
defines no functions. The predicate those models describe — the release check, the
refusal-reason vocabulary, and the cross-limb join — is a 23 kilobyte module inside the
development conformance package, which imports the application models and implements the
logic on top of them. The shipped application therefore carries the vocabulary for release
eligibility but cannot evaluate it, and any gate asserting release state can only run from
the contributor tree. This is the structural reason the registry has no standing gate that
continuous integration can reach, and it inverts the dependency direction the architecture
rule requires.

### export-ref-symmetry-is-unenforced | medium | Eighteen casillas declare an export reference no derived field satisfies

The casilla-to-export-field relationship is declared from both ends, and only one direction
is checked. Measured through the resolved field accessor across the whole corpus, 7841
casillas declare export references and 18 of them are satisfied by no derived field. All 18
are in one modelo. Registry validation passes with those references dangling, so the
asymmetry is undetected rather than tolerated by decision.

### casilla-identifier-grammar-is-unvalidated | high | Three identifier grammars coexist and twelve modelos mix two of them

Casilla identifiers appear in three grammars across the corpus, in the proportions 19990
numeric, 4776 dotted and 2009 boxed. Twelve modelos use two grammars at once, among them
five of the largest by casilla count. No validator constrains which grammar a modelo may
use, so the mixing is neither declared nor refused. A numeric identifier is additionally
restated as a separate number field on all 29522 casillas, and the alias field the schema
provides is used by none of them.

### provenance-is-restated-at-eleven-sites | high | One citation is re-declared across eleven surfaces with no parent-to-child consistency check

A single legal or source citation can be declared at eleven distinct sites, spanning the
revision, the casilla, the calculation entities, the layout, every derived export field,
the completeness manifest, the family dispositions, and several development-side
provenance records carrying their own hash pins. Measurement found 14817 casillas
restating their own revision's legal references verbatim, and 6872 casillas citing sources
that do not appear in their revision's manifest, of which 6634 belong to one modelo. The
latter is legal under the current schema and is detected by nothing.

### applicability-sites-are-unreconciled | high | Seven surfaces express applicability and nothing checks them against each other

Applicability is expressed through registry rules, a small residual table of Python
literals, filing schedules, deadline windows, period tokens that also carry cadence and
scheme meaning, the orden-of-applicability field, and the scope ledgers held in code.
Nothing reconciles the rule, the schedule and the window against one another. The
asymmetry is observable within a single modelo: two of its revisions declare no deadline
windows at all while a third declares sixteen. Registry rules are additionally hydrated
from the first revision found rather than from the revision in force, which makes them
temporally blind.

### wire-type-divergence-is-undeclared | medium | Derived export fields commonly declare a different data type than the casilla they render

A single measurement pass reports that 3043 of 7709 derived export fields, a little under
two fifths, declare a data type differing from that of the casilla they carry, with the
money-to-decimal and ratio-to-decimal transitions dominating. The narrower wire vocabulary
is a deliberate schema choice and is documented as such at the export schema boundary, but
the mapping between the two vocabularies is neither declared nor validated. This figure
comes from one pass and has not been independently reproduced; it is recorded as
indicative and should be re-measured before it grounds any decision.

### second-pass-claims-requiring-correction | low | Three claims from the verification pass did not reproduce and are corrected here

Three claims made by the independent verification pass were probed and did not hold. A
reported 384 casillas with unsatisfied export references reproduces as 18: the reported
count for the largest contributing modelo was 366 and its true value is zero, because that
modelo's linkage resolves through a projection reference rather than a direct casilla
identifier and the pass counted only the latter. A claim that two capability fields do not
exist in the tree is incorrect for both: one is present as a revision key in at least three
revisions as well as a conformance field, and the other exists as a modelo-level field
under a shorter name. A claim that one modelo's authorisation entry carries defective
enrolled years overstates the case: the years are forward-dated but fall inside the span
of an open-ended revision. The broader structural findings those claims accompanied are
unaffected.

### export-ref-symmetry-finding-withdrawn | medium | The eighteen unsatisfied export references were also a resolution artefact and the true residue is zero

The finding recorded above as eighteen unsatisfied export references is withdrawn. A third
linkage path exists that neither measurement pass used: a record maps repeated-row field
names to the casillas they carry, on the record rather than on the field, so a walk over
fields alone counts every row-mapped casilla as unsatisfied. All eighteen belonged to one
repeated counterparty block in a single modelo and are satisfied through that mapping.
Recomputed across the whole corpus with all three paths resolved, the residue is zero. The
casilla-to-export-field edge is in fact symmetric today.

This is the fourth wrong figure in this campaign produced by measuring a surface shallower
than the one the renderer consumes, and it is the most instructive because it survived a
verification pass, a correction, and a screen written specifically to guard against the
first two instances of the same error. Each instance used a different resolution step:
binding derivation, projection reference, and now record-level row mapping. The recurring
cause is not carelessness but that the resolved surface is assembled from several
mechanisms with no single accessor that yields it whole, so each new measurement discovers
the paths it happens to know about.

### resolved-surface-has-no-single-accessor | high | Nothing in the tree returns the complete set of casillas an export layout carries

The casillas a resolved layout carries are reachable only by combining three mechanisms:
binding derivation over the authored collection, an endpoint accessor that falls back from
a direct casilla reference to a projection reference, and a record-level row mapping.
Nothing exposes their union. Every consumer that needs the question answered must
reassemble it, and the four wrong figures recorded in this audit are what reassembly
failure looks like. This is the same fragmentation the identity, provenance and
applicability findings describe, appearing on the export edge, and it is the one instance
where the cost has been measured directly in defective conclusions.

### wire-type-divergence-remeasured | medium | The wire-type divergence is confirmed and larger than first reported, across thirty-three distinct transitions

The wire-type figure recorded above as indicative has now been reproduced through the
resolved-surface accessor. It moved, as expected of any figure taken from a partial walk:
the corpus carries 8075 casilla-to-wire transitions of which 3349 diverge, against the 3043
of 7709 first reported. Thirty-three distinct transition pairs occur.

The distribution matters more than the total. Two pairs account for most of it and are
plainly legitimate narrowings of a richer domain vocabulary into a fixed-width wire
vocabulary: money rendered as decimal, 2140 occurrences, and ratio rendered as decimal, 619.
A long tail is more interesting and is where a transition table earns its keep: money
rendered as integer, 133 occurrences, which discards the decimal places unless an implicit
scale is understood; text rendered as integer, 60; text rendered as date, 49; money rendered
as text, 23; and date rendered as integer, 6. Each of those either encodes a convention
nobody has written down or is a defect, and nothing in the registry currently distinguishes
the two cases.

Row-mapped endpoints are excluded from the measurement rather than dropped from it. After
binding derivation a repeated row's slot is a binding-kind field naming the binding, so it
carries no rendered type to compare; counting those as divergent or as identity would both
be wrong.

### parity-gate-partial-surface-is-latent-not-live | low | The narrow surface reader is a real hazard with zero current instances

The pre-write parity gate and the registry-build export-exemption gate both delegate to the
narrow record scan, which reads casilla-kind fields and the record row mapping but not the
projection fallback. A completeness-manifest casilla served only by a projection field would
therefore be judged out of scope by the parity gate and would need no exemption reason,
which is a silent under-demand. Measured across the whole corpus, the count of such casillas
is zero: the 366 projection-only casillas all sit outside their revision's completeness
manifest, and no manifest casilla anywhere is invisible to the narrow scan. The hazard is
real and the exposure today is nil, so this is a gate to add rather than a defect to repair.
The earlier suggestion that this was a live defect is not supported.

### closure-predicate-relocation-is-not-atomically-possible | medium | The release predicate cannot move while two of its consumers are held by another contributor

An attempt to move the release-eligibility predicate into the shipped application established
two things. First, the predicate cannot live in the closure vocabulary module: the three
coverage composers import that vocabulary, so joining their reports from inside it closes an
import cycle. The predicate needs its own module above the composers and below the rendering
CLI, which is a sound shape and was proven to typecheck and import cleanly. Second, the move
cannot be completed at present. Two dev-side consumers of the displaced names carry pending
changes from another contributor, and the architecture rule requires a relocation to move the
definition and every consumer in one change. A partial move leaves the conformance CLI unable
to import, which is what the attempt produced before it was reverted. The work is ready and
blocked on those two files, not on any unresolved design question.

### revision-name-mismatches-remeasured | medium | Fourteen revision names disagree with their declared window, not six

The revision names recorded above as misstating their windows have been measured
systematically rather than spotted. Fourteen revisions disagree with the window they
declare, in three kinds.

Four misstate their opening year: one names 2025 and opens in 2023, one names 2025 and opens
in 2026, one names a span beginning 2008 and opens in 2022, and one names 2013 and opens in
2012. These were already recorded.

Seven were not. Each names a single year while declaring an open-ended window: two for 2026,
three for 2025, and two for 2024. A reader taking the name at face value would believe the
revision expires at the end of the year it names, when in fact it claims validity onward
indefinitely. That is the more dangerous direction of the two, because it understates reach
rather than overstating it.

Three carry no year token at all. They are the scheme-named revisions of the one modelo that
puts a non-temporal axis in the revision slot, and the screen surfaces them as a distinct
kind rather than skipping them, so the abstraction leak recorded elsewhere in this audit now
has a standing measurement rather than a prose note.

A screen now reports all three kinds and proves its detection against a window moved away
from its name on a copy of a real revision. It reports and does not gate; a gate belongs
here once the fourteen names are corrected, and the count is the work item.

### export-proof-emptiness-is-deliberate-and-fail-closed | medium | The empty proof enrolment is designed refusal, not an oversight, and the finding above is re-framed

The finding recorded above described the filing-export proof channel as built and structurally
empty. The emptiness is correct behaviour, and the record should say so. The declaration site
carries a comment stating that empty inputs are deliberate, that they yield typed per-channel
refusals, and that they are never treated as a waiver or a proof. The offline closure report
bears this out: the filing-export limb refuses with missing evidence rather than reporting a
pass or an unmeasured blank. That is the no-silent-under-declaration contract working, not
failing.

What stands from the earlier finding is the coverage statement alone: no coordinate is
enrolled, so no exported byte has been proven against an official record design. What is
withdrawn is the implication that the channel was left broken or forgotten.

### export-proof-enrolment-is-blocked-on-evidence-not-engineering | high | No official emitted-byte reference exists in the corpus for any modelo

Enrolling a conformance vector requires the acceptance values an independent emitted-byte
review recorded, plus a builder that materialises the render inputs. The corpus was searched
for the first of those and does not contain it. It carries record designs, official forms,
instructions, manuals, calculation oracles, and a pair of AEAT validation-response samples.
It carries no filled filing artefact for any modelo: no official worked example of an emitted
file, and nothing of that shape under any category.

The consequence is that this work cannot be completed by engineering. A vector whose expected
bytes came from this project's own writer would be the engine agreeing with itself, which the
conformance tool's own caveat disclaims and which the calculation-grounding rule forbids as
non-independent evidence. Authoring one would convert an honest refusal into a false proof,
which is strictly worse than the current state.

The prerequisite is therefore evidence acquisition: an official AEAT reference file for one
modelo and revision, or a filing independently produced and reviewed byte by byte against the
official record design by someone other than the implementation. Until one exists, the
release-eligibility claim cannot be made for any revision, and the filing-export limb should
go on refusing. This is the critical path to the product's central claim, and it is an
operator and sourcing task rather than a coding one.

### identifier-grammar-remeasured | high | Five grammars are in use and twenty-one modelos mix them, not three and twelve

The identifier finding recorded above has been measured rather than sampled, and both its
figures moved. The corpus uses five identifier grammars across its 29522 casillas: numeric
19990, dotted 5622, page-qualified 2009, kebab 1745, and bare token 156. Twenty-one modelos
use more than one, not twelve.

Two of the five were missing from the earlier account. Kebab, a hyphenated form carrying no
dot, is the third most common shape in the corpus and its first segment is sometimes numeric,
which is why an initial reading mistook 74 of them for unclassifiable. Page-qualified is a
compound rather than a grammar of its own: a page or block reference joined by a colon to a
tail that is itself one of the other shapes, so its classification has to recurse. A rule that
checked only the head would accept any tail whatever and hide an unrecognised identifier
behind a valid prefix, which is the hazard the screen's detector case pins.

After both corrections no identifier in the shipped registry is unclassified, so the set of
five is complete as a description of what exists today. That completeness is the useful part:
an identifier contract can be written against a closed set, and the screen fails if the corpus
ever grows a sixth shape the set does not name.

The mixing is concentrated where it matters most. The three largest modelos by casilla count
all mix: one carries numeric with token, another numeric with page-qualified, a third
page-qualified with dotted. Cross-revision continuity is asserted between identifiers whose
form is unconstrained, which is why the identifier decision has to precede any continuity
work rather than follow it.

### temporal-site-agreement-measured | high | Deadline declarations are the fragmented axis's weak point, and the earlier example was wrong

The temporal declaration sites have now been compared against one another rather than merely
counted. Thirty-six disagreements exist across the corpus, in two kinds, and two further kinds
were looked for and do not occur.

Twenty-seven revisions declare no deadline window at all. Nine more declare a closed window
containing years that no deadline window serves; one of them spans fourteen years and serves
none of its first seven. Because a deadline window is a third statement of which years a
revision serves, both kinds mean the revision's own sites cannot be reconciled, and the
registry validates either way.

Two conditions were screened for and are absent: no deadline window anywhere is declared for a
filing year outside its revision's window, and no period selector carries both an explicit
years tuple and a year bound at the same time. Those negatives are worth recording, because
they narrow what a temporal contract has to defend against: the fragmentation shows up as
silence rather than as contradiction.

The example given in the applicability finding above is withdrawn. It stated that two revisions
of one modelo declare no deadline windows while a third declares sixteen. Measured, that modelo
declares deadline windows on every one of its six revisions, sixteen on three of them and four,
six and ten on the others. No revision of it has none. The underlying claim that nothing
reconciles rule, schedule and window stands; the illustration attached to it did not.

Open-ended windows are excluded from the year-gap measurement rather than assumed to run to a
horizon. Measuring them against an invented end date would manufacture findings the declaration
does not support, which is the same error as reading a name as a window.

### continuity-integrity-is-sound-and-my-sequencing-claim-was-wrong | medium | No continuity chain crosses an identifier grammar, so the identifier decision does not gate continuity work

The identifier finding above closed with a sequencing claim: that cross-revision continuity is
asserted between identifiers whose form is unconstrained, and that the identifier decision must
therefore precede any continuity work. Measured, that claim does not hold and it is withdrawn.

The corpus carries 1294 continuity chains over 6090 casillas, with 3122 evolution records. Not
one chain spans two identifier grammars. Not one evolution names a chain no casilla carries.
Exactly one chain sits in a single revision, asserting continuity across nothing. The risk the
unconstrained grammar creates is real in principle and has not materialised in practice, so
the two decisions are independent and may be taken in either order.

What the measurement does surface is absence rather than breakage. Twenty-five modelos carry
more than one revision and declare no continuity at all. One of them has five revisions whose
casilla sets are identical in size year on year, which is the shape a modelo takes when nobody
has asserted that this year's box is last year's box. Absent continuity is reported as its own
kind rather than folded in with broken continuity, because the remedies differ: a broken chain
is corrected, a missing one is authored.

The two conditions that hold corpus-wide are now gated as invariants carrying no tolerance.
Coverage is deliberately not gated: most casillas are revision-local, and demanding a chain for
every casilla would manufacture identity rather than record it.

### monetary-scale-undeclared-on-156-fields | high | A monetary amount is emitted with no scale anywhere in the registry, concentrated in four modelos

A fixed-width record carries no decimal point, so a monetary amount is emitted as digits and how
many of them are cents is a convention. The codec settles that convention for two wire types and
for no others. A field rendered as money is multiplied by the cents factor when written and parsed
at two decimal places, so the rule lives in the renderer. A field rendered as decimal refuses
unless it declares a decimal count.

One hundred and fifty six monetary casillas are rendered by a wire type that does neither. One
hundred and thirty three are emitted as integers and twenty three as text, and in both cases the
value is written as it stands with no scaling and no declared count. Whether those digits mean
euros or cents is decided nowhere in this registry. Nothing can check the writer against a rule
that is not written down, and a wrong reading is a filing out by two orders of magnitude.

They are concentrated rather than spread, which makes this a bounded work item: one hundred and
twenty eight sit in a single informativa, twenty two in another, five and one in two more. Each is
answered by reading the official record design for that position.

One further field renders money at four decimal places where every other money field uses two. It
is a unit security value, where four may well be right, and nothing records it as an exception.

The screen that measures this initially reported 3069 fields, because it counted every monetary
casilla that declared no decimal count including those rendered as money, where the codec supplies
the scale. That figure was wrong by a factor of twenty and was corrected before publication by
reading the renderer rather than the declaration. The corrected screen exempts the two self-scaling
wire types and says in its own docstring why.

### money-rendered-as-text-is-faithful-to-the-official-design | medium | The suspicious wire type is correct and the missing scale is the whole defect

Twenty three of the unscaled monetary fields are rendered as text rather than as a number, which
looked like the more serious half of that finding: a money value emitted through a text renderer
gets no sign handling and no numeric padding. Checked against the official record design for one
of them, the wire type is right and the suspicion was wrong.

The design for the modelo carrying fourteen of these declares the field at positions 145 to 160 as
alphanumeric across sixteen positions, and then subdivides it. Position 145 is a sign, an
alphabetic field carrying the letter N when the total is negative and a space in every other case.
Positions 146 to 160 are a fifteen-position numeric importe, itself subdivided into thirteen
positions of integer part at 146 to 158 and two positions of decimal part at 159 to 160. The
authority calls the whole field alphanumeric precisely because its first position is a letter, and
the registry declaring it text mirrors that rather than contradicting it.

Two things follow. The wire type needs no change for these fields, so the remedy for them is
narrower than the wire-type decision assumed: they need a declared scale of two, not a different
type. And the scale the design specifies is unambiguous and written down in the source the project
already holds, so answering these is a reading exercise rather than an open question.

One thing this does not establish is that the writer composes the sign and the fifteen digits
correctly. A text renderer applies no numeric formatting, so the composition happens elsewhere or
not at all, and nothing in the project checks the emitted bytes for these positions against the
design. That remains blocked on the same missing emitted-byte evidence recorded above, and it is a
concrete example of what that evidence would catch.

This is the first finding in this audit grounded in the official authority rather than in the
registry's internal consistency. It cost one file read, and it corrected a reading that three
previous measurements of the same fields had left standing.

### monetary-scale-defect-is-24-fields-not-156 | high | Most of the apparent gap is the official part split, and the render profile cannot express the rest

The monetary scale finding recorded above is corrected again, downward, and the correction rests on
the official designs rather than on the registry.

One hundred and thirty two of the one hundred and fifty six are the authority's own part split. The
design for several informativas carries one amount across two positional fields, an integer part
and a decimal part, and the registry points both at the same casilla. Neither field declares a
decimal count because the split is the encoding. A per-field reading calls both unscaled when the
pair together is complete, which is what the earlier figure did.

Twenty four fields remain genuinely without scale. Twenty three of them are the sign-prefixed
alphanumeric form already examined, where the wire type is faithful to the design and only the
scale is missing. One is a single integer field carrying a whole amount with no split beside it and
no declared count, which is the one case in the corpus that is neither design-faithful nor
structurally scaled.

The reason the twenty three cannot simply be annotated is structural. The generator's render
profile for the modelo carrying most of them contains only numeric representation rules, because
its authority extends to the fields the authority types as numeric. A monetary amount the authority
types as alphanumeric, which it does whenever the field's first position is a sign character, falls
outside the profile entirely, so there is currently nowhere in the authored inputs to declare its
scale. That is a gap in the generator's model rather than a missing annotation, and it is what the
wire-type decision has to close for this class.

The screen now separates the three shapes and its tests pin the precedence, because ordering the
checks wrongly reported fields the codec already scales as split. The published figure for this
condition has now been 3069, then 156, and is 24. Each correction came from reading what consumes
the declaration rather than the declaration itself, and the last two came from the official design.

### one-casilla-emits-euros-where-its-siblings-emit-cents | critical | A filing-grade 2026 revision renders one amount unscaled beside five identical fields that are scaled

The single monetary field that the corrected scale screen could not explain as design-faithful or
structurally split has been traced to the official design, and it is a defect.

The design for the 2026 revision of the IVA group-of-entities aggregate declares six consecutive
liquidation amounts at positions 1126, 1143, 1160, 1177, 1194 and 1211, each seventeen positions
wide and each typed numeric. They are the same kind of field in the same record, and the design
distinguishes them only by what they mean, not by how they are written.

The registry renders those six in three different ways. Three are decimal fields declaring two
decimal places. Two are money fields, which the codec multiplies by one hundred when writing and
parses at two decimal places. Both of those forms produce cents. The sixth, the pago a cuenta
attributable to the State, is an integer field declaring no decimal count, and the integer renderer
applies no scale at all. That field would therefore be written in euros where its five siblings are
written in cents, a factor of one hundred on a filing-grade revision currently in force.

The defect is in the declaration, and the emitted bytes follow from it through two different
renderer branches. What is not established here is the end-to-end byte output, because nothing in
the project compares emitted bytes against the design for any revision. This is the clearest
example yet of what that missing evidence would have caught, and of what it costs not to have it:
the condition was reachable only by comparing a field against its own siblings, which no gate does.

A second, milder inconsistency sits beside it. The five correct fields use two different
representations for the same thing, decimal with a declared count and money with an implicit one.
Both are right and the choice between them is unexplained, which is the wire-type fragmentation the
sibling decision addresses.

### sibling-comparison-is-a-gate-class-nothing-else-covers | medium | Comparing declarations against each other finds what comparing them to a rule cannot

The factor-of-one-hundred defect recorded above was found by hand, by comparing one field against
the five beside it in the same record. None of the nine screens could have found it, and the
reason is structural rather than an oversight in any of them: every one compares a declaration
against a rule, and no rule was broken. The field is a valid integer field with a valid width and a
valid casilla reference. Only its siblings show it to be wrong.

A screen for that comparison now exists and reports exactly one finding across the whole corpus,
which is the known defect. Zero false positives over seventy-four revisions is what makes it worth
keeping rather than a source of noise.

The comparison is on outcome rather than spelling, and that distinction is the whole design. Two
of the correct fields in the same record are money-typed, where the codec applies the cents factor,
and three are decimals declaring two places. Those are different spellings of the same result.
Comparing declared wire types would have reported five disagreements in that record and buried the
one that matters; comparing what the emitted digits mean reports only the field that emits a
different magnitude from its neighbours.

This screen is the only one in the suite whose detector evidence is a live defect rather than a
constructed fixture, which is a stronger proof than the others carry. Its test says so explicitly
and says what must replace it once the defect is corrected, at which point the condition becomes
gateable at zero like the others.

### cross-revision-scale-drift-is-not-worth-gating | low | The only drift the corpus contains is legitimate design evolution, so the screen was not built

The sibling comparison that found the scale defect generalises in an obvious direction: the same
casilla across consecutive revisions of one modelo should presumably scale the same way. That was
measured before building it, and the measurement says not to.

Exactly one casilla in the corpus changes scale outcome between revisions. The property-record
operation amount of one informativa reads as unscaled in the revision covering 2011 to 2024 and as
cents in the revision from 2025 onward. Traced to the authored render profiles, the two revisions
govern that amount with different rules because the authority changed the record design between
them: the earlier design splits the amount into an integer-part field and a decimal-part field,
and the later one carries it as a single field with two implied decimals. Both are correct for
their own revision, and a screen reporting the difference would be reporting that AEAT changed a
form.

The reading was additionally distorted by the probe itself, which applied the per-field scale rule
without the split awareness the shipped screen carries, so it labelled the two halves of a
deliberately split amount as unscaled. Corrected for that, the remaining signal is one legitimate
design change and nothing else.

No screen was built. A gate whose only corpus signal is a false positive would train its readers to
ignore it, and cross-revision representation change is exactly what a new revision is for.

One fact worth keeping from the exercise: the casilla carrying the factor-of-one-hundred defect
does not exist in the previous revision of its modelo. The defect was introduced when the casilla
was first authored, not by a change to an existing declaration, so a gate at authoring time is
where it would have been caught and no cross-revision comparison would have seen it.

### rendering-properties-other-than-scale-are-soundly-authored | low | Padding and justification never disagree between sibling amounts, and signedness varies correctly

The sibling comparison that found the scale defect was applied to the other rendering properties an
export field declares, to see whether the same method yields more. It does not, and the negative
result narrows where the remaining risk lives.

Across every group of monetary fields sharing a record and a width, padding and justification never
disagree. Not one group in the corpus varies on either. Those two properties are therefore already
uniform wherever uniformity is meaningful.

Signedness varies in six groups, and the variation is correct rather than drift. Inspecting one
such record field by field, the signed fields are exactly the four that can carry a negative value:
the two partial results, the net after reduction, the difference, and the final result. Every
unsigned field beside them is a retention, a volume of income, an instalment amount or a deduction,
none of which can be negative. The authoring distinguishes them deliberately.

No screen was built for either property. Padding and justification have never varied and are
produced by the generator systematically, so a gate would guard a condition with no mechanism to
fail. Signedness varies for a reason a gate cannot evaluate without knowing which figures may be
negative, which is a matter of tax meaning rather than of declaration consistency.

This is the second consecutive measurement that argued against building a screen. Taken with the
scale finding it locates the risk on this axis precisely: among the properties governing how an
amount is written, only scale is both silently lossy and inconsistently declared, and it is the one
that now has a screen and a decision behind it.

### scale-defect-root-cause-is-one-missing-anchor | high | The field is governed by no width rule, and the fix is blocked by a missing generator entry point

The factor-of-one-hundred defect has a precise root cause in the authored inputs, and it is an
omission rather than a wrong decision.

The official design for that revision declares four amount fields seventeen positions wide and
typed numeric, at ordinals 122, 123, 124 and 127. The render profile governs width-seventeen
amounts through two membership rules. The first covers ordinals 122, 123 and 124 and carries the
correct representation of fifteen integer positions and two decimals. The second covers a long list
of sibling ordinals including 121, 125, 126 and 128. Ordinal 127 appears in neither. Governed by no
rule, it fell through to a bare integer with no decimal count, which is precisely the unscaled
rendering observed.

The governing rule's own recorded justification states that every width-seventeen amount slot on
this modelo is an importe, so the rule already asserts the coverage it fails to provide. The fix is
to add one anchor to that rule's membership, in a file no other contributor is holding.

The fix cannot be applied. Publishing a regenerated export tree requires a fully assembled pipeline
context, a joined semantic map, rendered output, the render profile and its source evidence, and
the only callers that assemble those are tests driving isolated fixtures. There is no supported way
to regenerate one real modelo revision from its authored inputs. Hand-assembling that call to write
into a shipped registry tree would be driving a generator through a path it does not expose, on
data that feeds filing.

That missing entry point is the finding worth carrying forward. A defect whose root cause is a
one-anchor omission, whose corrected value is stated in the design, and whose authored input is
uncontended, is still unfixable because the generator has no verb. The tooling charter proposed
exactly such a verb; this is the first case where its absence blocks a correction rather than
merely inconveniencing a maintainer.

### missing-anchor-root-cause-withdrawn | high | The field is excluded from render-profile authority by design, not omitted from it

The root cause recorded immediately above is wrong and is withdrawn. It stated that the unscaled
field fell through because its ordinal was missing from the width-seventeen membership rule, and
that the fix was to add one anchor. The fix was attempted on a scratch copy of the profile and the
resolver refused it, which is how the claim was disproven rather than shipped.

Adding the anchor produced a refusal saying that the profile must cover exactly the eligible blank
numeric fields, that nothing was missing, and that the added anchor was unknown. The eligible set
was already complete without it. The field is therefore not omitted from render-profile authority;
it is outside that authority altogether.

The reason is a deliberate rule in the generator. A render profile exists to state a wire fact the
official design left unstated, so a field is eligible for a reviewed rule only when the design says
nothing about how it is written. For a workbook design that test is whether the field's content
cell is blank. The three sibling amounts have blank cells and are governed by the profile; this one
does not, so the generator took the design's own statement instead. The unscaled integer rendering
came from interpreting that statement, not from a fallback.

What remains true is the defect itself: the field still emits an unscaled magnitude beside five
siblings that emit cents, and the sibling screen still reports it. What changes is where the fault
lies and therefore who can fix it. It is not an authoring omission correctable by adding a line to
a profile. It is either a design cell whose stated fact genuinely differs from its siblings, or an
interpretation of that cell that produced the wrong representation, and telling those apart means
reading the workbook cell and the parser together.

The attempt cost one scratch edit, one test run and a revert, and the profile is untouched. It is
recorded because a plausible root cause that survives only until someone tries the fix is worth
less than the refusal that disproved it, and because the previous finding would otherwise stand as
a fix that does not work.

### scale-defect-root-cause-proven-an-applicability-note-read-as-a-wire-fact | critical | A footnote reference in the design's content cell excludes the field from render-profile authority

The root cause is now established by evaluating the generator's own eligibility predicates against
the field rather than by reading code and inferring. Two earlier explanations in this audit are
superseded: the missing-anchor claim, already withdrawn, and the reading that the field's content
cell is blank, which was taken from column position rather than from the header mapping and is
wrong.

The two predicates evaluated side by side on a correct sibling and on the defective field differ in
exactly one place. The sibling carries no content and the predicate reporting whether the design
left the wire fact unstated returns true, so it is eligible for a reviewed render-profile rule and
receives the fifteen-integer, two-decimal amount representation. The defective field carries the
content value ``Nota 4.`` and the same predicate returns false, so it is excluded from
render-profile authority entirely. Excluded, it renders as a bare integer with no scale.

The content value is a footnote reference. The note it points at reads that the field applies only
from period 02 onward. That is an applicability statement and says nothing whatever about how the
value is written, but the generator treats any non-blank content cell on a workbook design as the
design having stated the wire fact. The predicate's own documentation records this hazard for PDF
designs, where descriptive prose lands in the same field and states the representation sometimes,
partially, or not at all. The same hazard exists for workbook designs and is not guarded there.

The blast radius in this design is one field of one hundred and forty three: exactly one content
cell holds nothing but a note reference. That narrowness is why the defect survived, since a
systematic failure would have been visible in every amount.

The defect is therefore a generator interpretation fault, not an authoring omission and not a
design inconsistency. AEAT's design is coherent: four width-seventeen numeric amounts, one of them
footnoted for applicability. The remedy belongs in the eligibility predicate, which must not accept
a bare footnote reference as a statement of representation, and it is a code change rather than a
data change. The corrected field then falls to the existing width-seventeen rule that already
governs its three siblings.

### the-predicate-fix-is-correct-but-not-narrow | high | Thirty-six fields across four designs become newly eligible, so the remedy carries a migration

The proven remedy is to stop accepting a bare footnote reference as a statement of representation.
Before proposing it as a small change, the counterfactual was measured across every design the
generator publishes, and it is not small.

Thirty-six numeric fields across four designs carry a content cell holding nothing but a note
reference and would become eligible for render-profile authority under the corrected predicate.
The distribution is lopsided: thirty-two of them sit in one corporate-tax design, all seventeen
positions wide and all footnoted to the same note, with two more in an IVA design, one in the group
aggregate carrying the known defect, and one in a payments-on-account design at four positions
wide.

That matters because the profile coverage gate demands exact coverage of the eligible set in both
directions. It already refused an anchor that was not eligible, which is how the earlier hypothesis
was disproved; it will equally refuse a profile that fails to govern a field that has become
eligible. Correcting the predicate without authoring rules for all thirty-six would therefore turn
four currently reproducible generated trees red, not one.

So the remedy is a predicate change plus thirty-six reviewed representation decisions, each of which
has to be read off its design. It remains the right fix, because the alternative is leaving a
footnote to decide how an amount is written, but it is a bounded migration rather than a one-line
correction, and the plan should carry it as such.

One detail sharpens the corporate-tax case. Thirty-two width-seventeen amounts in one design all
carry the same note reference, which means their representation is currently being taken from a
footnote in exactly the same way as the field with the proven defect. Whether those thirty-two are
also rendered unscaled was not measured here, and it is the first thing to check: if they are, the
known defect is not one field but thirty-three.

### the-footnote-fault-is-one-live-field-and-thirty-two-latent-ones | high | The corporate-tax exposure is real but unpublished, which changes when it must be fixed rather than whether

The question left open above was whether the thirty-two footnoted corporate-tax amounts are also
rendered unscaled, which would have made the proven defect thirty-three fields rather than one. They
are not, and the reason is worth recording precisely.

That modelo has no published export tree at all. Its revision directory carries casillas, formulas,
bindings, relations and the rest, and no export directory. The design is enrolled in the generator's
tree list, so the pipeline can render it, but nothing is shipped. Thirty-two fields whose
representation would be taken from a footnote therefore render nowhere today. The exposure is latent
and becomes live the moment that tree is published, which is a scheduling fact rather than a
reprieve.

Of the four remaining footnoted numeric fields in published trees, none is an amount. Two sit in an
IVA design at one position wide and one in a payments-on-account design at four, and none appears in
the monetary screen's list of unscaled fields, which names only four modelos and does not include
them. A one-position numeric field carries an indicator, not a magnitude, so a missing scale on it
has no meaning to lose.

The live blast radius of the footnote fault is therefore exactly one field, the one already recorded.
The migration the predicate fix carries is still thirty-six reviewed decisions, because the coverage
gate counts eligibility rather than publication, and the thirty-two unpublished ones become eligible
the moment the predicate is corrected whether or not their tree is shipped.

That separation is the useful outcome. The correctness urgency attaches to one field in a revision
currently in force. The migration cost attaches to thirty-six. Treating those as one number would
either overstate the emergency or understate the work.

### footnote-migration-surface-is-183-not-36 | high | The measurement stands, the screen was withdrawn, and the two facts are separate

The migration estimate recorded above is wrong and is corrected. It said thirty-six numeric fields
would become eligible under the corrected predicate. Measured across every record design any
revision references, rather than across the twenty-five designs the generator's tree list enrols,
the figure is one hundred and eighty three: ninety-six in published trees and eighty-seven in
unpublished ones, spread over eight modelos. The annual IVA summary alone contributes eighty, all
seventeen positions wide and all published.

The more important correction is what that number is not. Exclusion from render-profile authority
does not imply a wrong rendering. The generator can still derive a correct representation from the
design's own type column, and almost all of these fields do render correctly: of the eighty in the
annual summary, the monetary screen reports none as unscaled. The intersection of this population
with an actual scale defect remains one field. A reader taking one hundred and eighty three as a
defect count would be wrong by two orders of magnitude, which is why the number is recorded here
as a migration surface and nowhere as a finding count.

The screen that produced it was withdrawn rather than shipped. Deciding which fields are numeric
and which are source-reserved requires two predicates that live in a private module, and importing
them across a module boundary is what the architecture rule forbids. Restating them locally would
be the restatement this whole plan exists to remove, and the module that could expose them publicly
is one another contributor is holding. A screen that can only be written by breaking the rule it
serves is not worth shipping, so the code was deleted, the runner and the contributor README were
returned to nine screens, and the enrolment and documentation gates confirm both.

What survives is the measurement and the sequencing consequence. Correcting the eligibility
predicate costs one hundred and eighty three reviewed representation decisions, not thirty-six, and
eighty-seven of those attach to trees not yet published. Publishing any of those trees before the
predicate is corrected converts latent work into shipped data that must then be corrected in place.

### six-published-export-trees-do-not-reproduce-from-their-inputs | critical | Two carry record-level drift and four carry a stale provenance attestation

Eight enrolled generated trees fail the reproducibility check, and separating them changes what
each means. The separation was made against the reference test implementation rather than against
the re-render verb built alongside this audit, so it does not depend on that verb's known gaps.

Two of the eight are not published at all. One is the corporate-tax design already recorded as
having no export directory, and one is an annual IVA revision in the same position. For both, the
test reports that a fresh render succeeded and instructs that the tree be published through the
generator's own publication authority rather than the enrolment retired. Neither is drift.

Four of the remaining six differ only in the generation provenance manifest. Their record bytes are
identical to a fresh render, so what is shipped is correct and what is stale is the attestation:
someone changed an authored input, or the generator changed, without republishing. That is a
repairable bookkeeping fault rather than a wrong filing, but it means the manifest no longer proves
what it claims for those revisions.

Two differ in a record file. Both revisions of one informativa carry a declarado record whose
committed bytes are not what the current authored inputs produce: the shipped record repeats over
binding rows and carries binding-kind fields, and a fresh render of today's inputs produces plain
casilla fields with no repeat. That is record-level drift in a published, filing-grade export tree,
spanning revisions that cover filings from 2011 onward.

This correction matters to a claim made earlier in this campaign. The re-render verb reported the
same difference for that modelo and it was attributed to the verb's own incompleteness, because the
verb is known not to supply every input the publishing pipeline stages. The reference test reports
the same record file, so the difference is real and the attribution was wrong. The verb's caution
about inconclusive differences remains correct in general and was misapplied here.

What cannot be settled from inside the registry is which side is right: whether the shipped record
reflects inputs that were later changed, or the current inputs are correct and the shipped record is
stale. Both readings fit the evidence, and choosing between them needs the official design and the
publication history rather than another internal measurement.

### the-shipped-declarado-record-is-correct-and-republishing-it-would-break-the-filing | critical | The drift direction is settled against the official design, and the obvious remedy is the dangerous one

The record-level drift recorded above left open which side was right. The official design settles it,
and the answer inverts the natural repair.

The design states that a declaration carries one record of type one and as many records of type two
as it has declarados and inmuebles. The declarado record therefore repeats, once per counterparty,
which is the entire purpose of this informativa: it reports operations with third parties, and a
filer with two hundred counterparties emits two hundred such records.

The shipped record expresses exactly that. It carries a repeat over binding rows and nine
binding-kind fields, so one authored row becomes one emitted record. A fresh render of today's
authored inputs produces neither: the repeat is absent and the nine fields come out as plain casilla
fields, which can only emit a single declarado record. The shipped bytes are right and the current
render is wrong.

The consequence is the important part. Republishing this modelo from its current inputs would not
correct a stale tree; it would collapse every counterparty into one record and produce a filing that
under-reports everything after the first. The instinctive remedy for a tree that does not reproduce
is to regenerate it, and here that remedy is the defect. Any republication of this modelo must be
blocked until the inputs reproduce the repeat.

What is not established is why the inputs stopped producing it. The semantic map for this revision
contains no repeat or binding-row concept anywhere, so the structure was never expressed there; it
came from the generator's own join, and either that join changed or an input it reads did. Both
remain open and neither changes the direction: the shipped record matches the design and the render
does not.

This also bounds the republication step recorded above. Four trees carry a stale provenance manifest
with correct record bytes and are safe to republish. The two revisions of this modelo are not, and
republishing them alongside the others because they appear in the same failure list would ship the
defect.

### the-generated-corpus-reproduces-except-for-one-modelo | medium | Twenty-one of twenty-seven published trees are byte-identical to a fresh render

Every published generated export tree was re-rendered from its authored inputs and compared. The
result bounds the drift recorded above rather than extending it.

Twenty-one of the twenty-seven reproduce exactly, byte for byte. Four differ only in their
generation manifest, shipping correct records under a stale attestation. Two differ in a record
file, and both are revisions of the same informativa. No other modelo carries record drift anywhere
in the corpus.

That is a strong positive result about the generator and it deserves saying plainly, because most of
this audit reads as a list of faults. The pipeline is deterministic across twenty-one revisions
spanning eleven modelos, and where it is not, the cause is confined to one modelo and one record.

The sweep also corrected the comparison tool's own account of itself. It had carried a caveat saying
a difference was inconclusive, because the modelo that fails re-renders without the repeat its
shipped record carries, and that loss was read as the tool's incompleteness. The sweep showed that
modelo is the only one exhibiting it, the reference implementation reports the same record file, and
the official design requires the record to repeat. The missing repeat is a real defect in what the
current inputs produce, and the caveat was excusing it as a tooling gap. It has been removed and
replaced by the measurement that disproves it.

The lesson generalises past this tool. A caveat that a measurement might be wrong is cheap to write
and hard to retire, and while it stands it converts every finding the tool makes into a question. A
caveat that survives a sweep proving the tool right is no longer caution; it is a reason to ignore a
defect.

### the-declarado-drift-was-already-known-and-guarded | medium | The codebase documents this defect and its remedy, so the contribution here is the census and the gate

The record-level drift recorded above was presented as a discovery. It is real, and it is not new.
The generation pipeline already carries a dedicated refusal for exactly this condition, written by
someone who found it first, and the refusal's own documentation names the same modelo, quotes the
same clause of the same official design, and draws the same conclusion: that a regenerated tree
would declare the first counterparty and drop every other one.

It goes further than this audit had. It records that the semantic map can now express the repeat,
so reaching the refusal means the map has not been authored with it rather than that the vocabulary
is missing, and it names the three things to author: the record repeat, the binding record, and the
per-row casilla identities. It is deliberately raised before the byte comparison so an operator is
told the map is incomplete rather than that two trees differ. The reasoning this audit reconstructed
over three findings was already written down one directory away.

What this audit adds is narrower and worth stating accurately. The refusal fires when a regeneration
is attempted; nothing surveyed the corpus to say how many trees are in that state, and nothing
distinguished a tree carrying this defect from a tree carrying a merely stale attestation. The sweep
established that twenty-one of twenty-seven published trees reproduce exactly, that four differ only
in their manifest, and that this modelo is the only one with record drift anywhere. The disposition
file and its gate make each of those six states explained and make a seventh impossible to acquire
quietly.

The correction matters beyond the credit. A defect that is known, documented and guarded, and that
is still present in shipped data across two revisions covering filings from 2011 onward, is a
different problem from one nobody had noticed. The obstacle is not detection and never was. It is
that the remedy requires authoring input data for a modelo, and until this campaign there was no way
to verify such a change short of publishing it.

### the-declarado-repair-is-the-first-use-of-a-vocabulary-nobody-has-used | high | Every value the repair needs is known except one, and there is no precedent to copy

The repair for the record drift was reduced to a concrete authoring task, and it stops one value
short. Recording where it stops is more useful than guessing the rest.

Three things must be authored on the declarado record of this modelo's semantic map: the record
repeat, the binding record it repeats over, and the per-row casilla identities. Two of the three are
fully determined. The repeat is the literal binding-rows term. The per-row identities are the nine
pairs the shipped tree already carries, mapping row field names to counterparty casillas for tax id,
legal name, operation key, annual amount, the four quarterly amounts and the country code. All nine
bindings those rows resolve to exist in the registry under their own declared ids, so the shipped
tree is internally consistent with the bindings beside it.

The third value has no determined answer here. The binding record names the record whose binding
rows the repeating record follows, and nothing in the corpus shows what that should be for this
modelo, because no authored semantic map anywhere declares this vocabulary at all. A search across
every map in the tree returns nothing for the repeat term, the binding record term, or the per-row
identities term. This modelo's two shipped trees are likewise the only ones in the registry carrying
a repeat.

That explains why the defect has survived being known. The generator once produced the repeat by
some other route, the map vocabulary was added afterwards so that the structure could be authored
rather than derived, and this modelo's map was never brought across. Repairing it is therefore the
first use of that vocabulary rather than a correction following an existing example, and the value
without precedent is the one a reviewer has to decide.

No authoring was attempted. Inventing the undetermined value would put a guess into registry input
data that changes what a filing emits, on the one modelo already carrying a filing-grade defect, and
the verification available would only confirm that the guess reproduces the shipped bytes rather than
that it is right.

### the-map-regression-dropped-a-field-not-only-the-repeat | high | The declarado repair needs four changes, and one needs a design reading nobody has done

The repair was attempted rather than described further, and the attempt found the regression is
larger than the missing repeat. Each step was verified against the pipeline's own refusals, and the
work was reverted when it reached something undetermined.

The undetermined value from the previous finding turned out not to be one. The binding record is
never read when a record repeats over binding rows: the renderer finds its rows from the
binding-kind fields themselves, and consults that value only to decide whether a NON-repeating
record carrying binding-derived fields should be suppressed for want of data. The shipped record
carries no such value, so the correct authored state is its absence, and the earlier reading that a
reviewer must supply it was wrong.

Declaring the repeat alone is refused: a record that repeats binding rows must carry binding fields,
and the map attributes those nine positions to casillas rather than to bindings. Rewriting them is
fully determined, because the shipped tree names which binding each export field carries, and eight
of the nine rewrote cleanly.

The ninth does not exist in the map. The shipped record carries a country-code field that the
current semantic map does not declare at all, so the regression dropped a whole field as well as the
repeat and the binding attribution. Restoring it requires an anchor, meaning the sheet, source row
and ordinal of that position in the official design, and that is a reading of the design rather than
something recoverable from the shipped output.

The repair is therefore four changes, not three: the record repeat, the per-row casilla identities,
nine field entries moved from casilla attribution to binding attribution, and one field entry
re-authored from the design. Three are determined and one needs the design opened. The attempt was
reverted rather than left partial, and the tree is unchanged.

### the-declarado-repair-is-blocked-by-a-map-schema-limit-not-by-missing-data | critical | Two design subdivisions of one PDF anchor cannot both be authored

The repair was carried as far as the schema allows and stopped at a structural limit. Each step was
decided by a refusal from the pipeline rather than by reasoning, and every intermediate conclusion
that proved wrong is corrected here.

The record repeat, the nine per-row casilla identities, and the nine field entries moved from casilla
attribution to binding attribution all author cleanly and were applied. What they produce is a
single four-position field at design positions 77 to 80 bound to the country code. The shipped tree
instead carries two fields there: a two-position province code at 77 to 78 addressed as a casilla,
and a two-position country code at 79 to 80 addressed as a binding. The official design says exactly
that, declaring one field CODIGO PROVINCIA/PAIS across 77 to 80 and subdividing it into a numeric
province code and an alphabetic country code.

Authoring both subdivisions is refused. A semantic map identifies each entry by an anchor of sheet,
source row, optional source cell, printed ordinal and record identity, and two entries sharing all
five collide at load. The optional cell is the only field that could separate them, and it exists
only for workbook designs; this modelo's design is a PDF and carries none. Two values at one PDF
anchor are therefore inexpressible in the map as it stands.

That locates the obstacle precisely. It is not missing data: both casillas exist, both bindings
exist, the design states both positions, and the shipped tree shows the intended output. It is not a
judgement anyone has to make: the earlier reading that a reviewer must supply a binding record was
wrong, since that value is never read for a repeating record. The obstacle is that the map cannot say
what the design says, and closing it means extending the anchor or the entry model so one PDF
position can carry two attributed subdivisions.

Every attempt was reverted. The mappings are unmodified, the comparison reports the same state as
before, and the disposition gate still passes.

### the-obstacle-is-the-design-parser-not-the-map-schema | critical | Only one parser field exists where the shipped tree carries two, so no anchor can address the second

The obstacle recorded in the previous finding was placed in the semantic map's anchor model. That is
wrong, and the correction moves it one layer down.

An anchor names a parser field. The record-design intermediate for this design yields exactly one
field at the position in question: printed ordinal nine, offset seventy-seven, four positions wide.
It does not descend into the two printed subdivisions the design states beneath that row, the numeric
province code at seventy-seven to seventy-eight and the alphabetic country code at seventy-nine to
eighty. Across all three records of this design no printed ordinal appears more than once, so the
parser never descends anywhere here.

That makes two map entries impossible for a reason that has nothing to do with the anchor's shape.
There is no second parser field for a second entry to name. Extending the anchor with a discriminator
would let two entries be written and neither would correspond to anything the parser produced.

The descent mechanism exists and is documented. The render profile's vocabulary carries an
integer-part and fractional-digits pair for quantities AEAT prints as a subdivided row, and its note
states that the export intermediate descends to those leaves so the layout carries two fields for one
casilla. It also states the rule that decides when descent is right: parts of one quantity are
subdivided halves, while a printed subdivision carrying distinct facts earns a casilla per fact. A
province code and a country code are distinct facts, and the registry does carry a casilla for each,
so this position is the second case and the intended shape is two fields.

The shipped tree carries exactly those two fields. It was therefore produced when the intermediate
descended into this row, or by a route that no longer exists. What the current pipeline produces is
one field, and no authoring in the map can change that. The repair belongs in the record-design
parser, and until it lands the shipped bytes remain correct and unreproducible for a reason no
authored input can address.

### an-inherited-figure-reached-a-decision-record-unverified | medium | The open-ended count in the temporal decision was carried from the first pass and is wrong

All four decision records this feature carries were audited against live measurement, on the
principle that a decision resting on a superseded number authorises the wrong work. Two needed
correction and both corrections are recorded here.

The wire-type record claimed one hundred and thirty three unscaled monetary fields with one hundred
and twenty in a single informativa, in four places. That was the pre-split-awareness reading and the
real count is twenty-four. A reviewer accepting it would have authorised a migration five times its
real size and gone looking in a modelo where nothing is wrong.

The temporal record stated that forty-nine revisions are open-ended with twenty-seven filing grade.
Measured against the loaded authority, taking open-ended to mean a revision declaring neither a
closing date nor a closing selector year, it is fifty-four and twenty-eight. That figure was
inherited from the campaign's first pass and was never independently re-derived, unlike every other
figure in that record, which verifies exactly. The definition is now stated in the record so the
number can be checked rather than trusted.

The identifier record verifies exactly on every figure it cites, as do the temporal record's other
claims: twenty-seven revisions declaring no deadline window, nine closed windows with unserved
years, and fourteen names disagreeing with their window all reproduce from the shipped screens.

The lesson is narrow and uncomfortable. This audit opened by finding that a proposed decision rested
on premises the tree no longer exhibited, and spent much of its length correcting figures inherited
from earlier passes. One such figure still reached a decision record written after all of that,
because it arrived in a summary rather than from a command and nothing in the writing of the record
forced it through one. A figure that cannot be reproduced by running something should not appear in
a decision record at all.

### decision-record-figures-cannot-be-gated-by-code | medium | The separation that keeps the vault removable also stops anything mechanical from keeping its numbers honest

The rule recorded above, that a figure which cannot be reproduced by running something does not
belong in a decision record, was examined for whether it could be enforced rather than merely
stated. It cannot, and the reason is structural rather than an oversight.

A gate comparing a decision record's cited figures against live measurement would have to name the
record. The project's always-on mandate forbids exactly that: source code, comments, docstrings,
tests and configuration may not embed development-record stems, decision identifiers, step ids,
wiki-links or harness paths, and the reference direction is one-way. Vault documents cite code by
locator; code never cites the vault. The one place in the tree that mentions the vault at all does
so as an inert path glob, declaring the corpus removable rather than citing anything in it, which is
the distinction the mandate draws.

That separation is deliberate and worth keeping. The corpus is removable scaffolding, and a test
that broke when it was removed would make it load-bearing. But it has a cost this campaign
demonstrated twice over: nothing mechanical can notice when a decision record's evidence goes stale.
The governing coverage decision this audit opened by examining had drifted from its premises with
nothing to catch it, and two of the four decisions written during this campaign drifted the same way
within days, one of them from a figure that arrived in a summary rather than from a command.

So the honest position is that decision-record freshness is a review discipline with no gate behind
it, and the practical mitigations are on the vault side rather than the code side: cite a figure only
where the command producing it is named beside it, prefer a screen's exact output to a paraphrase,
and re-run every cited number before accepting a record rather than before writing it. None of that
is enforceable here, which is precisely why it has to be written down.

### a-failing-gate-asserts-a-revision-that-never-existed | low | The static-inspection failure is a transposed year in the test, not a registry fault

Two tests in the static-inspection suite have failed throughout this campaign and were repeatedly
set aside as pre-existing. They are, and neither is caused by the protocol change made here, which
was separately proven neutral by running the affected suite with the change reverted and restored.
One of them is worth naming rather than leaving as background noise.

It asserts that a modelo's inspection carries the revision identifier for a year beginning two
thousand and two. That modelo declares two revisions, one opening mid twenty twenty four and one
from twenty twenty five onward, and no revision of it has ever carried the asserted identifier. The
asserted and actual strings differ by a transposition of the last two digits, which is what a typed
expectation looks like when it was never run green.

The consequence is small but worth recording in an audit about declarations drifting from what is
true: a gate that has never passed protects nothing, and its failure is indistinguishable from the
background of a suite that has other known failures. It has been read as evidence of a registry
problem more than once during this campaign, including by this audit's own earlier passes, and it is
not one.

The second failure is a boundary check listing files that import the inspection type across a
boundary the rule forbids. Its offenders are workspace modules the in-flight refactor renamed, so it
is a real finding owned by that work rather than by this one.

### a-dead-gate-was-restored-and-its-staleness-had-one-cause | medium | Four assertions were stale together because a modelo was re-grounded and its test was not

The never-passing static-inspection gate recorded above has been repaired and now passes. What it
asserted and what the registry declares differed in four of its seven assertions, and every
difference has the same cause.

The modelo it covers was re-grounded from the 2002 orden it originally cited onto an orden published
in 2024. That single move renamed the revision, added two legal references for the new orden beside
the retained older ones, replaced an enrolled layout source with the 2024 record design, and renamed
the workbook parity reference to match. The casillas, the bindings and the live cross references are
untouched by it, and those three assertions were already correct.

That coherence is what made the repair safe. Fixing the assertions one failure at a time would have
been copying actual values until the test went green, which proves only that a test can be made to
agree with whatever it measures. Reading all seven at once showed a single explicable change with
three assertions unaffected by it, which is a different thing: the test predates a registry
evolution rather than disagreeing with it. The reasoning is recorded in the test's own docstring so
the next reader does not have to reconstruct it.

The wider point is about renames. This project's rules require a rename to move code, tests,
dynamic references, documentation and generated output atomically. This one moved the registry data
and left the test behind, and because the suite already carried another known failure, a second
failing test read as background rather than as a signal. A gate that has never passed is worse than
an absent one: it occupies the place where a working check would sit and it trains its readers to
scroll past.

### eleven-tests-cover-a-filing-proof-surface-that-was-removed | high | A displaced single-channel proof kept its whole test suite after the two-channel one replaced it

A sweep of the registry test suites for permanently failing gates, prompted by the dead
inspection gate repaired earlier, found a second and larger case.

One suite fails in its entirety, eleven tests, and the reasons are substantive rather than an import
break. The production code refuses the path they exercise outright, reporting that the legacy
single-channel filing proof is disabled and that two-channel source and custody authorities are
required. Others fail because the authority object no longer carries the method they call, or because
a refusal message they match by regular expression has been rewritten. The suite tests an API that
was replaced.

None of the files involved carries a pending change, so this is not the in-flight refactor's doing;
it is older debt. The project's own rule on legacy surfaces is explicit that a displaced surface is
removed in the same change that replaces it, and that a passing old caller is not a reason to keep
one. Here the surface was removed and its tests were not, which leaves eleven permanently red gates
asserting behaviour the code deliberately refuses.

The cost is the same as the dead inspection gate but multiplied. A suite that cannot pass tells a
reader nothing about whether the thing it names works, and it raises the ambient failure count until
new failures stop being visible. This campaign spent fifty iterations reading around exactly such
noise: the two static-inspection failures were dismissed repeatedly as background, and one of them
turned out to be a real dead gate that had never passed.

What to do with it is an owner decision rather than a repair. Rewriting the eleven onto the
two-channel authority would give them a subject again, but that authority currently has no enrolled
vectors, so most of what they could assert is a refusal. Deleting them removes a claim of coverage
that does not exist. Either is better than leaving them.

### the-wider-dev-failures-are-the-refactor-and-one-of-them-is-a-gate-working | low | The sweep stops at the boundary of this work, and the first failure it found is an example worth copying

The dead-gate sweep was extended beyond the registry suites to the wider development tests. Roughly
two dozen scattered failures appear there, and they are not this work's to triage: twenty files under
one development package are deleted or changed by the in-flight refactor, and the failures follow
that rather than clustering on a removed surface the way the filing-proof suite does. The sweep
therefore stops at the registry boundary, where the two real findings were.

One of those wider failures is worth recording because it is the codebase defending itself, and it is
the pattern this audit has been applying by hand throughout. A gate asserts that the population it
searches is not empty, and its message states the reason exactly: without that assertion the gate
would be asserting enrolment over an empty set and would stay green if the whole directory it
searches were deleted. The directory has now largely been deleted, and the gate fires.

That is the same hazard this audit met repeatedly from the other side. A conformance measurement
reporting zero of zero says only that nothing could have declared the axis either way. A screen
enrolled in no runner reports nothing and looks clean. A test whose subject was removed keeps
asserting and never passes. Each is a check whose silence means absence rather than health, and only
the first of those three carries a guard.

The registry screens built during this campaign inherited the guard by accident rather than design:
their enrolment gate compares the modules defining a screen against the runner's table, so a screen
that stopped running fails. Nothing equivalent asserts that a screen's population is non-empty. That
is worth adding, and it is worth adding on the strength of this example rather than after a screen
quietly measures nothing.

### the-guard-against-treating-an-empty-proof-as-evidence-is-not-running | critical | One removed method disabled the check that protects the claim this whole campaign is about

The filing-proof suites were examined in the lane that actually runs them, rather than the default
lane that deselects them, and the result is more serious than the retired suite recorded above.

One suite in the integration lane is live rather than legacy: seven of its ten tests pass. The three
that fail all fail for the same reason, an authority object no longer carrying a method the coverage
composer calls, and the same removed method that orphaned the eleven-test suite. So a single API
change took out a whole legacy suite and three tests from a working one, and only the whole suite was
visible as such.

One of those three is the important one. It asserts that an empty canonical live proof cannot turn a
declared layout into emitted-byte evidence. That is the guard against precisely the circularity this
campaign has warned about at every turn: a proof channel with nothing enrolled must not be readable
as though it had proven something. The behaviour it guards is still correct, and was confirmed by
observation early in this audit, since the offline closure refuses the filing-export limb with
missing evidence for every filing-grade revision. But the check that would notice if that ever
changed has not run since the method was removed.

The two others cover the same ground from different directions: that every filing-grade revision has
one law-selected export limb with an honest proof outcome, and that two revisions of one modelo keep
distinct law coordinates and each require production emission proof.

This is the sharpest instance of the pattern this audit has been accumulating. A gate that fails by
not running is invisible, and these were doubly so: deselected from the default lane, and failing on
an attribute error rather than on the assertion they exist to make. The protection against the
product's central claim being made falsely is currently unguarded, and nothing about the failure says
so.

### the-broken-guard-is-a-test-holding-the-old-authority-not-a-broken-composer | high | The production code migrated to the two-channel proof and the tests kept constructing the single-channel one

The cause of the disabled emitted-byte guard was traced rather than left as a missing attribute, and
it sits on the test side, not the production side. The plan Step recorded for it named the wrong file
and has been corrected.

Two proof authorities exist in the same module. The two-channel one carries the assessment method the
coverage composer calls, alongside its enrolment report and vector resolution. The live single-channel
one carries only the older proof lookup. The composer calls the assessment method, so it has migrated
to the two-channel contract; the three failing tests construct the single-channel authority and hand
it over, and the attribute error is what that mismatch looks like from inside.

So the production path is correct and the tests are behind it, which is the same shape as the retired
eleven-test suite and the modelo inspection gate: a surface moved and its callers did not. Three
suites in one area now carry that fault, from one migration, and none of the three announced itself.

The repair is bounded and does not touch production code: point the three tests at the two-channel
authority. What they then assert is worth keeping exactly as written, because the middle one is the
guard that an empty proof channel cannot be read as emitted-byte evidence, and that guard is more
valuable now than when it was authored. The channel it polices is empty by design and will stay empty
until an official reference exists, which is precisely the window in which something might be tempted
to treat a declared layout as proof.

### the-empty-proof-guard-is-running-again | high | Restored by pointing three tests at the migrated authority and asserting the refusal instead of its wording

The disabled guard on this campaign's central claim has been repaired and the suite carrying it now
passes in the lane that runs it. No production code changed.

Two of the three tests were restored by the fixture change alone: they built the single-channel proof
authority, and the coverage composer requires the two-channel one, so pointing the fixture at the
latter and passing no secure-replay inputs was enough. Those tests exercise the public channel, which
is what they were written for; an operator supplies the secure attestations.

The third then failed differently, and the difference matters. It stopped failing on a missing
attribute and started failing on its own assertion, which is the guard doing its job. What it found
was that the empty channel does refuse: the limb reports refused, the reason is missing evidence, the
conformance channel reports evidence missing, and no evidence is attached. The only thing that had
changed was the wording of the human-readable detail, which the two-channel migration rephrased.

The assertion on that wording has been replaced by assertions on the structured refusal: which
channel is empty and that no evidence is attached. The prose belongs to the composer and may be
rewritten again; the guarantee is that an empty channel refuses for want of evidence and names which
channel is empty. Pinning the sentence rather than the fact is what let a working guarantee read as a
broken test, and it stayed silent for as long as that lasted.

The integration lane was swept in full while this was diagnosed. These three were its only failures
across the registry suites, so that lane is now clean.

### every-registry-test-lane-is-now-accounted-for | medium | The not-running class is bounded, and the codebase had already met it twice

The investigation into gates that fail by not running is complete for this area, and the picture is
bounded rather than open-ended.

Registry tests use three lanes. The default unit lane holds fifty-one modules and is clean except for
the eleven-test suite covering the removed single-channel proof and one boundary check whose
offenders are modules the in-flight refactor renamed. The integration lane holds two modules and was
swept in full: its only failures were the three emitted-byte acceptance tests, now repaired, so that
lane is clean. One module is marked for heavy external tooling, held out of every lane by that marker
and enrolled by a named recipe, which is a deliberate exclusion rather than a silent one. No registry
test carries the live-service or keychain markers.

So every registry test now either runs in a lane that is run, or is held out by a marker whose
enrolling recipe is named. That is the useful closing statement, because the whole class of defect
here is a check nobody notices is absent.

Two things found along the way are worth recording for proportion. This codebase had already met this
failure mode twice before this audit did. One module exists solely because a ratchet pointed at a
file that no longer existed and raised rather than measuring, and its documentation says so and
explains why it deliberately does not sit beside the externally-tooled module where it would lose its
teeth. Another gate asserts that its own search population is not empty, stating that without it the
gate would stay green if the directory it searches were deleted.

That is the third and fourth time in this campaign that a defect this audit reached by measurement
turned out to be already understood somewhere in the tree. The pattern is consistent: the knowledge
exists in the place where it was learned, and nothing carries it to the next person who needs it. An
audit is one way to carry it; a gate is a better one, and both of those authors chose the gate.

### a-screen-label-drifted-from-what-its-count-means | low | The runner said one thing and counted another, and the gate covering it only checks the words exist

The audit's headline figures were cross-checked against live screen output, the same discipline
applied earlier to the decision records. Eight of nine reproduce exactly: no unsatisfied export
references, twenty-one modelos mixing identifier grammars, fourteen revision names disagreeing with
their window, thirty-six revisions whose temporal sites disagree, three thousand three hundred and
forty-nine wire-type divergences, twenty-six continuity findings, thirty-six unearned grades and the
provenance total.

The ninth had drifted, not in its count but in its description. The runner announced it as monetary
fields whose emitted scale is undeclared, and by then the screen had grown two further kinds: the
official part split, where the scale is encoded by the split rather than undeclared, and the sibling
comparison, which is not about declaration at all. So the runner reported one hundred and fifty eight
under a label true of only twenty four of them. Both the runner and the contributor README have been
corrected.

The gate covering this asserts that each screen says what it counted, and it passed throughout,
because it checks that the description is non-empty rather than that it is true. That limit is worth
stating plainly rather than trying to close: no gate can check prose against meaning, which is the
same boundary that stops decision-record figures being gated at all. What a gate can do is force the
description to exist and force it to sit beside the count, so a cross-check like this one has
something to compare.

The drift happened because the screen gained kinds after its label was written, which is the same
shape as every other staleness in this audit: an artefact was correct when authored and nothing
revisited it when its subject moved. It was found by comparing a document against a command, which
remains the only reliable check available for anything a gate cannot reach.

### five-of-nine-screen-labels-described-only-one-of-the-kinds-they-count | medium | One inverted its meaning, and the runner is the surface a maintainer reads first

The label drift found on one screen was checked across all nine, and five had it. Each was accurate
when written and each screen then grew kinds without its description following.

The worst inverted its sense. A screen announced as reporting grades unsupported by their
prerequisites reports thirty-six findings, of which thirty-one are the opposite condition: a grade
lower than its prerequisites would support. A reader taking the label at face value would believe
thirty-six revisions overclaim their grade when five do, and would look for the other thirty-one in
entirely the wrong direction.

The rest understated rather than inverted. Three of fourteen revision-name findings are names carrying
no year at all rather than names disagreeing with a window. Twenty-seven of thirty-six temporal
findings are sites falling silent rather than sites disagreeing, which the audit had already
established as this axis's actual failure mode, so the label contradicted a finding recorded above it.
Twenty-five of twenty-six continuity findings are modelos carrying no chains rather than chains
failing to hold.

All five now describe the union they count, and the contributor README rows match. The pattern is the
same one this audit keeps meeting from different directions: an artefact correct at the moment of
writing, a subject that moved, and nothing that revisits the pair. Here it was caught by reading each
screen's own kind census beside its label, which took one command per screen and is the check that
should run whenever a screen gains a kind.

### two-screen-docstrings-never-named-the-kinds-they-emit | medium | Including the one condition that surfaces the corpus's only known filing-correctness defect

The kind token is the whole of what a screen's output row says about which
condition it reports; every other token in the row is coordinates. A kind the
owning docstring never names is therefore a row nobody can act on.

Two screens were in that state. `monetary_scale` documented three conditions and
never mentioned `sibling_scale_disagrees`, which was added later and is the
condition that surfaced the corpus's only known filing-correctness defect - the
monetary field emitted at the wrong magnitude in a revision currently in force.
`revision_name_window` described its rules narratively and named none of its six
kinds, so a reader seeing `kind=name_misstates_opening` could not find that token
anywhere in the module that emits it. Both docstrings now name every kind.

This is the same drift already recorded one layer up for the screen labels: a
screen grows a condition and its prose is not extended with it. Correcting the
text twice does not stop it happening a third time, so it is now gated. The gate
runs the enrolled screens, collects the kind of every finding they actually emit,
and requires the owning module's docstring to name it. The kinds are collected by
running rather than by reading the source, because a first attempt at static
extraction proved unreliable: kinds are assigned as a keyword argument, a local
variable and a typed enum across the suite, and an extractor reading only the
keyword form under-read `monetary_scale` as one kind and `grade_earned` as none,
which would have passed while both were undocumented. An earlier regex attempt
failed the other way, reporting function names as undocumented kinds.

The gate observes 270 kind-rows live, and its teeth were proven rather than
assumed: removing a single kind name from one docstring in memory is caught
exactly once, naming that screen and that kind. Kinds occurring only under a
constructed defect are outside its reach and stay covered by the detector test
that constructs them.

One apparent third case was not one. `coverage_residue_worklist` emits
`refused-selection` and `unbacked-declaration` without using either token in its
docstring, but documents both at length under `**Refused cells**` and
`**Unbacked cells**` headings that explain what each needs and why the rulings
differ. That is documentation; the missing literal is a false positive of a
verbatim-token rule, and no change was made.

### the-development-registry-tests-lane-is-red-and-its-runner-reported-success | high | Twenty-six failures, and a piped exit status that read as zero

The `dev/registry/tests` lane fails: **26 failed, 820 passed** in 6m47s. The lane
is not a passing gate and has not been one, so any claim resting on it is
unfounded until the failures are attributed.

The way this was nearly missed is worth recording, because it is a general trap
rather than a one-off. The run was launched as `pytest ... | tail -15`, and the
harness reported it as exit code 0. That zero is `tail`'s exit status, not
pytest's: a pipeline reports its last command, so piping any gate through a
filter discards the very status the gate exists to produce. The same pipe also
truncated the failure list to its last fifteen lines, so twelve of the
twenty-six failures had no name recorded at all. A gate whose output is piped
reports the pipe.

Attribution of the fourteen named failures. None is caused by the work in this
plan, and that was checked rather than assumed:

- eight in `test_generated_export_trees.py`, over the modelo trees already known
  not to reproduce from their authored inputs;
- three in `test_load_census_classification.py` and one in
  `test_regulatory_prose_parser_channel.py`, both over files the other
  contributor is holding with pending diffs;
- one in `test_modelo_branch_classification.py`;
- one in `test_static_inspection.py`, which refuses use of the static-inspection
  API from runtime boundaries and now names three modules under
  `src/cadrumo/application/modelo/`. That directory is mid-rename in the
  in-flight import-centralisation refactor, so the offenders are that work's,
  not this plan's. This was verified specifically because this session had
  edited both `static_inspection.py` and that test module, which made a
  self-inflicted regression the first hypothesis worth eliminating.

The remaining twelve are the eleven in `test_filing_export_live_proof.py`
recorded in the finding below, plus one the truncation destroyed.

### the-eleven-dead-filing-proof-tests-are-dead-for-two-different-reasons | medium | The plan step named one cause; there are two, and the second is the sharper

The plan step retiring these tests described all eleven as covering the removed
single-channel filing proof. Running them shows two distinct causes, and the
distinction changes the remedy.

Eight drive `LiveFilingExportProofAuthority`, which now refuses on construction:
`legacy single-channel filing proof is disabled; two-channel source and custody
authorities are required`. The displaced surface is still present with its tests
still enrolled, which is the state `no-legacy-compatibility` exists to prevent.

The other three never touch that authority. They exercise
`verify_filing_export_payload_acceptance` and `FilingExportLiveProofEntry`, which
are live, and they fail because their modelo 200 fixture was withdrawn beneath
them: both revisions now declare `calculation` grade, and the modelo carries **no
export layouts at all**. The tests still name probes into
`m200-2025.dp200001.f0001` and index `export_layouts[0]`. So three real
invariants - payload digest, emitted extent, official-offset agreement, and
refusal of distinct probe ids at overlapping bytes - stopped being gated when a
modelo's grade changed, and nothing reported the loss.

Re-siting them is not a rename. It needs a modelo holding filing grade *and* a
layout carrying a filing envelope; the corpus offers 151, 202, 303, 322 and 353,
and none of them has an approved draft helper in the filing test support. Modelo
200 was the only fixture with both a draft and an envelope, and it no longer has
the envelope. Authoring a draft for one of the five is the actual cost of this
step, and it is stated here rather than discovered later.

### the-developer-registry-package-was-a-re-export-facade | medium | Retired, with the test that enforced it

`dev/registry/__init__.py` carried fifty-one lines of imports and a twenty-entry
`__all__` re-exporting the filing-proof and semantic-map surfaces. The
architecture rule is explicit that package initialisers are inert namespace
markers carrying no exports or forwarding, so this was the same defect as the
re-export module already removed earlier in this campaign, one layer up.

It was also load-bearing in only one place. Every other consumer already imported
the defining modules directly, and the sole symbol consumer was one test. A
second consumer imports the `filing_export_proof` module through the package,
which is ordinary submodule access and stays valid against an inert initialiser.

The facade was additionally *enforced*: a test asserted its `__all__` against a
verbatim twenty-entry list, so the violation had a gate keeping it in place, and
that gate was a frozen inventory of the kind this project retired. Initialiser,
assertion and stale import are gone; the consumer imports the defining module.
The affected tests pass (34 passed).

One related condition is recorded rather than acted on, because acting on it
would have widened this change past its scope: the pipeline's defining modules
carry leading underscores while being imported from sibling packages
(`dev/registry/tests`, `dev/registry/analysis`). Under the naming rule an
underscore module is private to its package, so either those modules should be
publicly named or those imports are crossing a private boundary. The facade was
partly masking that question; removing it makes the question visible, which is
the right outcome, but the rename is a separate atomic change.

### four-payload-acceptance-invariants-were-restored-by-re-siting-onto-modelo-151 | medium | The blocker in the previous finding was real but avoidable, and the reasoning that removed it is the useful part

The finding above stated that re-siting the payload-acceptance tests needed a
modelo holding filing grade *and* a filing envelope, that five qualify, and that
none has an approved draft helper. That was accurate but led to an overestimate
of the cost, and the correction is worth recording because it generalises.

Modelo 303 was the obvious target and the expensive one. Its producer snapshot
refuses a general profile, requiring the canonical IVA profile, and then refuses
again without complete `M303FilingFacts` - an evidence graph whose own builder
takes a filing-instance evidence record plus six arrival structures. Authoring
that as a fixture would have been days of work for a re-hash test.

The cost collapsed once the acceptance surface was read rather than assumed.
`verify_filing_export_payload_acceptance` reads exactly three things from its
entry - the expected digest, the expected extent, and the official-offset probes
- plus the layout. It never reads the draft or the modelo. The draft is present
only because the entry's own validation refuses a coordinate its draft does not
match, and that validation checks identity and period, never completeness or
status. So the fixture needs a draft that *is* the coordinate, not a draft that
is complete.

That reduced the search to a modelo whose producer snapshot builds from a general
profile. Of the five candidates, 151 and 322 do; 202 requires its own producer
profile and 353 its own profile facts. Modelo 151's annual coordinate resolves to
a filing-grade revision whose layout carries the envelope and whose first record
is required, non-repeating, and holds five positioned literal fields - enough for
both a probe and a second probe to collide with. A minimal 151 draft built from
no inputs satisfies the entry.

The three tests now run there and pass. The four invariants they carry - payload
digest, emitted extent, official-offset agreement, and refusal of distinct probes
at overlapping bytes - are gated again after a period in which they were not.
The displacement check is deliberately kept sharp: the payload is built with the
literal present but shifted one byte, so a check that searched for the literal
rather than reading its declared position would pass it.

The eight tests driving the disabled single-channel authority were removed rather
than re-sited. Nothing now drives that authority, so the disabled surface itself
should follow under `no-legacy-compatibility`; that is a step of its own because
it still has non-test references.

Removing those tests orphaned the modelo 200 draft fixture, whose only remaining
mentions were its own name. It was removed in the same change, which is what that
rule requires rather than leaving it for a later sweep.

### twenty-four-filing-tests-demand-filing-grade-from-modelos-that-no-longer-declare-it | high | The same withdrawal that killed the payload tests is failing a whole suite

Running `src/cadrumo/application/filing/tests` gives 34 failed, 525 passed. None
of the failures references the work recorded here, which was checked by name
rather than inferred.

Twenty-four share one root cause, and it is the cause already met above: a
revision's authority grade was lowered while the tests demanding filing grade
from it stayed enrolled. Twenty-one raise `modelo 200 revision 2025-y-siguientes
declares 'calculation' authority grade, which cannot satisfy the requested
'filing' snapshot authority`; two raise it for modelo 038 and one for modelo 036,
both at `applicability` grade.

Lowering a grade is the honest act - it is `no-silent-under-declaration` working
as intended, and a modelo that cannot be filed should not claim it can. What did
not happen is the other half: the consumers asserting the old claim were left
asserting it. The result is a red suite that says nothing about the change that
made it red, and a reader cannot tell from the failures whether a grade was
lowered deliberately or a revision regressed. A grade change needs to move its
consumers in the same change, exactly as an identifier change does.

### two-enrolled-generated-trees-render-but-were-never-published | medium | The remedy the failing gate names is a verb whose implementation exists and has no caller

A suspicion about this campaign's own artefacts turned out to be unfounded, and
the checking is recorded because the conclusion changed twice.

The disposition file for non-reproducing generated trees carries six rows and
states that every non-reproducing tree carries one. Eight tests in
`test_generated_export_trees.py` fail. Six of those eight match the six rows;
`200/2025-y-siguientes` and `390/2022` do not, which read as the disposition file
under-declaring by two.

It does not. Neither modelo ships a committed export tree at all, and the
disposition gate walks only revisions that have one, so both are correctly out of
scope. The published population really is twenty-seven, and the census figure of
twenty-one reproducing, four provenance-only and two record-drift stands.

What the two failures actually say is different and more useful. Both are
enrolled as generated trees, both render successfully under the reference
implementation, and neither has ever been committed. The gate's own message is
the instruction: publish through the generator's publication authority, and do
not retire the row.

That authority exists. `publish_validated_generated_export_tree` is implemented in
the pipeline, and a search for its callers returns exactly one hit: a test
asserting that the tree-check module does *not* reference it. So the pipeline can
render, validate, check and publish, and the publish limb is reachable by no
caller in the repository. The plan step covering this described the verb as
something to be written; it is something to be *invoked*, and the step now says
so. This is the second step in this campaign whose premise was wrong in the same
direction - describing as absent something that exists but is unreachable - which
is worth noting as a pattern rather than two coincidences.

One discrepancy between the two render paths is recorded rather than resolved.
This campaign's read-only comparison refuses both trees: modelo 200 because the
revision declares no export layout, modelo 390 because a literal field disagrees
byte-for-byte with its official constant. The reference implementation renders
both, because it synthesises the layout identifier from a naming convention
(`generated-modelo-<modelo>-<revision>-fichero`) instead of reading the declared
layouts. Neither approach is wrong for its purpose - a read-only comparison
against committed bytes should refuse when the registry declares no layout, and a
generator that has not published yet cannot read a layout it has not created -
but the two disagree about what is renderable, and after publication only one of
them is consulting the registry.

### the-pipeline-package-was-a-second-re-export-facade | low | Same defect one level down, retired the same way

`dev/registry/pipeline/__init__.py` re-exported five pipeline entry points behind
an `__all__`, the same violation as the package initialiser above it. Every
consumer already reaches its modules by submodule access, which stays valid
against an inert initialiser, and no caller imported the symbols from the package
root. Unlike the facade above it, nothing enforced this one: the only test naming
a re-exported symbol does so in a forbidden-name check, asserting the tree-check
module never references publication.

The initialiser is now the docstring alone; the affected tests pass (39 passed).

### every-open-step-target-was-checked-against-the-tree-and-forty-five-of-forty-eight-hold | low | A negative result, recorded because the checking was the point

Two steps in a row had premises that were wrong in the same direction - naming as
absent something that existed but was unreachable. Rather than meet the third one
by accident, all forty-eight open steps were resolved against the live tree.

Six name a target that does not exist, and in each case the step exists to create
it: three test modules, a coordinates declaration, a conformance vector, and a
temporal-selection test. That is the expected shape, not a defect.

The risky class is the opposite - a step asking for behaviour a file may already
have - so the three likeliest were read rather than assumed. The revision-identity
module handles reference and casilla identity and carries no name-against-window
check, so that step is real work. The closure-capture module's coordinate is
explicitly an opaque, non-persisted, same-process value, so recording a persisted
coordinate set is also real work. Both premises hold.

The value here is the cost avoided: the two corrected steps were each found only
after starting the work they described.

### the-spent-applicability-migrator-is-retired | low | Its own retention rationale cited a step id from a plan that no longer exists

A one-shot transcriber that moved applicability literals into registry fragments
was still shipped in the development tree. Its retention was justified in its own
docstring by a future step that would reuse it for modelos 303 and 390.

Three things were checked before removing it, because the docstring's own account
argued against removal. Its output has landed: a dry run reports it would write
fragments for thirty-five modelos, but those fragments already exist on disk, so
the report is unconditional re-transcription rather than a list of absences. The
exclusion it defends is empty of work: modelo 390 already carries eight
applicability fragments despite being excluded, and modelo 303 carries none - but
neither does over a third of the corpus, so zero fragments is the ordinary state
for a modelo with no applicability declarations, not evidence of pending
migration. And the step id the docstring names does not exist in the current
plan.

That docstring was itself a rule breach: it cited plan and step identifiers in
source, which the code-stands-alone mandate forbids outright. The reference
direction is one-way, and a module explaining itself by campaign state is exactly
what that rule exists to prevent.

Nothing referenced the module. Its removal leaves the dependency-surface test the
only remaining mention of the packaging dependency it required, and that test
asserts the declaration rather than a consumer, so it is unaffected.

### an-in-flight-rename-left-a-stale-consumer-in-the-packaging-tooling | medium | Not this campaign's work, reported rather than edited

Two tests in `dev/packaging/tests/test_dependency_surface.py` fail with
`FileNotFoundError` for `src/cadrumo/core/_optional_extras.py`. That module was
renamed to `optional_extras.py` by the import-centralisation refactor, and
`dev/packaging/dependency_surface.py` still names the underscore form.

This is the atomic-relocation obligation in the architecture rule: a symbol moves
together with every consumer, and a rename that updates the definition and leaves
a caller behind is the failure that rule describes. It is recorded rather than
corrected here because the rename belongs to another contributor's in-flight work
and they may still be sweeping consumers; a second writer on that surface would
be the more expensive mistake. The fix is a single path.

### correction-the-single-channel-authority-does-not-refuse-on-construction | medium | The finding above said construction; the refusal is conditional and sits one level in

An earlier finding here recorded that `LiveFilingExportProofAuthority` "now
refuses on construction". That was inferred from a traceback whose raise site sat
near a construction call, and it is wrong. Constructing it with no entries
succeeds, which was checked directly rather than re-read.

The refusal lives in `proof_for`, and only after a matching entry is found: with
no entry for the requested coordinate the method returns `None`. So the class has
two live paths and one dead one. Asked about a coordinate it does not carry, it
answers honestly that it has no proof. Asked about a coordinate it *does* carry -
the only path that could ever produce a proof - it refuses. The canonical entry
tuple is empty, so in production it always takes the first path and always
answers `None`.

That makes the surface dead in substance while remaining constructible, which is
why retiring it is still right and why the retiring step's own premise needed
correcting too. The step said no test drives it. One does:
`test_real_closure_outcomes.py` builds the authority with a real modelo 151 entry
and asserts a satisfied filing-export outcome over 11,618 emitted bytes. That
test fails today. Deleting the authority therefore means rewriting that test onto
the two-channel authority, not simply removing an unused class, and the step now
says so.

The deletion is deliberately not being made yet. That same test file is failing
for a second and unrelated reason - `RegistryClosureRevisionReport` now rejects
the `temporal_coverage` fields `status`, `failure_code`, `failure_detail` and
`refused_coordinates` as `extra_forbidden` - which is a model change in the
application registry package belonging to another contributor's in-flight work.
Editing that file now would put a second writer on a surface already moving.

### the-conformance-test-directory-is-outside-every-lane-run-this-campaign-has-made | medium | A whole directory of real-authority tests whose state was simply unknown

Every full-lane measurement in this campaign ran `dev/registry/tests`. The
conformance suite lives at `dev/registry/conformance/tests` and was never in that
path, so its results have not once been observed while this plan reported lane
state to two decimal places.

Run directly, it gives 2 failed, 5 passed in 11m36s. Both failures are real and
neither was known: the live-filing closure row above, and a grade-scope guard
whose expected refusal message no longer matches what the code raises.

The lesson is not that these two failures matter most - they are both downstream
of other work - but that a measurement's scope is a claim in itself. "The lane is
fifteen failures" was true of the path measured and silently excluded a sibling
directory of tests that exercise the real closure authority. Its runtime is also
why it is easy to omit: at nearly twelve minutes for seven tests it exceeds the
default foreground timeout, so it drops out of any run that is not deliberately
backgrounded.


## Recommendations

Re-ground the proposed grade-bound coverage decision before it is accepted. Its problem
statement, its cited source paths, and its population figures all now describe a tree that
no longer exists. Re-grounding is a body revision to that record, not a new decision, and
it should establish which part of the original problem survives the work that has since
landed. Until it is re-grounded, the in-flight plan executing this feature is progressing
against a stale authorisation.

Enrol coordinates in the filing-export proof channel. The mechanism is built and empty,
which makes this authoring against existing machinery rather than new construction, and it
is the shortest path from the current position to a defensible statement that any export
is byte-correct. The generated-provenance verifier defect must be repaired first or
concurrently, since it blocks the same path. Neither requires an architectural decision.

Replace the deleted ratchet with a semantic standing gate and retire its residue. The gate
should assert coordinate identity and declaration completeness rather than a frozen count,
and it must be placed where it demonstrably executes, given that a warm load skips
registry validation. Re-point the runbook, the justfile target, the development README,
and the gate test away from the deleted command, and delete the dead baseline and ratchet
classes.

Decide the temporal declaration contract in an ADR rather than by accretion. The decision
must name which single site is authoritative for a revision's temporal fact, which other
sites are derived projections of it, and what makes a contradictory declaration
unconstructable rather than merely detected by an agreement validator. It must also decide
how valid until superseded is distinguished from verified valid for year N, and where the
non-temporal scheme axis lives once it leaves the revision slot. This is the decision the
fragmentation finding points to and it is architecturally significant; it is not recorded
here.

Correct the revision directory names that misstate their windows, as a mechanical change
separable from the contract decision above. Because the directory name is the revision
identifier, each rename is an identifier change and must move code, tests, generated
output, and review stamps atomically.

Treat derived layouts as the only valid measurement surface for export coverage in any
future audit or gate, and state the derivation entry point wherever such a figure is
published.

Move the release-eligibility predicate into the application registry package beside the
models it already ships, leaving the development tooling as a thin caller. Until the
predicate ships, no gate asserting release state can run anywhere except a contributor
machine, and the standing-gate recommendation above cannot be satisfied.

Require every coverage or completeness figure, in a gate or an audit, to be measured
through the resolved accessor rather than the authored fragments. Three separate wrong
figures in this campaign have come from the authored surface, in two independent passes,
including two findings this record withdraws and one it corrects. The remedy is not
vigilance; it is that the gates themselves read through the resolution entry point and say
so where a reader will see it.

Add the four missing edge checks as semantic gates rather than counts: export-reference
symmetry in both directions, a declared and validated casilla-to-wire type mapping, a
grade that must be earned from its derived prerequisites or carry a reasoned disposition,
and parent-to-child provenance consistency. Each has live violations recorded above, so
each can demonstrate detector teeth against a real defect rather than a synthetic one.

Constrain identifier grammar per modelo as a declared property, and retire the restated
number field and the unused alias field. This is a precondition for any cross-revision
continuity work, because continuity is asserted between identifiers whose form is
currently unconstrained.

Sequence the architectural decisions as a cluster rather than a queue. The declaration-kind
contract governs the temporal, provenance and value-semantics axes at once, and deciding
any one of them alone will fix its shape before the general rule exists. The re-grounding
of the feature's proposed coverage decision should be taken together with that contract,
not before it.

Correct the export-reference symmetry recommendation above. That edge has no live
violations, so the gate it proposed cannot demonstrate detector teeth against a real defect
and must use a constructed fixture like any other. The gate remains worth building, because
the edge is unenforced whether or not it is currently clean, but it is a regression guard
rather than a repair.

Provide one accessor that returns the complete resolved casilla surface of a revision's
export layouts, and require every gate, screen and audit to consume it rather than
reassemble the three mechanisms. This is the narrowest change that would have prevented all
four wrong figures recorded here, and it should precede the four edge gates rather than
follow them, since three of those gates measure that same surface.

### Consolidated position

The recommendations above accumulated as the audit ran and some are superseded by later findings.
This section states the current position and takes precedence where they differ. Two of the earlier
recommendations are withdrawn: the export-reference symmetry gate was described as repairing live
violations and repairs none, and the estimate that the eligibility correction costs thirty-six
reviewed decisions is wrong at one hundred and eighty three.

One defect is proven and affects filing. A monetary amount in a revision currently in force is
emitted unscaled beside five identical siblings emitting cents, a factor of one hundred. Its root
cause is established: a footnote reference in the design's content cell is read as a statement of
how the field is written, which excludes it from render-profile authority. The remedy is a change to
one eligibility predicate. Nothing else in this audit is a known wrong number.

Three things block work that is otherwise ready, and none is a design question. Files another
contributor holds block the predicate correction, the release-predicate relocation and the ratchet
removal. The absence of a generator verb blocks every correction to a generated tree, including the
one above. The absence of any official emitted-byte reference blocks the filing-export proof
entirely, and no amount of engineering substitutes for it, because a vector whose expected bytes come
from this project's own writer proves only self-consistency.

Sequencing has one hard constraint discovered by measurement. The eligibility correction must precede
the publication of any further export tree. Eighty-seven of the affected fields sit in designs not
yet published, sixty of them in the corporate-tax design; publishing first converts authoring work
into correction of shipped filing data.

The four decisions this feature needs are written and proposed. Each rejected the obvious rule
because measurement contradicted it: strict agreement checking finds contradictions where the
temporal axis fails by silence, one grammar per modelo would force abandoning either official box
numbers or unnumbered domain concepts, a blunt permitted-transition table cannot separate two
thousand correct cents encodings from a hundred and thirty three ambiguous ones, and the general
contract makes restatement unrepresentable rather than merely policed.

What the tooling built here can and cannot do is the last point, and it bounds what further
iteration is worth. Nine screens and seven gates measure the registry against itself, and they are
sound: they found the candidate that led to the one proven defect. They cannot establish that any
emitted byte matches what AEAT expects. The remaining distance to the claim this product exists to
make is not more screens; it is one official reference file and the decisions above.

### Consolidated position, second revision

The consolidated position above was written before roughly half this audit's findings existed and is
superseded by this section. Nothing in it was wrong when written; it is simply no longer the whole
picture.

Two defects touch filing data and both are located precisely. One monetary field in a revision
currently in force emits an unscaled magnitude beside five identical siblings that emit cents, and
its root cause is a footnote reference in the design's content cell being read as a statement of how
the field is written. One informativa ships a declarado record, across two revisions covering
filings from 2011 onward, whose repeating structure the current authored inputs no longer produce;
the shipped bytes are correct and regenerating that tree would collapse every counterparty into one
record.

Neither is repairable from where this work sits, and the reasons differ. The first needs a change to
an eligibility predicate in a file another contributor holds, and that change makes one hundred and
eighty three fields newly eligible, each needing a reviewed representation rule authored in the same
change. The second needs the record-design parser to descend into printed subdivisions that carry
distinct facts, because only one parser field exists where the shipped tree carries two, and no
authoring in the semantic map can create the second.

The generated corpus is otherwise sound and that is worth stating: twenty-one of twenty-seven
published trees reproduce byte for byte from their authored inputs, four differ only in a stale
provenance attestation and are safe to republish, and the two above are not. Each of the six carries
a written disposition and a gate refuses both an undispositioned failure and a disposition whose
tree has been repaired.

A separate class of finding emerged late and is worth acting on independently of everything else.
Gates in this area fail silently by not running rather than by going red. A modelo inspection gate
asserted a revision identifier that had never existed and had therefore never passed; it is now
repaired and passing. Eleven tests cover a filing-proof surface the codebase removed and refuses,
and they should be retired or rewritten rather than left permanently red. One of this campaign's own
screens was enrolled and gated for days with nothing proving it could detect either condition it
guarded. Each of those was invisible because the suite already carried failures that had been read
as background.

What has not changed is the ceiling. Nine screens and ten gates measure the registry against itself
and they are sound, but nothing here establishes that an emitted byte matches what the authority
expects. Four measurements in this audit were settled only by opening an official design, and every
one of them corrected a conclusion the internal tooling had reached. The remaining distance to the
claim this product exists to make is one official reference file and the decisions listed above.
