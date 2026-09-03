---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-09-01'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:8dc762da0849d5ae4401cefd813d5e6b981dc2efec81f0000151c54b1a7c3a64'
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

### seven-package-initialisers-were-facades-and-the-condition-is-now-gated | medium | Two were fixed one at a time before anyone asked how many there were

Two re-export facades were removed from this tree in earlier findings, each
found by walking into it while doing something else. Neither prompted the
obvious question, which is how many others there are. Surveying every
`__init__.py` under the registry development tree answers it: of eleven, five
still carried imports and an `__all__`, including one of eighty-five lines and
one of sixty-five.

All five were removable without touching a single caller. An AST sweep for
symbol imports from those five package roots returns zero across the repository:
every consumer already imports the defining module. The facades were carrying
nothing except the ability to grow, and three of them were pure - docstring,
imports, `__all__`, and no other statement - so reducing them to their docstrings
was mechanical.

Two checks were made that a symbol search would not have caught, because these
packages are executed as well as imported. Three are run as `python -m
dev.registry.<package>` from the justfile and CI, which loads `__main__.py`; each
of those imports `from .cli import app`, the submodule, not the package root. The
fourth is referenced in two CI workflows as
`python -m dev.registry.parity.maintenance_cli`, again a submodule path. All four
entry points were then imported directly to confirm it rather than argued.

One of the five was this campaign's own: an `analysis` initialiser declaring an
empty `__all__`. An empty export list is still an export declaration, and leaving
it while removing four others would have been the kind of exemption that makes a
rule unenforceable.

The condition is now gated: every initialiser in the tree must carry nothing but
a docstring. The gate is paired with a detector that builds a facade as source
text and shows the predicate catches its import and its `__all__` - constructed
in memory rather than written into the tree, because a gate over the
contributor's working tree must not modify it to prove itself. The argument for a
standing gate rather than five fixes is that nothing made the first facade fail,
so nothing would have made the sixth.

### the-lane-figure-was-wrong-again-for-the-same-reason-one-size-down | medium | Reported as seventeen, measured as eighteen: a file was run where a directory was meant

The previous finding here established that every lane measurement had covered
`dev/registry/tests` and silently excluded the conformance suite beside it, and
put the corrected total at seventeen. Measured over both directories the total is
**eighteen**: `PYTEST_EXIT=1`, 18 failed against 833 passed in 15m05s.

The missing one is a third conformance failure, in `test_closure.py`. It was
missed because the correction ran a single *file* of that directory rather than
the directory - the identical error to the one being corrected, one size smaller,
committed while writing the correction for it.

The plan criterion now names paths rather than reciting a count, because the count
has been wrong twice and the path is what makes it checkable.

### five-code-boundary-violations-in-the-registry-tree-are-cleared | medium | A shipped check already existed for the rule; nobody had run it

The retired applicability migrator was found citing plan and step identifiers in
its own docstring, which the code-stands-alone mandate forbids. That prompted the
question of how many others do the same, and the answer did not need new tooling:
`vaultspec-core vault check code-boundary` exists for exactly this rule and had
twelve findings.

Five were in this campaign's tree and are now cleared. The generation pipeline's
source-defect module cited an ADR and a reference document to justify its own
adjudication; the citation was unnecessary, because that docstring already argues
the whole case from the document it adjudicates - a workbook that prints an
eleven-character constant into a slot it declares twelve bytes wide - and the
vault record cites the module by path, not the reverse. Four modelo 390 casilla
declarations carried an ADR identifier in a parenthetical inside an otherwise
self-contained comment, which the sentence survives losing.

These are shipped filing-grade declarations, so the change was verified rather
than assumed safe: the diff is four files of one line each, the authority still
compiles all five modelo 390 revisions and their 1,450 casillas, and the annual
snapshot still resolves at filing grade.

Seven violations remain, all outside this tree, and they are recorded rather than
fixed for the same reason as before: they belong to surfaces this campaign does
not own.

### the-facade-condition-was-not-peculiar-to-this-tree | low | Eleven of fifty-two initialisers elsewhere in the development tree carry exports

Having found seven facades in the registry development tree, the same predicate
was run across the rest of the development tree to see whether that was unusual.
It is not: eleven of fifty-two initialisers outside the registry carry statements
beyond a docstring, the largest fourteen.

They are deliberately not touched. They sit outside this plan's feature, and the
gate written here is scoped to the registry tree for the honest reason that a
repository-wide version would fail immediately on surfaces nobody has agreed to
change. The measurement is recorded so that the scoping is a decision someone can
revisit rather than an omission.

### the-closure-report-is-snapshot-bound-and-costs-211-seconds | high | Seventeen hundred isolated snapshots for one hundred and twenty-eight rows

The third conformance failure is not an assertion. `test_cli_live_mode_uses_
canonical_loaders_but_blocks_without_durable_filing_proof` exhausts the suite's
300-second budget inside `copy.deepcopy`, and the reason is a cost nobody had
measured: one registry closure report takes **210.8 seconds** to produce 128 rows.
That leaves no room for a test that builds the report and then does anything at
all.

The attribution was taken rather than guessed, and the first guess was wrong. The
traceback points at deepcopy, so "snapshot isolation is the cost" is the obvious
reading; timing snapshots individually gives 0.04s to 0.23s, which across 128 rows
accounts for about 26 seconds, so the obvious reading appeared to fail and the
remaining 185 seconds looked unexplained. A profiler run was started and abandoned
after forty minutes without output - cProfile's overhead over deeply recursive
deepcopy is severe enough to be useless here.

Timing the report's four composable phases directly settles it in one run.
`compose_temporal_coverage` takes 103.8s and `compose_filing_export_coverage`
73.4s, together 84% of the total. Counting inside the first: **1,727 `snapshot()`
calls costing 82.9 seconds, 95% of that phase**. So the earlier estimate was wrong
not about the mechanism but about the multiplier - the composer takes about
thirteen and a half snapshots per row, not one.

What makes this structural rather than a slow function is where the isolation
sits. The authority caches the compiled registry, and the freshness test asserts
that identity directly. What `snapshot()` does per call is `model_copy(deep=True)`
on the revision projection, so the cache prevents recompilation and not
re-isolation: N calls cost N deep copies whatever the cache does. The registry
authority rule requires callers to receive isolated validated snapshots rather
than shared mutable state, so the copying is deliberate and correct; what is
accidental is taking seventeen hundred of them to answer a question about a
hundred and twenty-eight rows.

Two constraints bound the remedy, and both are worth stating before anyone reaches
for a cache. Memoising above the authority is explicitly forbidden and gated: a
fingerprint-blind memo would outlive the authority's own cache entry and hand back
a pinned object after invalidation. And that gate is itself red right now -
`test_snapshot_resolution_is_not_memoized_above_the_authority` is among the
currently failing filing tests - so the property it defends cannot presently be
assumed to hold. The tractable directions are reducing the call count in the
composers, or making isolation cheap for models that are already frozen, and
neither is a cache above the authority.

### the-temporal-coverage-phase-is-eleven-times-faster-and-provably-unchanged | high | Seventeen hundred deep copies were made to read seventeen hundred strings

The composer took one isolated snapshot per coordinate and used exactly one
thing from it: `str(snapshot.revision.id)`. Every field of the validated
projection was deep-copied and then discarded. The call had a second real
purpose - proving the snapshot boundary admits the coordinate at its declared
grade, which is the module's stated reason for going through the boundary at all
- but that purpose is served by whether the call raises, not by the object it
returns.

The measurements that settle where the cost sits, all against the bundled
registry:

- `_cached_snapshot` on a hit: **0.0 ms**. The compiled registry really is cached.
- deep copy of the full `RegistrySnapshot`: **236.5 ms**.
- the whole `snapshot()` call: **241.1 ms**.

So the isolating copy is **98%** of the call, and the cache prevents
recompilation rather than re-isolation. `compose_temporal_coverage` made 1,727
such calls for 128 rows.

A new accessor returns the admitted revision identifier through the same
selection, the same validation and the same refusals, without the copy. Giving
up the copy is safe for exactly one reason and no more: the copy exists so a
caller cannot mutate cached registry state, and a string is not mutable state. A
caller that goes on to READ the projection still takes a snapshot and still gets
its own isolated copy. The phase falls from **103.8s to 9.5s**.

Behaviour was proved unchanged rather than asserted: every one of the 1,727
coordinates the composer visits was replayed through both the old and the new
path and the outcomes compared including exception type and message - **0
differ**. The owning tests pass (44), and the accessor carries its own tests
covering four unlike modelos, an identical refusal on a grade the registry
genuinely will not admit, and the string-ness that the safety argument rests on.

One self-correction is recorded because it nearly damaged an accurate record. An
intermediate measurement put the deep copy at 18% of the call, which appeared to
refute the finding above and prompted a correction to it. That measurement was
wrong: it timed a deep copy of `snapshot.revision` against a call that
deep-copies the entire `RegistrySnapshot`, which is a comparison of unlike
things. Measuring the same object on both sides gives 98%. The lesson is narrow
and worth keeping - a correction needs the same standard of evidence as the
claim it corrects, and this one nearly replaced a true statement with a false
one.

### the-conformance-cli-test-now-passes-and-the-margin-says-the-work-is-not-finished | medium | 262 seconds against a 300 second budget is a pass nobody should rely on

`test_cli_live_mode_uses_canonical_loaders_but_blocks_without_durable_filing_proof`
failed by exhausting the suite's 300-second budget. With the temporal-coverage
phase cut from 103.8s to 9.5s it now passes: `1 passed in 262.71s`. The whole
closure report fell from 210.8s to 93.0s over the same 128 rows.

The pass is real and it is also thin. Thirty-seven seconds of headroom on a
four-minute test is not a margin, it is a coincidence: any machine slower than
this one, any concurrent test run competing for CPU, or any future row added to
the report puts it back over the line. The failure would then look like a
regression in whatever changed last rather than the cost cliff it actually is.

So this is recorded as progress with the remedy unfinished rather than as a
fixed test. `compose_filing_export_coverage` is still 73.4s and is now the
dominant term in the report; the same question that resolved the first phase -
whether it materialises isolated snapshots whose projections it discards - is
the first thing to ask of it. Until that lands, the honest statement is that the
test passes on this machine today.

### all-five-classification-failures-are-refactor-collateral-and-four-need-an-owner-not-an-edit | high | The gates are working; they are reporting that adjudication ledgers were not carried through a rename

The five remaining classification failures in the lane were attributed. None is a
defect in the classification tooling's logic and none is a stale assertion. In
every case the gate is doing its job and reporting that the in-flight refactor
moved modules while the adjudication ledgers stayed behind.

One was mechanical and is fixed. The private-to-public promotion renamed 44
application modules, and the branch ledger keys on `path::symbol::modelos`, so
every key went stale on its path segment alone. A strict bijection was proved
before rewriting - each stale key maps to exactly one unclassified key by
dropping the leading underscore, all 44 new files exist and no old file survives
- and 82 other keys naming modules that are still private were correctly left
alone, so this was a per-key mapping rather than a blanket strip. That gate now
passes; the lane's classification failures fall from five to four, verified
independently at 4 failed / 21 passed.

The other four were deliberately not fixed, and the reasoning is the valuable
part. Closing them means *authoring* adjudications, not repairing keys: seven
modules split out of two parents need a machinery-versus-regulatory-embed ruling
each, and one of them carries a live regulatory prose literal whose
classification is a filing-grade judgement that has to be grounded in AEAT
authority. Twenty-one newly reachable modules need a trigger naming a concrete
surface, and that file's own gate exists to refuse a trigger that names none.
Writing plausible justifications for either would satisfy the gate and destroy
its meaning, which is the precise failure these gates were built to prevent.

A fourth is a real question rather than a defect: `ledger_bindings.py` was split
and every consumer repointed at the children, so the parent is now unreferenced.
The gate is asking whether it is genuinely dead, and the answer decides whether
it should be deleted rather than classified.

### the-static-load-closure-conflates-reachability-with-what-a-load-imports | medium | A function-scoped import is a graph edge but not a load-time import

The closure gate compares the statically derived import closure against what a
real load actually imports, and fails for eight registry modules. The chain was
traced to its last surviving link: a function-local deferred import inside
`validate_m303_regimen_simplificado_annual_summary_revision`, sitting after an
early return. At runtime the two enclosing modules are in `sys.modules` after a
load while the imported one is not.

The underlying weakness is in the instrument, not the assertion. The graph tool
records function-scoped imports as ordinary edges, so the derived closure means
"reachable if every function ran" while the comparison treats it as "imported
when a load runs". Those are different claims and the gate is the place the
difference surfaces.

The assertion should not be relaxed to accommodate this - it is the gate
confronting the graph with reality, which is exactly its purpose. The two honest
remedies are hoisting that import to module scope if no cycle forbids it, or
teaching the closure to exclude function-scoped edges and say so. Both sit
outside this campaign's ownership and are recorded rather than taken.

### what-this-product-can-actually-file-is-now-stated-and-the-answer-is-small | critical | Sixty-eight revisions claim filing grade; fifty-two of them cannot be presented

The first question anyone asks of this registry is which modelos the product can
calculate and file. Until now that answer had to be reconstructed from grades,
layout counts and directory listings, which is why it kept being answered
differently. It is declared data and was simply never assembled.

Assembled, over 58 modelos and 128 revisions:

- 22 modelos declare `applicability` only - the censal and informational ones,
  including 036 and 038, whose alta, modificacion and baja are filed on AEAT's
  sede and produce no fichero here. That is the correct and complete state for
  such a modelo, and the screen reports nothing for it.
- 5 modelos declare `calculation` only: 117, 126, 128, 136 and 200. Modelo 200's
  grade is not an anomaly needing investigation; it sits with four siblings.
- 68 revisions reach filing grade with a layout to render from.
- **52 of those 68 declare no filing envelope.** They can render bytes and have
  nothing to present them in.
- 25 revisions carry an export layout while declaring a grade below filing,
  including modelo 222, which ships a committed generated export tree at
  applicability grade.
- Modelo 100, the IRPF declaration, declares filing grade across six revisions
  with six layouts, no envelope on any of them and no committed tree.

So the honest headline is that filing capability is declared far more widely than
it is built. Sixteen revisions carry a complete filing chain; the rest claim a
rung and stop somewhere short of it.

None of the three reported conditions is automatically a defect, and the screen
is deliberately built so that a modelo which is genuinely not filed here produces
no row at all - that case is proven by a test over modelo 036 rather than
asserted. What the screen refuses to allow is a filing claim and the machinery
behind it drifting apart in silence, which is the same failure the
under-declaration rule names.

The distinction is recorded as a screen rather than as prose in a README for the
reason every other census here is: a maintained list of which modelos are real
filings would be wrong within a release, while a derivation from the declarations
cannot be. The three conditions it reports are now plan steps.

### the-shipped-code-boundary-check-misses-step-identifiers-and-declarations-carried-them | high | It reported the registry clean while filing-grade declarations cited a plan step

The code-boundary rule was checked earlier with the shipped
`vaultspec-core vault check code-boundary`, five registry violations were
cleared, and the registry was recorded clean. It was not. Two modelo 200
revision declarations - shipped, filing-relevant, read as tax-domain evidence -
each carried the sentence "until the canonical generator publishes the exact
20xx design under downstream step W04.P08.S22", and a third citation sat in a
development channel declaration.

The check did not miss them by accident of scope. It matches vault document
*stems* - the dated `yyyy-mm-dd-feature-type` form - and a plan step identifier
is not one. So the class of citation most likely to be written casually mid-work,
and least likely to look like a reference at all, is precisely the class the
check cannot see. Running it and reading "clean" was therefore evidence about
stems, not about the rule.

A declaration is the worst place for such a citation. It ships in the wheel, it
is read as evidence about Spanish tax law, and it names development scaffolding
the product is supposed to be removable from.

All three citations are removed and the condition is now gated in this
repository rather than delegated to the installed check. The gate matches four
kinds - wave-phase-step and phase-step identifiers, dated document stems, and
literal vault paths - across the registry development tree and the shipped
registry declarations, and it scans over a thousand files.

Two details of its construction are worth keeping, because both were found by
the gate failing rather than by design. The phase-step pattern first matched
inside the wave-phase-step form, so one citation reported as two; it is now
anchored to reject that. And the gate reported *itself*, because its paired
detector must contain an example of each kind to prove the patterns fire -
the module excludes its own path, with the reason stated in the code, since
removing the examples would leave the patterns unproven and scanning them makes
the gate self-accusing.

The detector proves the negative half too: a revision directory name like
`2025-y-siguientes`, a casilla identifier like `DP200014:01033`, an Orden
citation and a `2024-2025` span must all NOT match. A detector that fired on
ordinary registry vocabulary would be unusable, and a clean corpus would never
reveal it.

### the-three-grade-withdrawals-were-deliberate-correct-and-evidenced | high | The accident was the filing claim, not its removal

The twenty-four filing tests demanding filing grade from modelos 200, 038 and
036 were investigated against the commit history. All three withdrawals are
deliberate and correct, and no filing-correctness regression exists.

Modelo 200's demotion to `calculation` carries its rationale in the declaration
itself: the revision spanned two incompatible AEAT layouts, so filing refuses
until layout-correct revisions exist. Filing capability had already been
withdrawn separately and atomically - 149 export fragments deleted in one commit
that simultaneously recorded the removal decision, reasoning that retaining a
partial layout "would permit silent under-declaration". Today both revisions
declare no export layouts at all, so filing grade would be a false claim.

Modelo 038 is the sharpest case, because there the *filing* grade was the
accident. A bulk edit inserted `authority_grade = "filing"` into 97 revision
files under an unrelated subject, contradicting the human-written applicability
prose two lines above it in twenty-five of them. The correction four days later
was a demotion plus a transcription that added no claim. Restoring filing here
would re-introduce the original defect.

Modelo 036 is read through censo synchronisation rather than produced, and
production code already names it as the motivating case for the below-filing
boundary.

What was actually missed is atomicity: three commits changed a grade without
moving the consumers asserting it, which is the architecture rule's atomic-change
requirement applied to grades rather than identifiers. The twenty-four failures
are that debt. Eight were never about modelo 200 at all and merely used it as a
convenient filing fixture; fourteen assert a decimal-slot contract that is
modelo-agnostic and whose stated premise is false today independently of the
grade; two are not grade failures at all but stale expectations of a refusal
shape that production deliberately made richer.

### the-envelope-finding-was-mostly-noise-and-the-real-defect-was-hiding-inside-it | critical | Fifty-two reported, thirty-one real, and the real ones lose the mandatory developer identity

The capability screen's first envelope condition reported 52 filing-grade
revisions carrying no filing envelope. Grounded against the bundled official
record designs, most of that was the screen's error rather than the registry's,
and the correction is recorded in full because the corrected finding is worse
than the original.

Three things were wrong with it. The envelope is not universally required: a
design that declares no variable composition is complete as records alone, and
ten hand-authored and seven pipeline-derived revisions were correctly envelope
free, confirmed against their designs. There is a second legal spelling,
`auxiliary_envelope_header`, the total-less page-zero header, which the counter
ignored. And an XML-dictionary layout may never carry an envelope at all - the
schema refuses it - which alone accounted for modelo 100's six revisions.

What was left after removing the noise is a genuine defect the count had buried.
**Thirty-one revisions carry their envelope smuggled into the record tuple as an
`envelope_header` pseudo-record instead of the typed slot**, twenty of them at
filing grade. The bytes can look right while the envelope is invisible to every
consumer that asks the layout whether it has one - including the export
boundary, which branches on exactly that question, takes the plain-records path,
and then *refuses* the product and software identity an enveloped filing must
carry.

Modelo 714 shows what the spelling costs. Its envelope record declares filler
across most of the 328-byte prefix, and offsets 93-96 and 101-109 - the
Version del Programa and NIF Empresa Desarrollo the design marks mandatory - are
covered by **no field at all**. A typed envelope would have compelled them.

Modelo 322 proves it is a regression rather than unfinished work: three of its
revisions are pipeline-generated with typed envelopes, and the newest,
filing-grade revision lost it to the record spelling.

The condition was replaced rather than tuned. A screen whose signal is a third of
its rows teaches its reader to skim, which is the failure mode this campaign has
already recorded for frozen counts. It now fires regardless of declared grade,
because the defect does not become real when a grade is raised - it is inherited.

Two further cases need a decision rather than an edit. Modelo 100 declares filing
grade for an XML layout that will refuse at render for want of a grounded
aux-version token, so the value is honestly absent while the grade overstates the
outcome; the token must not be invented. Modelo 222 declares applicability while
shipping a generated tree with a typed envelope, and its own rationale comment -
that nobody has mapped its box numbers - was made false by the same commit that
installed the mapping.

### two-revisions-ship-filing-bytes-while-declaring-they-cannot-file | high | And the honest response was a structural gate, not a prose correction

Modelo 222 declares applicability grade while shipping a committed generated
export tree whose layout carries a typed filing envelope. Modelo 185 does the
same without the envelope. Two of the twenty-seven revisions that ship trees are
in this state: the product ships the bytes of a filing for a revision whose own
declaration says it cannot file.

Modelo 222's declaration also contains two statements that are now false. A file
comment says the money-closure casillas remain deferred because "nobody has yet
mapped its box numbers", and a reviewer attestation says the revision "declares 2
casillas" and that "no export layout of either kind is declared". The revision
carries seventy-six casillas and one export layout, and the mapping was authored
by the same commit that installed the tree.

Neither was corrected, and the reasoning matters more than the finding. The
attestation is a person's signed statement bounded in time - it ends "This review
reaches scheduling and applicability only" - and rewriting it to match the
current data would forge a review that never happened. The staleness IS the
evidence: the declaration was materially enlarged after a review that explicitly
limited its own scope, and nobody re-reviewed it. Editing the prose would destroy
the only trace of that.

So the condition is reported structurally instead, comparing the shipped tree
against the declared grade - two facts, neither of them prose. That gate fires on
both revisions today and is proven not to fire on modelo 303, which ships trees
across six filing-grade revisions and is the intended state. A screen that
flagged those would be reporting the product working correctly, and its reader
would learn to ignore the kind.

The remedy is a re-review of modelo 222 against what it now declares, not a
grade edit made on the strength of a tree being present.

### the-contract-can-say-a-family-is-inapplicable-but-not-that-a-capability-is-withheld | high | Twenty-five revisions carry filing machinery below filing grade and none can say why in typed data

Twenty-five revisions declare an export layout while sitting below filing grade.
Grounded against the registry, they are not one condition. Three are correct by
law - modelos 117, 126 and 128 each state that the liable filer is a third party,
so the product's user never files them. Eighteen are deliberate conservatism,
and one of them states the doctrine plainly: a layout "proves byte geometry only;
it does not promote the revision to filing grade... promoting it is an operator
decision, and it is not made here on the strength of the layout". One is stale.
Three - modelos 189, 280 and 345 - carry no rationale of any kind, which is
indistinguishable from oversight.

The obvious hardening was to require the reason as typed data, and the registry
appeared to have the mechanism: revisions carry `family_dispositions`, a mapping
from schema family to a declaration with a reason, already used for four
families. Zero of the twenty-five use it for the export family.

They cannot. The validator refuses a disposition against a family that HOLDS
content, on the ground that claiming the law does not require what the revision
already declares is a contradiction the coverage projection would have to
arbitrate. That reasoning is right, and it means the mechanism expresses "this
family is not applicable here" and cannot express "this family is present and its
promotion is deliberately withheld". They are different statements and only the
first is typed.

A sweep of every field a revision carries confirms no other slot holds it. The
grade states the rung reached; the review fields state who looked and when;
nothing states why a revision holding filing machinery stays below filing. So the
eighteen documented deferrals are documented only in comments - unqueryable,
unenforceable, and invisible to every gate - and the three undocumented ones
cannot be told apart from an accident.

This was very nearly implemented as a gate requiring the typed disposition, which
the schema would have refused for exactly the reason above. Reading the validator
before writing the gate is the only thing that prevented shipping an invalid
contract. It is recorded as a decision for the declaration-contract phase rather
than an invented field, because the choice between a new typed slot and widening
the existing disposition semantics is a contract decision with consequences for
the coverage projection.

### ninety-nine-percent-of-each-isolating-copy-is-data-the-caller-never-reads | high | Which makes the safe remedy cheaper than the one that needed a guard relaxed

The conformance audit's remaining cost is one call site: 884 of its 952 snapshots
come from the model-law coverage loop, and unlike the sites fixed so far this one
genuinely READS its projection - the ledger consumes the snapshot's legal refs,
sources, workbook parity refs, live cross references and coordinate. So the
remedy applied twice already, discarding a copy nobody reads, does not apply
here.

Two remedies were then available and they are not equally safe.

The first is coordinate reuse. Every one of those 884 snapshots is built for a
distinct filing coordinate of an ALREADY-PINNED revision, and the resulting
ledgers were shown to be coordinate-invariant: grouping all 1,729 ledgers by
modelo and revision and comparing them with only the two coordinate fields
removed gives 95 of 95 multi-coordinate groups byte-identical. So one snapshot
per revision would serve. But the ledger builder refuses a coordinate that
disagrees with its snapshot, and that guard is what makes a mismatched pairing
impossible. Reusing one snapshot across coordinates means relaxing it, which
trades a real safety property for speed on a filing-adjacent path.

The second remedy came from asking what the copy actually costs. Against modelo
390: a full snapshot deep copy is 127.5 ms, its revision alone 25.3 ms, and the
four collections the ledger genuinely reads **1.4 ms**. The revision carries 393
casillas; the ledger reads none of them. So roughly ninety-nine percent of every
one of those 884 copies is data the caller never touches, and the isolation the
copy provides is being bought for the whole projection when it is needed for a
hundredth of it.

That makes the safer remedy also the cheaper one: isolate the facts a coverage
ledger reads rather than the snapshot that contains them. Every coordinate keeps
its own isolated data and its own coordinate, the guard stays exactly as it is,
and no contract moves. The arithmetic is 884 x 127.5 ms against 884 x 1.4 ms.

The measurement is recorded before the change because it inverts which remedy is
obvious. The coordinate-invariance proof is genuinely strong evidence and it
pointed at the more dangerous fix; the cost breakdown took one command and made
it unnecessary.

### the-conformance-audit-is-six-times-faster-and-every-ledger-is-byte-identical | high | 133.9s to 22.1s, without relaxing the guard that made the fast path look dangerous

The isolating copy now covers what a coverage ledger reads rather than the
projection that contains it. A new authority accessor returns the coordinate and
the four evidence collections, each deep-copied, and the ledger builder accepts
that projection alongside the two it already took.

The results, each measured rather than projected:

- one call: **126.4 ms to 0.2 ms**.
- the model-law coverage audit: **48.3s to 5.8s** over its 884 coordinates.
- the whole conformance audit: **133.9s to 22.1s**, having been 66.3s after the
  first fix in this chain.
- the registry closure report earlier in this campaign: 210.8s to 15.0s.

Equivalence was proved on the audit's own coordinates rather than on a
reconstruction of them. A first attempt derived the coordinate list from the
period selector, matched nothing, and compared zero ledgers - a proof that would
have read as a pass. Capturing what the audit actually requests gives 884
coordinates, and building every ledger through both the old and the new path
yields **884 identical, 0 differing** by full JSON comparison.

The isolation guarantee is unchanged and that is the point of the shape. Every
collection is still copied, so no caller can reach cached registry state; each
coordinate still gets its own facts rather than sharing one revision's copy; and
the builder still refuses a coordinate that disagrees with the data beside it.
The alternative remedy - one snapshot per revision, reused across coordinates -
would have required relaxing exactly that refusal.

Two tests in the owning suite fail, and both were shown pre-existing rather than
argued to be. Each was A/B tested by restoring the original call, re-running, and
putting the change back: `test_committed_registry_tree_has_required_model_law_coverage`
and `test_every_modelo_resolves_exactly_one_revision_for_every_filing_year_through_today`
fail identically with the original accessor. The first reports executable parity
evidence gaps on modelos 714 and others, which is registry evidence debt this
change neither creates nor repairs.

### the-new-projection-is-gated-on-its-contract-and-not-on-its-speed | medium | The isolation it gives up the snapshot's copy for is proven by breaking it

The coverage-facts projection was landed on a performance argument, which is
precisely why its tests assert none of it. Cheapness is not the contract. The
contract is that it answers identically, refuses identically, and isolates what
it hands out, and if any of those breaks the speed is worthless.

Four gates cover it. It carries the same coordinate and all four evidence
collections a snapshot does, across three unlike modelos. A ledger built from
either projection is byte-identical - the substitution the coverage audit
performs 884 times, so a divergence would silently alter published coverage
findings rather than fail loudly. A grade the registry will not admit is refused
with the identical message, because an accessor that skipped the copy and also
skipped a refusal would hand out facts for a coordinate the boundary never
admitted.

The fourth is the safety argument itself, and it is proven by breaking it rather
than by inspection: a caller deletes an entry from the mapping it was given, and
the next caller must still see that entry. Asserting that a deepcopy call appears
in the source proves the code was written; deleting from what came back proves it
works. Run against the live authority, the deletion leaves both the next caller's
facts and the cached snapshot intact.

One of these tests was initially written with a line that was not valid Python
and a mutation that would have proven nothing even if it had parsed. It was
rewritten rather than deleted, because the property it was reaching for is the
only reason skipping the snapshot's copy is defensible.

### the-provenance-screen-reported-thirty-one-thousand-rows-for-three-hundred-and-fourteen-references | medium | Nineteen citation sites per thing to fix, and the same lesson as the envelope count

Running the whole screen suite gives 35,287 findings, of which one screen
contributes 31,589. A five-figure count from a screen whose siblings report tens
is a claim about the screen, not the corpus, and this one proved to be exactly
the failure already recorded for the envelope condition one iteration earlier.

The measurement is right and the report was wrong. The screen finds each child
whose citations reach outside its revision manifest, which is the correct unit to
measure. It then printed one row per child, so a single reference missing from a
manifest appears once for every casilla, formula and binding that cites it. The
31,589 rows collapse to **1,389 outside references across modelo, revision and
reference kind, and 314 distinct references overall** - roughly nineteen sites per
thing anyone would actually fix.

The output now names the reference and carries the number of children citing it,
which is not a smaller report but a differently-keyed one: the reference is the
unit someone acts on, and the citing count is how much of the revision depends on
that single fix. The census line keeps all three numbers, so nothing was lost to
make the report shorter.

One self-correction. An ad-hoc measurement taken while investigating put the
collapse at 1,669 and 519. Those figures keyed on the whole reference tuple a
finding carries rather than on each reference inside it, so they counted distinct
*combinations* rather than distinct references. The screen's own decomposition -
1,389 and 314 - is the correct one, and the earlier pair should not be quoted.

### the-lane-is-fifteen-failures-and-runs-in-a-third-of-the-time | high | Eighteen to fifteen, and fifteen minutes to six and a half

A full-scope run over both directories now gives **15 failed, 848 passed in
6m26s**, against 18 failed / 833 passed in 15m04s when the scope was first
measured correctly. Exit status read from pytest itself.

Three failures are genuinely gone rather than reclassified: the branch
classification gate, once its forty-four ledger keys were re-pointed at the
renamed modules; the conformance CLI test, which was failing on a three hundred
second timeout that the closure report's cost caused; and one of the two closure
outcome tests, whose mutation payload had gone stale against computed fields the
temporal-coverage model added.

The runtime is the more useful number. A suite that took a quarter of an hour was
run rarely and, as this campaign found, was silently excluded from every earlier
measurement because it exceeded a foreground timeout. At six and a half minutes
it is a suite a contributor will actually run, which is worth more than the three
failures.

### the-twenty-four-grade-stale-filing-tests-are-re-sited-and-one-was-doubly-stale | high | No grade restored, and the invariants moved rather than being lowered

All twenty-four tests demanding filing grade from modelos 200, 038 and 036 now
pass, with no grade restored and no test deleted, skipped or weakened. Verified
independently at 24 passed and 47 passed across the affected files.

The eight convenience-fixture tests moved to modelos that still file, chosen by
asking the registry which ones do. The fourteen decimal-slot tests were
re-grounded on a modelo 303 page whose scales genuinely vary, which makes
"scale is per-field" demonstrable rather than asserted, and every modelo 200
diseño quotation was replaced by that page's own transcribed geometry rather than
carried across - a quotation that no longer describes the modelo it sits under
has stopped being evidence.

One test was worse than grade-stale. Its ambiguity assertion used a `match=`
pattern that could never have matched, because the error's string form is only a
message key; it had been passing on the exception type alone for however long. It
was rewritten to prove the ambiguity structurally - the typed context offers back
more than one candidate, which is what separates it from the single-candidate
case - rather than restored to a comparison that never worked.

The honest replacement for what the fourteen used to prove now lives in the
modelo 200 suite: that it declares no export layouts, sits at calculation grade,
still computes, and refuses a filing snapshot naming both grades. Both halves
together, so a future promotion turns it red rather than passing quietly.

### the-suite-census-counted-sites-and-the-work-it-implied-was-two-orders-of-magnitude-too-large | high | Thirty-five thousand findings became one thousand seven hundred, and one step shrank from 3,349 items to 27

Having found the provenance screen reporting citation sites where it should
report references, the same question was asked of every screen rather than
waiting to meet the third instance. The runner's census - the one command a
maintainer runs to ask what state the declarations are in - totalled 35,287
findings. It now totals 1,765, and nothing was measured differently: only the
unit counted changed.

Two screens dominated it and both were counting sites.

The wire-type screen reported 3,349 divergent casillas. Those resolve to **27
distinct declared-to-wire transitions**, dominated by money to decimal (2,140)
and ratio to decimal (619). The screen's own output already reported per
transition; it was the runner that counted casillas, which matters because the
runner is the surface read first. The consequence is not cosmetic: the plan step
that settles this declares permitted transitions as registry data, so its real
size is twenty-seven declarations, not 3,349 adjudications. The step said 3,349
until this measurement, which would have made it look like a campaign rather than
an afternoon.

The provenance screen contributed 31,589, resolving to 1,389 outside references
and 314 distinct ones.

A generic proxy was tried first and discarded, which is worth recording because
it read as reassuring. Comparing row counts against distinct detail strings gives
provenance a ratio of 1.0 - apparently no duplication at all - because each
detail embeds the child that cites the reference. A screen-shaped question
("what would someone act on") found the collapse the generic one hid. There is
no mechanical test for this; each screen has to be asked what its unit is.

The raw per-site counts are not lost. Each screen still measures per site and
still prints those counts beside the unit, because how many casillas depend on a
single missing reference is exactly what tells someone whether to fix it first.

### the-census-counted-a-shape-the-screen-says-is-not-wrong | medium | A hundred and thirty-two of a hundred and fifty-eight, and the screen said so in its own docstring

The monetary screen reports 158 findings and the audit records 24 unscaled
fields. Both are right, which is the problem. The 158 is four conditions summed:
132 part splits, 24 fields without a scale, one unusual scale and one field
disagreeing with its siblings.

The 132 are not defects, and the screen says so in the docstring beside the
condition: a monetary casilla carried by several fields of one record is the
official integer-and-decimal part split, "reported so the shape is visible and
countable, not because it is wrong". The census counted them as findings anyway,
so the first number a maintainer reads overstated the work six-fold - and it
overstated it with rows that a reader who investigated would find are correct,
which is the fastest way to teach someone that this screen's number means
nothing.

The census now counts the twenty-six findings that need a decision. The screen is
unchanged and still reports all four conditions, because the part split is worth
seeing; it is the *census* that had no business calling it a finding. This is the
same filter already applied to identity type transitions and non-mixing modelos,
so the runner had the precedent and this condition had simply never been held to
it.

With that, the suite census is 1,633 where it began at 35,287.

The remaining six screens were then checked the same way rather than assumed
correct, and none needs the treatment: identifier grammar counts mixing modelos,
name-window counts revision names, temporal agreement and grade-earned count
revisions, continuity counts modelos and chains. Each already counts the thing
someone would act on.

One condition is deliberately left overstated, and it is worth naming so nobody
"fixes" it. The capability screen reports 25 revisions carrying a layout below
filing grade, of which three are correct by law and eighteen are documented
deferrals. Those twenty-one are not structurally distinguishable from the rest,
because the deferral lives in a comment and the contract has no typed slot for
it. Filtering them would mean matching prose. The census stays honest and
overstated until that slot exists, which is the declaration-contract decision
recorded above.

### five-revisions-claim-they-can-be-filed-and-cannot-say-by-when | high | A filer asks two questions and these answer one

Twenty-seven revisions declare no deadline window. Twenty-two of them sit below
filing grade, where saying nothing about a due date is the correct and complete
answer - a modelo filed on AEAT's sede, or one this product does not file, has no
deadline of its own to declare.

The other five reach filing grade with an export layout: modelos 145, 151, 165,
308 and 309. They can render a fichero and cannot say when it must be presented.
A filer asks two things of a modelo - what to send and by when - and these answer
only the first, which makes the filing claim incomplete in a way no export test
would catch, because the bytes are fine.

This bears directly on the question that opened this campaign: what the product
supports and for what time range. Part of the answer turns out to be that for
five filing-grade revisions the second half of the question has no declared
answer at all.

The distinction is structural rather than a reading of prose - filing grade plus
a layout, against a deadline count of zero - so unlike the deferral cases
recorded above it can be reported honestly without prose matching. It is gated in
both directions: modelo 151's earlier revision is caught, and modelo 036 is proven
not to be, because demanding a deadline from a censal modelo that has none is how
a screen earns being ignored.

### fourteen-filing-revisions-carry-no-formula-and-ten-of-them-are-right-to | high | The distinction that separates them is declared, so the finding is four

Fourteen of the sixty-eight filing-grade revisions with an export layout declare
no formula at all. Reported as fourteen, that would have been the envelope error
for a third time: most of them are correct.

A declaracion informativa transmits data and computes no liability, so having no
formula is its complete state, not a gap. Modelos 347, 184, 720, 165 and others
are exactly that. What makes this checkable rather than a matter of opinion is
that the registry already declares it - each modelo carries a
`calculation_class`, and ten of the fourteen declare themselves informative.

The remaining four declare `calculation_class = filing` and still carry no
formula: modelos 296, 308, 349 and 360. Each claims to compute what its filing
reports, and nothing computes it.

The condition reads the modelo's own declared class rather than counting formulas
alone, so an informative modelo is never asked for arithmetic it has no reason to
do. Both directions are gated: modelo 349 is caught, and 347, 184 and 720 are
proven not to be.

Worth recording separately: two of the fourteen - modelos 145 and 232 - carry a
tax domain of IRPF and Sociedades while declaring an informative calculation
class. That pairing is not a contradiction, because a modelo can belong to a tax
and still only report, but it is the reason the condition keys on calculation
class rather than tax domain. Keying on the domain would have flagged both as
defects.

### naming-every-kind-was-not-enough-because-the-count-above-them-can-still-lie | medium | Two stale counts, one introduced by the edit that fixed the names

An earlier gate here requires every kind a screen emits to be named in its own
docstring, and two screens satisfied it while still opening with a count from an
earlier version of themselves. The monetary screen said "Three conditions are
reported" above four documented bullets, and the capability screen said three
above six.

The monetary one is the instructive case: that sentence went stale in the very
edit that fixed the names. A fourth bullet was appended for the condition that
surfaces the corpus's only known filing-correctness defect, and the sentence two
lines above it was left saying three. The gate written to stop names drifting had
no opinion about the number introducing them.

A wrong count is worse than a missing name. It tells the reader the list is
complete, so the condition they never find is the one they conclude does not
exist.

Both counts are corrected and the claim is now gated: a docstring stating "N
conditions are reported" must match the bullets it introduces and must not
understate the kinds the screen emits live.

The gate found two further errors immediately, both in this work rather than in
the corpus, which is the useful part. Its first version counted every
backtick-bulleted line and failed on a docstring whose number was right, because
several screens also bullet the FACTS they read in the same form; the count is
now scoped to bullets following the claim. Then it rejected the correction
itself: the capability screen was set to five, counting the kinds observed live,
when six are documented - one occurs only under a constructed defect and is
covered by the detector that constructs it. Six is the honest number, and the
distinction between documented and live conditions is exactly what the gate
checks in the two directions it checks it.

### four-filing-claims-fail-more-than-one-capability-axis-and-one-fails-three | critical | The same revisions keep appearing, which is the answer to which claims to distrust

The capability conditions were built one axis at a time - grade, layout,
envelope, deadline, calculation - and the same modelos kept recurring across
them. Crossed against each other, four filing-grade revisions fail more than one
axis:

- **308/2019-y-siguientes fails three.** It declares a filing calculation class
  with no formula, declares no deadline window, and its declared grade exceeds
  what its prerequisites support.
- **145/2012-01-31-y-siguientes** and **165/2016-2022** each fail two: no
  deadline, and a grade the prerequisites do not support.
- **360/2010-y-siguientes** fails two: a filing calculation class with no
  formula, and a grade the prerequisites do not support.

A separate reading of the grade screen makes the pattern sharper. All five
revisions whose declared grade exceeds their prerequisites fail on the same
missing prerequisite - a completeness manifest - and four of those five are in
the list above. So this is not five unrelated shortfalls; it is one class of
unfinished revision that also happens to be missing the other things a filing
needs.

That is the useful output of building the axes separately. Any one condition
reads as a small gap: a missing deadline, an absent formula, a grade a shade too
high. Together they identify the revisions whose filing claim rests on the least,
and they are the ones to distrust first. Sixty-eight revisions claim filing
grade; these four are the ones where several independent checks agree the claim
is thin.

The cross-axis reading is recorded rather than gated. Each axis is already gated
on its own, and a gate that fired on "fails at least two of these" would add no
detection - it would only re-report what the individual conditions already say,
while inventing a severity ordering the registry does not declare.

### two-feature-documents-fail-their-own-attested-body-schema | low | Not this work's documents, so reported rather than filled in

Validating this feature's documents surfaces two structural failures that are not
in this audit or its plan. A modelo 353 audit from 26 August is missing the
`## Scope` section its attested body schema requires, and a registry temporal
coverage reference from 31 August is missing `## Summary`.

Both predate this work, both were last written by other commits, and neither
carries a pending diff. The obvious move is to add the sections, and it is the
wrong one: a required section is not a formatting slot, it is a claim about the
document - what its author was looking at, what they concluded. Filling in a
Scope for someone else's audit would put words in a record that reads as their
assessment.

This is the same reasoning that left the modelo 222 reviewer attestation
uncorrected. A vault document is a person's account of what they examined, and a
missing section is evidence that the account is incomplete rather than a defect
in the file's shape.

### the-file-blocking-the-filing-defect-is-free-and-the-work-is-still-not-unblocked | high | 183 fields measured exactly, 149 of them due immediately

The eligibility predicate that causes this campaign's only known
filing-correctness defect sits in a file another contributor was holding. That
file now carries no pending diff, which was checked rather than assumed. It does
not follow that the Step is unblocked, and the measurement says why.

The defect is precise. For a workbook design, a non-blank Contenido cell means the
design stated the field's wire fact, so no reviewed rule is needed. The
instruction-only vocabulary that overrides this holds exactly one phrase. Modelo
353's field carries `Nota 4.` - a bare footnote pointer, which states nothing at
all - so it is read as a statement, never receives a reviewed rule, and renders
unscaled beside siblings that emit cents.

Across 107 designs and 66,522 workbook fields, **331 carry a bare footnote
pointer as their entire Contenido**, spread over ten modelos and dominated by
`Nota 1` (195) and `Nota 2` (105). Of those, **exactly 183 would become newly
eligible** once the other eligibility conditions are applied - independently
reproducing the figure the plan carried, and now resolved per modelo: 390 has 80,
200 has 60, 220 has 27, 131 has 7, 303 has 6, and modelos 202, 222 and 353 have
one each. The modelo 353 field is the defect.

The coverage gate demands exact coverage of the eligible set in both directions,
so every newly eligible field needs a reviewed representation rule authored in
the same change. Six of the eight modelos already carry a render profile and are
therefore held to that gate immediately: **149 rules fall due with the
correction**, and the remaining 34 only when modelos 220 and 131 gain profiles.

So the honest position is that a one-line predicate correction carries 149
grounded authoring decisions with it, each needing the official design's own
statement for that field. Landing the predicate alone would break six modelos'
coverage; landing it with invented rules would be worse, because a reviewed rule
is an assertion about what AEAT requires. The blocker moved from a held file to
authoring capacity, which is a better place for it to be and not the same thing
as progress.

### the-note-behind-the-filing-defect-says-nothing-about-the-wire-and-now-says-so-in-quotation | high | The design's own words, not a characterisation of them

The field that renders unscaled in modelo 353 carries `Nota 4.` in the cell where
the design states a wire fact. What that pointer points at, quoted from the
design's own transcription:

> Nota 4: Solo para periodos 02 y siguientes.

It is an applicability statement. It carries no scale, no decimal count, no sign
convention. So the fact really is unstated and the field really should be under
reviewed authority - which until now was an inference from the field's behaviour
and is now a quotation from the source.

Resolving the pointer is also the tool the 149 due rules need. An author writing
them has to know what each pointer names, because the answer decides the rule:
this design's Nota 1 gives the numeric conventions in full - alignment, zero
fill, the sign character - and constrains any rule written against a field
pointing at it, while Nota 2 is about declaration type and Nota 4 about periods,
neither bearing on the wire at all. A pointer cell naming two notes resolves each
separately, because one may constrain and the other may not.

The resolver authors nothing and decides nothing; it puts the design's wording in
front of whoever writes the rule. Two deliberate refusals in it are worth
recording. A pointer the design does not define comes back unresolved rather than
omitted, because an author who sees nothing cannot tell a note that says little
from a note that was not found. And a cell that says more than a pointer -
"Importe con 2 decimales. Nota 1" - is not treated as a pointer at all, since
widening the correction to swallow real design statements would be the opposite
failure and the worse one; that is asserted in both directions rather than left
to the regex's shape.

One implementation detail was corrected on inspection rather than shipped: the
extracted text was being read with decode errors silenced. The corpus files are
valid UTF-8 and the mangled Spanish first seen was the terminal rather than the
read, but a silenced decode error would drop accented characters from note text
an author is about to rely on. It now reads strictly, so a genuinely bad file
fails instead of quietly losing a word.

### the-one-hundred-and-eighty-three-due-rules-are-triaged-and-one-hundred-and-seventy-five-are-unconstrained | high | Only six point at a note that says anything about the wire

Resolving every newly eligible field's pointer against the design that names it
triages the authoring work the eligibility correction makes due:

- **175 point at a note that says nothing about the wire.** The note is about
  periods, declaration types, complementary pages - real content, none of it
  scale, sign or decimals. For these the reviewed rule is genuinely needed and
  the note constrains it not at all.
- **6 point at a note that does bear on the wire**, all in modelo 131. Those
  rules are not free authoring: they must agree with what the note already says,
  and the design keeps its veto.
- **2 remain unresolved**, where the design defines no note of that number.

A correction to this measurement is worth recording because the first version
reported eight unresolved rather than two, and the difference was entirely mine.
The transcription was located by globbing the design directory and taking the
first file, which is wrong wherever a modelo bundles several designs - modelo 303
bundles fifteen. Deriving the transcription from the source reference's own
corpus path, which names the exact file, drops the unresolved count from eight to
two and moves six fields into the silent-on-wire group. A measurement that picks
an arbitrary member of a set will usually still produce a plausible number.

### thirteen-bundled-record-designs-have-no-transcription | medium | Evidence tooling is blind to them, and three belong to a modelo already failing three capability axes

The same sweep found that thirteen bundled record designs across eight modelos -
126, 128, 165, 194, 270, 308, 309 and 341 - ship the original workbook or PDF
with no extracted text beside it. Modelo 308 is the clearest case: four designs
bundled, one transcribed.

The parser reads the workbook directly, so this does not break generation. What
it breaks is every tool that needs to QUOTE the design - the footnote resolver
above, any evidence check that compares a reviewed rule against the design's own
wording, and any reviewer who wants the source text without opening a spreadsheet.
For those designs the evidence is present in the repository and unreadable by
anything that reasons about text.

Three of the thirteen belong to modelo 308 and three to modelo 309, both of which
already appear among the revisions failing more than one capability axis. That is
not a coincidence worth theorising about, but it does mean the modelos whose
claims are thinnest are also the ones whose evidence is hardest to read.

### the-triage-is-now-repeatable-and-deliberately-stops-short-of-the-eligibility-predicate | medium | The mistake that produced a plausible wrong answer is now the thing the tool cannot make

The pointer triage existed as a script run twice, once wrongly. It is now an API
with tests, and two of its decisions are worth recording because both were forced
by earlier mistakes in this work.

A design's transcription is derived from the path the source reference names,
never by searching the design's directory. That is the bug from the first triage
pass elevated into a function: searching returns an arbitrary sibling, modelo 303
bundles fifteen designs, and resolving a note against the wrong year's design
still produces an answer. It is asserted in a test that quotes why - a wrong
answer that looks right is the failure mode, not a crash.

A design with no transcription returns nothing, and the docstring and test both
state that the caller must check: thirteen bundled designs ship without extracted
text, and an empty result is indistinguishable from a design that carries no
pointers. Returning empty is correct; returning empty silently would be the same
class of defect as the census counts corrected earlier.

The tool deliberately does not replicate the eligibility predicate. Doing so
would mean either duplicating it or importing a private helper across a package
boundary, which is the violation this campaign has already recorded as an open
contract question. It answers what it can answer publicly - what each pointer
cell names and what the design says behind it - and leaves eligibility to the
pipeline that owns it.

The wire-vocabulary flag is labelled a reading aid in the code, not a verdict. It
says which notes are worth opening first among many; a note mentioning decimals
still has to be read, and the rule's author decides. Calling it a verdict would
re-enact the mistake this campaign keeps finding: a heuristic presented as a
measurement.

### the-plan-was-held-to-the-gate-the-plan-added | low | Its own gate count was stale, and the first correction was wrong too

A gate landed here requiring a screen that states how many conditions it reports
to agree with what it documents and emits. The plan carries the same shape of
claim in its verification criteria - a criterion asserting that N gates cover the
screens - and it had gone stale the same way, still saying seven after an eighth
was added.

Correcting it produced a second error, which is why this is recorded rather than
fixed quietly. The count was raised to eight and the enumeration listed eight
clauses, but the module holds nine screen-integrity gates: the one requiring every
symbol the contributor READMEs name to still resolve was omitted, because it reads
as documentation hygiene rather than screen integrity. It is neither optional nor
separate - a screen documented with a symbol that no longer exists is not honestly
documented - so the criterion now says nine and names it.

The pattern is worth stating plainly because it has now happened four times in
this campaign: a count written beside a list goes stale when the list grows, and
the person adding the entry is the least likely to reread the sentence above it.
Three of those four were caught by a gate; this one was caught by holding the
plan to the gate the plan had just added, which is the only reason it was checked
at all.

### the-private-module-breach-is-fourteen-imports-not-one-hundred-and-eleven | medium | The split between tests and production changes what the remedy is

The naming rule says a leading-underscore module is private to its package and
not a cross-package API. Measured across the registry development tree, **111
imports reach 22 such modules from outside their package** - which reads as the
underscore naming having stopped describing reality entirely, and as a rename of
twenty-two modules.

Splitting them says otherwise. **97 of the 111 come from tests**, and a test
exercising a package's internals is inside that package's boundary in every sense
that matters: it ships with the code, changes with it, and is exactly where a
private module is legitimately probed. Treating those as a violation would push
the suite towards testing only public surfaces, which is a worse outcome than the
naming inconsistency.

**Fourteen come from non-test code**, and those are the breach. They concentrate
sharply: five in the filing-export proof module, seven across three analysis
modules, and `_paths`, which four separate consumers import - a CLI, two analysis
modules and another CLI. A module that four unrelated consumers reach for is not
private by any reading; it is shared infrastructure wearing an underscore.

So the decision shrinks from renaming twenty-two modules to promoting the few
that non-test code genuinely depends on, or routing those consumers through a
public surface. The step now says that, with the counts, because the version that
said "decide whether these are public or private" invited the twenty-two-module
answer and would have been a week of atomic renames for a naming rule that the
tests were never breaking.

### the-plan-cannot-be-gated-the-way-the-screens-are | low | And the rule that prevents it is one this campaign has been enforcing

Four stale counts have now been found in this campaign's own prose, and the
natural next move - a gate over the plan's counts, matching the one over the
screens' - is not available. A test lives in `dev/`; the plan lives in `.vault/`;
and the code-stands-alone mandate forbids source from referencing the project's
own development records. A gate that opened the plan to check a number would be
the precise violation this campaign cleared five instances of, including two in
shipped filing declarations.

The rule is right and the consequence is real: vault prose is checked by the
person writing it or not at all. That is worth stating rather than working
around, because the workaround would look like diligence and would reintroduce
the coupling the mandate exists to prevent. If this class of drift is worth
mechanising, it belongs in the vault tooling, which is already permitted to read
vault documents - not in a repository test reaching sideways into `.vault/`.

### an-entire-module-was-left-behind-by-its-own-split-and-duplicated-fifty-nine-definitions | critical | Two thousand one hundred and thirty-nine lines, zero importers

Searching the codebase for one concept expressed twice found `ledger_bindings.py`
duplicating the modules that replaced it. A commit split it into per-channel
modules - IVA, renta, OSS, impatriado - and repointed every consumer, but the
parent was never removed.

Measured rather than assumed: **59 of its 60 top-level definitions have a
byte-identical body in another module**, the sole exception being one private
helper. It has **zero importers** by AST search across the repository, no dynamic
import, and its only remaining mention was an adjudication row in this campaign's
own classification data. It is deleted, with that row removed in the same change
so the ledger does not go stale.

This is the largest parallel declaration found: for every one of those 59
functions, two definitions of the same fact sat in the tree, and a change to the
live one would leave the dead one disagreeing silently. The classification gate
had already noticed something was wrong - it reports `ledger_bindings.py` as the
sole unreferenced-module candidate and asks whether it is genuinely dead. The
answer is yes, and the gate was asking the right question.

Verification: the registry compiles, the bindings module imports, and 614 of 615
ledger and binding tests pass. The single failure is a home-office carve-out
worked example that fails identically at HEAD, proved by restoring the original
files, re-running, and putting the change back.

### three-copies-of-one-type-guard-and-two-of-one-predicate | medium | And a fourth apparent duplicate that is a legitimate boundary wrapper

Two smaller parallel declarations were collapsed onto canonical definitions.
`is_object_list` had three byte-identical copies across IVA modules beside the
definition in the core type-guard module, differing only in whether the docstring
spells "unparameterised" with an s or a z. `mapping_lacks_fact` had two copies
beside the one in its selector support module. All five sites now resolve to a
single object, which is asserted directly rather than inferred from the imports.

A third candidate was left alone after reading it. `sha256_file` exists twice
with genuinely different bodies, which looks like the worst case - one concept,
two behaviours - and is not. The second delegates to the canonical digest and
adds error translation plus filename redaction, because diagnostics must not leak
source filenames. That is a boundary wrapper with its own responsibility, and
collapsing it would remove a redaction the security rule requires. The name it
shares is the only thing duplicated.

That is now the third time in this campaign a duplication signal has turned out
to be legitimate on inspection. The measurement finds candidates; only reading
them decides.

### a-module-was-serving-as-a-re-export-path-and-only-deleting-the-duplicate-revealed-it | medium | The consumer reached a type guard through a module that merely happened to define it

Collapsing `is_str_keyed_mapping` onto a canonical definition exposed a second
parallel declaration underneath it. The guard was defined in two IVA modules; one
of them never called it. Removing the unused copy broke sixteen tests, and the
reason is the finding: a third module, `country_vocabulary`, imported
`establishment` and called `_establishment.is_str_keyed_mapping` at four sites.

So `establishment` was not a definition site at all. It was a re-export path, and
a consumer was reaching a general-purpose type guard through a module about
Spanish IVA establishment rules because that module happened to define it. The
import said nothing true about where the concept lives.

Both are now pointed at the core type-guard module. The guard was promoted with
its precondition preserved rather than copied verbatim: unlike its sibling it
checks nothing about the keys at runtime, and is sound only where the provenance
guarantees them - a TOML table always has string keys. That docstring now says so
and names the sibling to prefer otherwise, because a guard that asserts less than
its name suggests is exactly the ambiguity this work is removing. 829 IVA tests
pass.

The sequence is worth keeping: the duplicate was visible to a scan, the
re-export path was not, and only removing the duplicate surfaced it. A tree can
hide a second parallel declaration behind the first.

### the-deleted-module-was-cleared-by-three-independent-a-b-tests | medium | A large deletion beside a red suite needs causation established, not asserted

Deleting a 2,139-line module while neighbouring suites already fail is exactly
the situation where a real regression hides among inherited noise. Three failures
were therefore each A/B tested by restoring the module, re-running, and deleting
it again: a ledger evidence-grounding test failed identically both ways, a
resolver enrolment gate failed identically both ways, and a home-office carve-out
example failed identically both ways.

The combined run of the aggregation and ledger suites reports 468 failures, which
looks alarming beside a deletion. Aggregation alone is 5 failed against 1,049
passed, so the weight sits in the ledger suite, and the sampled failures there are
the other contributor's in-flight module renames and unenrolled split-out
resolvers. None of the failures mentions the deleted module, and no import error
appears anywhere - consistent with a module that had zero importers by AST search.

The general point is that "the suite was already red" is not evidence about a
specific change. Only restoring the change and observing the same failure is.

### one-schema-construction-had-five-spellings-in-one-package | medium | Four identical private helpers and a fifth built inline

Four command-spec modules each defined an identical private `_schema` helper
building a deferred result schema for a config payload, and a fifth module built
the same object inline. One concept, five spellings, inside one package.

They agreed, which is exactly what let it persist: nothing failed, and each new
spec module copied whichever neighbour it was written beside. The risk was never
disagreement today - it is that the payload module's name, the schema state or
the deferred-target shape changes in one of them and the rest keep working while
meaning something slightly different.

All four now alias one canonical helper, which is asserted by identity rather
than by reading the imports. The CLI spec suite reports 10 failed and 394 passed
both before and after, proved by restoring the four originals, re-running, and
putting the change back.

### two-functions-that-look-identical-to-an-ast-scan-are-not-duplicates | medium | Same syntax, different module constants, and the shared mechanism already exists

The two AEAT sede checkers each define `extract_verdict_from_response_text` with
byte-identical bodies, which reads as an obvious duplicate. It is not. Each body
references its own module-level `_POSITIVE_MARKERS` - GROI's ROI-registration
phrases in one, the NIF-IVA identification phrases in the other - and both
already delegate to a shared marker-verdict extractor, which is the canonical
mechanism. What is duplicated is the delegation, and collapsing it would mean
parameterising away the thing that distinguishes the two checkers.

The limitation of the measurement is worth stating: comparing function bodies by
AST shape treats a reference to a module-scoped name as equal wherever the name
matches, regardless of what it holds. So a body-identical result is a candidate
and not a finding - the fourth time in this campaign a duplication signal has
survived measurement and died on reading. Both files are also held by another
contributor, so this would have been reported rather than changed in any case.

### a-function-describing-itself-as-the-single-projection-existed-twice | medium | And modelo 390 resolves to no revision for the current filing year

The clearest instance of the pattern this work is removing: a twenty-two line
helper whose own docstring says it reads the operator profile "through the
SINGLE projection", carried verbatim in two application modules. The claim was
true of the projection it delegates to and false of the helper making it.

It now lives beside that projection, and its docstring records why rather than
repeating the claim. Two callers alias one object, asserted by identity.

Separately, running the affected suites surfaced a registry coverage hole worth
recording on its own: **modelo 390 declares revisions 2021 through 2025 and
resolves to nothing for filing year 2026**, which is the current year. Several
calculation tests fail on it, and the earlier revision-span gate reports the same
shape - a closed-ended tail the calendar has passed. It is registry data rather
than tooling, and it is now a step.

Duplicate function bodies across the shipped package are down from 27 to 18, and
redundant copies from 45 to 36, with every collapse verified by object identity
rather than by reading imports.

### the-a-b-method-was-wrong-and-is-corrected | high | Restoring a file from git is not the same as undoing an edit, and it risks other people's work

Several failures in this session were attributed by restoring a file with
`git checkout --` and re-running. That was wrong twice over and both reasons
matter.

It is destructive. The working tree carries over six hundred modified files from
another contributor, and discarding a file's working state to test a hypothesis
risks deleting work that exists nowhere else. Each use here was preceded by a
copy and followed by a restore, and the files were verified byte-identical
afterwards, so nothing was lost - but the safety came from a manual backup, not
from the method, and one missed copy would have been unrecoverable.

It is also wrong on its own terms. Restoring from the index gives the COMMITTED
version, not the state before the edit under test. With hundreds of uncommitted
changes in the tree that is a different and older world, which is exactly why one
such attempt produced 534 failures and no usable comparison.

The correct method, used since, is surgical: re-add the removed definition in
place, run, and remove it again. It touches only the edit being tested, cannot
discard anyone else's work, and compares against the tree as it actually is. Two
attributions were re-done that way and both came back identical, which is the
result the earlier method was reaching for without the risk.

### uncommitted-canonicalisation-was-reverted-by-another-contributor-s-commits | high | The definitions survived and the consumer repointing did not, which is the worse half

Three collapses completed in this session were undone without anyone intending
it. While the work was uncommitted, the other contributor committed three times
and the working-tree edits to nine command-spec modules, six live CLI modules and
one registry internals module were overwritten.

The asymmetry is what matters. Every canonical definition survived - eleven new
helpers and one deleted module - because those landed in files the commits kept.
What reverted was the *consumer* side: the local copies came back and now sat
beside the canonical helper rather than instead of it. That is a worse state than
before the work started, because the tree then carries both the shared definition
and the duplicates it was meant to replace, and a reader has no way to tell which
one is authoritative.

It was detected only because the duplicate census was re-run and two counts that
had gone to zero were back at nine and five. Nothing failed; the code worked
exactly as it had. A canonicalisation that is reverted leaves no failing test,
which is precisely why the measurement has to be repeated rather than trusted
from the last run.

All three are re-applied and verified by object identity. The general lesson for
this kind of work in a shared tree is that a collapse is not durable until it is
committed, and that the census is the only thing that notices when it is lost.

### five-of-the-nine-remaining-duplicates-are-not-duplicates | medium | Same syntax over a per-module constant, verified by reading rather than by pattern

Of the nine duplicate function bodies left, five are artefacts of comparing
syntax rather than meaning, and each was settled by reading the constant the body
references.

Two sede helpers call `assert_read_http_for(READ_GUARD_POLICY, ...)` and
`assert_query_browser_action_for(READ_GUARD_POLICY, ...)`. `READ_GUARD_POLICY` is
declared separately in each sede module, so five apparently identical bodies
guard five different policies. A command-spec helper indexes `_HANDLER_MODULES`,
a table each spec module owns. A repository helper calls a per-module `factory`.
And the verdict extractor reads per-module marker phrases while both callers
already delegate to one shared extractor.

Collapsing any of them would parameterise away the thing that distinguishes the
modules, which is the opposite of the goal: it would replace five honest
declarations with one function taking five arguments.

The measurement limitation is now stated plainly: an AST body comparison treats a
module-scoped name as equal wherever the name matches, whatever it holds. It
finds candidates. Only reading them decides, and five of nine here died on
reading.

### the-duplicate-body-sweep-is-finished-and-every-survivor-is-a-false-positive | high | Twenty-seven bodies to five, and the five must not be collapsed

Duplicate top-level function bodies across the shipped package are down from 27
(45 redundant copies) to 5 (8 copies). Every collapse was verified by object
identity rather than by reading the imports, and the canonical home was chosen by
what already owns the concept: a type guard beside its siblings in core, a JSON
locator beside the parsers that need it, a flow traversal beside the types it
walks, a snapshot identity beside the serialisation rule it states.

The five survivors are all false positives of the same shape, and each was
settled by reading the constant its body references rather than by pattern. Two
sede guards call `assert_*_for(READ_GUARD_POLICY, ...)` where the policy is
declared separately in each module; a command-spec helper indexes a per-module
table; a repository helper calls a per-module factory; and the verdict extractor
reads per-module marker phrases while both callers already delegate to one shared
extractor. Collapsing any of them would replace five honest declarations with one
function taking five arguments, which is the opposite of the goal.

So the sweep is complete rather than stalled: what remains is not work deferred,
it is work that would be wrong to do.

The largest single item was a module left behind by its own split - 2,139 lines,
59 of 60 definitions duplicated in the modules that replaced it, zero importers.
The subtlest was an alias: `ModeloEditCasillaDataType = CasillaDataTypeField`,
exported with no consumers outside its own module. That is not a duplicated
declaration at all - the object is shared - but it is a second public NAME for
one concept, which is the same ambiguity in a form no duplicate-body scan can
see.

### three-instruments-and-three-different-blind-spots | medium | Traded with a peer session working the same tree

A second session is running a vocabulary-canonicalisation campaign over the same
worktree, and comparing instruments produced something neither had alone. Its
scan cannot separate a repeated vocabulary from a deliberate NARROWING of one -
five surfaces declare a data-type vocabulary and four are intentional subsets, so
the mechanical collapse would have widened what four surfaces accept. This
campaign's scan cannot separate a body over a shared constant from a body over a
per-module one. And neither can separate an alias from a declaration, which is
how the `edit_models` hit was classified as a duplicated vocabulary when it was a
renamed re-export.

All three reduce to one rule worth keeping: the instrument finds candidates, and
only reading decides. Of nine candidates surviving into the final pass here, five
died on reading.

One concrete defect came out of the exchange in the other direction. That
session's promotion of the casilla data type to a typed enum makes
`CasillaDataTypeField` an annotated type, and an operation-schema gate refuses a
field whose type customises its Pydantic core schema:
`schema.submission.baseline.permitted_surface.data_type must not customize its
Pydantic core schema`. It is reported to them with the commit that introduced it.
The alias removal recorded above was ruled out as a cause first, on the ground
that substituting an identical object cannot change a schema shape.

### the-alias-sweep-found-eleven-second-names-and-only-two-were-wrong | medium | Naming a primitive after the domain is the opposite of duplication

The duplicate-body scan cannot see an alias, so a second scan looked for type and
constant aliases: an assignment giving an imported name a second name in the
importing module. Eleven exist across the shipped package, and the interesting
result is that nine are right.

`ContentDigest = Hex64Str`, `BucketEventId = Hex64Str`,
`M145CommunicationRecordId = Hex64Str`, `ModeloDraftContentAddress = Hex16Str` -
these give a domain name to a primitive shape, and a reader of
`ContentDigest` learns what the value MEANS where `Hex64Str` says only what it
looks like. Collapsing them would trade meaning for uniformity, which is the
opposite of what this work is for. Two more rename a constant to the spelling the
rest of the codebase actually uses.

Two were genuinely wrong: `BINDING_SOURCE_DISPOSITIONS` and
`ENROLLED_SOURCE_KINDS` in the calculation source policy, each exported in
`__all__` and each carrying exactly one reference repository-wide - its own
definition line. A second public name with no reader is pure ambiguity: it
survives long enough that someone eventually imports it, and then two names for
one constant are in the tree with nothing recording which is preferred. Both are
removed; the module imports, the registry loads, and the owning tests pass.

A measurement error inside this sweep is worth recording because it nearly caused
four removals instead of two. The first pass counted a name's occurrences within
its DEFINING FILE and read four aliases as unused. Counted repository-wide,
`MAX_AGE_MENOR_TRES` has twenty references - it is the name the codebase prefers,
and the longer canonical spelling is the one nobody uses. An in-file count answers
a different question from the one being asked, and it answered it plausibly.

### two-classes-shared-a-name-and-only-one-of-them-could-be-collapsed | medium | The other had to be renamed, because the architecture forbids merging it

A third scan looked for the form the first two miss: a class declared under one
name in more than one module. Two existed, and neither had an identical body -
which is the worse shape, because one name meant two different contracts.

`_IdentifiedRecord` was declared three times in the registry package, spelling
the same protocol two ways: `id: str` in one, a read-only property in another.
One site was collapsed earlier in this campaign and a third was found only by
this scan, which is the pattern already recorded here - removing one duplicate
exposes the next. All three now resolve to one protocol.

`CustodyDigestModel` was the interesting case, because it could not be collapsed.
One is declared in the application layer and one in the persistence adapter, and
both docstrings open with the same claim to be the shared canonical digest
behaviour for custody records. They genuinely differ - the adapter's declares a
`self_digest` field and a third class variable - and merging them is forbidden
rather than merely awkward: application code must not depend on an adapter, so
the dependency that would share the definition cannot exist.

The remedy was therefore a rename, not a collapse. The application class had
twelve fewer consumers than the adapter's - in fact none outside its own module,
despite being exported - and its three subclasses were already named
`ProfileCustody*`. It is now `ProfileCustodyDigestModel`, and its docstring
records why the name carries the layer: sharing one name across a boundary that
forbids sharing the definition made a reader guess which contract they were
reading.

That distinction is worth keeping for the rest of this work. Where two
declarations of one concept can be merged, merge them; where an architectural
rule forbids the merge, the duplication is legitimate and the NAME is the defect.
No classes share a name across modules now.

The custody lock-order test fails either way, verified by renaming back, running,
and renaming forward - a threading assertion about an event that never sets,
untouched by any of this.

### a-redaction-token-was-declared-eight-times | high | Eight places had to agree, and disagreement leaks a taxpayer's filename with nothing failing

A fourth scan looked at module-level constants sharing a name AND a value across
modules: the same fact stated twice. Twenty-three existed. The largest is
security-relevant.

`_INPUT_PDF_SOURCE_LABEL = "<input-pdf>"` was declared separately in eight
inbound PDF modules. It is the token that stands in for a taxpayer's document
path in logs, diagnostics and error messages, because the filename alone can
disclose who they are, which return it is, or where it was stored. Eight
independent declarations mean eight places must agree; the failure mode of
disagreement is that one surface emits a real path and nothing fails, which is
exactly the shape of defect a test does not catch.

It now lives in one module whose docstring states why it exists, and all eight
consumers resolve to that object. The two packages that exercise it pass 194
tests.

Two further constants were collapsed on the same reasoning: a wizard section
identifier declared in three modules, now owned by the catalogue that defines the
section, and the modelo edit responsible owner declared in three modules, now
owned by the service the other two build on.

### a-shared-value-is-not-always-a-shared-fact | medium | Three manifests at version one are three facts that agree, not one fact repeated

The constant scan's obvious failure mode is the mirror of the alias scan's:
assuming that two declarations carrying the same value carry the same MEANING.

`_MANIFEST_VERSION = 1` appears in three modules - an attachment envelope, an
evidence service and a modelo workspace manifest. Three unrelated manifests, each
independently at its first version. Collapsing them would couple their
versioning: the next time one manifest's format changes, either all three claim a
new version or the shared constant has to be un-collapsed under pressure. They
agree today by coincidence and must remain free to disagree.

That is the fourth distinct shape this campaign has had to separate by reading
rather than by measurement, after a body over a per-module constant, an alias
versus a declaration, and a narrowing versus a repeat. The scans are worth having
precisely because each one finds a class the others cannot; none of them can tell
whether two things that look alike mean the same thing.

Twenty duplicated name-and-value constants remain and are recorded as a step
rather than swept, because that judgement has to be made per constant.

### the-constant-sweep-is-judged-rather-than-swept | medium | Twenty-three to sixteen, and the seven removed were chosen one at a time

Every remaining duplicated constant was read and classified, because the scan
cannot tell a shared fact from two facts that agree. Seven were collapsed and the
rest were left, each for a stated reason.

Collapsed as one fact: the PDF redaction token declared eight times; a wizard
section identifier declared three times, now owned by the catalogue that defines
the section; the modelo edit responsible owner declared three times, now owned by
the service the other two build on; five wizard locale keys, now owned by the
format-hints module that already declared four of them and gained the fifth; and
`SHA256_HEX_LENGTH = 64`, which is a property of the algorithm and cannot
differ between two modules without one of them being wrong.

Left as separate facts: three manifest versions that agree at one by coincidence
and must stay free to diverge; a signature envelope version on the same
reasoning; a default page limit and a file extension shared by unrelated
surfaces.

One was left for a different reason worth recording, because the naive answer
would have been to collapse it. The W3C XML Schema namespace is declared in two
production modules - a filing XML dictionary and an AEAT e-invoice schema reader
- and it genuinely is one fact. But the only home shared by those two layers is
the external-constants registry, which is documented as a read-only mirror of
remote endpoints and hostnames, and a format namespace is not that. Creating a
new core module to hold one immutable W3C string would couple two subsystems that
otherwise never meet, to remove a divergence risk that is zero because the string
cannot change. The duplication is cheaper than the coupling, and that is a
different judgement from "these are separate facts" - both end in leaving the
code alone, and conflating them would lose the reason.

### the-collapsed-concepts-are-now-gated-because-a-sweep-already-undid-them-once | high | A canonicalisation is undone silently, and the duplicate that returns works

Sixteen concepts examined and collapsed during this work are now held at one
definition by a gate. It exists because they were already lost once: a whole-tree
commit in the shared worktree restored nine local key helpers, six alias
wrappers and a record protocol, leaving each canonical definition sitting beside
the duplicates it had replaced. Nothing failed, because the restored local copy
works. The census noticed on its next run; no test would have.

The gate names each collapsed concept and its owning module and asserts a single
definition across the shipped package. It carries no count and no tolerance - one
definition is the contract, and a second is a regression whatever the total. An
import of the symbol is deliberately not a definition, since every consumer is
expected to import it and only a second declaration is the fault. It also checks
the definition has not silently moved module, which would leave the gate watching
an address nothing lives at.

What it deliberately does NOT do is refuse duplication generally, and the reason
is the whole finding of this campaign's second half. Several duplicate-looking
declarations in this tree are correct: a guard over a per-module policy, an alias
giving a primitive a domain name, two manifests agreeing at version one by
coincidence, a W3C namespace whose single shared home would cost more coupling
than the duplication costs risk. A gate that refused those would be refusing the
codebase's own judgement, and would be argued down within a week. Only concepts
that were read, judged to be one fact, and collapsed are listed.

Its teeth were proven rather than assumed: planting a second
`is_str_keyed_mapping` beside the canonical one is caught and named, and both
probes were removed afterwards.

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

SUPERSEDED. Two later revisions of this section follow it, and the third revision is the current
position. This one is retained because its withdrawals and its statement of the single proven
filing defect are still the record of what was believed when it was written; its claim to take
precedence is not, and that claim is what this marker corrects.

The recommendations above accumulated as the audit ran and some are superseded by later findings.
This section stated the current position when written and took precedence where they differed. Two of the earlier
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

SUPERSEDED by the third revision below, on scope rather than on substance: the two filing-data
defects it locates still stand.

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

### Consolidated position, third revision

The second revision above is superseded on scope rather than on substance: its two filing-data
defects still stand and are still unrepaired from here. What has changed is that the question this
audit opened with now has an answer, and the answer is smaller than the registry's own declarations
imply.

**What the product can file.** Of 58 modelos, 22 declare applicability only - the censal and
informational ones, correctly carrying no filing machinery, and a screen that demanded any from them
would be wrong. Five declare calculation only. Sixty-eight revisions reach filing grade with an
export layout, and that is where the claim thins: 31 layouts spell their envelope as a record the
export boundary cannot see, and one of those loses the developer identity fields the official design
marks mandatory; 5 can render a fichero and cannot say when it is due; 4 declare a filing calculation
class with no formula behind it. Four revisions fail more than one of those axes and modelo 308 fails
three. Sixteen revisions carry a complete filing chain.

**The distinction is decidable and is now stated in code.** Which modelos are real filings was
treated as a judgement call earlier in this work, and it is not: authority grade, calculation class,
export layout, filing envelope and deadline window are all declared, and a screen reads them. A
maintained list of "real" modelos would be wrong within a release; a derivation cannot be.

**The measurement discipline is the transferable result.** Three conditions were first measured far
larger than they are - 52 envelope gaps where 31 are real, 14 formula gaps where 4 are real, 35,287
census findings where 1,633 are actionable - and each overstatement had the same two causes: counting
the sites that exhibit a condition rather than the unit someone fixes, and counting a declared,
correct shape as a defect. A screen whose signal is a fifth of its rows teaches its reader to skim,
which is the same failure the retired frozen ratchets had. Every count in this audit that survived
was re-derived after that lesson.

**Performance stopped being invisible.** A conformance test failed on a timeout and read as a logic
failure; measured, one closure report took 210.8s and the conformance audit 133.9s, both dominated by
one mechanism - a snapshot is a free cache hit plus an isolating deep copy that is 98% of the call,
and callers took one per coordinate to read a single string or four small collections. They are now
15.0s and 22.1s, and the lane runs in 6m26s rather than 15m04s. No caller gained access to shared
registry state to get there, which is the only reason the speed is acceptable.

**What is blocked, and on whom.** Two contract decisions are genuinely open and neither should be
settled by tooling: there is no typed slot to record why a revision holding filing machinery stays
below filing grade, so eighteen documented deferrals live in comments and three have no reason at
all; and modelo 100 declares filing grade for a layout that refuses at render for want of an
aux-version token that must not be invented. Modelo 222 needs re-review rather than a grade edit,
because its attestation reaches scheduling and applicability only while the revision it describes has
since tripled. The twenty-four filing tests demanding grades three modelos no longer declare are
resolved; the grades themselves were correct and it was the consumers that were owed the change.

### serializer-change-filled-the-drift-class-with-correct-records | high | A quote-style change put 141 semantically unchanged records into the class that means unsafe to republish

The closed-vocabulary enum conversion turned the export record `encoding` field from a
plain string into `ExportEncoding`. The value did not change and the encoding did not
change, but the TOML serializer now emits it single-quoted where the committed trees
carry it double-quoted. Every one of the 141 committed export record files uses the
double-quoted form and none uses the single-quoted form, so the flip is uniform and the
committed spelling is the anomaly: every other string field in those same files is
single-quoted.

The consequence is not cosmetic. `render_check` classifies any difference in a record
file as `record_drift`, and its own documentation states that a tree in that state ships
bytes its inputs no longer produce and must not be republished. That verdict is now
wrong for these trees. The bytes mean exactly what they meant before; only the quoting
differs. A screen that compares bytes cannot tell a changed value from a changed
serializer, and here it reported the more alarming of the two.

This is worth stating plainly because the safe-looking reading is the dangerous one. The
`record_drift` class exists to stop someone republishing a tree whose inputs have gone
bad, and modelo 347 genuinely sits in that state for a proven reason. Filling the class
with 141 false members is how a real member stops being noticed.

The remedy is not mine to apply: republishing generated trees is registry data governed
by its own disposition file, and the enum conversion is another contributor's committed
work. What belongs here is the attribution and the measurement. The regression is
commit `2606941009`, the failure count moved from 15 to 46 across the two registry test
directories, and 30 of the 31 new failures are this single field.

The three fixtures that fed the encoding as the literal `latin-1` were repaired here,
because they are dev-owned and the spelling was never canonical: `latin-1` and
`iso-8859-1` resolve to the same codec, which was verified rather than assumed, and
`ExportEncoding` admits only the second. Those six failures are gone. The remaining
twenty-four are the quote flip and are reported, not patched.

### ambiguity-was-never-measured-only-duplication | medium | Every duplication measure counted things said twice; none counted one word meaning two things

Every duplication measurement in this campaign counted things said twice. None counted
things that say two things under one word, which is the harder defect: a duplicated body
is repaired by deleting a copy, but a name defined in two modules loses behaviour if
either copy is deleted, and a reader who greps it cannot tell which definition runs.

The census now separates four classes, because a count that lumped them would be mostly
noise. A module's `main` is convention and is reached by module path, never by the bare
name. Several definitions inside one module are an `@overload` set - one implementation,
several signatures - and the naive scan that started this counted `redact_structured`
five times before the eight overload stubs in that file were read. Both are reported so
the total is honest and excluded so the findings are not diluted.

That leaves 12 names claimed across architectural layers and 9 claimed inside a single
layer. The cross-layer class is often legitimate: a layer states a concept in its own
vocabulary and the hexagonal boundary is what stops the two from being merged, which is
the same reasoning that kept nine aliases and five duplicate bodies earlier in this
campaign. The same-layer class has no such excuse.

`resolve_bucket_event_repository` is the sharpest instance and shows why the class is
worth separating. Two definitions sit in one package, `application/ledger`, under an
identical signature, and they do not agree. One returns the protocol and accepts any
implementation of it. The other returns the concrete class and asserts the passed
repository is that class, so a caller supplying a valid protocol implementation that is
not the concrete type fails - and because the guard is an `assert`, it disappears
entirely under `python -O`, leaving the return annotation stating something the function
no longer checks. Neither definition is dead and neither is a copy of the other. They
are two contracts wearing one name, and the arity that would normally distinguish them
is identical, which is why nothing had surfaced them.

Arity is carried in every row for that reason: differing arity is the cheapest evidence
that two same-named functions are not the same function. It is a hint and never a
verdict - `review_view` differs at 2 against 4 and is plainly two things, while this
pair matches at 0 and is also two things.

The screen exits 0 whatever it finds. A gate belongs here once the nine same-layer
collisions have been adjudicated, and not before: refusing a condition the corpus still
contains would only teach the next contributor to route around it.

### drift-screen-separates-serializer-from-value | medium | record_drift now means a record whose meaning moved, proven at 25 provenance-only against 2 real

The previous finding recorded that a one-character quote flip had reclassified 141
semantically unchanged export records as drifted. The screen has been taught the
distinction rather than the finding merely noted.

`render_check` still compares bytes, because bytes are the truth about what ships. What
changed is that a differing file is now also parsed, and a file whose bytes moved while
its parsed content did not is recorded as `serialization_only`. `record_differing` means
what its name always claimed: a record that now means something its inputs do not
produce. A new `semantically_reproduced` answers the question the old `reproduced` was
being asked to answer and could not.

An unparseable file is never excused. `_parsed` returns `None` on a file that does not
decode or does not parse, and `None` is deliberately not equal to `None` for this
purpose - the comparison requires the committed side to parse before it will consider
the two equal. A corrupted record must not be forgiven as a spelling change, which is
the failure mode a looser implementation would have introduced.

`provenance_only` was tightened in the same pass, because the first version of this
change made it lie. Under the new parsing it reported True for a tree whose records
differed in spelling, which claims the manifest was the only file that moved. It now
requires the manifest to be the single differing file, and the broader question is asked
of `semantically_reproduced`.

The discrimination was proved in both directions on live trees, not asserted. Across
every published generated tree the screen now reports 25 in `provenance_only` and 2 in
`record_drift`, and the two are exactly modelo 347's revisions - the genuine defect this
audit already documents, whose declarado record must repeat over binding rows and no
longer does. Before this change that real pair sat among roughly twenty-three false
verdicts of the same class. A gate whose alarming category is mostly false is worse than
no gate, because the one member that matters is indistinguishable from the noise.

### disposition-gate-fails-accurately | medium | Re-keyed onto the explained state, the gate names 21 stale attestations instead of an undifferentiated diff

The gate that requires every non-reproducing tree to carry a written disposition was
keyed on byte equality. It has been re-keyed onto a `disposition_class` that returns
`record_drift`, `provenance_only`, or nothing at all for a tree differing only in
spelling. Putting the classification in the module rather than in the test matters:
the test was deciding what counted as an explained state, which is the screen's job.

The gate still fails, and it should. Twenty-one trees that previously reproduced
byte-for-byte now carry a stale attestation, because the manifest attests the inputs and
an input changed. That is a true statement about the corpus and the gate is right to
refuse it. It was already failing before this change; what changed is that its message
now names the twenty-one trees and their state instead of reporting an undifferentiated
byte difference.

No disposition rows were added for them. Twenty-one rows describing one shared cause
would be documentation of a mass condition dressed as twenty-one explained states, and
the disposition file's own header says a row must name a tree that genuinely does not
reproduce. The remedy is republication, which is safe for all twenty-five
`provenance_only` trees and must never be applied to 347's two. Republishing generated
registry data is neither this campaign's scope nor its author's to perform, so the state
is reported with the remedy named and left for the owner of that commit.

A note on what was not claimed: no type checker is installed in this environment, so the
change carries lint and format verification and real-behaviour test evidence, and no
type-check evidence. Saying so is cheaper than the reader discovering it.

### one-definition-of-record-sameness | medium | The generated-tree suite carried a second byte comparison; both now call the same parse helper

The generated-tree suite carried its own byte comparison, a `filecmp.cmp` over every
fragment, entirely separate from the render comparison. Two surfaces were deciding what
"the same record" means and they disagreed the moment a serializer changed. Rather than
teach the second surface the same distinction a second time, the parse helper was
promoted from private to `parsed_tree_file` on the module that owns the comparison, and
both call it. This is the campaign's own rule applied to itself: where two declarations
of one concept can be merged, merge them.

The effect is measurable and was measured. Each of the twenty-seven tree tests
previously listed up to sixteen differing files; each now lists exactly one,
`_generation.provenance.json`. Across the three affected modules the failure count fell
from 46 to 28, and every remaining failure has one cause and one remedy.

The manifest is deliberately not excused. It differs because it attests the inputs and
an input changed, which is a true and useful signal: it is the only staleness detector
the committed trees have. Excusing it would have turned twenty-seven accurate failures
into twenty-seven silences and removed the evidence that a republication is owed. The
suite is not green and should not be until the trees are republished by the owner of the
commit that staled them.

What was fixed here is precision, not the underlying condition. A failure naming one
file and one cause is actionable; a failure naming sixteen files, fourteen of which
differ only in how a string is quoted, teaches the reader to skim it.

### signature-declared-the-enum-and-returned-strings | medium | An annotation had been wrong since it was written, hidden because a StrEnum compares equal to its value

`_evidence_for_workbook_kind` is annotated to return `EvidenceTier | None` and a tuple of
`EvidenceTier`, and it returned bare strings such as `"executable_parity_evidence"`. The
annotation had been wrong since it was written. Nothing surfaced it because a `StrEnum`
member compares equal to its own value, so every test asserting the tier passed against
either form and no reader had cause to look.

The closed-vocabulary conversion is what made it fail, and that is worth stating in the
enum conversion's favour. The conversion did not introduce this defect; it revealed one
that a permissive boundary had been hiding. The same is true of the three fixtures
spelling the encoding as `latin-1`: the token was never canonical, and only a typed
field refused it.

Both sites now construct the enum. The failure this fixes is real rather than cosmetic,
because the value crosses into a strictly-validating registry model, and the annotation
now describes what the function does.

### green-run-selected-nothing | high | A change was verified against a run that deselected all 24 tests exercising it, and exited zero

Verifying that change first produced "3 passed" over two test modules, and the number was
the finding. `test_workbook_parity.py` carries the `external_tool` marker and the default
lane selects `unit and not external_tool`, so all 24 of its tests - every test that
actually exercises the module being changed - were deselected. The three that ran came
from the other file and touch none of it.

Re-run with the marker admitted, the 24 pass. The change is verified; it was not verified
by the run that first appeared to verify it. This is the second time in this campaign that
a marker turned a change's own test suite into an empty selection reported as success, and
the remedy both times was to read the collection count rather than the exit code. A count
that is lower than the file obviously contains is the cheapest available signal, and it
costs one `--collect-only`.

### determinism-and-shipped-equality-conflated | medium | One assertion carried two claims; rendering twice stays byte-exact while shipped-tree equality is semantic

The m303 envelope proof asserted `first == second == committed` in a single chain. Two
different claims sat inside it. That rendering twice yields identical bytes is
determinism, it is what the test is named for, and no serializer change can excuse a
difference between two runs of the same code - that half stays byte-exact. That the
render matches the shipped tree is a claim about meaning, and it is the half the quote
flip breaks.

They are now separate assertions with separate comparisons, and the failure message names
which claim failed. The residue is the same stale manifest as everywhere else, and it is
left failing for the same reason.

### invisible-test-condition-now-reported | medium | Lane visibility is a screen rather than a reader noticing a low collected count

Twice in this campaign a change was verified against a run that selected none of the
tests exercising it, and both times the exit code was 0. Relying on a reader to notice
that a collected count looks low is not a control, so the condition is now a screen.

`default_lane_visibility` reads the lane predicate out of the project's own `addopts`
rather than restating it, which matters for the same reason the rest of this campaign
matters: a hand-copied predicate is a second declaration of one fact and is free to
drift from the selection it claims to describe. Markers are read statically from the
module-level `pytestmark` assignment, so no test is imported or executed to produce the
report and the screen cannot suffer the collection effects it exists to describe.

The first version of the screen was wrong and the corpus said so immediately. It
reported 99 modules as carrying no execution marker; every one of them carried
`integration`. Those modules run - in their own lane - and calling them unrun would have
made the report useless by burying its own sharpest row under ninety-nine false ones,
which is precisely the failure this audit recorded for `record_drift` two findings
earlier. The classes are now separated: `other_execution_lane` for a module that runs
elsewhere, `no_execution_marker` for one that runs nowhere.

Corrected, the tree reports zero modules carrying no execution marker. That is a
reassuring result and it is only worth anything because the condition is constructed and
caught in the same suite: a module marked `hex_core` alone is reported, so the empty
corpus result means the tree is clean rather than the screen being blind.

One module carries per-function markers instead of a module-level assignment, and the
screen says so rather than guessing. The live collection agrees with that refusal: one
of its two tests is selected and one is held out by `resident_service`.

A defect in the screen itself surfaced through its own tests. `visibility_census`
anchored every reported path to the repository root, so it raised `ValueError` on any
tree outside it - which is every constructed fixture. The remedy was in the module rather
than the test: the path is now anchored to the repository when it sits inside one and to
the scanned root otherwise. A screen that can only be run over the repository cannot be
shown to detect anything the repository does not already contain.

### same-layer-collisions-adjudicated | medium | Three are correct, four want a rename or merge, one is a contract conflict no rename settles

Reporting nine shared names was the easy half. Each was read, and they do not divide the
way a count would suggest: three are fine, four want a rename or a merge, one is a defect
in the code rather than the name, and the single pair with byte-identical bodies is the
least interesting of the nine.

`resolve_bucket_event_repository` is the sharpest and is classed on its own as a contract
conflict. Two definitions in `application/ledger` share a signature and disagree about
what they accept: one returns the protocol and takes any implementation, the other
returns the concrete class and asserts the argument is that class. A caller passing a
valid protocol implementation that is not the concrete type fails - and the guard is an
`assert`, so under `python -O` it disappears entirely and the return annotation goes on
promising something the function no longer checks. This cannot be settled by renaming;
someone has to decide which contract is right.

`extract_pages_text_from_bytes` is the most confusing shape rather than the most severe.
The `adapters/inbound/pdf` definition is the shared primitive - it takes an explicit
`error_class` and `pdf_label`, which is what makes it reusable - and the declaracion
backend's function is one of its callers, adding a pypdfium2 fast path with
declaration-specific canaries. A primitive and its own caller sharing a name reads as two
competing implementations, which is the one thing it is not.

Two are plain duplication: `extract_verdict_from_response_text`, byte-identical in one
package and already dependent on that package's shared marker table, and
`validate_category_id`, where the support module carries the reasoned version naming the
closed taxonomy and the rules CLI re-derives the same refusal.

Three are legitimate and were nearly miscounted as defects. `extract_pages_text` names
the same role in two inbound families and is reached by module path; the parallel naming
is what makes the two backends recognisable as the same thing. `review_view` is two Typer
commands over different subjects, distinguished at every call site by arity. And
`active_profile_label` has two definitions with different cost contracts on purpose: one
resolves the pointer and reads the manifest, the other picks from rows already joined
specifically to avoid re-reading it. Collapsing that pair would make the list command
repeat work it has already done.

The reasoning is now a dispositions file with a gate that refuses in both directions, the
same shape the generated trees use. An unadjudicated collision fails; a row whose
collision has been resolved fails too, so an explanation cannot outlive its cause. It
stores no count: a tenth collision fails whatever the nine say.

Cross-layer collisions deliberately carry no rows. A layer restating a concept in its own
vocabulary is what the boundary is for, and demanding a written reason for each of the
twelve would bury these nine - which is the same mistake, in a different costume, as the
141 false drift verdicts recorded earlier in this audit.

### constant-value-conflicts-are-all-private | low | Sixteen constants carry two values under one name and none of them is public, so the underscore holds

Earlier passes counted constants sharing a name and a value. That is the harmless form.
The dangerous one is a name carrying two *different* values, because a reader who greps
it gets two truths and nothing in the name says which one the code in front of them
reached.

Measured across the shipped package: 28 names repeat with one agreed value, and 16 names
carry conflicting values. Not one of the 16 is public. Every conflict sits behind a
leading underscore, and that is what makes them safe rather than lucky - a private
constant cannot be imported, so two modules holding different values under one private
name are two local facts that never meet. `_MODULE` naming its own module, `_PAYLOADS`
naming its own payload module, `_SUBMIT_SELECTORS` carrying one page's selectors,
`_MAX_REPLY_TOKENS` tuned per prompt at 1024 and 200: each is correct where it sits and
would be wrong anywhere else.

This is the architecture rule earning its keep rather than a coincidence worth
celebrating, so the invariant is now gated on visibility instead of on disagreement. A
gate refusing every disagreement would demand the collapse of sixteen correct
declarations; a gate refusing a public disagreement protects the case where a consumer
choosing an import has no signal that the choice changes the value. The corpus satisfies
it at zero, and a planted public conflict is caught in the same suite, so zero means
clean rather than blind.

Two deliberate refusals in the screen. A constant built by a call or comprehension is
skipped rather than approximated, because a guessed value would report agreement or
conflict the source does not support. And a boolean is not a shared value: `True` under
one name in two modules is evidence of nothing.

### size-baseline-caught-this-campaigns-growth | low | A four-line growth was shrunk to fit rather than raising another contributor's reviewed ceiling

The evidence-tier repair grew `_workbook_parity.py` from 1399 to 1403 lines and tripped a
reviewed-size baseline. The failure was correctly attributed to this campaign rather than
to the enum conversion, which is the only reason it did not join the inherited residue.

The baseline was not raised. Raising another contributor's reviewed ceiling to
accommodate one's own growth is precisely what a size gate exists to prevent, and this
audit has argued twice already that a gate diluted by accommodation stops naming
anything. The four lines came from wrapping one over-long return; binding the four tier
members to locals once at the top of the function removed the wrap and brought the module
to 1396, three lines below where it started. The gate passes, the 24 marker-held parity
tests still pass, and the function reads better than either previous version.

### load-census-does-not-survive-a-rename | medium | A classification keyed on a module path follows neither side of a rename, and nothing reports the drift

`run_census` reports 21 registry modules carrying no classification and 14 rules naming
modules that are no longer in the universe. The two numbers are one condition seen from
both ends. `_validate_references` appears among the stale rules and `validate_references`
among the unclassified modules: a module lost its leading underscore, and the
classification followed neither the old name nor the new one.

That is worth naming as a property of the census rather than a backlog. A classification
keyed on a module path is a second declaration of where a symbol lives, and this campaign
has argued throughout that a second declaration drifts from the first. Here the drift is
mechanical and silent - the rename succeeded, the tests that matter passed, and the only
signal was a census gate reporting a set difference. The same rename that this campaign
has been performing deliberately, promoting private definitions to public canonical
modules, is what produced it.

The residue was checked for this campaign's own fingerprints before anything else.
`ledger_bindings`, deleted here earlier, appears in neither set, so the module removed by
this work left no orphaned rule behind. The 21 unclassified modules are the
`record_design_*` and binding splits from the concurrent consolidation, and they are
still landing.

They are therefore reported and not adjudicated. Writing 21 classifications would mean
asserting what each module is for while another writer is still moving it, and the
assertions would be stale before anyone read them. That is the same judgement already
applied to the 25 staled attestations: measure it, attribute it, name the owner, and
leave the remedy where the knowledge is. The distinction this audit keeps returning to is
between work that is blocked and work that belongs to somebody else; only the second kind
is finished by reporting it.

### shape-identity-is-not-concept-identity | low | Eighty-one type declarations share a field shape and every one of the seven sharpest is correct

The obvious next sweep after names, values and bodies is shapes: type declarations whose
field names and annotations match exactly under different class names. Across the shipped
package there are 81 such shapes - 39 spanning layers, 35 inside one layer, and 7 inside a
single module. On the pattern established earlier in this campaign the seven same-module
cases should have been the sharp ones, and a gate should have followed.

Every one of the seven was read, and every one is correct as it stands.

`GeneratedArtifactSource` is a `Protocol` and `StaticGeneratedArtifactSource` is a
structural implementation of it. They share a shape because that is precisely what a
protocol means. A gate reporting this pair would be reporting the type system working.

`WorkStatusResult`, `WorkRenameResult` and `WorkDiscardResult` share 21 fields in one
module and are the strongest-looking case in the set. They are the declared output schemas
of three distinct CLI commands, and each is registered by name in the command specs, so
the class name is part of the machine-readable output contract rather than an internal
label. Collapsing them would not remove a duplicate; it would remove three commands'
ability to name what they return. The same holds for `RatiosSetResult` against
`RatiosUnsetResult`, and for `CounterSpec` against `TimingSpec`, where the type distinction
is what makes dispatch safe at all.

So no gate was built, and that is the finding rather than an absence of one. A screen
reporting 81 shapes of which the great majority are correct by construction would behave
exactly like the `record_drift` class did before it was repaired earlier in this audit:
the alarming category fills with true-but-harmless members until the one that matters
cannot be picked out. This campaign has now argued that three times, and the consistent
conclusion is that a category is only worth gating when a member of it is more likely
wrong than right.

The measurement is kept because it is cheap to re-run and answers a question someone will
ask again. What it does not support is a rule, and inventing one anyway would have been
the easier and worse outcome.

### conformance-closure-tests-are-outside-every-lane | critical | Sixteen tests proving real filing outcomes are named by no lane, and one of them fails

This campaign built a lane-visibility screen after a marker deselection twice turned a
change's own test suite into an empty selection reported as success. The tree already had
a stronger answer to that question, and finding it changed what this work should keep.

`dev/tests/test_lane_reachability.py` asks the same question per TEST rather than per
module, and asks both halves of it: whether a lane's path scope names the file, and
whether that lane's marker expression selects the test. Its own docstring records that it
replaced a `dev/`-only path-only predecessor and strictly subsumes it. Measured against
the same tree, it reports 73 marker-unreachable tests and two files outside every lane
path. The screen written here is the weaker instrument, and this campaign has spent
several findings arguing that two declarations of one question is the defect - so the
honest conclusion is that the older gate is canonical and the newer screen earns its place
only by what it adds, which is a static classification and no pytest run.

Running it produced something the campaign needed. Two files sit outside every lane's path
scope, so no marker expression could ever reach them:
`dev/registry/conformance/tests/test_closure.py` and
`dev/registry/conformance/tests/test_real_closure_outcomes.py`.

The second matters directly. Its one failure has appeared in every lane measurement in
this audit and was carried as inherited baseline, which was correct as far as it went and
missed the sharper fact: no CI lane runs that file at all. A failure nobody's pipeline
observes is not a baseline, it is an unobserved regression that happens to be visible only
because this campaign named the path by hand. The conformance closure suite is the one
that proves real filing outcomes, which makes it a poor candidate for the tree's only
path-unreachable corner.

None of this campaign's own gates are among the findings. All five modules authored here -
the two collision gates, the lane screen, the constant gate and the canonical-definitions
gate - are lane-reachable, and `dev/quality/tests` is named by the justfile and by
`ci-full.yml`. That was checked rather than assumed, because the alternative was to author
five gates that nothing runs while writing an audit finding about tests that nothing runs.

A smaller contradiction sits beside it. That module's docstring states its location is
load-bearing, that it lives under `src/cadrumo/tests`, and that it must not be moved back
under `dev/`. It is under `dev/tests`, moved there deliberately by a relocation commit
that carried its lane and justfile consumers with it. The instruction now forbids the state
the tree is in, which is the same class of defect as an annotation that promises what the
function stopped doing.

### campaign-removed-its-own-duplicate-check | low | A reachability assertion duplicating a stronger per-test gate was deleted rather than defended

The previous finding established that the lane-visibility screen written here overlaps a
stronger gate. Acting on that was the test of whether this campaign's rule applies to its
own output, and the answer had to be more precise than deleting the screen or keeping it
whole.

The overlap was verified rather than assumed. Every lane's marker expression was read from
the justfile, and each requires at least one execution marker; the project's marker
contract requires exactly one of `unit`, `integration` and `aeat_live`. So a module
carrying none is selected by no lane, and the reachability gate catches that per test,
which is strictly finer than the module-level verdict written here. The screen's sharpest
class added no detection value.

That assertion is deleted. What remains is the part the gate has no reason to answer:
given a module that IS reachable, why did the default lane not select it. A green
reachability gate is silent on that, and it is the question behind a run reporting three
passing tests over a file holding twenty-four. The screen's docstring now names the gate
as the authority so a later reader does not mistake the weaker instrument for the stronger
one.

The distinction matters because the same tree argues the other way elsewhere, and
correctly. The reachability gate deliberately keeps a cheap path-level check beside its
per-test one, because the per-test question is blind to a module holding no test functions
at all, and it records that dropping the weaker check would be "a regression wearing a
consolidation's clothes". Overlap is justified by distinct detection value and by nothing
else. Here there was none, so the overlap went.

### location-note-forbade-the-move-already-made | medium | A load-bearing docstring insisted on a directory the module had deliberately been moved out of

That gate's docstring stated its location was load-bearing, that it lived under
`src/cadrumo/tests`, and that it must not be moved back under `dev/`. It sits under
`dev/tests`, moved there deliberately by the full-corpus collectability relocation, which
carried its lane and justfile consumers with it. The note was not describing a constraint
the tree honoured; it was forbidding what had already been done, which is the same defect
class as the return annotation that went on promising what its function had stopped
checking.

The note now records the requirement rather than the address: what is load-bearing is
reach, not a particular directory. Measured from where the module actually is, `dev/tests`
is named by five justfile recipes and four workflow invocations, and the note asks the next
mover to count the lanes naming the destination and confirm the number does not fall. The
reasoning that made the original worth writing is preserved; only the claim that had become
false was replaced. Twenty-six tests pass and three fail exactly as before the edit, so the
change is behaviour-neutral and was shown to be.

### conformance-suite-omitted-from-every-recipe | critical | Three sibling registry directories are named by the dev tooling lane and the conformance one is not

The previous finding reported two conformance files sitting outside every lane's path
scope. Measured precisely, the situation is worse than a path-scope curiosity and simpler
to fix than it looks.

Across the tree, 170 tests are unreachable by any CI-invoked lane. Ninety-seven of those
carry a marker declaring a precondition a headless runner genuinely cannot satisfy, which
is the only excuse the reachability gate accepts. Seventy-three carry no such marker and
are therefore unexplained, concentrated in three subsystems: 39 in the TUI, 18 in
packaging, and 16 in the registry.

The registry's 16 are exactly the two conformance files - 9 tests in `test_closure.py`
and 7 in `test_real_closure_outcomes.py`. They carry `unit` and `hex_core` and nothing
else. There is no absent precondition, no heavy external tool, no credential store: they
are ordinary unit tests that no lane happens to name.

The omission is a single path. `dev/registry/tests`, `dev/registry/newmodelo/tests` and
`dev/registry/aeip/tests` are all named by the dev tooling recipe;
`dev/registry/conformance/tests` is named by no recipe and no workflow. One directory in a
list of siblings.

This bears directly on how this audit has been reading its own measurements. The single
failure in `test_real_closure_outcomes.py` has appeared in every lane run recorded here and
was each time attributed to inherited baseline. That attribution was true and incomplete in
the way that matters: the test is not a known-failing member of a suite CI watches, it is a
failing member of a suite CI has never executed. The conformance closure tests are the ones
that prove real filing outcomes against the live registry, which makes them the worst
candidates in the tree for that status.

The remedy is deliberately not applied here. The change belongs in the justfile, outside
this iteration's scope, and it is exactly the kind of one-line edit that should be made by
someone who can watch what turns red when sixteen previously unrun tests begin running -
at least one of them will, because one of them is failing now. The Step naming it is left
open rather than closed, because reporting a remedy is not performing it.

A marker would also silence the gate, and it would be the wrong fix. The gate's own text
refuses it: the only accepted excuse is a precondition genuinely absent from a runner, and
"nobody wired a lane" is explicitly not on the list. Marking these tests CI-incapable would
convert a wiring omission into a permanent exemption and lose the finding entirely.

### the-unrun-conformance-suite-is-fifteen-green-one-red | high | Run by hand: fifteen pass and one fails, and a later collection error was another writer's mid-edit state

Running the two conformance files by hand, so that whoever wires the lane knows the red in
advance: 15 pass and 1 fails, the failure being
`test_real_live_filing_success_cannot_invent_a_complete_source_limb` - the same test this
audit has been carrying. Eight minutes of wall time. That is the state the lane will
inherit on the day it starts naming the path.

A second measurement taken minutes later reported something different and alarming: a
collection error, `NameError`, only 7 of the 16 tests collected. Read at face value it
would have entered this audit as a conformance-suite defect, and it is not one.

The chain is `test_closure.py` to `conformance/authorities.py` to
`source_connectivity/live_proof.py` into the CLI package, and it terminates in
`entrypoints/cli/config/_spec_policies.py`, which uses `CommandWriteRoute` and
`CommandWriteRouteValue` before importing them. Both names exist and are canonical in
`command_spec.py`. The file carries a pending diff: it is another writer's uncommitted,
mid-edit state, and the concurrent campaign is collapsing three spellings of that concept
into one. The error name even changed between two consecutive collections, which is what a
file being typed into looks like from the outside.

So the conformance suite is not broken; the tree was momentarily unimportable through the
CLI, and anything importing the CLI would have shown the same face. The first run collected
all 16 because it began before the edit.

Two things worth keeping from this. A measurement taken in a shared worktree is a statement
about a moment, and the only defence is to notice when a result changes shape between two
runs and to find out why before recording either. And the rule against touching a file with
a pending diff earned its keep here in the plainest way: the fastest path to a green
collection was to add one import line to `_spec_policies.py`, which would have written into
the middle of another writer's unfinished edit and, at best, produced a conflict they would
have had to unpick.

### static-closure-and-real-load-answer-different-questions | high | A closure states what a load can reach and sys.modules what it did; the test demanded they be equal

The load census asserted that every registry module its import graph says a load imports is
present in `sys.modules` after the authority has loaded. It failed on exactly one module,
`_withholding_rows`, and the open Step asked which of two remedies applied: exclude
function-scoped edges from the closure, or hoist the deferred import that causes the
disagreement.

Neither, as posed. The code decides it. `_withholding_rows` imports `withholding_bindings`
at module level, and `withholding_bindings` imports `_withholding_rows` from inside
`resolve_withholding_binding_row_values`. That is a cycle, and the function-scoped import
is the standard break. Hoisting it restores the cycle, so the second remedy does not exist,
and the first would have silently narrowed what the closure means without saying so.

The real defect was the assertion. A closure built from an import graph states what a load
can REACH; `sys.modules` states what it DID import. Those are different questions and the
test demanded they be equal, which no amount of graph tuning makes true while a legitimate
cycle break exists. This is the same shape as `record_drift` comparing bytes where it meant
meaning, and as the module that answered two contracts under one name: one word, two
questions.

The claim is now the sharper one it should always have been. The difference between reach
and load must consist exactly of deferred edges: every module the graph reaches and the load
did not import must have no module-level importer at all. A new helper,
`module_level_importers`, answers that by walking module-scope statements and descending
into `if` and `try` blocks - which execute on import - while stopping at function, method
and class bodies, which do not.

It discriminates, and that was checked in both directions rather than assumed:
`_withholding_rows` has zero module-level importers, and a control module in the same
package has 115. So a module that vanishes for any other reason - deleted, renamed, dropped
from the load path - still fails the test, which is the detection it existed for. The
module's failures fell from two to one, and the survivor is the twenty-one unclassified
modules belonging to the concurrent rename, left where they are for the reason already
recorded.

### monetary-scale-gated-before-emission | medium | 3,385 decimal fields all declare a scale, pinned by a gate that refuses at declaration not at render

Two wire types carry money through the export boundary. `money` is self-scaling: the codec
renders and parses it at two decimal places without consulting the declaration. `decimal`
is not, and `_require_decimals` demands the value from the field.

The codec already refuses an undeclared scale, so the invariant was not unprotected. It was
protected at the wrong moment. The refusal fires when that particular field is rendered or
parsed, which means a revision can compile, validate, ship and sit in the registry with the
defect latent until something reaches the field. Given that this audit's original monetary
finding was a field emitting at the wrong magnitude in a revision currently in force, "it
fails when someone touches it" is not where this check belongs.

Measured across the corpus before the gate was written, because a gate authored against an
unknown state is either red on arrival or unproven: 18,231 export fields, of which 3,385 are
`decimal` and 4,028 are `money`. Decimal fields declaring no scale: zero. The invariant holds
today, so the gate lands green and pins it.

Three tests rather than one. The invariant itself; a constructed field with its scale
stripped, so the gate is shown able to report the condition rather than only ever having
seen a clean corpus; and a check that both wire types are actually present, so a corpus that
stopped declaring monetary fields could not satisfy the invariant by emptiness. That third
one exists because this campaign has now twice recorded a green result that had selected
nothing.

The Step that authors missing scales stays open and is registry data. Nothing needs
authoring today, which is what the measurement established.

### operator-path-committed-in-a-sibling-audit | high | A committed vault document carries an absolute path under a named user's home directory

The full lane surfaced a privacy gate failing on
`2026-08-27-calculation-correctness-campaign-restrictive-default-sweep-audit.md`, which
carries an absolute path under a named user's home directory including an agent job
identifier. Committed vault text is shipped text, and the gate's own message is right that
host, login and path data must not be in it.

It is another campaign's document and is reported rather than edited. What was checked here
is the obligation this campaign owns: the audit and plan for this feature carry zero
operator-identifying tokens, verified by search rather than assumed. A finding about leaked
paths written in a document that leaks paths would be worth very little.

### retired-audit-command-models-removed | medium | 279 lines of ratchet apparatus with no importer, whose only external reference was a docstring bullet

The conformance manager carried a ratchet apparatus for a command that no longer exists:
`ConformanceRatchetCeilings`, `ConformanceProgressFloors`, `ConformanceVacuityFloors`,
`ConformanceBaseline` and `ConformanceAuditResult`, together with `render_audit` and the
three `_current_*` helpers that fed it. 279 lines of a 1,781-line module, now 1,502.

The deletion was worth making carefully, because a crude scan would have got it wrong in
both directions. A substring search over the tree reported these symbols as referenced,
which they are - by other modules named `manager` that define unrelated symbols the same
scan happened to match. An import-based scan reported the module's own internal uses as
external. What settled it was asking the question exactly: word-boundary matches for each
class across `dev/`, `src/` and `tests/`, then the same for every function referencing them.

All four models had zero references outside the module. `render_audit` and the three
helpers had zero. `ConformanceAuditResult` had exactly one, and it was a docstring bullet
in the package initialiser describing "the ratchet comparison against the committed
baseline" - prose about an apparatus nothing invoked. That line is removed too, because a
reference surviving its subject is how the next reader learns to look for something that
is not there.

Non-code references were checked before deleting rather than after: no TOML, JSON, YAML,
justfile or workflow names any of it, so nothing reached the cluster dynamically.

All six were listed in `__all__`, which is the detail worth keeping. The module declared
this apparatus as its public surface and no consumer had ever imported it. An export list
is a claim about what callers need, and this one had gone on asserting a need that ended
when the command was retired - the same shape as the annotation promising what its function
stopped checking, and the location note forbidding the move that had already happened. This
audit has now recorded that shape four times in different materials.

Verified after: the module imports and declares 23 public symbols, lint and format are
clean, and the conformance suite runs 18 tests with 17 passing. The single failure is the
pre-existing one in `test_real_closure_outcomes.py` that no CI lane executes, unchanged by
this deletion.

### development-vocabulary-restated-the-applications | medium | All seven application refusal reasons were copied rather than composed, so an eighth would never arrive

The development closure module already imports from the application's closure module, and
then declared its own refusal-reason alias listing twelve values. Compared against the
application's seven: all seven appear in the development list verbatim, and five are
genuinely new - the temporal-coverage reasons that exist only on this side of the boundary.
Nothing was production-only. The development vocabulary was a strict superset built by
copying.

The failure mode is quiet and one-directional. An eighth reason added to the application
would simply not reach this alias, and nothing would report it: the copy stays valid, keeps
validating, and silently means less than the thing it shadows. That is the same shape as
the load classification that survived neither side of a rename, and it is why this campaign
treats a second declaration as the defect rather than the disagreement it eventually causes.

The alias is now composed rather than restated - the application's alias unioned with the
five reasons that are actually local. The seven shared values have one declaration, and an
addition on the application side arrives here automatically.

Verified behaviourally rather than by introspection, and the first attempt to check it was
wrong in an instructive way. Reading the union's arguments reported two reasons rather than
twelve, because a union of an alias and a literal does not flatten. The type was correct
and the measurement was not. Constructing the model with each of the twelve reasons in turn
accepts all twelve, and an invented reason is still refused, which is the property that
actually matters.

The Step asking for this module to carry no predicate at all stays open. What moved here is
the vocabulary, not the four predicate functions, and those belong on the application side -
work this iteration's scope does not reach. Recording the difference matters more than the
tidier claim: the duplication is gone, the relocation is not done.

### constants-orphaned-by-this-campaigns-deletion | low | A deletion left three module-private constants referenced by nothing, found by a sweep that should have run first

Removing the retired audit command's models left `_BASELINE_FILENAME`,
`_DEFAULT_REVIEW_CADENCE` and `_RECORD_COMMAND` referenced by nothing, each with a comment
describing an artefact the module no longer produces. They are gone, with their comments,
bringing the module to 1,489 lines from the 1,781 it started at.

They should have gone in the same change. A deletion that leaves its own residue is the
thing this campaign keeps finding in other people's work, and the check that caught it - a
sweep for module-private names with zero remaining references - took one command and should
have run before the first edit was reported rather than after. No committed baseline
artefact exists on disk and nothing else references one, so there is no data residue behind
the constants.

### composed-vocabulary-gate-overclaimed-its-teeth | medium | The gate detects staleness, not the act of copying, and its first docstring claimed otherwise

Composing the development refusal vocabulary from the application's removes today's
duplication; it does not stop someone re-listing the values tomorrow. Three tests now hold
the composition: that the application vocabulary is contained entirely, that what the
development side adds is exactly the five temporal-coverage reasons, and that every locally
owned reason carries a work item so a refusal names the work that would resolve it.

The first version of that gate's docstring claimed re-listing the shared values as literals
would be caught by the containment check. It would not, and the error was mine, written
while describing my own change. Re-listing today leaves all seven values present, so
containment passes. What the gate actually detects is staleness: the moment the application
adds an eighth reason, a copied list stops containing the vocabulary it claims to extend.

The docstring now says that, because the weaker true claim is more useful than the stronger
false one. A copy that is currently identical is harmless; a copy that has fallen behind is
the one that silently means less than the thing it shadows, and that is the condition worth
gating. The containment logic was exercised against a vocabulary with one application reason
removed, which fails and names the missing value, so the check discriminates rather than
being satisfiable by anything.

A helper flattens the composed alias, and it exists because of the mistake recorded in the
previous finding: a union of an alias and a literal reports two members rather than twelve
under a naive read. Putting the flattening in one place means the next reader inherits the
correction instead of repeating it.

The tests sit in the conformance test directory, which is the narrowest directory owning the
module under test and also the directory no CI lane names. Placing them where they would run
was available and was not taken: distorting test location to route around a wiring omission
would hide the omission, and the open Step that fixes the lane is the honest remedy.

Separately, the closure suite was re-run after the vocabulary change and reports 15 passing
with the single pre-existing failure, unchanged.

### private-import-step-named-the-wrong-surface | medium | Eleven violations run from dev into src, not out of dev/registry/pipeline as the Step described

The Step asking for promotion of privately-reached modules described a handful under
`dev/registry/pipeline` reached by fourteen non-test consumers. Remeasured, the direction is
the other way round and the surface is different.

There are eleven non-test cross-package private imports reachable from `dev/`, and every one
of them is a development module reaching into `src/`: six into `cadrumo_harness.mcp` from a
single benchmark, two into `cadrumo.domain.calculations.registry`, one into
`cadrumo.entrypoints.cli`, and two into `cadrumo.application.modelo`. Nothing reaches into
`dev/registry/pipeline` at all. The eleven test-side imports are left alone, as the Step
always intended.

Two forms, and the second is the quieter one. Most violations import a module whose name
begins with an underscore. But `live_proof.py` imports `_require_calculation_route_resolver`,
`_source_bound_casilla_inputs` and `_source_provenance_refs` from `calculation_actions`,
which is a perfectly public module. A private name reached through a public module is the
same breach with nothing in the import path to signal it, and it survives a reader skimming
for leading underscores in module names.

The Step has been corrected to name `src/cadrumo` and `src/cadrumo_harness` and left open,
because the remedy is a promotion on the application side. Editing the Step rather than
closing it matters: a Step whose description no longer matches the tree is worse than an
open one, since the next person to pick it up would look under `dev/registry/pipeline` and
find nothing wrong there.

No gate was added, and deliberately. The existing production gate holds this invariant at
zero over `src/cadrumo` with detector teeth and no exemption list, and its own text explains
why it carries no baseline: a hand-maintained list of accepted violations is how 114 became
270. Extending the same gate over `dev/` today would land red at eleven, and the only ways to
make it green are to fix the eleven, which is out of this iteration's reach, or to baseline
them, which is the practice that gate exists to refuse. Measuring and recording is the honest
middle, and the Step carries the work.

Worth noting in that gate's favour: it asserts its scan reaches more than ten thousand import
sites, so a scan that silently found nothing cannot report zero violations. That is the same
defence this campaign built after twice recording a green result over an empty selection, and
it was already there.

### campaign-authored-a-duplicate-step | low | A timed-out add had succeeded; the retry created a second identical Step that then absorbed a closure

A `step add` in the previous iteration exceeded its timeout and was reported as incomplete.
It had in fact succeeded in the background, and the retry created a second Step with
identical action text and identical scope. S187 and S188 were one Step declared twice.

It surfaced by accident. The next `step add` returned S189 rather than the S188 expected, and
that one-off discrepancy was the only signal; the plan rendered perfectly well with both
rows, and a reader would have seen two gates where one exists. The closure I then applied
went to S188, the duplicate, leaving the real new Step open - so the duplicate had already
begun absorbing work intended for something else, within minutes of being created.

S188 is retired through the owning verb, which retires the identifier permanently rather than
reusing it, and the one surviving row is S187. The count is 126 closed of 187.

The lesson is the one this campaign has been applying to other people's declarations all
along, and it cost nothing to learn here only because the identifier sequence happened to
expose it. A tool reporting a timeout is not reporting a failure: it is reporting that it
stopped waiting. Every retry of a mutating command needs the same question asked first that
this campaign asks of every measurement - did the thing already happen - and the answer is
one read of the document, which is cheaper than the duplicate.

### publication-limb-had-no-caller-because-inputs-had-no-name | medium | Seven values were assembled inside a comparison, so any second consumer had to re-derive them

`publish_validated_generated_export_tree` takes seven assembled values and is reached by
nothing but its own tests - confirmed again here, with the only other mention being a test
asserting a different module does not reference it. The plan recorded this as a limb that
exists and cannot be reached, and asked for an invocable entry point.

The reason it had no caller is more specific than "nobody wrote one". Those same seven values
were assembled inside `compare_revision_against_committed`, seventy-four lines deep in a
function whose declared purpose is to compare. Anything else needing them had two options:
call the comparison and throw the comparison away, or derive them again. The second is how a
second derivation gets written, and this audit has spent a campaign on what happens when two
derivations of one fact drift.

The assembly is now `revision_render_inputs` returning a named `RevisionRenderInputs`, and
the comparison consumes it like any other caller. That does not by itself publish anything;
it removes the reason a publication entry point could not be written without duplicating the
derivation.

Behaviour was checked to be identical rather than assumed. Both screened revisions report
byte-identical summaries to before the extraction - modelo 303 at zero record drift with nine
serialization-only differences, modelo 347 at one record drift - and the two owning suites
run 22 tests with 21 passing, the single failure being the disposition gate that is failing
deliberately.

The Step stays open. It asks for an entry point and for two enrolled trees to be published,
and publishing writes filing data into the registry. Building the capability is development
work; exercising it against shipped filing data is the decision of whoever owns those trees,
and this campaign has already recorded that the twenty-five stale attestations are theirs to
resolve. The missing half is now available to them rather than blocked behind a derivation
that lived inside a comparison.

A note on attribution. While the extraction was being verified, the harness reported two
continuity modules as modified by the command that ran the screen. They were not: both carry
pending diffs from the concurrent writer, neither contains any reference to the screen, and
the command has no write path to them. A timing coincidence read as causation would have put
another writer's edits into this campaign's record.

### derivation-publication-seam-is-gated | medium | A gate asserts the derived inputs still supply every revision-describing value publication needs

Naming the render inputs removed the reason a publication caller had to derive them again.
It did not stop the two halves drifting apart afterwards, which is a different failure and
the one that would put the second derivation back.

Publication takes six values. Two are its own concern - the target context and the rendered
tree. The other four describe the revision and must come from the validated authority, and
those four are exactly what the derived inputs carry. A gate now asserts that containment,
so a seventh revision-describing parameter on publication, or a field dropped from the
derivation, fails rather than quietly forcing the next caller to derive its own.

The check discriminates in both directions and that was demonstrated rather than asserted: a
hypothetical seventh parameter fails and names it, and a derivation missing `semantic_map`
fails and names that. A companion test pins that the signature being read is real - at least
six parameters including the two publication-owned ones, and at least four derived fields -
because a signature read as empty would make the containment vacuously true. That defence is
now standard in this campaign's gates for the reason it keeps earning: a check over nothing
reports success.

The suite runs 19 tests, all passing.

### pending-diff-rule-caught-a-file-that-changed-hands | medium | A diff assumed to be this campaign's was another writer's, because the earlier edits had been committed

The natural home for this gate was the render-check test module, and it carries a pending
diff. The reflex answer was that the diff was mine, since this campaign edited that file
earlier. Reading it showed otherwise: four inserted lines repointing an import, and none of
the semantic assertions written here. Those had already been committed by the concurrent
campaign's tree-wide sweep, so the file's uncommitted state belongs to another writer
entirely.

The gate went into the publication test module instead, which is the better home anyway - the
seam it guards is publication's - and which was verified clean first. The rule earned its
keep for the second time in three iterations, and the specific lesson is narrower than the
rule: "I edited this file recently" is not evidence that the current diff is mine, in a
worktree where another writer commits across the whole tree. The diff has to be read.

### two-of-this-campaigns-gates-could-pass-over-nothing | high | The empty-population defence this audit argues for was met by three of five gates written here

This audit has argued repeatedly that a check over an empty population reports success, and
has recorded twice that a green result had selected nothing. Turned on the gates written
here, the standard was not being met by two of the five.

The disposition gate compares the census against the file and was safe only by accident: the
file carries nine rows, so a census that silently returned nothing would fail loudly against
them. That safety is a property of the file's current contents, not of the check. Both sides
emptying together - a census that breaks and a file someone clears - would leave an equality
between two empty sets, passing while asserting nothing. A check that works only while
somebody remembers not to empty a file is not a check.

The lane-visibility screen had no population assertion at all. A scan reaching nothing would
have reported a clean tree in exactly the same way it reports a genuinely clean one.

Both now assert their population before asserting their invariant, and the thresholds were
set against measured reality rather than picked: 4,462 public definitions against a floor of
500, 101 classified modules against a floor of 50, and a requirement that the same-layer
census be non-empty at all, which it is at nine. Wide enough that ordinary movement in the
tree will not trip them, narrow enough that a scan that stopped reaching the tree will.

The other three already carried the defence, which is worth stating because it means the
standard was being applied unevenly rather than not at all - and unevenly is the harder
failure to notice. The five gates now run 28 tests, all passing.

Worth naming plainly: every instance of this defect that this campaign has reported in the
tree - the annotation that stopped describing its function, the location note forbidding the
move already made, the export list naming a retired surface, the copied vocabulary - had the
same shape as this one. The difference here is only that the author and the auditor were the
same person, which is the case where it is least likely to be found.

### empty-filing-export-proof-refuses-rather-than-passes | medium | Zero enrolled vectors, and a declared layout is refused as missing evidence rather than read as proven

The plan recorded that the filing export proof carries zero enrolled coordinates, so no
exported byte has ever been checked against an official record design. That is true, and the
Step asked for vectors to be loaded from registry data instead of the empty canonical tuples.

The emptiness turns out to be deliberate, documented and, more importantly, load-bearing in
the right direction. Both tuples carry a comment saying so: an empty live-proof authority is
"an honest authority with no successful entries; it is not permission to infer proof from
layouts", and empty vectors "yield typed per-channel refusals; they are never treated as a
waiver or proof". Comments are only a claim, so the behaviour was checked. A test takes a
real revision that declares an export layout, composes coverage against the real empty proof
authority, and asserts the limb comes back refused with reason `missing_evidence` and a
disposition naming an owner, a work item and a reconsideration condition.

That is the distinction this audit has been drawing since its first pages, and here the tree
gets it right: a declared layout does not become emitted-byte evidence because nothing
contradicts it. Missing proof stays missing and says whose job it is.

So the Step is not blocked on plumbing, and describing it as loading vectors from registry
data understated what it needs. A conformance vector asserts what official bytes look like,
and this project's own grounding rule refuses expected values derived from the implementation
under test. Authoring vectors requires official record-design examples as the source; without
them the only way to make the tuples non-empty is to invent the thing they are supposed to
prove. The Step has been rewritten to name official examples as the input and left open.

Recording this as a correction rather than a discovery: the hole is real and unchanged, and
what changed is that the plan now says what would fill it.

### closure-test-repair-is-blocked-behind-vector-enrolment | high | Rewriting onto the two-channel authority changes what the test fails on, because the vectors are empty

The one conformance failure this audit has carried throughout fails with an
`AttributeError`: the modelo 151 test builds `LiveFilingExportProofAuthority` and the closure
report calls `assess_for` on it, which that class does not have. Its Step names the repair -
rewrite the test onto the two-channel authority and delete the single-channel one - and the
repair does not work.

The single-channel class is not a peer of the two-channel one. It is the two-channel
authority's own internal verifier, constructed inside it with an empty entry tuple, so
"delete it" is a restructuring of the class that uses it rather than the removal of a
displaced alternative.

More decisively, the rewrite changes what the test fails on. The two-channel authority was
built against the live registry and asked for the same coordinate, and it returns no proof:
the conformance channel refuses with `evidence_missing`, because the canonical vector set is
the empty tuple recorded in the previous finding, and the secure-replay channel refuses with
`authority_unavailable`. The test asserts a satisfied filing-export limb. No arrangement of
the two-channel authority produces one while there are no vectors.

So the failing test is downstream of the missing filing evidence, and both are downstream of
official record-design examples this campaign cannot author. That ordering is now in the
plan's parallelization section, where the three previously discovered constraints already
live.

The workaround was available and is worth naming so that it stays refused. Stubbing the
conformance channel, or asserting the refusal instead of the satisfaction, would turn this
suite green today. It would also convert a real absence of filing evidence into a passing
test, in the one suite whose subject is whether real filing outcomes can be proven. The
failure is more useful than the green would be, and it is the second time in this campaign
that the honest move has been to leave a test failing and say precisely why.

### crashed-worker-reported-as-a-failing-test | high | A summary line was trusted over the log beneath it, and the run's results were unusable

The filing suites were run and reported "1 failed, 7 passed", and that was recorded here as a
failure. Reading the log rather than its summary line shows something different: worker
`gw1` crashed while running the named test. The test did not fail an assertion. It stopped
existing, along with however many tests were queued behind it on that worker.

The tree says so itself, loudly, and the warning was in the output that was skimmed. A
session hook prints that the counts describe only what came back, that a dying worker takes
its remaining tests with it and they are not redistributed, and that the failure list must
not be read as the set of things wrong because it is a subset of unknown size. The
configuration backs it with `--max-worker-restart=0`, which makes a worker death terminal
rather than silently retried.

So the correct reading of that run is not "one test fails". It is "this run's results are
unusable, and the affected path must be re-run serially" - which the hook states in plain
words and which is now being done. The number of tests that never ran is not knowable from
the log.

This is the same error this campaign has documented in other people's work all campaign, in
its most literal form: a summary line was trusted over the evidence beneath it. The specific
habit that failed was the one already established here for exit codes - never read the
wrapper's status, read the tool's own - and it does not go far enough. An exit code and a
pass/fail tally are both summaries. When a run reports a failure, the failure's own text
decides what happened, and a crash reads nothing like an assertion.

Two things stand undamaged. The empty-proof refusal recorded in the previous finding was
established by reading the code and its test, not by that run. And this campaign's own five
gates were re-run against the concurrent campaign's latest commits and pass at 28 tests.

### campaign-runs-swept-for-lost-worker-markers | low | Eight runs carrying this audit's figures were re-read for crash markers and none carries one

Having recorded a crashed worker as a failing test, the obvious next question is how many of
this audit's other numbers were taken from runs with the same defect. Every lane and suite
run whose figures appear in these findings was re-read for the three markers a lost worker
leaves: `node down`, `crashed while running`, and the hook's own `subset of unknown size`.

Eight runs, zero markers. The three full-lane measurements that carry this campaign's
headline numbers - 46 failures, then 36, then 36 against 978 passing - are clean, as are the
conformance, declaration-gate, publication and generated-tree runs. The detection was
confirmed against the one run that did crash, which carries three markers, so a zero here
means the marker was absent rather than the check being blind.

One integrity check was attempted and does not conclude, which is worth recording as
carefully as the one that did. Comparing a run's reported total against a fresh collection
would catch tests that vanished, and the lane path now collects 1,090 where the run reported
1,014. That gap is not evidence of loss: this campaign and the concurrent one have both added
tests since, and the tree is not the tree that run measured. A comparison against a moved
baseline answers nothing, which is a lesson this audit recorded early about type-check
burndowns and had to relearn here in a different material.

The method changes accordingly. A run's own log must carry its collected count, so the
comparison is between two numbers from the same invocation rather than between a remembered
number and a later tree. Until then the crash-marker sweep is the available integrity signal,
and it is a check on the run rather than on the result, which is the weaker of the two things
worth knowing.

### measurement-integrity-criterion-added | low | Four measurement failures that all looked like success are made an acceptance term of the plan

Four of this campaign's measurements failed in ways that all looked like success: a suite
reporting three passing tests over a file holding twenty-four, a gate comparing two sets that
could both be empty, a crashed worker reported as a failing test, and a comparison against a
remembered total taken from a tree that had since moved. Those are not four accidents of the
same author being careless. They are four shapes of one defect, and a plan whose entire
subject is declarations that stop matching what they describe should say so in its own
acceptance terms.

The plan now carries an eleventh criterion requiring that every measurement it rests on names
its population, that every gate refuses to pass over an empty one, that a run's collected
count comes from the same invocation as its result, and that a reported failure is read from
its own text rather than a summary line - because a crash and an assertion are different
events that a tally spells identically. The criterion is met by evidence rather than
assertion: all four failures are recorded here with what they cost, the gates now assert
measured floors, and every run quoted by this plan has been swept for lost-worker markers.

Separately, a state check worth having done. Every file this campaign authored or edited has
been committed by the concurrent campaign's tree-wide sweeps, except one - and that one's
pending diff is theirs, not this campaign's: forty-five lines adding a bootstrap transport
identity, built on top of the render-input extraction recorded two findings ago. The
extraction was made so that a second consumer would not have to re-derive what the comparison
derives, and a second consumer is now being written against it.

That is the more useful confirmation than any test result. A seam is justified by something
arriving to use it, and one has.

### serial-rerun-shows-the-test-passes | medium | Three collected, three passed: the parallel run's failure was the crashed worker and nothing else

The filing acceptance suite was re-run serially, as the lost-test hook instructs. Three tests
collected, three passed, exit status zero. The test this audit briefly recorded as failing
does not fail. The parallel run's "1 failed, 7 passed" was the crashed worker and nothing
else, which is precisely what the hook's warning says such a line means.

Two conclusions, and the second is the durable one. The filing acceptance path is green and
this campaign's residual failure list loses an entry it never should have gained. And the
hook's instruction is worth following the first time: it named the remedy exactly, the remedy
took one command, and the ten minutes it cost bought a correct answer in place of a wrong one
that had already been written down.

### feature-health-warning-belongs-to-another-writer | low | Three body-section warnings fall on an untracked scaffold created under this feature's tag

The feature's body-section check reports three warnings, and none of them are against this
campaign's documents. They fall on an audit scaffolded under this feature's tag for a modelo
200 publication review, whose Scope, Findings and Recommendations are still template
placeholders. The file is untracked, so it is a scaffold created and not yet written, and its
author is the concurrent campaign.

It is left alone. Filling those sections would mean authoring findings about a review this
campaign has not performed, under someone else's document, and a health check satisfied that
way is worth less than the warning it silences. The warning is accurate: the sections are
empty, and they should be, until whoever created it writes them.

Worth stating because the alternative is tempting when a shared feature tag makes another
writer's incomplete document look like this campaign's failing check.

### footnote-sizing-measured-an-absent-attribute | medium | A confident zero came from reading content off an object that does not carry it

The footnote-pointer correction is blocked behind authoring reviewed rules for whatever
fields it newly makes eligible, so the useful question is how many that is. The predicate
that decides eligibility admits three shapes today - a PDF anchor, a blank content cell, and
the single filing-instruction phrase - and the correction would add a fourth: a Contenido cell
holding only a footnote pointer.

The pointer shape was characterised first and discriminates correctly, matching `(1)`,
`(1)(2)`, `(*)` and a trailing-period variant while rejecting a real description and the
filing instruction. Run across three loaded designs it reported zero footnote-only cells in
all three, which would have been a clean and quotable finding.

It was wrong, and the check that caught it is the one this campaign now applies by habit:
before believing a zero, confirm the population is real. Of the 416 fields in the first
design, the number carrying any non-empty content at all is also zero. The `content`
attribute belongs to the record-design intermediate, and what was being read was the joined
result, where it does not exist. The pattern never had anything to match, so "zero
footnote-only cells" measured the absence of the attribute rather than the absence of the
condition.

No sizing figure is recorded, because none was obtained. The correct source is the
intermediate the design loader produces, and the measurement has to be taken again from
there.

This is the fifth time in this campaign a measurement has failed by looking like success, and
the first one caught before it reached a finding rather than after. That is the whole value of
the criterion added in the previous iteration: the habit cost one extra command and saved a
number that would have been quoted, believed, and used to argue that a correction had no
work behind it.

### footnote-sizing-retaken-from-a-real-population | low | 845 content cells actually read across four designs, and the zero now says something

The previous attempt read `content` off the joined design, where the attribute does not
exist. The second attempt read it off the intermediate and asked for `records`, which the
intermediate does not have either - and it printed `footnote_only=0` again on the way to the
error, which is the same meaningless zero arriving by a second route.

Introspecting the model rather than guessing at it gave the shape in one command: a
`RecordDesignIntermediate` carries `sheets`, and a `RecordDesignIntermediateField` carries
`content` alongside `source_cell`, `offset`, `length` and the rest.

Read correctly across four designs: 1,649 fields, of which 845 carry a non-empty Contenido
cell. Footnote-only cells: zero. Cells containing a parenthesised pointer in any form,
whether alone or beside descriptive text: also zero. The measurement now has a population -
845 content cells were actually read - so the zero says something.

What it says is bounded and the bound matters. Four designs is not the corpus, and the
condition the correction addresses is known to exist somewhere, or the Step would not have
been written. These four are workbook designs, and the predicate already admits every PDF
anchor unconditionally because a PDF design has no Contenido column at all; the footnote
shape can only bite where a workbook cell holds a pointer. So the honest reading is that the
condition does not occur in these four, not that it does not occur.

The full sizing needs every transcribed design, of which there are 7,777 files, and that is a
sweep rather than a spot check. What this iteration establishes is the method: read from the
intermediate, assert the content population is non-empty before believing any zero, and state
which designs were read.

Three attempts at one number, two of them producing a confident zero from an empty
population. The number was worth the trouble only because the third attempt can be checked;
the first two could not, and both would have supported the same wrong conclusion.

### bare-footnote-pointer-does-not-occur | medium | 20,776 content cells, 26 carrying a pointer inside prose and none consisting only of one

The four-design spot check has been replaced by a sweep of every record design the registry
can reach: 111 designs loaded, one refusing to load, 73,040 fields, and 20,776 carrying a
non-empty Contenido cell. That is the population the earlier attempts lacked.

Cells containing a parenthesised pointer in any position: 26. Cells consisting only of a
pointer: zero. Every one of the 26 carries the pointer inside descriptive prose - "se
cumplimentará una de las siguientes claves:(1) 'C': Si la..." - which is the design stating a
wire fact and citing a note about it, not deferring the fact to the note.

That puts the correction's premise in question rather than settling it. The Step asks to
refuse a bare footnote pointer as a stated wire fact, and in the designs the registry reaches
there is no bare footnote pointer to refuse. Three readings survive and the difference
matters: the condition may have been corrected since the Step was written, it may live in the
designs this sweep could not reach, or the original evidence may have been a cell of the kind
found here - a pointer inside prose - read as a bare one. The Step should not be actioned
until which of those it is has been established, and it should not be closed either.

One design refuses to load, `720/2013-y-siguientes`, with a registry validation error. It is
recorded rather than worked around: a sweep that silently skipped it would have reported a
clean corpus over 111 of 112 designs and called it all of them.

A scope slip worth recording plainly. The sweep script needed the repository root on its
import path, so it was copied there, run, and deleted in the same command; the working tree
was confirmed clean of it afterwards. The constraint on this work is dev and vault only, and
the repository root is neither. Nothing was overwritten and nothing persisted, but the
correct move was a scratch location with the path supplied to the interpreter, not a file
written beside the project's own.

### lane-measurement-reconciles-against-its-own-collection | low | 1,091 collected against 35 failed plus 1,056 passed, from one invocation and with no lost worker

The eleventh criterion asks that a run's collected count come from the same invocation as its
result. The first measurement taken that way reconciles: 1,091 tests collected of 1,125 with
34 deselected, and 35 failed plus 1,056 passed, which is 1,091 exactly. Nothing vanished
between collection and reporting, and the log carries no lost-worker marker. The exit status
is 1, from the tool rather than a wrapper.

That arithmetic is the whole point. Every earlier figure in this audit was a pass/fail tally
with no independent statement of how many tests were meant to run, so a lost worker or a
marker deselecting a module would have been invisible in the number itself. This one can be
checked by anyone reading the log, without trusting the person who ran it.

The residue stands at 35, one fewer than the previous full lane, and the change is
attributable: the load-census module reports one failure where it reported two, which is the
static-closure repair recorded earlier. The 27 generated-tree failures remain the stale
attestation from the concurrent campaign's serialization change, each naming one file. The
conformance closure failure remains the one no CI lane runs. The privacy failure belongs to
the sibling campaign's committed operator path.

Every remaining failure is attributed to a cause outside this campaign's reach or recorded as
deliberately left, which is a different claim from a green suite and a more honest one.

### step-scopes-appeared-stale-withdrawn | low | WITHDRAWN: all fifteen were correct, nine recording where work happened and six naming files to create

A sweep of the plan's own scope clauses finds fifteen naming a path absent from the tree.
Some are this campaign's own doing: the ledger-bindings module and the applicability-fragment
migrator were deleted here, and the Steps that scoped work to them still point at them. Others
predate it.

This is the plan committing the defect the plan exists to remove. A scope clause is a
declaration of where work lives, and fifteen of them describe a tree that is gone - the same
shape as the export list naming a retired surface and the location note forbidding a move
already made, now in the campaign's own tracking document. It is recorded here before it is
repaired so that the repair is not mistaken for the discovery.

### stale-scope-finding-withdrawal | medium | The check measured file existence and never asked what a scope clause is for

The previous finding reported fifteen Step scopes naming files absent from the tree, called it
the plan committing the defect the plan exists to remove, and promised a repair. There is no
defect. The finding is withdrawn.

Splitting the fifteen by Step state is what settles it, and it was not done before the claim
was written. Nine belong to closed Steps. A closed Step's scope records where the work
happened, and some of that work was deletion - the ledger-bindings module and the
applicability-fragment migrator were removed by this campaign, so a scope naming them is
accurate history rather than a dangling pointer. Repairing those would have erased the record
of what was touched.

The remaining six belong to open Steps, and every one names a file the Step exists to create:
"author the conformance vector for the modelo 303 revision" scoped to the vector file, "record
the satisfied filing-coordinate set as registry data" scoped to the TOML that would hold it,
and four tests scoped to the modules that would prove them. For creative work a scope names a
destination. A destination that already existed would be the thing worth questioning.

So the check was measuring file existence and calling absence a defect, without asking what
the scope was for. It is the same failure this audit has now recorded five times in
measurements - a number produced without establishing what it counts - and this is the second
one caught, though later than the last: it had already been written into a finding and
described as a defect in the campaign's own document before the split was run.

What the episode leaves is a narrower true statement. Nothing in the plan's scope clauses is
known to be wrong, and a check that would detect a genuinely stale scope has to distinguish a
path the work will create from one it once touched, which file existence alone cannot do.

### modelo-720-opening-year-makes-its-design-unloadable | high | valid_from 2012 against a design applying from 2013 leaves one design no sweep can read

The corpus sweep reported one design refusing to load. Diagnosed, it is
`720/2013-y-siguientes`, and the refusal is precise: the record-design source `aeat-dr-720`
does not apply to filing year 2012.

The numbers behind that are worth setting out. The revision declares `valid_from`
2012-01-01 and a period selector opening in 2012. Its only record-design source declares
epoch 2013 and applies from 2013-02-01. The revision's own name says 2013.

The revision-name screen written earlier in this campaign already flags this exact revision,
independently, as `name_misstates_opening` - "name claims 2013; valid_from declares 2012". So
two instruments built for different purposes agree on one revision, and both point at the
same field. That agreement is what raises this above a curiosity: a name screen and a design
loader have no shared code path, and the second turns the first's finding into a consequence.

The consequence is that one design in the corpus cannot be read at all. Every sweep this
campaign has run is over 111 designs, not 112, and the fields in the missing one are invisible
to all of them - including the footnote sweep whose result was recorded two findings ago.

Whether the data is wrong is genuinely open, and this is the interesting part. Modelo 720 is
the informativa on assets held abroad, first filed in 2013 for exercise 2012. Read as a tax
year, `valid_from` 2012 is correct and the design's February 2013 date is a filing date on a
different axis, in which case the loader is comparing two quantities that were never
comparable. Read as a legal opening date, the revision is wrong and the name is right.

That is the temporal-axis question this plan's migration Step exists to settle, and it now has
a live instance with a measurable cost rather than a general argument. Nothing is corrected
here: choosing an axis for modelo 720 is a filing-grade decision about what `valid_from`
means across the registry, and this campaign has no authority to make it by guessing which
reading keeps a loader quiet.

### four-misstated-openings-are-three-defects | medium | Two names to correct, one declaration to author, one axis decision to take

The revision-name screen reports four revisions whose name claims an opening year their
window does not declare. Read against the declarations themselves, they are not four
instances of one problem.

Two are plain naming errors with no coverage consequence. Modelo 185's
`2025-y-siguientes` declares `valid_from` 2026-01-01 and a selector opening in 2026, while
its sibling `2003-2025` runs through 2025 - so coverage is continuous and the revision is
simply named a year early. Modelo 151's `2025-y-siguientes` declares `valid_from` 2023-01-01
and a selector opening in 2023, while `2015-2022` ends in 2022 - again continuous, and the
name is two years late. Both were confirmed against the live authority: filing years 2023 and
2024 admit the revision named `2025-y-siguientes`, which is the name misleading a reader about
work the registry performs correctly.

Modelo 322 is a different defect wearing the same label. Its `2008-2022` declares `valid_from`
2022-01-01 and a period selector carrying neither `year_from` nor `year_to`, while all three
of its siblings carry explicit bounds. The name asserts a fourteen-year span; the window opens
in the last of those years; the selector declares nothing at all. That is under-declaration
rather than misnaming, and the name is the only place the fourteen years are stated.

Modelo 720 is the axis question recorded in the previous finding, and remains open.

So the screen's single condition covers a name to correct, a name to correct, a declaration to
author, and a decision to take. The label was accurate and the remedy is not shared, which is
the argument this audit has made about every other collapsed category: a category is useful
when its members want the same thing done, and this one needs splitting before it can be
acted on.

One correction to method, made mid-measurement. The first attempt passed a `Period` object
where the accessor takes a period code string, and three of the four modelos returned an
`AttributeError` that could have been read as a registry refusal. The two genuine
`NoRevisionForPeriodError` results that arrived before it were real, but they were sitting
beside an artefact of the call. Reading the signature took one command and separated them.

### selector-window-condition-withdrawn-same-iteration | low | Thirty-five of thirty-six members were correct, so the condition was removed rather than shipped

The previous finding argued that one screen condition covered four defects wanting three
remedies, so the condition was split. Two of the three splits survive; the third was built,
run, and removed on the evidence it produced.

The surviving split is by direction. `name_opens_after_window` is a name later than the window
it declares, so the revision serves years its name does not claim - modelo 151 serves filing
years 2023 and 2024 under a name saying 2025, confirmed against the live authority.
`name_opens_before_window` is the reverse, a name claiming years the revision does not serve,
which is modelo 185 and modelo 322. Two members each, and the correction differs: one name is
late, the other early. The tests now pin both directions and assert the other is absent.

The withdrawn split was `selector_declares_no_window`, added because modelo 322 states its
fourteen-year span nowhere but its name. Run against the corpus it reported 36 revisions and
took the screen from 14 findings to 50. Checking the members before believing the count: modelo
100's 2023 and 2024, modelo 714's 2023 and modelo 390's 2024 each admit themselves through the
live authority. A single-year revision declares no selector bounds because its id names the year
and selection resolves through `valid_from`. Thirty-five of the thirty-six were correct.

Narrowing it to names claiming a span left two, and the second one broke the condition rather
than saving it: modelo 232's `2016-2017` resolves correctly for both 2016 and 2017. So what
distinguishes 322 is not its missing selector at all - it is that its `valid_from` disagrees
with its name, which the direction split already reports. The condition detected nothing the
screen did not already say.

It is gone. This is the third time in this campaign that something built here was removed on
its own evidence, and the first where the evidence arrived within the same iteration as the
build. The cost of checking the members was two commands; the cost of shipping it would have
been a category of 36 whose 35 correct members hide the one that is wrong - which is the exact
failure this audit documented in `record_drift` and has argued against four times since.

### unselectable-open-ended-window-condition | medium | Five revisions declare an open-ended valid_to their selector does not carry, and all five stop at their year

Scrutinising the single-year category the way the previous iteration scrutinised the last one
produced a better result than expected, and corrected the reasoning that removed a condition
even while confirming the removal.

The category splits. Modelo 194's 2024 and modelo 721's 2024 declare no `valid_to` and a
selector `year_from`, and they genuinely serve later years: filing year 2026 admits the
revision named 2024. Their names understate their reach and the finding is real. Modelo 131's
2026, modelo 189's 2025 and three others admit their own year and refuse the next, so their
names describe what they do.

Chasing that difference found the discriminator, and it is the field the withdrawn condition
was keyed on - looked at correctly this time. Fifty-four revisions declare an open-ended
`valid_to`. Five of them pair it with a selector carrying neither bound, and all five admit
their own year and refuse the following one. The other forty-nine carry a selector
`year_from`, and those are the ones that actually extend.

So the previous iteration's withdrawal was correct, and the reason given for it was not the
strongest one available. It was withdrawn because thirty-five of thirty-six members resolved
correctly - and the probe used asked each revision about its own year, which is the question
they were always going to answer. The better reason, established now, is that those
thirty-five carry an explicit `valid_to`: their window is stated in the dates, so an empty
selector beside it declares nothing that is missing.

The narrower condition is shipped because its membership was checked before it was written,
not after. Five instances, all five verified against the live authority to admit their named
year and refuse the next, and the shape that genuinely runs open-ended is verified not to be
swept in. Three tests pin all three cases: the condition, the open-ended revision that must
not be reported, and the closed window whose empty selector is harmless.

The lesson is narrower than "check the members", which this audit already says. It is that a
probe has to ask the question the condition claims to be about. Asking a revision whether it
serves its own year cannot distinguish a window that ends there from one that should not have.

### two-conditions-contradicted-each-other | medium | One row said the window does not extend while another said the name omits years it serves

Adding the unselectable-window condition exposed an error in the one beside it. Both fired on
modelo 131's 2026 and on four others, and they say opposite things. One row states the window
does not extend beyond the named year. The other states the name omits years the revision
serves. Both cannot be true of one revision, and the second is the false one: selection admits
2026 and refuses 2027, so the name `2026` describes exactly what the revision does.

The single-year condition now excludes a revision whose open-endedness is unselectable, and
its membership falls from seven to two - modelo 194's 2024 and modelo 721's 2024, the pair
verified to admit filing year 2026 under a name saying 2024. Every remaining member of that
category genuinely understates its reach.

The exclusion is keyed on selectability rather than on the name, and two tests hold that
distinction from both sides: modelo 131 must carry the unselectable finding and not the
single-year one, and modelo 721 must carry the single-year one and not the unselectable one.
Without the second test the exclusion could have silenced the condition entirely and still
looked correct.

The screen's total is unchanged at fourteen findings, which is the point worth drawing out.
Five rows moved from a category where they were wrong to one where they are right, and two
categories that previously mixed accurate and inaccurate members now each contain only
members wanting the same thing done. A count that did not move records none of that, which is
why this campaign stopped treating finding totals as the measure some findings ago.

### modelo-369-schemes-disambiguate-by-period-family | medium | Two alarming readings were both artefacts of asking with a period code the scheme does not declare

The last unexamined category is `no_temporal_claim`, whose three members are all modelo 369:
`esquema-exterior`, `esquema-importacion` and `esquema-union`. These are the one-stop-shop
regimes, a non-temporal axis sitting in the revision slot, which is the condition an existing
plan Step exists to move.

Chasing the consequence produced two wrong conclusions in succession, and both were the
probe's fault rather than the registry's.

The first: all three declare identical temporal windows - `valid_from` 2021-07-01, no
`valid_to`, selector opening in 2021 - and asking for filing year 2024 with period `1T`
returned `esquema-union` every time. That reads as temporal selection unable to tell three
revisions apart and silently answering with one of them, which would be a serious violation of
the rule against silent under-declaration.

The second: asking for each scheme explicitly, two of the three refused. That reads as two
declared regimes the registry ships and no consumer can reach.

Both are artefacts of asking with the wrong period code. The schemes are disambiguated by
period family, and each declares its own: `esquema-union` takes `1T` through `4T`,
`esquema-importacion` takes the twelve monthly codes, and `esquema-exterior` takes `EXT-1T`
through `EXT-4T`. Asked with `EXT-2T`, `03` and `2T` respectively, each of the three resolves
to itself. There is no ambiguity and nothing is unreachable.

So the axis is not undeclared, it is declared somewhere the name does not show, and the
screen's finding is accurate and benign as written: the name carries no year because the axis
is not temporal. The plan Step that would move the scheme out of the revision slot remains
worth doing for legibility, and its justification is now weaker than it looked an hour ago -
it is a naming and modelling improvement, not the repair of a selection defect.

Three probes, two false alarms, and the same root cause as the `Period` object and the `0A`
code earlier in this campaign: an argument shaped wrongly returns a refusal indistinguishable
from a registry that cannot answer. The check that resolved it was reading what the selector
declares before asking it anything, which took one command and should have been the first.

### selection-probe-asks-with-declared-codes-only | medium | The probe reads each revision's own period codes, so a refusal is a refusal of a well-formed question

Three investigations in this campaign reached a wrong conclusion the same way. A revision was
asked whether it resolves, the question carried a period code that revision does not declare,
and the refusal was read as the registry being unable to answer. It read once as temporal
selection silently collapsing three regimes into one, once as two regimes being unreachable,
and once as modelo 322 refusing every year of its own span.

The refusal is byte-identical in all cases, which is the root of it: a revision with no
coverage for a year and a revision asked in the wrong period family raise the same error. The
caller cannot tell a finding from a mistake without returning to the declaration, which is the
step a caller who believes they have found something skips.

`revision_selection_probe` reads the codes off each revision's own selector and asks with
those. It supplies no default, because a default is how the wrong code gets asked: a revision
declaring nothing yields no probe rather than a guessed one. On modelo 369 it returns twenty
probes with nothing resolving to anything but itself, which is the answer three manual attempts
failed to reach. On modelo 322 it returns forty-eight, also clean.

It also rescued a finding that was resting on the artefact. Modelo 322's `2008-2022` was
recorded as refusing every year tested, which was the wrong-code result. Asked with its own
monthly code it serves 2022 and refuses 2008, 2015 and 2021 - so the name really does claim
fourteen years the revision does not serve, and the finding now rests on evidence rather than
on a mistake that happened to point the same way.

One test premise was wrong and is recorded rather than quietly fixed. It asserted the corpus
contains revisions declaring no period codes; modelo 100 declares `0A` on every revision, and
what it lacks is `year_from` and `year_to` - a different field on the same selector, conflated
while writing the test. The test is now constructed against the function's contract, which
holds whatever the corpus does.

### shared-registry-invalid-for-a-window | high | Modelo 200 casillas referenced absent export fields in committed state, blocking every consumer

Three of the four tests errored mid-iteration with the registry refusing to validate: modelo
200 revision 2024 carried casillas referencing export fields that did not exist. No registry
data was uncommitted at the time, so the invalid state was committed rather than a partial
edit on disk, and every consumer of the bundled authority was blocked by it - not only these
tests.

It was repaired by the concurrent campaign within the iteration, by a commit restoring those
casillas from the semantic map and the official design, and all four tests then pass. An
earlier command in the same iteration had failed differently, with the authority refusing a
torn read while the registry directory changed under it during cache fingerprinting.

Both behaviours are the authority failing closed, which is what it should do, and both are
worth recording for the same reason: in a shared worktree a red result carries a timestamp,
and the question "was the tree valid when I measured" has a different answer at two points in
one iteration.

### no-revision-is-unreachable-when-asked-correctly | low | 441 well-formed probes and every one resolves, including the mid-year split once given a date

The declared-code probe was run across every modelo: 441 probes, and exactly one did not
resolve to itself - modelo 308's `2011-julio-2015`, refused as ambiguous.

It is not a defect. All four of modelo 308's revisions declare the single period code
`AD-HOC`, so the period cannot separate them and only the date can. Two of them split inside
2011, at the end of June, and the probe asked about the year alone. The registry refused a
coordinate that genuinely does not decide, which is the behaviour the no-silent-under-
declaration rule requires of it. Asked with `on` a March date it returns `2009-2011-junio`;
with a September date, `2011-julio-2015`; and every year falling inside exactly one window
resolves without a date at all.

That is precisely the assertion the open Step for modelo 308 asks to be proven - that the
coordinate resolves and that a genuinely ambiguous one still refuses - and the evidence now
exists, though the test it belongs in lives on the application side and outside this
iteration's scope. The Step stays open with its ground established.

The probe was the thing at fault and has been corrected: it now retries a refused year-only
question with a date inside the revision's own window. Reporting that refusal would have been
this module committing the exact error it was written to prevent, one iteration after it was
written to prevent it. Two tests hold both halves - every modelo 308 probe resolves, and the
year-only coordinate still refuses for a caller who asks it.

So across 441 well-formed questions the registry answers every one correctly. That is a
stronger statement than any of the three false alarms suggested, and it could not have been
made by the manual probing that produced them.

### crashed-worker-read-correctly-second-time | low | The word crashed was hidden by terminal escape codes until the log was stripped

The corrected test suite then reported a failure on the modelo 369 test. The instinct was to
treat it as a regression from the retry change, and the output said otherwise: worker `gw0`
crashed while running it. Re-run serially, all six tests pass.

This audit recorded the same confusion several findings ago and drew the lesson that a crash
and an assertion are different events a tally spells identically. The lesson held only because
the log was read before the diagnosis was written - and the first attempt at reading it
produced nothing, because the terminal escape codes hid the line. It took stripping them to
see the word "crashed" at all.

Worth noting what made the crash likelier: the retry doubles the authority calls for any
refused probe, and this suite was already slow. A change that makes a test slower makes a
timeout-driven crash more likely, and the crash then reads as a failure of the change. The two
are easy to confuse and were nearly confused here.

### date-retry-narrowed-to-ambiguity | medium | Retrying every refusal doubled the work and made the timeout crash likelier; suite runtime halved

The date retry added last iteration fired on every refusal, which was both wasteful and
imprecise. A date decides between windows that split inside one year; it decides nothing about
a year the revision does not cover at all. So every genuine refusal was being asked a second
time to hear the same answer.

It now fires only on `AmbiguousRevisionSelectionError`, which is the one refusal a date can
resolve. Behaviour is unchanged where it matters and was checked in both directions: modelo
308's four probes still resolve to themselves, and modelo 322 at 2015 still reports twelve
refusals with none of them retried into a resolve.

The runtime is the reason this is worth recording. The suite ran in 164 seconds and now runs
in 69, and the previous iteration's crash was a timeout under parallel execution on a suite
that had just been made slower. A correctness fix that halves the work also removes the
condition that produced a false failure, and the two were the same change.

The narrower point is about what a retry is for. Retrying a failed question makes sense only
when something about the second attempt could change the answer. Retrying because the first
attempt failed is how a probe turns a definite refusal into twice as much evidence for the
same conclusion, and this one did that for an iteration.

### plan-declares-each-section-several-times | high | Three Descriptions, two Parallelizations and three Verifications against a template declaring one each

Counting the plan's own headings found `## Description` three times, `## Parallelization`
twice, and `## Verification` three times. The template declares exactly one of each, so this
is the campaign's subject appearing in the campaign's own tracking document: one section
declared repeatedly, with the copies drifting apart.

They have drifted. The first Description opens "the registry declares the same fact in many
places"; the third opens "at many sites". Same sentence, two spellings, which is what a copy
does when someone edits the one they happened to open.

Content is spread rather than duplicated wholesale, which is what makes this a merge and not
a deletion. The three Descriptions run 54, 36 and 45 non-blank lines; only the third carries
the paragraph recording how this work extended from the registry into the codebase. The two
Parallelization sections run 41 and 145 lines, the longer one holding the concurrency
constraints written during this campaign. Deleting any of them by heading alone would lose
material that exists in only one copy.

The duplication predates this session and was not introduced by it: the plan's first commit
already carried three Descriptions and four Verifications. That is worth stating plainly
because this campaign has been appending to these sections all along, and a reader could
reasonably assume the appends caused it. They did not; they added to a structure that was
already wrong, which is why some of this campaign's own prose now sits in a section a reader
may never reach.

No merge is attempted in this iteration. Reconciling roughly four hundred lines across eight
sections, on a document the concurrent campaign commits, is focused work rather than a
tidy-up at the end of an iteration - and a hasty merge that drops a paragraph would be
strictly worse than the duplication, which at least keeps everything.

### plan-sections-merged-without-loss | medium | 126 paragraphs to 107 with no-loss made structural rather than checked after the first attempt refused

The three Descriptions, two Parallelizations and three Verifications are one of each. The
document went from 126 prose paragraphs to 107, the nineteen removed being near-duplicates,
and the Steps were untouched at 212 rows with 151 closed before and after.

The first merge attempt was refused by its own check, which is the part worth recording. It
grouped paragraphs by similarity and kept the longest of each group, and the no-loss check
then found two Verification paragraphs matching no survivor - a transitive chain where the
first and last members resemble the middle one but not each other. Had the check been written
as a formality it would have passed on the counts and quietly dropped two paragraphs.

The second attempt makes no-loss structural rather than checked. Paragraphs are considered
longest-first and one is kept only when nothing already kept resembles it, so every dropped
paragraph is by construction similar to one that survives. Order is then restored to first
appearance. The check still runs, and now it cannot fail, which is the right relationship
between a guarantee and its test.

Verified against a copy of the document taken before the edit: zero paragraphs lost, Step
count and closed count identical, and seventeen vault checks clean. The one remaining warning
is the stale feature index, caused by the untracked audit scaffold the concurrent campaign
created under this feature tag - not linked here, because linking another writer's unwritten
document is not this campaign's call.

Two path translations bit during the work and neither reached the document. A backup written
through the shell's `/tmp` was invisible to the interpreter, which resolves that path
differently on this platform, so the verification could not read its own baseline until the
real location was resolved. It is the same class as the sweep script that needed the
repository root on its import path, and the same remedy: resolve the path rather than assume
the two tools mean the same thing by it.

### criteria-were-being-appended-to-parallelization | high | The duplicated structure made the block before a Verification heading look like Verification

Reading the merged Verification section found it opening "beyond that, five criteria" when the
campaign has written twelve. The twelve-criteria text existed, and it was inside
`## Parallelization`.

The cause is the duplicated structure itself. With three Description blocks and three
Verification blocks in one document, the block sitting immediately before a `## Verification`
heading looks like Verification prose, and every criterion added this session was appended
there. The merge could not correct it: it reconciles copies of a section against each other,
and these paragraphs were in a different section entirely, so they were never compared.

That is a sharper version of the defect this campaign keeps finding. A duplicated declaration
does not only drift - it changes where a later author puts things, so the damage compounds
in a direction nobody is watching. Ten iterations of acceptance criteria went into a section
about ordering constraints, and every vault check passed throughout, because nothing validates
that a paragraph is under the right heading.

The block from the criteria opener to the end of Parallelization is now inside Verification,
merged with what was there under the same no-loss construction: 28 paragraphs to 25, none
lost. The superseded "five criteria" opener was then removed by hand, deliberately and as the
single exception to no-loss, because its content is carried entirely by the sentence that
replaced it and keeping both would leave the section stating its own size twice with two
different numbers.

The document now carries one Description, one Steps, one Parallelization and one Verification,
in template order, with 213 Step rows unchanged. Seventeen vault checks pass; the remaining
warning is the concurrent campaign's untracked scaffold.

Worth noting what did not catch this. The merge verified paragraph counts and no-loss, ran
clean, and reported success - and the section it produced said five where it should have said
twelve. The check answered the question it was asked, which was whether anything was dropped,
and the thing that was wrong was never in its scope. Reading the output was what found it.

### parity-gate-caught-its-own-author | medium | The screen said six conditions while emitting eight, invisible to every check but this one

The full lane reconciles: 1,281 collected, 41 failed plus 1,240 passed, and no lost-worker
marker. Against the previous run's 35 failures, six are new, and one of them was this
campaign's.

`test_a_screen_that_counts_its_conditions_states_the_right_number` is a gate written earlier
in this work, asserting that a screen documenting a condition count documents the number it
actually emits. The revision-name screen said "Six conditions are reported". Over the last
several iterations its conditions were split by direction, one was added, one was withdrawn
and one was narrowed - and the sentence stating how many there are was never touched. There
are eight. The gate failed, correctly, and the count now says eight.

That is the first time in this campaign that a gate written here caught its author rather than
the tree. It is worth recording for what it says about the parity gate's value: the defect it
found is invisible to every other check, reads as harmless prose, and is precisely the shape -
a declaration that stopped describing what it declares - that this entire plan exists to
remove. The gate was written against other people's screens and the first thing it caught was
mine.

The remaining five new failures are not this campaign's. Two are in the publication suite and
three in modules the concurrent campaign has added or changed - a monetary-scale test, a
restored-semantic audit for modelo 200, a generated-tree CLI - all committed, none carrying a
pending diff. The two gates this campaign added to the publication suite were run in isolation
and pass; the failures beside them are in tests that predate this work.

Attribution before repair, as this audit has argued throughout. The one that was mine took a
one-word fix; assuming the other five were also mine would have cost an iteration chasing
another writer's in-flight work.

### four-paragraphs-no-threshold-could-judge | low | Two subsumed, one carrying a lost clause, one longer than its replacement, one not a duplicate at all

The merge left five older wordings of criteria in the Verification section, below its
similarity threshold and above the point where a machine could tell them apart. Reading them
in full gave four different answers, which is why no threshold would have worked.

Two were plainly subsumed. The older resolved-surface criterion says a test proves the
accessor fails when a linkage path is dropped; the current one says that and names the second
gate that checks the import rather than the result, and why. The older release-eligibility
criterion is the current one without its closing sentence recording that neither half holds
yet. Both were removed.

One was superseded but carried a clause its replacement had lost. The older gate-detection
criterion says "one gate is exempt" where the current says two, so the current supersedes it -
but the older also required each gate to pass the normal path in the same suite, and that had
fallen out. The clause was carried across before the paragraph was dropped.

One was longer than the paragraph replacing it. The older conformance-vector criterion holds
the reason the first half cannot be engineered at all: a vector whose expected bytes came from
this project's own writer would prove only that the writer agrees with itself. The current
paragraph has a regression guard the older lacks. Neither subsumes the other, so they were
merged rather than either deleted.

One is not a duplicate at all. "Each of the four edge gates" and "each declaration gate" score
0.87 against each other and describe different gate families in different Waves. It stays, and
it is the single near-duplicate pair the section still reports - deliberately, and recorded
here so the next reader does not remove it as residue.

Twenty-four paragraphs to twenty, 215 Step rows unchanged, seventeen vault checks clean. The
general lesson is the one the previous iteration reached from the other direction: the merge
was right to keep what it could not judge. A threshold tuned to catch these four would have
also caught the fifth, which is not a duplicate, and the campaign would have lost a criterion
to a number.

### two-descriptions-disagreed-on-the-screen-count | medium | The longer, later-sounding paragraph carried the stale count; the entry point settled it

The Description carried one near-duplicate pair the merge had left, and it was worth reading
for a reason the Verification pairs were not: the two paragraphs state different numbers. One
says ten screens measure the declaration conditions; the other says eight.

The longer, later-sounding paragraph is the one that is wrong. Counting the entry point
settles it - `SCREENS` in the analysis package enumerates ten - so the shorter paragraph
carries the correct figure and the fuller one carries a stale count picked up when the screens
were fewer.

That is the whole argument for checking rather than preferring the longer variant, which is
what the automated merge does and what a reader skimming would also do. Length correlates with
recency often enough to be tempting and not often enough to be trusted, and here it points
exactly the wrong way.

Both paragraphs carried unique material: one the sixteen gates and the detail that several
gates caught their own author, the other that each screen proves its detection against a
constructed defect, that several conditions turned out clean corpus-wide, and that two of the
audit's own claims were withdrawn when measured. They are now one passage with the verified
count and everything both said. The Description reports no near-duplicate pair.

A verification of that merge reported one clause lost, and it had not been. The check searched
for the clause with the line break where the older paragraph happened to wrap it, and the
merged text wraps it elsewhere. Normalising whitespace before comparing showed all four clauses
present. It is the third time in this campaign that a literal newline inside a search string
has produced a false result, twice in a check and once in an edit anchor - the same lesson each
time, and cheap enough to keep relearning only because the checks are run at all.

### name-window-findings-were-already-stepped | medium | Eight open Steps named the same revisions; what this work added was consequence, not discovery

Sweeping the plan's numeric claims found one stale and, more usefully, found that several
iterations of this campaign re-derived work the plan had already recorded.

Phase `W05.P12` carries eight Steps naming the exact revisions the name-window screen reports:
modelo 151 claiming 2025 while opening in 2023, modelo 185 claiming 2025 while opening in
2026, modelo 720 claiming 2013 while opening in 2012, modelo 322 claiming a 2008-to-2022 span
while declaring 2022 only, and modelo 194 and modelo 721 named for a single year while
declared open-ended. All open, authored from the audit's earlier measurement, and every one of
them presented in recent findings here as though newly found.

The correction matters more than it costs. What those iterations actually added is not the
list but its consequences, and those are new: that modelo 720's opening year makes its own
record design unloadable, so every corpus sweep this campaign ran covered 111 designs and not
112; that modelo 322 serves only 2022 when asked with its declared monthly code, which was
established after a wrong-code artefact first appeared to show it refusing everything; and
that modelo 194 and modelo 721 genuinely admit filing year 2026 under names saying 2024, which
separates them from the five whose open-endedness selection does not honour. The condition
split and the two withdrawn false alarms are also new. The findings are not.

Independent re-derivation is worth something and is worth naming as what it is: two
measurements taken from different directions agreeing on the same six revisions is stronger
evidence than either alone. It is not discovery, and reporting it as discovery inflates a
campaign's apparent yield while burying the fact that the plan was right the first time.

Separately, one numeric claim was stale and is now gone rather than corrected. The
Parallelization section described "the twelve Steps of `W06.P13`", a phase that now holds
sixty-five. Updating the number would have bought a few iterations before it was wrong again,
so the sentence now says every Step of that phase lives on the dev-owned surface, which stays
true however many there are. A count in prose is a declaration that has to be maintained, and
this plan has spent several findings on declarations that stopped describing what they
describe.

### two-screen-conditions-had-never-fired | high | A condition never emitted is indistinguishable from one that cannot be reached, and two were untested

The revision-name screen documents eight conditions and emits five against the corpus. Of the
three that never appear, one is asserted by an existing test. Two were neither emitted nor
tested: `name_claims_open_ended`, for a name promising every later year over a window that
ends, and `name_misstates_closing`, for a name whose stated closing year is not the declared
one.

A condition that has never fired is indistinguishable from one that cannot. Either could have
been unreachable - a predicate ordered so an earlier branch always wins, a comparison that can
never be true - and the screen would report a clean corpus for a defect it is blind to, which
is worse than not screening for it at all.

Both are now constructed and caught. A revision with an open-ended name is given a closing
date and the first condition fires; one whose name states a span has its window's close moved
a year earlier and the second fires, naming both years. Neither existed in the corpus, which
is why the corpus could not prove them.

A third test now pins that the set of documented conditions equals the set the module can
emit, read from the source rather than from a count. It compares eight against eight, and it
was checked to be comparing eight rather than passing on two empty sets - the defence this
campaign added to its own gates after finding two of five could pass over nothing.

This is the same defect as the stated condition count corrected two iterations ago, one level
down. That one had the screen claiming six conditions while emitting eight; this one has the
screen claiming two conditions it had never been shown to reach. Both are a declaration
drifting from what it describes, and neither is visible in a passing test run - the first was
caught by a gate written here, the second only by asking which documented conditions the
corpus never exercises.

### unfired-condition-defect-confined-to-one-screen | low | Six screens declare condition bullets and all six agree with what they emit; four sweep hits were artefacts

Having found two conditions in the revision-name screen that had never been shown to fire, the
obvious question is how many others carry the same. All ten screens were compared: the
conditions each documents against the kinds each can emit.

The answer is none. Six screens declare condition bullets and all six agree with what they
emit - continuity integrity at four, monetary scale at four, revision name at eight, temporal
site agreement at four, and the rest. Four screens document their findings without a bulleted
condition list, so the comparison does not apply to them. The revision-name screen was the
only one carrying the defect, and it is fixed.

Reaching that answer took two corrections to the sweep, both of the same kind and both caught
before anything was recorded. The first extraction matched only `kind="x"` as a keyword
argument, so the monetary-scale screen appeared to document three conditions it never emits;
it emits all three, assigning `kind = "x"` to a variable first and passing it later. The second
extraction still reported two screens, and both were bullet lists that are not conditions at
all - the casilla grammar screen documents five identifier grammars, and the capability screen
explains what an authority grade is.

So the sweep reported four defects and the tree contains none of them, which is worth stating
as plainly as a real finding would be. Every one was an artefact of reading source with a
regular expression that did not know how the code produces its values or what its prose is
describing. That is now the fifth measurement artefact this campaign has produced and caught,
and the pattern across all five is identical: the extraction was tested against the answer it
was expected to give rather than against the shape of what it reads.

The result stands as a negative one. A defect found once was checked for everywhere and found
nowhere else, which is a smaller conclusion than the sweep promised and the only one the
evidence supports.

### twenty-one-modules-ruled-by-measurement | medium | Live when sys.modules holds it after a load, conditionally reachable when it does not

The load-census residue was deferred earlier on the ground that the modules were still being
moved by the concurrent campaign. Re-measured, it is unchanged at twenty-one unclassified
modules and fourteen stale rules, the modules carry no pending edits, and nothing has committed
against them in hours. They are stable, so the reason for deferring has expired.

The Step asks for grounded rulings rather than key repair, and the ground turns out to be
available. Every one of the twenty-one sits inside the static load closure, which on its own
says nothing: the closure includes function-scoped edges a real load never walks, which is the
distinction established when the closure test was repaired earlier in this campaign. Asking the
sharper question - which of them `sys.modules` holds after the authority has actually loaded -
splits them cleanly. Nineteen are imported by a real load and are `live`. Two are not:
`_withholding_rows` and `calculation_revision_identity`, each with zero module-level importers,
so each is reached only through a deferred edge and is `conditionally_reachable`.

Both classifications already exist in the rule table, so no new vocabulary is needed. What
remains is authoring each rule's trigger and reason, which is prose about why a module loads
rather than a decision about whether it does. The decision is now made by measurement, and the
Step is smaller than it was written to be.

### registry-load-failure-was-stale-bytecode | medium | An error listing permitted values without the one a revert had restored is a module older than its file

The measurement first failed with modelo 100's 2021 revision declaring an extraction surface
outside the permitted set. Read as a data defect it would have been a serious finding and a
second instance of the shared registry being committed invalid.

It was neither. The schema file permits that surface, and the most recent commit is a revert
restoring the borrador parser and its extraction profiles. The error listed the permitted
values without the restored one, which is a loaded module older than the file it came from.
Clearing the package's compiled cache made the load succeed and the measurement complete.

Stale bytecode has now produced two false findings in this campaign, and both looked like the
tree being broken by someone else. The tell is the same both times: an error whose message
contradicts the source that would have produced it. Reading the file the error blames, rather
than trusting the error, is what separates them - and it costs one command against an
iteration spent reporting another writer's imaginary defect.

### most-stale-rules-were-not-stale | medium | Twelve named core modules outside the census universe and one named a genuinely renamed module

Reading the stale-rule entries rather than pattern-matching them changed what they are. Only
two named a registry module that had moved. The other twelve name modules under
`cadrumo.core`, and the message is not that they vanished but that they are "not in the census
universe" - the census covers the registry package, and those rules list core dependencies as
members. Whether that is a rule-authoring choice or an error is a question for whoever wrote
them; it is not fourteen renamed modules, which is what the count suggested and what an earlier
finding here implied.

Of the two genuine ones, one is repaired and one is deliberately not. `_validate_references`
became `validate_references` when the concurrent campaign dropped the leading underscore, the
successor is in the census universe, and the member is repointed - the stale count falls from
fourteen to thirteen, confirming exactly one entry was resolved.

`snapshot` is left alone. The registry has `snapshot_coordinate` and `_snapshot_internals` and
no plain `snapshot`, and the rule's own reason cites a third filename that is also gone. Any
of those could be the successor and the difference matters, because the rule classifies when a
module loads and pointing it at the wrong sibling would produce a confident wrong answer rather
than a visible gap. The stale entry is the honest state until the author of that rename says
which module inherited the members.

That distinction - repair what the rename makes unambiguous, leave what it does not - is the
same one this campaign applied to the export trees and to the twenty-one classifications. A
gap that stays visible costs a failing check. A guess that looks like a repair costs the next
reader their assumption that the file means what it says.

### load-classifications-grounded-in-the-loader | medium | Five rules cover every unruled module, and the table caught a member this campaign misprefixed

Five classification rules now cover every module the refactor left unruled, and the census
reports zero unclassified where it reported twenty-one. The Step asked for grounded rulings
rather than key repair, and what grounds them is a measurement rather than an opinion about
what each module is for: a module is `live` when `sys.modules` holds it after the bundled
authority has loaded, and `conditionally_reachable` when it does not.

Nineteen are live. They group by the importers the census reports, which is what the triggers
name: the record-design parse chain, nine modules that the PDF orchestration, workbook reader
and shared layout markers were split into; the binding families, five carrying parts of the
compilation that runs on every load; three the revision validators import directly; and the
modelo 100 formula runtime split.

Two are not, and they are the interesting pair. Neither `_withholding_rows` nor
`calculation_revision_identity` appears in `sys.modules` after a load, and neither has a single
module-level importer. The first is imported from inside the function that uses it, which is
the break for the cycle it forms with `withholding_bindings` and cannot be hoisted without
restoring the cycle - the same finding that repaired the closure test earlier in this campaign,
now doing a second job.

The rule table caught an error in the rules written for it, which is the behaviour worth
recording. `calculation_revision_identity` was written with the registry prefix every other
member carries, and it lives under `domain.modelos`. The census reported one module still
unclassified and one new stale member simultaneously - the same mistake seen from both ends -
and the rule refuses in both directions precisely so that a member pointing at nothing cannot
sit quietly beside a module nobody ruled.

The Step is closed on its stated subject. The census is not yet clean: thirteen stale entries
remain, twelve naming core modules outside the census universe and one naming the `snapshot`
module whose successor is ambiguous. Both were separated from this work in the previous finding
and neither is what this Step asked for.

### one-stale-count-three-defects | high | Six members a load imports, three a rule over-claims, one renamed module: three owners, one number

The thirteen remaining stale entries were treated in an earlier finding as a scope question to
be left to whoever wrote the rules. Measured against a real load, they are three separate
things and the rules are right about most of them.

Six name modules a real load does import. `cadrumo.core`, `cadrumo.core.classification`,
`cadrumo.core.errors.not_found`, `cadrumo.core.redaction` and `cadrumo.domain.calculations` are
all in `sys.modules` after the bundled authority has loaded, so the rules claiming they load are
correct and the census is calling them stale because its universe does not contain them. The
universe is documented as the static load closure unioned with what the closure reaches
dynamically and with the registry package, and these modules are demonstrably reached by a
load, so the closure is not seeing edges the interpreter walks. That is a defect in the census,
not in the rules it checks, and it is the largest share of the count.

Three are the reverse. The justificante protocol, error and package modules are claimed `live`
under the trigger "ValidatedRegistryAuthority.load", and a real load does not import any of
them. That rule over-claims. The caveat is stated rather than buried: this was measured on one
load path, the bundled authority, and the census distinguishes load regimes elsewhere, so a
cold-regime load might reach them. The claim needs checking against both regimes before the
rule is edited, and it is not edited here.

One is the `snapshot` module, which does not exist on disk and whose successor is ambiguous
between two siblings. Unchanged from the previous finding and still not guessed at.

So a single number covered a census too narrow, a rule too broad, and a rename nobody
completed - three defects wanting three different owners, presented as one count of stale
rules. This audit has made that observation about the registry's own categories repeatedly;
it applies to the tooling that measures the registry just as well.

### census-universe-omitted-ancestor-packages | high | An import graph records no edge to a parent package, so the universe missed packages every load holds

The six stale members a real load imports had one cause between them, and it is a property of
import graphs rather than of this tree. The graph records the edges written in source, and
importing `cadrumo.core.hashing` writes no edge to `cadrumo.core`. The interpreter loads that
parent regardless, and every ancestor above it. A universe built from edges alone therefore
omits packages a running load certainly holds, and rules naming those packages were reported
stale for naming something real.

Four of the five missing modules were packages, which is what pointed at the cause. The census
universe now includes every ancestor package of every member it already had, and the stale
count falls from thirteen to seven.

Including them surfaced three modules no rule covered - `cadrumo.domain`,
`cadrumo.domain.manuals` and `cadrumo.domain.modelos` - because a universe that grows must have
its new members ruled. All three are in `sys.modules` after a load, and they are ruled `live`
with the reason stated plainly: they are inert namespace markers carrying no load behaviour of
their own, and they are live because a load holds them, not because they do anything. The
census returns to zero unclassified.

Four stale entries survive and they are the ones already separated: `snapshot`, which does not
exist; the two justificante modules under a rule that over-claims, still unverified against the
cold regime; and `cadrumo.core.errors.not_found`, which is a module rather than a package and
so is not explained by the ancestor fix. That last one is a residue of this repair rather than
a new finding, and it is left named rather than absorbed.

The wider point is about what a graph is evidence of. This campaign has twice now found the
static closure and a real load disagreeing - once over function-scoped imports, which the graph
records and the interpreter skips, and now over ancestor packages, which the interpreter loads
and the graph never records. The disagreements run in opposite directions and both were
invisible until `sys.modules` was consulted directly.

### in-process-load-measurement-was-inverted | high | One module reported absent that a clean subprocess holds, an error running opposite to contamination

The classifications authored two findings ago were decided by asking `sys.modules` what a load
holds. That measurement was taken in the same interpreter that had already imported the census
tooling, and for one module it gave the opposite of the truth.

`calculation_revision_identity` was classified `conditionally_reachable` because it was absent
from `sys.modules` after `bundled_authority()` in that process. Measured in a clean subprocess
importing nothing but the authority, it is present - in the cold regime and the warm regime
alike, with separate cache directories to make the two genuinely different. The module is
`live` and the rule now says so.

The direction of the error is what makes it worth recording. Contamination adds modules to
`sys.modules`; it cannot remove them, so the natural suspicion was backwards. Whatever the
in-process mechanism is - most plausibly that importing the tooling had already produced an
authority, leaving the later call a cache hit that imported nothing - the lesson does not
depend on identifying it. A process that has imported the analysis package is not a process
performing a plain load, and only the second one answers the question.

`_withholding_rows` was re-measured the same way and is unchanged: absent in both regimes, no
module-level importer, reached only when the function holding its import runs. It is now the
sole member of the conditional rule, which is a smaller and more accurate claim than the pair
it started as.

The justificante over-claim is also now confirmed on a clean load rather than suspected: those
modules are absent in both regimes, so the rule calling them live is wrong. It is still another
writer's rule and still not edited here.

Three measurements in this campaign have now been taken in a process that had already imported
the thing being measured - the stale bytecode twice, and this. The remedy each time was a
clean interpreter, and it costs one subprocess.

### cold-and-warm-regimes-differ-by-forty-three-modules | high | 378 modules cold against 335 warm, a strict subset, and one live claim held only in the cold regime

Having found one classification decided by a contaminated measurement, the remaining eighteen
were re-measured the same way: two clean subprocesses importing nothing but the authority, one
with empty cache directories and one with the real ones.

Seventeen of the eighteen hold in both regimes. `formula_runtime_m100` does not: it is in
`sys.modules` on a cold load and absent on a warm one. It is now `conditionally_reachable`,
classified by the regime that does not load it rather than the one that does, because a rule
saying a module always loads is falsified by any load where it does not.

The regimes differ by more than that one module. A cold load holds 378 first-party modules and
a warm load 335 - forty-three modules loaded only when the caches are empty, and none loaded
only when they are full. That asymmetry is worth stating: the warm path is a strict subset, so
every classification made against a warm load is safe as a lower bound and every one made
against a cold load may over-claim. The rule table distinguishes exactly these two states, and
until now this campaign had been measuring one of them without saying which.

A module appeared mid-measurement that no rule covers, `renta_web_open_replay_corpus`, added by
the concurrent campaign while the subprocesses ran. It is left unruled rather than guessed at,
for the same reason the `snapshot` successor was: its load behaviour is measurable in ten
minutes by whoever needs it, and inventing a classification is cheaper and worse.

### scratch-file-committed-before-removal | medium | A create-and-delete in one command left a tracked file, because another writer commits on a timer

The measurement needed the repository root on its import path, so a script was copied there and
deleted in the same command - the same slip recorded earlier in this campaign, repeated after
being recorded. This time the concurrent campaign's tree-wide sweep committed it in the window
between the two, under a message describing it as captured scratch.

Deleting it now leaves a tracked deletion in the working tree rather than an untracked file
disappearing. The deletion is correct and is left standing for the next sweep to carry, since
committing is not this campaign's to do.

The lesson is not that scratch files are risky in general. It is that in a worktree where
another writer commits everything on a timer, the window between creating a file and removing it
is a window in which it becomes part of the project's history - and the earlier finding that
recorded this slip described it as harmless because nothing persisted. That was true then and is
not a property of the practice.

### forty-live-claims-are-unsupported | critical | Eleven load in no regime and twenty-nine only cold, in rules the census had no way to check

The two clean module dumps were already collected, so checking every `live` rule in the table -
not only the ones written here - cost nothing further. Of 225 members claimed live, 40 fail in
at least one regime, and they fail in two distinct ways.

Eleven are never loaded at all, in either regime. Four are the justificante modules already
identified, four more sit under `cadrumo.domain.modelos`, and three are core modules -
`json_contract`, an observability recorder, and `output_rendering`. The rules claiming these
load on `ValidatedRegistryAuthority.load` are simply wrong about them, and no regime rescues the
claim.

Twenty-nine are loaded on a cold load and not on a warm one. Those rules are right about the
regime they were evidently written against and over-broad about the other, which is exactly the
error this campaign made with `formula_runtime_m100` and corrected in the previous finding. The
same mistake at a scale of twenty-nine suggests the table was authored from a single cold trace
and never re-measured warm.

None of the forty are this campaign's. The nineteen rulings authored here were re-verified in
both regimes and seventeen held; the eighteenth was corrected. That is worth stating precisely
because the finding otherwise reads as this campaign auditing its own work and finding it
sound, which it is not - it is this campaign finding, in someone else's rules, the error it had
just made in its own.

The rules are not edited. Forty members across an unknown number of rules, each carrying an
authored reason describing why a module loads, is another writer's reasoning to revise rather
than a mechanical repair. The measurement is recorded with its own limits: one machine, one
bundled corpus, one entry point into the authority, and two cache regimes distinguished by
their directories. A rule claiming a module loads under some other entry point is not
contradicted by any of it.

### unsupported-live-claims-are-reproducible | medium | A screen probes both regimes in clean subprocesses and raises rather than returning an empty set

The census checks that every module is ruled and every ruled member exists. It never checks the
claim the rule makes, which is how forty live members came to disagree with the interpreter
without any gate noticing. `load_claim_verification` asks that question and reproduces the
finding exactly: 378 modules cold, 335 warm, forty unsupported, eleven never loaded and
twenty-nine cold only.

Two properties of the screen were learned by getting them wrong earlier in this campaign and are
built in rather than left to whoever runs it. The probe runs in a subprocess importing nothing
but the authority, because a measurement taken inside the tooling's own process reported a
module absent that a clean load holds - an error running opposite to the obvious direction of
contamination. And both cache regimes are measured, because the warm set is a strict subset of
the cold one, so a claim verified cold alone cannot tell an always-loaded module from a
cache-dependent one.

The probe raises when it produces no output rather than returning an empty set. That distinction
is the difference between reporting a failed load and reporting that every live claim in the
table is unsupported, and the tests pin it from the other side: an empty regime pair does report
every member, which is the shape a swallowed failure would take.

The comparison is pure and the tests exercise it against constructed sets, so five tests run in
under two seconds while the screen itself costs two registry loads. Splitting them that way was
deliberate: a test suite that pays ten minutes to check a set difference gets run less often
than one that does not.

It is a screen and not a gate. Forty members is not a state to freeze into a baseline, and this
campaign has refused that twice already; the gate belongs here once the claims are corrected by
the rules' owner, and the screen is what makes correcting them cheap to verify.

### two-tools-sit-outside-the-single-registry-entry-point | low | A coordinate probe and a subprocess screen cannot run over one loaded registry without losing their point

The plan's Description says the screens run from one entry point over a single loaded registry.
Checked, that entry point still enumerates ten, and the two tools added later are correctly not
among them.

Neither could be. The selection probe asks a modelo's revisions whether they resolve using the
period codes each declares, so it takes a coordinate rather than sweeping a corpus. The
load-claim screen spawns clean subprocesses in both cache regimes, because the question it asks -
whether a module a rule calls live is one a load actually imports - is unanswerable from inside a
process that has already imported the tooling. Adding either to a single-registry sweep would
either break the sweep's guarantee or destroy the tool's own.

The Description now says this, and says the screen count is whatever the entry point enumerates
rather than stating a number that has to be maintained. That is the same treatment given to the
Steps count two findings ago, and for the same reason: a count in prose is a declaration whose
maintenance nobody owns.

Both tools' tests are selected by the default lane, confirmed by collection rather than assumed -
thirty tests across the four newest modules - and the lane-visibility screen reports no module in
the tree carrying no execution marker at all. That check has now been run at every point where
this campaign added tests, because the two occasions it was skipped both produced a green result
over an empty selection.

### campaign-findings-use-a-second-heading-format | high | Seventy-seven findings appended here cannot be cited, because they abandoned the format the preceding hundred and thirty-one use (count corrected by campaign-findings-count-corrected)

This audit's headings divide exactly at the point this campaign began writing in it. The 131
findings before line 3279 carry `slug | severity | summary`. The 80 after line 3390 - every one
appended by this work - carry a prose sentence and nothing else.

The consequence is not cosmetic. A structured heading gives a finding a stable identifier, and
the earlier findings are cited by it throughout this document and its siblings: B9, GENREVIEW-003,
REVIEW-001. Not one of the eighty can be referenced except by quoting a sentence that may be
rewritten. They also carry no severity, so a reader cannot triage them, and the 131 that do can
be sorted by one.

This is precisely the defect the campaign exists to remove, committed by the campaign in the
document recording its removal. A second declaration of one concept - here, of what a finding
looks like - introduced by an author who did not read the convention before writing eighty
instances of an alternative. The earlier findings were read constantly for evidence; their
headings were looked past every time.

The conversion is not attempted in this iteration and the reason is worth stating rather than
leaving as an omission. Each of the eighty needs a slug and a severity, and severity is a
judgement about consequence that this campaign has spent forty findings arguing cannot be
assigned mechanically. Eighty provisional severities would read as authoritative and be worth
less than none, which is the same argument that refused a baselined gate twice.

This finding uses the correct format, which is the smallest honest start: the convention is
followed from the moment it is noticed, and the backlog is named rather than absorbed.

### campaign-findings-count-corrected | low | Seventy-seven of the eighty unstructured headings are findings; three are section headers that never needed a slug

The previous finding counted eighty prose headings and attributed them all to this campaign.
Three are not findings and not this campaign's: the "Consolidated position" headers, two of which
were present at the audit's first commit and one added later, which structure the recommendations
rather than record a defect. They need no slug and no severity, and converting them would be
applying a finding's format to something that is not a finding.

The corrected figure is seventy-seven, and the shape of the document is sharper than the first
count suggested. At its first commit the audit carried seventy-seven headings, seventy-five of
them structured. It now carries two hundred and eleven, of which one hundred and thirty-one are
structured. So fifty-six structured findings were authored between those two points, by writers
who read the convention and followed it, and then seventy-seven unstructured ones were appended
by this campaign.

That makes the original finding worse rather than better. The convention was not a historical
artefact preserved in an old section: it was actively maintained by other authors in the same
document, and this campaign wrote seventy-seven findings past fifty-six recent examples of the
format it was ignoring.

The conversion backlog is seventy-seven, not eighty, and remains unstarted for the reason
already given: severity is a judgement each finding has to earn.

### campaign-findings-conversion-complete | low | All seventy-seven findings now carry a slug and a severity, and the distribution says something about the campaign

The conversion is done. Two hundred and ten findings carry `slug | severity | summary`, every
slug is unique and kebab-case, every severity is one of the four the document already used, and
the only prose headings left are the three "Consolidated position" section headers, which are
not findings and were never meant to carry a slug.

Severity was assigned by reading each finding rather than by rule, and the distribution across
all 210 is 16 critical, 68 high, 92 medium and 34 low. Within the seventy-seven added by this
campaign the shape is different and worth naming: the two criticals are both the conformance
closure suite - sixteen tests proving real filing outcomes that no CI lane runs - and the third
is the forty live claims the census had no way to check. Everything else this campaign found is
high or below.

The lows are almost entirely self-correction: a condition built and withdrawn inside one
iteration, a duplicate Step authored and retired, a sizing that measured an absent attribute, a
sweep whose four hits were all artefacts of my own extraction, a scratch file, a crashed worker
read correctly only after stripping escape codes. Thirty-four of seventy-seven.

That ratio is the honest summary of the work. A campaign about declarations that stop
describing what they declare spent a third of its findings discovering that its own
measurements, gates, plan sections and audit headings had done exactly that. The three criticals
are real and belong to the tree; most of the rest belongs to the process that found them.

The one thing the conversion changes materially is that all of it is now citable. A finding
without a slug cannot be referenced by the plan Step that acts on it, and seventy-seven of them
could not be until now.

### warm-probe-was-not-guaranteed-warm | high | A warm measurement against empty caches is a cold measurement wearing the wrong label

Measuring the module the census still reported unruled returned something that should not have
been possible: 380 modules cold and 380 warm, where the gap had been forty-three. Running the
claim screen minutes later returned 380 and 337, the gap intact.

The explanation is the screen's own method. The cold probe points the cache variables at a
temporary directory, so it is genuinely cold every time. The warm probe uses the real cache
directories and is warm only if something has already filled them. The first warm run of a
session against empty caches compiles exactly as a cold one does, reports cold numbers, and
then leaves the caches populated - so the next run is warm and the discrepancy disappears
before anyone looks for it.

Every warm figure this campaign has recorded was taken after a warm run had already happened,
so they stand. What was wrong is the screen's guarantee, not the numbers it produced: it
promised a regime comparison and delivered one only when the environment happened to cooperate.

The probe now runs the warm case twice and discards the first result. That makes the label
true by construction rather than by circumstance, which is the same correction applied to the
no-loss merge earlier - a guarantee the code enforces beats a guarantee the runner has to
remember.

Separately, `renta_web_open_replay_corpus` is ruled. It loads in neither regime and carries no
module-level importer, so it joins the conditional rule, and the census returns to zero
unclassified with the seven stale entries already accounted for.

### third-import-graph-blind-spot-is-a-string-class-path | medium | The last stale member is reached by a dotted class path in a table, which no import edge records

`cadrumo.core.errors.not_found` was the one stale member the ancestor fix could not explain,
because it is a module rather than a package. Traced, it is a third kind of edge the graph
cannot see.

Its module-level importer, `cadrumo.core.resources.errors`, is itself absent from the closure,
so the gap is upstream of both. What reaches them is a string:
`cadrumo.core.errors.registry._core` carries the literal
`"cadrumo.core.errors.not_found.CoreNotFoundError"` in an error table, resolved at runtime. A
real load holds all three modules; the graph records an edge to none of them.

That completes a set. This campaign has now found three distinct disagreements between the
import graph and the interpreter, each in a different direction. A function-scoped import is an
edge the graph records and a load may never walk. An ancestor package is a module the load
always holds and the graph never records. And a dotted class path in a data table is a
dependency written in neither form, invisible to both a static edge and the dynamic
`import_module` scan the census already performs.

No fix is attempted. The census could union its universe with what a cold load actually imports,
which would resolve this and any future blind spot of the same family, at the cost of a
subprocess on every run - and that trade belongs to whoever owns the census rather than to a
campaign passing through. What is worth leaving behind is that the remaining stale entry has a
cause, and the cause is neither a stale rule nor a missing module.

### lane-figures-describe-a-selection-ci-does-not-run | high | Every lane number in this audit comes from a path overlapping the CI recipe in one directory of eighteen

This campaign has quoted a "development registry lane" figure in a dozen findings - 46 failures,
then 36, then 41, then 42 - and treated the movement as the tree's state. The path producing
those numbers is `dev/registry/tests`, `dev/registry/conformance/tests`, `dev/quality/tests` and
one file, chosen early and reused since.

The recipe CI actually invokes names eighteen directories. It shares exactly one with that path:
`dev/registry/tests`. Seventeen directories that CI runs on every push have never appeared in a
measurement here, and two directories measured here are not in that recipe - one of them covered
by a different recipe, the other by none, which is the conformance omission already recorded as
critical.

The figures are not wrong, and that is the trap in them. Every one was correctly measured,
correctly reconciled against its own collection, and correctly swept for lost workers. What was
never checked is whether the thing being measured is the thing that matters, and the answer is
that it substantially is not. A campaign can execute a measurement discipline perfectly against
the wrong population, and this one did for the length of the work.

The lane the recipe defines is now running under the same reconciling method. Whatever it
reports, the previous figures should be read as describing a registry-focused subset chosen by
this campaign, not the gate CI applies.

This is the same defect as the plan's criteria going into the wrong section, and as the
footnote sizing reading an attribute the object does not carry: the method was sound and pointed
at the wrong thing. It is the third instance, and the cheapest check in all three cases would
have been to ask, once, what the thing being measured is called by someone else.

### three-dev-test-directories-are-named-by-nothing | critical | 163 tests sit in directories no recipe and no workflow names, and the conformance suite is only the smallest of them

The conformance omission recorded earlier is not a single oversight. Of twenty-nine test
directories under `dev/`, twenty-five are named by a justfile recipe or a workflow and four are
named by neither. One of those four is empty.

The other three hold tests: `dev/source_connectivity/tests` carries 105 across sixteen files,
`dev/tui/tests` carries 39 in one, and `dev/registry/conformance/tests` carries 19 in two. One
hundred and sixty-three tests that nothing runs, of which this campaign had found only the
nineteen it happened to be standing next to.

The conformance suite was reported as critical because it proves real filing outcomes. On
volume it is the smallest of the three, and source connectivity - the surface that decides
whether a registry source is reachable and current - is more than five times its size. Whether
that suite matters as much is not something this campaign can judge from outside it, and the
point is that nobody has had to judge it, because nothing surfaced the question.

The measurement took two attempts and the first was wrong in the usual way. A pattern requiring
an intermediate path segment did not match `dev/tests`, which the recipe names plainly, so the
first run reported five uncovered directories including one that is covered. The sanity check
that caught it was asking the pattern whether it matched a directory known to be named - one
line, and the same class of error this audit has now recorded six times.

Recommending nothing here. Adding three directories to a recipe is a one-line change and the
reason to hesitate is not difficulty: 163 tests that have never run in CI will not all pass, and
whoever wires them needs to be ready for what they say rather than surprised by it.

### never-run-tui-suite-reports-this-campaigns-own-defect | high | A coverage table names two interfaces the tree does not define, in a suite nothing runs

The three uncovered directories cannot be wired into a lane without knowing what they say, so
the smallest was run: 33 passed, 5 skipped, 1 failed, in fifteen seconds.

The failure is `test_the_coverage_table_only_names_interfaces_that_exist`, and it is this
campaign's subject exactly. `dev/tui/_coverage.py` names
`cadrumo.entrypoints.tui.flows.app.FlowTuiApp` and `...app.QuestionScreen`. That module defines
`FlowPresenter`, `FlowScreen` and `run_flow_tui`, and neither named class exists anywhere in the
tree. A table declaring what is covered has been naming two things that are not there.

The test that says so has existed for as long as the defect and has never once run.

That is the shape worth sitting with. The campaign spent forty findings on declarations that
stopped describing what they describe - an export list naming a retired surface, a location note
forbidding a move already made, a screen claiming six conditions while emitting eight - and
built gates to catch each. Here the gate already existed, correct and specific, and the defect
survived anyway because nothing invoked it. A gate nobody runs is not weaker than no gate; it is
worse, because it also carries the appearance of coverage.

Whether `FlowTuiApp` and `QuestionScreen` were renamed or removed is not established here, and
the table's owner should decide whether the entries or the interfaces are wrong. What is
established is that one of the three unwired suites reports a real defect on its first run, at a
cost of fifteen seconds, which answers the question the wiring Step depends on for that
directory.

### never-run-source-connectivity-suite-splits-three-ways | high | 101 pass, 20 error on absent custody infrastructure, and 9 drift - eight frozen hashes and one locator, per transient-syntax-error-masked-a-real-locator-drift

The largest unwired directory was run to answer what wiring it would cost: 101 passed, 9 failed
and 20 errored, in under ten minutes. The three groups want three different things and none of
them is "add a directory to a recipe".

The twenty errors are environmental. Every one fails at setup with `profile custody
infrastructure has not been composed`, and their names - real live authority, encrypted payload
round trips - say why: they need the encrypted profile storage that a headless runner cannot
compose. That is precisely what the `os_keychain` marker exists to declare, and these tests
carry plain `unit` and `hex_core` instead. Wiring the directory without marking them adds twenty
errors to CI for a precondition CI cannot satisfy.

Eight of the nine failures are frozen-hash drift. The census asserts a recorded sha256 per
capability and reports `capability coverage drift for coverage.remaining-calculation-helpers:
expected sha256:cf1081c0... got sha256:b460f149...`. The tree moved and the recorded state did
not, which is the failure mode this project's own rules name when they say frozen corpus counts
and baseline ratchets do not prove completeness. Nothing ran the check, so nothing reported the
drift, and the drift is now of unknown age.

One failure in `test_campaign_close.py` remains unclassified here.

Together with the TUI suite's single failure, both unwired directories examined report real
findings on first contact, and neither is a simple wiring job. The Steps naming them stay open
with this recorded, because the honest sequence is: mark the twenty, refresh or retire the eight
frozen hashes, understand the one, and only then name the directory in a lane.

### ninth-source-connectivity-failure-is-a-mid-edit-syntax-error | medium | SUPERSEDED by transient-syntax-error-masked-a-real-locator-drift: the IndentationError was hiding a real failure, not causing it

The failure left unclassified in the previous finding is `test_final_census_has_no_expired_
disappearance_or_unsupported_connection`, and it fails on an `IndentationError` at
`src/cadrumo/entrypoints/tui/ledger/controller.py:391` - a stray indented block sitting after a
closing bracket.

That file carries a pending diff. The working tree does not parse it, the last commit touching
it is a feature advance, and the concurrent campaign is evidently mid-edit. It is transient,
external, and not touched here.

So the source-connectivity suite's own state is eight frozen-hash drifts and twenty
environmental setup errors, not nine failures and twenty errors. The ninth belongs to whoever is
typing, and will disappear when they finish.

Two things follow that are worth more than the correction. A syntax error in the working tree
fails every test that imports the module, so a measurement taken during another writer's edit
can attribute their keystroke to the suite being measured - which this one nearly did, and which
the pending-diff check caught for the fourth time in this campaign. And a suite nobody runs was
the thing that noticed a broken file at all: nothing else in the session had imported that
controller.

### transient-syntax-error-masked-a-real-locator-drift | high | The ninth failure was not the IndentationError; the IndentationError was hiding it

The previous finding classified the ninth source-connectivity failure as another writer's
mid-edit syntax error and expected it to disappear when they finished. They finished - a sweep
now parses all 5,837 files under `src` with none unparseable - and the test still fails.

The real failure was underneath. `census capability locator drift for
inventory.stock-valuation: ingress:src/cadrumo/entrypoints/cli/_ledger_inventory_cli.py:
inventory_create now resolves to src/cadrumo/entrypoints/cli/_app_ledger_inventory_command_
specs.py:30`. The census records where a capability lives, the code moved, and the record did
not follow.

So the suite's own state is nine drifts, not eight: eight frozen hashes and one recorded
locator, both the same defect - a declaration holding a position the tree has left. That is
this campaign's subject appearing again in a suite nothing runs, which is now the third such
finding from the two unwired directories examined.

The correction worth keeping is about transients. The previous finding treated an external
syntax error as a complete explanation and stopped there. It was a real transient, correctly
attributed, and it was also concealing a real defect in the file being measured. A transient
that explains a failure is not the same as a transient that causes it, and the only way to tell
them apart is to re-run once the transient is gone - which cost three minutes and changed the
answer.

### ci-selection-run-rejected-by-its-own-reconciliation | high | 3,881 collected against 3,618 reported: 263 tests vanished and the result is unusable

The CI dev-tooling selection was run under the reconciling method, and the method rejected it.
Collection reported 3,881 tests. The run reported 142 failed, 3,416 passed and 60 errors, which
is 3,618. Two hundred and sixty-three tests are unaccounted for, and the log carries five
lost-worker markers.

No figure from that run is recorded here. The tempting one - 142 failures across the selection
CI actually invokes - would have been the campaign's first measurement of the right population
and is exactly the number to be most careful with. It describes 3,618 of 3,881 tests, and which
263 are missing is not knowable from the log.

This is the first time the reconciliation added by the eleventh criterion has caught anything.
Every previous run reconciled exactly, which made the check look like ceremony; twelve findings
quoted figures that were correct and the check that confirmed them cost a `--collect-only`. Here
it is the only thing standing between a crashed run and a headline number, because the summary
line reads as a complete result and says nothing about the gap.

Re-running is not attempted this iteration. Forty-seven minutes under xdist became unusable
partly through contention with this campaign's own measurements, and a serial re-run of eighteen
directories is a longer job than an iteration - so the honest state is that the CI-facing figure
remains unmeasured, and the earlier registry-subset figures remain the only ones this campaign
has.

### ci-selection-retry-launched-with-a-piped-exit-status | low | The retry captures tail's status, not pytest's, which is the first trap this campaign documented

The CI selection is being retried at two workers rather than automatic, on the reasoning that
the forty-seven-minute run lost 263 tests to worker deaths under contention this campaign's own
measurements were contributing to.

The retry was launched with the run piped through `tail`, so the `PYTEST_EXIT` it records is
tail's status and not pytest's. That is the first measurement trap this audit documented, in a
finding about reading a wrapper's exit code instead of the tool's, and it was reproduced by the
author of that finding roughly forty iterations later.

It is not worth killing the run to fix. A second heavy run competing with the first is what
produced the crashed workers in the first place, and the two numbers that matter - the collected
count and the pass/fail tally - are both in the captured output regardless of the exit line.
When the result is read, that exit line will be ignored and the reconciliation done from the
summary, which is what the eleventh criterion actually requires.

Recording it rather than quietly working around it, because the point of the criterion is that a
measurement states how it was taken. A run whose exit status is meaningless is usable if the
reader knows that, and misleading if they do not.

Separately confirmed while waiting: `dev/quality/tests` is named by two recipes, so its
appearance in this campaign's lane path was not measuring an unwired directory. The conformance
directory remains the only one in that path that no recipe names.

### empty-test-package-outlived-its-only-test | low | A test package survives with a docstring describing tests deleted in 2026-08

The fourth uncovered test directory holds no tests, which is why no recipe names it. What it
holds is an `__init__.py` whose entire content is `"""Tests for the live CLI baseline
generator."""`, and the test that docstring describes was deleted by a commit closing a
private-to-public module promotion, taking 213 lines with it.

So a package declares itself to be tests for a generator, and has declared that with no tests in
it since August. It is the smallest instance in this audit of the shape the whole campaign is
about, and it is worth one paragraph precisely because it is small: an export list naming a
retired surface and a package docstring naming deleted tests are the same defect at different
scales, and neither is caught by anything that runs.

No removal is proposed. An empty test package is harmless where a stale export list is not, the
deletion belongs to whoever made it, and the campaign has spent enough findings on the
difference between a gap worth reporting and a change worth making unilaterally.

What this closes is the accounting on the four uncovered directories. One is empty for a
traceable reason, and the other three hold 163 tests that no lane runs, of which two were
examined and both reported real defects on first contact.

### corrected-findings-now-point-at-their-corrections | medium | Three headings asserted figures or conclusions this campaign later revised, with the revision recorded only further down

An audit read start to finish carries its own corrections. An audit read by grepping for a slug
does not, and 222 findings is well past the length anyone reads through.

Three of this campaign's headings asserted something it later revised. One counted eighty
unstructured findings where seventy-seven are findings and three are section headers. One
classified a source-connectivity failure as an external syntax error, which was true and
incomplete - the error was concealing a real locator drift rather than causing the failure. One
summarised that suite as eight drifts where it is nine.

Each heading now names the finding that corrects it, in the summary field where a reader lands.
The bodies are untouched: what was written at the time stays as it was written, and the pointer
is added rather than the record rewritten.

That leaves three of 222 headings signalling a correction, which is the honest count and not a
reassuring one - it is only the corrections this campaign noticed it had made. A finding revised
by someone else's later work, or by a measurement nobody re-ran, carries no pointer and there is
no mechanism here that would add one.

### vacuity-screen-tests-broken-since-august-in-a-lane-ci-runs | critical | Sixteen tests fail on git exit 128 because a fix added a repository dependency their fixtures cannot satisfy

The crashed CI-selection run reported sixteen failures in `dev/audit/tests/test_vacuity_screen.py`.
A crashed run loses tests rather than inventing failures, so anything it reported is real, and
running that file alone confirms it: sixteen failed in 1.5 seconds, every one on
`CalledProcessError: git ls-files ... returned non-zero exit status 128`.

The cause is a commit from 27 August titled "screen only tracked test modules for vacuity". It
added `_tracked_test_paths`, which shells out to `git ls-files` with `cwd=root` and deliberately
refuses to degrade - the module's own docstring says absence of git is raised rather than
falling back to a filesystem walk, because a silent fallback restores the defect it was fixing.
That reasoning is sound.

The tests pass `tmp_path`. They contain no git initialisation at all - zero occurrences of git,
subprocess or monkeypatch in the file - so every one now runs the screen against a directory
that is not a repository, and git exits 128. The commit changed the screen and did not touch the
tests beside it.

What makes this critical rather than merely broken is where it sits. `dev/audit/tests` is named
by the dev-tooling recipe, so unlike the conformance suite this is a lane CI actually runs. Either
that lane has been red since August, or it has not been run in that time. Both are worth knowing
and this campaign cannot tell which from inside the worktree.

Not repaired here. The fixtures need a repository - `git init` in the temp tree, or a screen that
accepts an injected tracked-path set - and choosing between those is the screen author's call
about whether the git dependency belongs in the unit boundary at all.

### tui-boundary-proofs-fail-while-the-boundaries-hold | high | Seven tests that prove the import contracts bite are broken, and import-linter itself passes eleven contracts cleanly

The crashed run's second-largest failure group is seven tests in
`dev/tests/test_importlinter_tui_boundaries.py`. Run directly they fail in about a second, and
the contracts they guard are fine: `lint-imports` against the real configuration reports eleven
kept, zero broken, exit zero, over 5,749 files.

So the boundaries hold and the proofs that they bite do not. Those tests write a contract config
and a synthetic topology into a temp tree, call `lint_imports(no_cache=True)` with the working
directory moved there, and assert on the result. The call returns 1 where the test expects 0,
and the captured output carries only import-linter's box-drawing frame with no contract summary
in it. The installed import-linter is 2.14 and still accepts the `no_cache` keyword, so the
signature is not the cause; what the temp-tree run is failing on is not established here.

That is the detector-teeth pattern this campaign has argued for throughout, failing from the
inside. A contract that passes tells you the tree is clean. A proof that the contract would
catch a violation is what tells you the pass means anything, and seven of those have been
unable to run to completion.

Two lane observations came out of the diagnosis. These tests are `integration`-marked, so the
default lane deselects them - the first single-test run reported nothing ran, and the harness
said so in as many words: a green result there means the selection matched nothing. The suite is
reached by the dev-tooling recipe under its wider marker expression, so this is a CI-run lane,
like the vacuity screen and unlike the conformance suite.

Not repaired. Seven tests failing inside another campaign's boundary proofs need their author,
and the useful contribution is that the contracts and their proofs have been separated: the
first is verifiably sound, the second verifiably unrun.

### crashed-run-lower-bound-is-fifty-two-modules | medium | 142 reported failures across 52 modules, three examined and the rest left named rather than mined

The rejected CI-selection run remains unusable as a total and usable as a lower bound: every
failure it reported is real, and 263 tests it never reached may hold more. Reported, it names
142 failures across 52 modules - 37 under `dev/registry`, 27 directly under `dev`, 20 under
`dev/docs`, 17 under `dev/audit`.

Three of the 52 were examined here and each yielded a distinct finding: the vacuity screen's
sixteen failures on a git dependency added without updating its fixtures, the seven import-linter
boundary proofs failing while the contracts they guard pass cleanly, and the twenty-six generated
export tree failures already attributed to the serialization change.

The remaining forty-nine are named and not mined, deliberately. The plan this work serves is
registry declaration hardening, and the last two findings were about documentation runners and
import-linter fixtures - real, worth recording, and progressively further from the registry. A
campaign that follows every failing module in a shared tree stops being the campaign it was
chartered as, and the discovery chain that reached them was a qualification of this campaign's
own lane figures rather than an intent to audit the tooling at large.

What is left behind is the list and the method: run the module directly, read the first error
rather than the tally, check whether the file it blames carries a pending diff, and re-run once
any transient clears. Three modules took roughly one iteration each at that rate.

### second-live-monetary-scale-defect-in-modelo-353 | critical | A second field emits unscaled where its siblings emit cents, and the gate proving the first now fails on the count

The monetary-scale screen reports two sibling-scale disagreements where the plan's Verification
criterion says there is one. The known defect is modelo 200's casilla 03594, emitting unscaled
where 88 sibling amounts of width 17 in the same record emit cents. The new one is modelo 353,
revision 2026-desde-02, casilla 10, field `m353-2026.pagina01.f127`: unscaled where 7 sibling
amounts of width 17 in `m353-declaracion` emit cents.

The test that caught it is the one this campaign has held up as the right shape - a gate whose
teeth are proven against a live defect rather than a fixture, asserting exactly one
disagreement so that correcting the defect forces the test to be rewritten rather than
silently passing. It asserted one, found two, and failed. That is the design working: a gate
pinned to a known defect reports both a repair and a regression, and this is the second.

Two things follow for the plan. The Verification criterion stating "the one field that fails
this today is the plan's only known filing-correctness defect" is now false, and the criterion
is what a reader checks the work against. And the registry data carries no pending diff, so
this arrived through a commit rather than an edit in flight - the modelo 353 directory's recent
history is a closed-vocabulary canonicalisation and an extractor-link retirement, either of
which could have touched a field's declared scale.

Not corrected here. A monetary field's scale is filing-grade: emitting euros where the record
design expects cents is a hundredfold error in a submitted amount, and the fix is a registry
data change grounded in the official design for that revision, which is neither this
iteration's scope nor a change to make from a screen's output alone.

### monetary-criterion-figures-mapped-to-their-screen-conditions | medium | The criterion's two counts are 26 and 2, and the five unexpected-scale fields it does not count are a separate concern

Correcting the monetary criterion meant restating two numbers, and restating a number without
checking which measurement produces it is how this audit acquired several of its own errors. The
mapping was verified rather than assumed.

The criterion's first test - a field rendered by a wire type that scales, carrying a declared
scale, or one half of the official part split - is failed by exactly the screen's
`money_without_scale`, which the screen defines as a monetary casilla rendered as an integer,
text or another unscaled type. That count is 26, where the criterion said 24. Its second test,
that no field disagrees with the amounts beside it in its own record, is `sibling_scale_disagrees`,
now 2 where it said 1.

The screen also reports 5 `money_unexpected_scale` fields and 132 `money_split_representation`.
The split representations are the official part split the criterion already admits. The five
unexpected scales carry a declared scale and are therefore not failures of the criterion as
worded - they are decimals with a count other than two, which the screen itself says may be
correct on a unit security value and is simply recorded nowhere as an exception. They are not
folded into either figure, and the criterion is silent about them, which is a gap worth naming
rather than papering over with a third number.

Both criterion figures had drifted, not one. The defect count doubling is the finding; the
unscaled count moving from 24 to 26 arrived alongside it and would have gone unrecorded if the
restatement had copied the old number and changed only the part that prompted the edit.

### modelo-353-defect-is-not-new-its-classification-changed | high | The field was already recorded as unscaled; what is new is that it now also disagrees with its siblings

The previous finding reported a second live monetary-scale defect in modelo 353 as though it had
appeared through a recent commit. That over-claims, and this audit already contained the
correction.

An existing finding, `the-note-behind-the-filing-defect-says-nothing-about-the-wire-and-now-says-
so-in-quotation`, records that the modelo 353 field renders unscaled and quotes the design note
behind it - `Nota 4: Solo para periodos 02 y siguientes`, an applicability statement carrying no
scale, no decimal count and no sign convention. It even calls that field "the filing defect".

So the field was known. What changed is which condition it triggers. It was one of the unscaled
fields, failing the criterion's first test. It now also registers as a sibling-scale
disagreement, failing the second - meaning seven amounts of width 17 beside it in
`m353-declaracion` now emit cents where previously the comparison did not fire.

That is a smaller claim than "a new filing defect appeared" and a more precise one. It is still
worth the criterion correction: two fields now fail the sibling test where one did, and the
criterion said one. But the cause is a field moving between conditions rather than a defect
arriving, and the difference matters to whoever fixes it - the question is what changed about
the siblings, not what changed about casilla 10.

The check that would have caught the over-claim before it was written is the one this campaign
established for exactly this and did not run: search the audit for the subject before reporting
it as new. It found the eight already-stepped name-window revisions that way and then failed to
apply it four findings later.

### sibling-count-assertion-was-false-before-this-campaign-measured-it | medium | Nothing changed in modelo 353; the test asserting one disagreement has failed in every lane run since the module appeared

Chasing what changed about modelo 353's siblings found that nothing did. The 2026 export's
recent history is an encoding spelling corrected from `latin-1` to `iso-8859-1` in three lines,
a provenance refresh and a design-epoch bounding - no `data_type` touched. The field itself
still declares `data_type = 'integer'` at width 17, which is the unscaled rendering the audit
already recorded.

The answer is in this campaign's own lane logs. `test_monetary_scale.py` appears zero times in
the failure lists of two consecutive full-lane runs and twice in the two after them. The module
entered the tree between those runs and has failed in every run since it arrived.

So the assertion of exactly one sibling disagreement was already false when it was written, or
became so before it was first executed here. Nothing degraded; a test landed red and stayed
red, and this campaign noticed the failure four lane runs later while looking for something
else.

That also settles the previous two findings. The criterion correction stands - two fields fail
the sibling test - but the framing of both, first that a defect had appeared and then that a
field had moved between conditions, attributed change to a corpus that did not change. The real
event is a test arriving with an expectation the corpus did not meet.

The check that would have answered this in one command was available from the first: this
campaign keeps its lane logs, and asking when a failure first appears in them is cheaper than
reasoning about what might have caused it. Three findings were spent reasoning.

### registry-failures-dated-against-the-lane-logs | medium | Eight failures predate every measurement here and five arrived mid-campaign, two of them from commits to the module they test

Asking when each failure first appears in this campaign's six retained lane logs sorts the
current registry failures cleanly, and costs one pass over files already on disk.

Eight appear in all six runs: the generated export trees, the load census classification, the
real closure outcomes, the render check, the m303 envelope proof, the static inspection, the
modelo-specific embed classification and the regulatory prose parser channel. Those predate
every measurement this campaign has taken, which is what "inherited" has meant throughout and
is now dated rather than assumed.

Five appear first at the fifth run. Four are modules the concurrent campaign added or changed in
that window, including the monetary scale test already established as red on arrival. The fifth
was this campaign's own condition-count parity failure, which appears in exactly one run and
never again - the dating confirms the repair held rather than the failure merely moving.

One correction falls out. The two publication failures were reported here as "tests that predate
this work", on the reasoning that this campaign's additions to that module were signature checks
which pass in isolation. The first half was right and the second was not: those two tests appear
in no run before the fifth, and `_tree_publication.py` carries two commits from the concurrent
campaign that evening - one verifying the recovery package against the current authority, one
retiring a completed legacy orphan journal - which is exactly the recovery and journal behaviour
the two failing tests cover. They are new, and they are not this campaign's.

The technique is worth more than the table. A failure's first appearance in a retained log dates
it without reasoning about causes, and this campaign spent three findings reasoning about a
corpus that had not changed before running the one command that would have said so.

### inspection-authority-crossed-into-the-application-layer-by-decision | high | Four application modules reach the static inspection API a gate forbids, and a commit message says the crossing was decided

The static-inspection gate asserts that no runtime consumer references the inspection authority
and finds five files that do: `workspace.py`, `work_addressing.py`, `workspace_manifest.py` and
`workspace_producers.py` under `src/cadrumo/application/modelo`, plus a test beside them. Every
one names `RegistryRevisionInspection`.

Dated against the tree rather than reasoned about, the crossings arrive on 26 and 27 August, and
the commit that introduces the first says what it is doing in its subject line: "decide(tui-
architecture): S278, root a second field manifest at RegistryRevisionInspection". So this is not
a drift that nobody noticed. Somebody decided to root a manifest at the inspection authority, and
the gate forbidding exactly that has been red ever since.

That is a different situation from every other inherited failure this campaign has dated. The
others are a serialization change nobody intended to be visible, a test landing red, a rename
half-applied. This one is a deliberate architectural choice and a standing gate that contradicts
it, and one of the two has to give: either the decision supersedes the gate and the gate should
say so, or the gate holds and the manifest needs a different root.

Not resolved here. Which one gives is an architecture decision with a recorded rationale behind
it, belonging to whoever made it, and a campaign about declarations matching what they describe
should be the last to quietly delete a gate because something newer disagreed with it. What this
adds is that the disagreement is dated, attributed, and no longer sitting in a failure list as
an unexplained red.

### embed-classification-failure-is-three-conditions-not-one | medium | Twenty-one reconciliation failures split into seven unclassified modules, nine stale dispositions and three undispositioned literals

The modelo-embed classification gate reports twenty-one reconciliation failures against
forty-seven derived modelo-specific modules, and the pytest output truncates after the first,
which reads as twenty-one modules carrying no classification. Run directly, the screen says
otherwise.

Seven modules carry no classification: `_invoice_row_materialization` for modelos 347 and 349,
`_withholding_rows` for 190 and 193, `formula_runtime_m100`, three ledger binding families for
100, 130 and 131, and the modelo 303 annual summary bindings. Every one is a module the same
refactor split out - the identical set this campaign classified in the load census, arriving at
a second ledger that also needs them and was not updated either.

Nine are the reverse: a disposition naming evidence the screen no longer detects, mostly decimal
literals in the invoice and withholding binding families. Three are the third shape, a module
claiming to be machinery while leaving a regulatory literal undispositioned.

So one count covers a ledger missing entries, a ledger holding entries for things that are gone,
and a claim that does not cover what it claims about - the same three-way split found in the
load census's stale rules, in the four misstated revision openings, and in the generated trees'
drift classes. Four times now a single number has hidden three remedies.

Not adjudicated. The load-census rulings were derivable by measurement because loading is
observable; this ledger asks whether a Python literal encodes a value the law fixes, which is a
reading of intent against the official source and belongs to whoever authored the modules.

### this-campaign-was-one-of-the-four-undeclared-prose-parsers | high | A screen written here read design prose without enrolling in the channel, and the failure was filed as inherited for six lane runs

The last undiagnosed inherited registry failure names four undeclared regulatory-prose parsers.
One of them is `dev/registry/analysis/footnote_pointer_notes.py`, written by this campaign.

The channel exists because reading AEAT prose is permitted and must be declared: the ledger's own
ruling retains design-prose grammars rather than migrating them, on the reasoning that the prose
keeps changing and a one-shot import would remove the ability to onboard the next design. Its
condition is that enrolment authorises reading prose and authorises no value. A screen that
resolves a Contenido footnote pointer to the note beneath the table is exactly what the channel
governs, and it was added without an entry.

It is now enrolled, naming the corpus and stating what the enrolment does and does not authorise,
and the undeclared list falls from four to three. The ledger holds fifteen parsers and every
entry carries a corpus and a reason.

What is worth recording is not the fix but the six lane runs. This failure appears in every
retained log, and each time it was counted as inherited - a word this campaign used to mean
"present before any measurement here". It was, in part: two of the four modules date from 31
August. But the campaign added a third on 2 September and went on filing the whole failure as
someone else's for four more runs, because the label was applied to the failing test rather than
to its contents.

The dating technique established two findings ago would have caught it, and was applied to the
module list only after the diagnosis. Attribution has to reach the items inside a failure, not
just the first date the failure appeared.

### collision-gate-caught-a-deleted-adjudication-and-a-new-collision | high | One row was removed correctly and one was removed while its collision remained, and this campaign missed both for a day

A gate written here has been failing and this campaign did not notice, because the sweep that
dated the registry failures filtered on `registry` in the path and this gate lives under
`dev/quality`. A filter written to scope an inquiry excluded the author's own work from it.

What the gate reports is exactly what it was built for. The disposition ledger went from nine
rows to seven across two commits from the concurrent campaign, and the two removals are not the
same act. `extract_verdict_from_response_text` no longer appears in the census at all: that was
the one pair with byte-identical bodies, adjudicated here as owed a collapse, and somebody
collapsed it. Removing its row was correct and the gate's second direction - a row whose
collision is gone must fail - is what made the removal mandatory rather than optional.

`extract_pages_text` is the other case. Its row was deleted and the collision it describes is
still in the census, so the tree lost a reasoned judgement while keeping the thing it judged.
The row is restored with its original reasoning and a note recording the removal, because a
future reader finding it deleted a second time should know it has been deleted once already.

A third name arrived meanwhile. `declared_destination_ids` is defined in the TUI's routes and in
its navigation module, both reading a closed set from a type alias through `get_args` - and
reading different aliases, the modelo workspace's destinations in one and the whole TUI's in the
other. The first carries a docstring warning that a literal copy would be a second definition
agreeing with the first only until it does not. Neither is a copy, so that warning does not
cover this: a caller importing the wrong one gets a different set, not a stale one. Adjudicated
as owed a rename.

The gate passes at five tests. What it demonstrated is worth more than its green: it caught a
correct removal, an incorrect removal, and an arrival, in a ledger nobody was watching.

### adjudication-was-acted-on-and-the-collapse-is-now-watched | medium | The duplicate this campaign named as owed a merge was merged into the home it named, and the result is held at one definition

The previous finding said the byte-identical verdict extractor had been collapsed. Checking what
survived found no function of that name anywhere in `src`, which reads as a deletion rather than
a merge - and would have been recorded as one had the commit not been read.

It was a merge. `refactor(sede): share the marker verdict extraction across the identity checks`
removes seventeen lines from each of the two check modules and gives both
`from .._adapter_utils import extract_marker_verdict`. The pair is now one function in
`_adapter_utils`, which is precisely the home this campaign's disposition named: both copies
already depended on that module's shared negative-marker table, so that is where the single
definition belonged.

That is the first adjudication written here to be acted on by another writer. The disposition
named a remedy, someone applied it, and the disposition ledger's second direction then required
the row's removal - which is why the row was correctly deleted and the gate correctly demanded
it.

The collapsed concept is now watched by the canonical-definitions gate at one definition,
alongside the sixteen this campaign collapsed itself. That gate exists because a whole-tree
commit had already restored a set of collapsed duplicates once, silently, and a merge nobody
watches can be undone the same way.

Also confirmed this iteration: all eight gate modules written here pass, fifty-three tests, exit
zero - checked after finding that the sweep which dated the registry failures had excluded this
campaign's own directory from its filter.

### second-adjudication-acted-on-and-the-vanishing-guard-is-gone | medium | The contract conflict's most dangerous property was removed; the conflict itself remains and the row now says so

Measuring how widespread the optimiser-erased type guard is returned zero `assert isinstance`
in production code, which contradicted a finding written here days ago. Reading the file
rather than trusting the count showed why: the guard is gone.

`resolve_bucket_event_repository` in the actions module now calls
`require_concrete_repository(repository, BucketEventHistoryRepository, reason=...)`, a helper
that raises rather than asserting. Under `python -O` an assert disappears and the return
annotation goes on promising a concrete class nothing checks; a raising helper does not. That
was the sharpest half of the contract-conflict adjudication and it has been fixed.

The conflict itself stands. The projection version still returns the protocol and accepts any
implementation of it; the actions version still requires the concrete class. Two contracts under
one name in one package, as recorded - only now the disagreement fails loudly in every build
rather than silently in optimised ones.

The disposition row is updated rather than closed, because the row exists to say a decision is
owed about which contract is right, and that decision has not been taken. Closing it on the
strength of a partial repair would be the ledger claiming a resolution nobody made.

That is the second of this campaign's nine adjudications to be acted on by another writer, after
the verdict extractor's merge. Neither was requested; both were named in a file anyone can read
and both were addressed within a day. A ledger that states a remedy and its reason turns out to
be actionable in a way a finding buried in prose is not.

### ci-selection-measured-at-167-failures-and-72-errors | critical | The lane CI actually runs carries 239 failing or erroring tests of 3,881, measured cleanly at last

The CI dev-tooling selection has been measured to a total that reconciles. 3,881 tests
collected; 167 failed, 3,640 passed, 2 skipped and 72 errored, which is 3,881 exactly. No
lost-worker marker. Eighty-five minutes at two workers, where the automatic-parallelism attempt
lost 263 tests to crashed workers in forty-seven.

So the lane CI invokes on every push carries 239 tests that do not pass. This campaign has
quoted a registry-subset figure of forty-two for most of its life and qualified it four findings
ago as describing a selection sharing one directory of eighteen with this one. The qualification
was right and understated: the real lane is two orders of magnitude larger in failures.

The per-module breakdown is not usable from this run. The command piped pytest through `tail`,
which was recorded at launch as costing the exit status; it also truncated the failure list to
its last thirty-nine lines of two hundred and thirty-nine. The summary line survives because it
is printed last, which is why the total reconciles and the detail does not.

That is the second cost of the same mistake, and the more expensive one. An exit status has a
known workaround - read the summary - and a truncated failure list does not: the information is
simply gone, and recovering it means another eighty-five minutes. The earlier finding treated
the pipe as a nuisance affecting one line. It affected the part of the output this campaign
spends its iterations reading.

What stands: the total, the reconciliation, and the three modules examined from the earlier
crashed run, whose failures a lower bound made trustworthy even when its total was not.

### lane-criterion-named-a-lane-nobody-runs | high | The acceptance criterion quoted fifteen failures over a path sharing one directory of eighteen with the lane CI invokes

The plan's lane criterion said "the lane is red: fifteen failures over both directories", and a
reader would take that as the state of the gate this work is accepted against. It is the state
of a path this campaign chose on its first iteration and reused without asking what CI runs.

Corrected, the criterion now names both and says they are not two readings of one number. Over
the registry directories, the count has moved between fifteen and forty-two and every failure in
it is dated and attributed. Over the eighteen-directory selection CI invokes, measured once to a
reconciling total, it is 167 failures and 72 errors of 3,881 tests. The registry path shares a
single directory with that selection, so the smaller figure was never a subset of the larger.

The criterion's own reasoning survives and is worth keeping intact: it deliberately records no
passing count, because the passing count rises whenever this plan adds a gate and moved by two
within a day of being written. That instinct was right about one number and absent for the
other - the failure count was quoted for iterations without anyone asking which population
produced it.

A criterion is what a reader checks the work against, so a criterion quoting the wrong lane is
worse than one quoting no lane at all. This is the third acceptance criterion this campaign has
had to correct after measuring what it asserted: the screen count, the monetary defect count,
and now this.

### criterion-claimed-no-failure-belonged-to-this-plan | high | The accounting summed to a fifteen-failure state that no longer exists and asserted an ownership that was wrong

Sweeping the Verification section for figures found one paragraph accounting for every lane
failure by category: eight generated trees, four over uncommitted files, two classification
modules, one boundary check. That sums to fifteen, which is the state the adjacent sentence
described before it was corrected, and the lane has since been at forty-two over the registry
directories and 239 over the selection CI runs.

The stale sum is the smaller problem. The paragraph ended "None belongs to this plan, and that
was established by name rather than assumed" - and one did. The undeclared-prose-parser failure
names four modules and one of them is a screen written here, added on 2 September and filed as
inherited through six lane runs. The claim was established by naming the failing tests and not
by reading the module lists inside them.

The accounting is replaced with a dated one, which is the only version that stays true as the
tree moves: eight failures predate every measurement here, five arrived mid-plan, and one
belonged to this plan and is now enrolled. The correction records the misattribution rather than
quietly fixing the total, because a criterion that once asserted clean hands is exactly the
sentence a later reader would cite.

Three of this plan's criteria have now been corrected against measurement and a fourth against
its own arithmetic. The common cause is not carelessness in any one of them: each was written
from a figure that was true when taken, in a document that offers no way to notice when its
figures stop being true.

### the-obvious-fix-for-stale-criteria-is-forbidden-and-rightly | medium | A gate checking the plan's figures would make code depend on the vault, which the project explicitly forbids

Four of this plan's criteria have been corrected after measuring what they asserted, and the
diagnosis written for the fourth was that the document offers no way to notice when its figures
stop being true. The obvious repair is a gate: extract the checkable claims - ten screens,
twelve criteria, eight conditions - and assert each against what the tooling reports.

It cannot be built. The project's code-stands-alone mandate forbids embedding references to
`.vault/` documents in source, tests or configuration, on the ground that the vault is removable
development scaffolding and the reference direction is one-way: vault documents cite code by
locator, and code never cites the vault. A test reading the plan to check its numbers is exactly
the dependency that mandate exists to prevent, and it would fail the moment someone removed the
scaffolding the code is not supposed to know about.

That is worth recording rather than quietly not building, because the reasoning generalises. A
document's figures going stale is a real defect, and the tempting fix - make a machine watch the
document - inverts a dependency the project has deliberately chosen. The cost of that inversion
is paid later and by someone else, which is the same trade this campaign has refused four times
in the form of baselined gates.

What replaces it is cheaper and already demonstrated. Two figures in this plan were rewritten to
name their source rather than state a number: the screen count is whatever the analysis package's
entry point enumerates, and the dev-owned phase's Step count became "every Step" instead of
twelve. A figure that says where it comes from does not need a machine to check it, because the
next reader can.

### a-figure-recording-history-does-not-go-stale | medium | Only one of the Verification section's remaining counts needed retiring; the others describe past events and are correct as written

Applying the name-your-source remedy to the rest of the Verification section found fewer targets
than expected, and the reason is a distinction the earlier corrections had not drawn.

Three counts remained. "Twelve criteria decide whether the work achieved what it was for" is a
live figure: it counts the paragraphs beneath it, it has to be maintained, and it was already
wrong once. It now reads "the criteria below decide", which cannot drift because it names what it
refers to instead of counting it.

The other two are history. "A third condition had to stop firing on five revisions a neighbouring
condition already described more accurately" records what was true when that decision was taken.
"Two screens named every kind they emit while still opening with a count from an earlier version"
records why an eighth gate was written. Neither describes the tree now, and if the tree changes
neither becomes false - they would become false only if the events they record had not happened.

That distinction is worth stating because the correction habit this campaign has built could
easily damage such sentences. Four criteria were corrected for quoting figures that stopped being
true, and the reflex it leaves is to treat every number in a document as a liability. A number in
a record of what was done is not a claim about the present, and rewriting it to name a live source
would replace a true statement with a misleading one.

The test is what the sentence would be doing if the figure changed. A criterion saying twelve
criteria exist is wrong when there are thirteen. A sentence saying five revisions were reclassified
is still right when a sixth is reclassified later, because it was never counting the total.

### refusal-test-was-invalidated-by-someone-fixing-the-thing-it-relied-on | medium | A fixture pinned to a revision with no generated layout broke when that layout was published

The render-check suite gained a second failure, and its cause is the most benign one available:
`test_a_revision_without_a_generated_layout_is_refused_by_name` named modelo 200's 2025 revision
as an example of a revision that cannot be rendered, and somebody published its export tree.

The test then failed with `DID NOT RAISE ValueError`, which reads as the refusal being broken. It
is not. The refusal works; the example stopped being an example. A test pinned to a defect fails
when the defect is fixed, and that is usually the design working - the sibling-scale gate is
pinned deliberately for exactly that reason - but here the pin was to an absence that nobody had
promised to preserve.

The fixture is now derived. The test finds a revision carrying no export layout, asserts the
search found one at all, and exercises the refusal against it. Thirty-four revisions currently
qualify, so the search is not near empty, and if the corpus ever reached zero the assertion says
so rather than the test passing over nothing.

The distinction between the two kinds of pin is worth keeping. A gate pinned to a live defect
should fail when the defect is corrected, because somebody must then decide what replaces it. A
gate pinned to a convenient example should not, because nothing about that example was ever a
claim. Both look like a hardcoded coordinate in the source; only the first has a reason recorded
beside it.

### a-pin-to-a-live-defect-owes-its-replacement-in-writing | medium | Two of this campaign's tests pin revisions the plan has open Steps to rename, and neither said what happens when they are

Scanning this campaign's own tests for hardcoded coordinates found three files carrying them and
one distinction that had not been applied to its own work.

The render-check fixture repaired in the previous finding was pinned to a convenient example and
broke when the example improved. The name-window tests are the other kind: they pin modelo 151
and modelo 185 because those revisions genuinely misstate their windows, and the plan carries
open Steps to rename both. When someone renames them these tests fail, and that failure is the
correction arriving.

Neither test said so. A gate this campaign wrote earlier - the sibling-scale comparison - is
explicitly held up in the plan's own criteria for being proven against a live defect and saying
what must replace it once the defect is corrected. The name-window tests do the first half and
not the second, so the next person to act on an open Step meets a red test with no instruction
in it.

One now carries the instruction: what the pin is, that its failure is the rename landing rather
than a regression, what should replace it, and that deleting the test is the wrong repair
because the direction it distinguishes is why the condition was split from its opposite.

The general form is small and worth stating plainly. A test pinned to a defect is a message to
whoever fixes the defect, and a message that only says "assert equals" is not one. Fourteen
tests in that module pass; the one that will fail on purpose now explains itself.

### every-pin-to-a-stepped-defect-now-carries-its-replacement | medium | The three name-window tests pinned to defects the plan still owes a rename now each say what their failure means and what replaces them

The previous finding recorded that one of the pinned tests had been given a
replacement instruction and the others had not. All three now carry one:
`name_opens_before_window` (modelo 185), `name_opens_after_window` (modelo 151),
and the open-end condition (modelo 721, replaced by modelo 194, which sits in the
same state for the same reason).

Each instruction states the same four things: that the pin is deliberate, that
the plan carries an open Step whose landing turns the test red, that the red is
the correction rather than a regression, and what coordinate takes its place -
naming a live successor where one exists and falling back to construction where
none does. Each also says not to delete the test, because in every case the
condition exists apart from a near-neighbour precisely to keep a direction or an
exclusion visible, and deleting it would silence that distinction rather than
retire it.

The general form is worth stating once: a test pinned to a defect is a message
to whoever repairs the defect. A pin that only asserts a coordinate leaves that
reader a red test and no account of why it is red, which is how a correct fix
gets reverted or a gate gets deleted to make a suite green. Fourteen tests pass
in the module, exit 0, and the count of pins carrying an instruction equals the
count of pins.

### a-generator-refactor-left-twenty-one-attestations-stale | high | Twenty-one published export trees stopped reproducing on 2026-09-03; all sampled differ only in the manifest, so the records are correct and the attestations are not

The corpus gate went red against a tree that had been green the day before. The
newly non-reproducing trees are `151`, `202`, `210`, `222`, `232`, `303`, `322`
and `353` - twenty-one revisions in all. Eleven were classified directly: every
one reproduces its record bytes exactly and differs only in its generation
manifest. Cleared bytecode first, because stale `__pycache__` has twice produced
a false registry finding in this campaign; the state survived the clear, so it
is real.

The cause is visible in the intervening commits, which move the generator's
surfaces - the decimal separator and export repeat named at their call sites,
the invoice row materialization surface followed, the loader and schema surfaces
split. None of them changed what the records say. They changed what produced the
records, which is what the manifest attests, so every manifest in the corpus
went stale at once while the shipped filing data stayed correct.

The finding for the register is that the shipped attestations now claim inputs
that no longer exist. Republication is the remedy and it is safe for this class,
but it lands in generated trees under `src/` and is outside this work's scope;
the population is named here so the republication is a decision somebody takes
rather than a state nobody noticed.

### a-ledger-of-a-mechanical-mass-state-is-churn-not-explanation | high | The generated-tree gate demanded a written reason per tree for a condition that arrives twenty-one at a time, so it was split by class

The gate as written required every non-reproducing tree to carry a disposition
row, without distinguishing the class that is unsafe to republish from the class
that is merely stale. That was tolerable while both classes were small. The
refactor above showed what it costs when they are not: the honest response to
twenty-one manifest-stale trees would have been twenty-one rows all saying "a
refactor moved the generator", and the next refactor would ask for the corpus.
A file that grows by bulk on every refactor stops being read, and a reader who
learns to add rows to make a gate green has learned the opposite of what the
gate was for.

The two classes were separated on the ground that they fail for different
reasons and want different work. Record drift keeps the ledger: regenerating one
of those trees ships something worse than what is published, so each member owes
a written account, and the gate still refuses in both directions - a drifting
tree with no row fails, and a row whose tree has been repaired fails too.
Manifest staleness is now asserted rather than excused: the claim that makes the
class safe is that the records reproduce byte-for-byte, and that claim is
checkable on every member, so a tree calling itself provenance-only while a
record differs fails. The population is reported by the screen, which is the
reporting channel, not the gating one.

Both directions were demonstrated against constructed ledgers rather than by
mutating the file: dropping a row from the ledger is caught, adding a row for a
tree that does not drift is caught, and a provenance-only row placed in the
record-drift ledger is caught. The ledger fell from six rows to two, and that is
not the measure of anything - the two remaining rows are the two trees where
republishing would do harm.

The general lesson is about gate granularity rather than this gate. A per-item
explanation is the right instrument for a condition that arrives one at a time
and has a per-item cause. For a condition that arrives in bulk from a single
cause, the per-item ledger records the cause once per victim and calls it
accounting; what belongs there instead is the property that makes the bulk state
tolerable, asserted over every member.

### a-successor-that-is-itself-scheduled-for-correction-is-not-a-replacement | medium | All three name-window pins named live successors, and every one of those successors carries its own open rename Step

The replacement instructions written into the three pinned tests each named a
coordinate to move to when the pin's own defect is repaired. Checking those
claims against the corpus rather than leaving them asserted showed the naming
was right on the facts and wrong on the conclusion. Modelo 194's 2024 really is
in the same state as modelo 721's, and modelo 720 and modelo 322 really do hold
the only other members of the two directional kinds. But the plan carries an
open rename Step for every one of them - 151, 185, 720, 322, 194 and 721 - so
each named successor leaves at the same time as the coordinate it was offered to
replace.

An instruction that points the next reader at a coordinate scheduled to
disappear is worse than one that says nothing, because it will be followed. All
three now say that the other member is a companion rather than a successor, that
the cluster empties the kind entirely, and that the replacement is therefore
constructed - a real revision copied with its opening year moved or its closing
bound removed, which is the technique the sibling conditions in the same module
already use.

The general form: a replacement instruction is a claim about the future corpus,
not the present one, and checking it means asking what else the plan is going to
change, not only what the registry holds today.

### a-directory-ci-never-runs-held-a-stale-interface-table | high | dev/tui/tests reports 39 tests and one failure: the coverage table named two classes a refactor had removed

The three test directories the plan proposes naming in a lane were run to
establish what they report, which is the stated precondition for naming them.
`dev/tui/tests` collects thirty-nine and exits 1. The single failure is a
coverage table naming `FlowTuiApp` and `QuestionScreen`, neither of which the
tree defines: the flows module was refactored from an app-plus-screen pair into
a single screen with panes, and the table was not followed. The test's own
docstring states the intent it failed to deliver - "a rename must break the
table loudly, not quietly drop coverage" - and it did break loudly, into a
directory no lane executes, which is the same as not breaking at all.

The repair is not the rename it first appears to be. The refactor collapsed two
interfaces into one and turned the question view into a pane, and the inventory
counts only `App` and `Screen` subclasses as interfaces, so the pane cannot be
named in the table at all. The corrected entry is a single interface with a
comment saying why one is the whole of it; naming the pane would have kept the
gate red while looking like a fix. Thirty-four pass and five skip after the
correction, exit 0. The five skips want rendered SVGs that a separate render
command produces, which is a genuine precondition rather than a masked failure.

This is the argument for the lane Step in concrete terms: the directory was not
merely uncovered, it was uncovered and red, and the failure it held was a stale
declaration of exactly the kind this campaign exists to find.

### the-source-connectivity-step-quoted-a-count-nobody-had-recollected | medium | The Step said a hundred and five never-run tests; a live collection reports a hundred and thirty, of which the default lane selection admits a hundred and eight

The Step naming `dev/source_connectivity/tests` for a lane carried a figure from
an earlier measurement. Collecting the directory today reports a hundred and
thirty, with the default marker selection admitting a hundred and eight and
deselecting twenty-two. The Step now carries both numbers, because they answer
different questions: what the directory holds, and what naming it in the lane
would actually run.

Two hypotheses about that directory were wrong and are recorded because each was
plausible enough to have been written up unchecked. The first was that its tests
carry no `unit` marker and so would stay deselected even after the lane named
them; they carry it, and the selection proves it. The second was that sixteen
unfixtured `bundled_authority()` calls explain the directory's slowness; a
profile of the cache-hit path shows a repeat call costs 0.21 seconds and returns
the identical object, so repeated construction is not the cost. What the timing
does show is a startup shape worth knowing: the first authority build costs 103
seconds, a further one-time 18 seconds is spent on the call after it, and every
call thereafter is 0.21. That is a per-process cost, paid once per test worker,
not a per-test one.

The per-test cost in this directory is therefore still unexplained, and this
entry says so rather than offering a third guess. It will be read off a
durations report from the completed run rather than inferred, and no second
pytest was started against the directory while the first was still running,
because two runs over one cache contend and would have made both readings
untrustworthy.

### the-repository-already-answers-which-tests-no-lane-reaches | high | A hard gate computes the unreached set with no allowlist, and it disagreed with both my hand analysis and the plan

Three Steps propose naming test directories in a lane on the grounds that CI
never runs them. Comparing the directory listing against the justfile by hand
gave a set of four, which felt like a finding. It was not: `dev/tests` is named
by the tooling lane, `dev/registry` appears in a deptry invocation rather than a
pytest one, and `dev/source_connectivity/tests` is named by no recipe at all yet
is still reached, because it sits in the pyproject `testpaths` that every
path-less recipe falls back to. Thirteen declared lanes cover it.

`dev/tests/test_lane_reachability.py` already answers this question properly. It
resolves lanes from config, recipes and workflows, asks both whether a lane's
path scope covers a file and whether its marker expression selects each test,
and keeps no baseline. Run today it fails with a precise worklist: three tracked
files sit outside every lane's path scope - two in
`dev/registry/conformance/tests` and one in `dev/tui/tests` - and a hundred and
fifty-six findings in total, the remainder being tests whose markers no covering
lane selects, including nineteen in `dev/packaging/tests` that are path-covered
but marker-deselected.

Two corrections follow. The Step proposing to name `dev/source_connectivity/tests`
rested on a false premise and has been rewritten to record that the directory is
already reached; its hundred and thirty tests are run by the default unit lane,
so whatever they report, they have been reporting it in CI rather than in
silence. And the justfile comment introducing the tooling lane still says
`testpaths` names "only `src/cadrumo` plus one packaging file", which stopped
being true when the source-connectivity directory was added to it; the comment
sits outside this work's file scope and is recorded here rather than edited.

The method lesson is the one this campaign keeps relearning from the other
direction. Before measuring something by hand, ask whether the repository
already measures it, and prefer the gate's answer to your own: mine was wrong in
two independent ways, and the gate's worklist is per-test where mine was
per-directory. A hand analysis that merely agrees with a gate is wasted work; one
that disagrees is a defect in the analysis until proven otherwise.

### the-source-connectivity-failures-are-a-stale-reviewed-set-not-a-stale-count | high | Nine tests fail on a selector digest that no longer matches the live helper set, and they fail in the default CI lane rather than in silence

The directory completed at nine failed, ninety-nine passed and twenty-two
deselected, exit 1, in twenty-three minutes. The deselection matters: the run
inherited the project's default marker expression, so those hundred and eight
tests are the same ones the default unit lane selects, and the nine have been
failing in CI rather than out of reach of it. That is a different and better
state than the plan assumed, and it is the second correction today to the same
Step's premise.

Eight of the nine sit in the census-completeness module and one in the campaign
close. The failure is not the frozen count those test names advertise. It is
`capability coverage drift`: the census entry for the remaining calculation
helpers declares a sha256 over its reviewed selector set, and the live set now
hashes to something else, so the helper population moved after the review. The
count assertion never got the chance to fail.

The remedy is a review, not an edit. The digest exists to make an unreviewed
change to the helper set visible, so recomputing it to restore green would
delete the finding rather than resolve it; whoever re-reviews the set republishes
the digest as the product of that review. An attempt to name which helpers moved
failed honestly and is recorded as such: the entry's `capability_ids` is empty,
because the digest and not a list is the stored identity, so a diff against it
compares against nothing and reports the entire live population as new. The
figure that reconstruction produced is an artefact and is not repeated here.

One further defect is visible in the failing names themselves. A test is called
`test_s115_freezes_reviewed_s112_helper_set_by_secondary_count`, embedding two
plan Step identifiers in a test name. Code does not cite the project's
development records in either direction, and a Step id in a test name is that
citation in its most durable form: it outlives the campaign that produced it and
means nothing to the next reader. The rename is owed, and belongs with whoever
resolves the digest review rather than as a drive-by edit to a red test.

### the-conformance-directory-timed-out-on-a-host-that-was-already-saturated | medium | A closure test hit the 300-second per-test ceiling while the machine carried a hundred and sixty python processes at full CPU

`dev/registry/conformance/tests` ran five tests green and then
`test_cli_live_mode_uses_canonical_loaders_but_blocks_without_durable_filing_proof`
struck the per-test timeout ceiling, with the dump landing inside a deepcopy.
The run exited 1 with no summary line, because the timeout killed it before
pytest could print one.

The finding is deliberately not "this test is pathologically slow". The harness
banner recorded the host at 100% CPU across twenty-four cores with a thousand
processes and a hundred and sixty of them python, which is this tree being worked
by several sessions at once. A three hundred second ceiling struck under that
load is not evidence about the test. A Step now carries the re-measurement on an
uncontended host, and it is a precondition of naming this directory in a lane:
adding a path whose first slow test can consume the ceiling would make the lane's
failure mode a timeout rather than an assertion, which is the least legible
failure a contributor can be handed.

### a-deleted-gate-left-its-pattern-table-orphaned-and-its-violations-standing | high | The marker-integrity gate was deleted with 1770 lines; its declarative half survives with no consumer, and two test names it forbade are back

Two failing test names carrying plan Step identifiers -
`test_s115_freezes_reviewed_s112_helper_set_by_secondary_count` and
`test_s44_runner_observes_every_live_no_recovery_outcome` - raised the question
of which gate should have refused them. One did.
`dev/tests/test_marker_integrity.py` walked every test module's comments,
docstrings and durable symbol names for exactly this leak, and it was deleted in
`23eadb3884`, a private-to-public promotion sweep that removed two hundred and
five files.

Its declarative half was not deleted with it. `dev/tests/_marker_metadata_patterns.py`
still ships the pattern/target/near-miss triples, including a `W01.P02.S03`
firing fixture and a "the W3C standard" near-miss, and its module docstring
still names `test_marker_integrity` as the walk that consumes it. Nothing in the
live tree imports it: the only other copies are snapshots under `var/`. The
declaration survived its consumer, which is this campaign's subject exactly,
and the two Step-id test names are what the absence costs.

The pattern table being intact is the opportunity. A restored gate does not need
the deleted eighteen hundred lines, only the walk over test-module names and
docstrings that the table already declares, and it lands with two known
violations that have per-item causes rather than a bulk state - the shape where
naming each one is explanation rather than churn.

### the-src-to-dev-boundary-survived-that-deletion-and-a-third-hypothesis-died-checking-it | medium | The same sweep deleted the dev-path isolation gate, but its rule moved rather than lapsed, and the surviving gate's docstring is what misled

`test_dev_path_isolation.py` went in the same commit, and
`test_governance_corpus_isolation.py` still describes a deliberately
non-overlapping division of labour with it, in the present tense, saying that
gate "already closes the tooling tree for PYTHON modules ... and is proven".
Its data scanner does exclude Python modules, delegating them to the AST
families, and its `GOVERNANCE_TREE_ROOTS` names only `.vaultspec` and `.vault`.
Read together those facts say a `dev/` path literal in a shipped module is
caught by nothing, and a probe confirmed the governance scan is silent on one
while catching a `.vault/` literal in the same file.

It is caught. `dev/quality/import_hygiene_scan.py` declares itself the single
authority for the one-way boundary and carries three families for it, and
`find_dev_path_reach_violations` returns the planted literal when asked
directly. The rule moved to a better home during the sweep; only the sibling
gate's prose stayed behind, still crediting a module that no longer exists.

That prose is the defect, and it is worth recording for what it nearly caused:
three hypotheses in two iterations have now been killed by probing rather than
reasoning - that a directory's tests carried no lane marker, that repeated
authority construction explained a slow suite, and that this boundary had
lapsed. Each was consistent with everything visible at the time. The cost of
checking was one command in each case, and the cost of not checking would have
been a confident false finding in a record other people act on.

### the-orphaned-pattern-table-has-a-consumer-again-and-a-case-it-was-missing | high | Restoring the walk unchanged would have been green over sixteen files carrying a step id in a test name

The deleted marker gate's pattern table was reconnected, but the first
measurement said the restoration was not worth making as it stood: applied to
every tracked test symbol name, the whole table reported zero. The two names
that raised the question - `test_s115_...` and `test_s44_...` - matched none of
its cases, because the table names process NOUNS (`adr`, `wave`, `plan`, `pr`,
phase) and the live form is an ADDRESS. The nearest case matches the prose
"Step 3". A gate restored on those patterns alone would have passed over the
defect that motivated restoring it, which is the failure the table already keeps
a retired transposed pattern to illustrate. That lesson was written about a
pattern spelled `paln`; it applies unchanged to a table with a missing case.

The case now exists: a bare step id in a durable symbol, two to three digits.
The digit bound is the discrimination, not decoration - it admits the whole live
step range while leaving a single digit to the domain, so an S3 client test
keeps its name, and both halves are declared as the table's fixtures require.
Measured over every tracked test module, it finds thirty-seven names in sixteen
files: four under `dev/`, twelve under `src/`, one of them a whole module named
`test_s423_selected_language_cli.py`.

The table has a consumer again. It runs the table's own discrimination control,
asserts the retired transposed pattern still matches nothing live, and pins the
step-id case to the four `dev/` files, with the replacement instruction the pin
owes: when the renames land the expectation becomes the empty set and the
assertion stays, because its value afterwards is that it stays empty. The `src/`
population is recorded here rather than asserted, since this work does not own
those files and an assertion over them would go stale on somebody else's
schedule. Three tests pass, exit 0, and the reachability gate confirms the new
module is itself lane-reached - a marker gate outside every lane would be the
same defect it exists to catch.

One method failure is worth recording against my own earlier entry. The first
measurement of this population reported fourteen files, and it was wrong: the
listing was piped through `tail`, which cut two alphabetically-earlier `dev/`
files off the top - including one in this campaign's own subtree. This is the
same truncation that opened this campaign's trap list and that has now cost a
figure three separate times. The failure mode is stable enough to state as a
rule: a measurement whose output is piped through `head` or `tail` is not a
measurement, because the number that matters is as likely to be in the part that
was cut as in the part that was read.

### the-development-tree-step-id-names-are-gone-and-the-pin-redeemed-itself | high | Four test symbols renamed, the gate's expectation is now the empty set, and the rename changed no behaviour

The four `dev/` test symbols carrying a plan step id were renamed to describe
what they assert: a translation-helper guard, a simplified-projection anchor
set, a capability count guarding its reviewed set beside the digest, and a
runner observing every live no-recovery outcome. Each name occurred exactly once
across the justfile, the workflows, `pyproject.toml` and the whole development
tree, so no lane addressed any of them as a node id and the renames could not
orphan a selection.

Behaviour is unchanged, which the run shows rather than asserts: eight passed
and one failed, and the failure is the census digest drift already recorded
here, reporting the identical expected and observed sha256 values it reported
before the rename. A rename that leaves a red test red in exactly the same way
is the evidence that it renamed nothing but the name.

The pin then redeemed itself. The gate written last iteration held the four
files as its expectation and carried the instruction that when the renames
landed, the expectation should become the empty set and the assertion should
stay. That is what happened, one iteration later, and the docstring now says so:
the value of the assertion afterwards is that the set remains empty, which is
what a closed gate looks like. It is the first pin in this campaign to complete
the full cycle it was written for - pinned to a live defect, instructed, and
then redeemed by the correction it predicted - and the instruction is what made
the redemption mechanical rather than a judgement call about whether a red test
still meant anything.

The twelve `src/` files remain, recorded and not asserted. They are not this
work's to rename, and the gate deliberately does not fail on them.

### the-registry-tooling-prose-cited-plan-steps-as-if-they-were-components | high | Thirteen sites named a step where they meant a boundary; the subtree now carries only the fixtures a detector must contain

Extending the restored marker table from symbol names to prose found campaign
markers in twenty-three development files. Three classes came out of that,
and only one is a defect. Detector fixtures are the first and are legitimate:
the governance gate, the vault-citation gate and the pattern table itself must
contain the shape they detect, and a gate that could not name its own target
would be unprovable. Wrapped lint prose is the second - a comment explaining a
suppression, where the directive is scrubbed but the sentence describing it is
not, and a line-scoped discriminator misses it when the sentence wraps.

The third class is real, and thirteen of its sites were in this campaign's own
subtree. The pipeline modules called a loader boundary "the S10 loader
boundary", said "S10 validates it", described a candidate as "the S10
candidate", and gated publication "before S11 is allowed to publish it". The
census called a record's anchor index "the S63 declaration-index". In every case
a step id stood where the name of a thing belonged, which is worse than a bare
citation: it reads as though S10 were a component, and a reader who goes looking
for it finds a plan row describing work rather than a boundary in the code.

The rewrites name the thing. `S63` was checked against the registry data before
being touched, because a token that looks like a step id can be an official one:
it appears nowhere in the shipped declarations, while the real domain token
beside it, `DP30302`, is what the error message should have been quoting all
along. The test sentinel `S03-IR-DERIVATIVE` lost its prefix for the same
reason - a unique marker does not need a step number to be unique. Two hundred
and forty-seven tests pass over the edited surfaces, exit 0.

Re-measuring the subtree afterwards leaves six markers, all inside one test
function: the fixtures the vault-citation detector must carry to prove it fires.
That is the correct end state, and it is worth saying explicitly, because a
sweep that drove this count to zero would have done it by disarming the detector
that keeps the count honest.

### the-conformance-closure-test-passes-in-three-minutes-and-was-never-hung | medium | It exits 0 in 182 seconds under a host at 98.8% CPU; the earlier timeout was the ceiling being struck, not a deadlock

The test that struck the per-test ceiling was re-run with the ceiling raised to
twenty minutes. It passed in 182.58 seconds, exit 0, on a host carrying a
hundred and eighty-nine python processes at 98.8% CPU - worse contention than
the run that timed out. So the earlier `Timeout` was exactly what the ceiling is
for and nothing more: a slow test crossing a fixed line, with the deepcopy in
the dump being where it happened to be standing, not a deadlock.

Three minutes is still the finding. A test at that duration is not a unit test
in any useful sense, and naming its directory in a lane puts a three-minute
serial floor under that lane. The Step to name the directory should carry that
cost explicitly rather than discover it in CI.

The method deserves a correction against itself. This run was set up to measure
CPU time on the theory that CPU-seconds are contention-robust where wall-clock
is not, which is true but was not what happened: the shell's own timer reported
USER=0.015 and SYS=0.031, because `uv run` spawns its child in a process tree
the shell's accounting never sees. Those two numbers describe the wrapper, not
the test, and they would have been a confident nonsense had the wall-clock not
answered the question on its own. A timing technique needs its own sanity check
- a measurement reporting fifteen milliseconds for a three-minute run is
reporting nothing.

### the-marker-scan-now-tells-a-suppression-from-a-step-id | medium | A module's own lint vocabulary excuses prose naming it, and the exemption is keyed per module so it cannot be borrowed

The prose measurement recorded a limitation rather than working around it: a
comment explaining a lint suppression carries the code without the directive, so
the token-level scrub removes the `noqa` and leaves the sentence, and the
sentence wraps across lines in both live cases so no line-scoped check can see
it whole. That limitation is now closed rather than noted.

The rule is per module and stated as such: a module that suppresses a code has
established what that token means inside it, so prose naming the same code is
explaining the suppression. Nothing else changes - the token-level scrub still
does its own job, and the new judgement is separate because it needs the whole
text rather than one line.

Three tests hold it, and the second and third exist because the first alone
would be satisfied by a helper that reports nothing. A module suppressing a code
and explaining it yields no finding; a step id the module does not suppress is
still reported; and a code suppressed in one module buys no exemption in
another, which is what keeps the exemption from becoming a global allowlist
grown one file at a time. Six tests pass in that module, exit 0.

The corrected measurement over the development tree is seventeen files, down
from twenty-four, and the two files that left are exactly the two whose only
marker was a wrapped explanation of a bandit suppression. The largest remaining
population is seventy-six sites in one file, where a data field names a plan
phase pair as its `owning_authority` - a declaration whose stated authority is a
row in a plan rather than anything a reader can resolve. It belongs to another
campaign's surface and is recorded, not edited.

### the-largest-marker-population-is-a-provenance-field-nothing-reads | high | Seventy-six rows name a plan phase pair as their owning authority, validated only for being non-empty and consumed by nothing

The workspace action denominator classifies each action into a closed
hand-reviewed row, and every row records an `owning_authority`. Seventy-six of
them read `tui-interface W05.P10/W05.P11` or a sibling phase pair. Nothing in
`dev/`, `src/`, or any tracked configuration reads that field: eighty-four
occurrences all sit inside the declaring module, there is no `model_dump`, no
serialization and no report, and the field carries no assertion.

The model's own docstring is what makes the reading precise, and it argues
against the easy conclusion. It names four fields as the recorded mechanical
signature the row was classified against, and says the validator re-observes
the live signature and reds on drift. `owning_authority` is deliberately not
among those four. It sits with `reason`, `evidence_reference` and
`reopening_condition` in the group written for a human, and its only constraint
is a minimum length of one, so any non-empty string satisfies it.

So this is not a dead field to delete. It is a provenance field doing its job
badly: the authority it records is a row in a plan, which is unresolvable to
anyone outside the campaign that wrote it and becomes meaningless the day that
plan is archived, and nothing in the type system can notice because
non-emptiness is the whole contract. The remedy is to name a durable authority -
the interface, the ruling, or the owner - not to remove the field, and it needs
the writer of that surface rather than a drive-by edit from this work: the file
belongs to another campaign that is actively committing, and seventy-six values
are a review, not a substitution.

It is recorded here as the largest single population the marker scan found, and
as the clearest example in the tree of the difference between a declaration that
is absent and one that is present, validated, and empty of meaning.

### the-conformance-directory-holds-nineteen-tests-and-one-blocked-failure | high | Eighteen pass and one fails on a broken edge, in eight minutes fifty-seven seconds serial

With the ceiling raised past the three-minute test, the directory completes:
nineteen tests, eighteen passed, one failed, exit 1, in 536.76 seconds. That
settles the precondition the lane Steps carried. The directory is not a pile of
rot - it is one blocked test and a nine-minute serial cost, and both facts
belong in the Step that proposes naming it.

The failure is not an assertion. It is
`AttributeError: 'LiveFilingExportProofAuthority' object has no attribute
'assess_for'` - the closure report asks its filing proof authority to assess a
coordinate, and the authority handed to it offers only `proof_for`. Two classes
in one module declare the same concept with different surfaces: the canonical
two-channel authority carries `assess_for`, and the single-channel one does not,
so the report's call finds nothing. This is the broken edge a deletion leaves
when its consumer sweep misses a caller, and it sat in a directory no lane runs,
which is why it reads as a crash rather than as a refusal anybody had to answer
for.

The plan already names the remedy, and the reason it has not been taken is now
exact rather than assumed. The single-channel authority's only proof-producing
path raises `legacy single-channel filing proof is disabled` whenever it finds
an entry and returns `None` otherwise, so it cannot produce a proof by
construction and its private verification helpers are unreachable. Rewriting the
test onto the two-channel authority is the stated fix, and it cannot be done
today: that authority resolves a conformance vector before it will report a
satisfied outcome, and `CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS` is the
empty tuple. The test's whole point is that a satisfied filing export does not
make a row release-eligible while its source limb is unmeasured, and that
invariant needs a satisfied outcome to express.

So the chain is: the official emitted-byte reference, then vector enrolment,
then this rewrite, then the deletion. The Step now says so. The measurement that
matters here is negative - the work is blocked on evidence that does not exist
in the repository, not on effort - and recording which link is missing is worth
more than another attempt that would have to invent the evidence to succeed.

### the-plan-restated-its-own-sequencing-three-times | medium | A document arguing against declaring one fact in many places was doing it, and the copies had drifted

Measuring the plan's own prose the way this campaign measures the registry found
three restatements. One was an exact duplicate: the paragraph describing which
Phases may run in parallel appeared twice in the Parallelization section, word
for word. The other two were paraphrases, which is the harder half and the one a
duplicate check misses - the Wave sequencing was argued once thinly and once
fully, and Wave six's dependence on unwritten decisions likewise.

The copies had drifted, which is the argument against keeping either. The thin
sequencing paragraph said Wave two "returns the project to having a standing
regression gate"; the full one says the same and then says what that requires -
moving the release-eligibility predicate into the shipped application, because a
predicate that exists only development-side cannot gate anything. The thin Wave
six paragraph omitted that the first five Waves need no architectural decision
at all, which is the sentence that makes Wave six's difference legible. In both
pairs the later text was a strict superset, so the earlier one carried no fact
of its own while still being a place a reader might stop.

Afterwards the plan holds fifty-nine prose paragraphs with no exact restatement
and a highest pairwise similarity of 0.42, down from 0.74. That figure is a
measurement of this document, not a target for it: two paragraphs about the same
Wave will always share vocabulary, and driving the number lower would mean
writing worse prose rather than removing duplicated meaning.

One fact was added rather than removed, and only once. The missing official
emitted-byte reference gates three Steps in three Waves - the proof vector Phase
that names it, the modelo 151 closure rewrite that needs a satisfied outcome the
empty vector tuple cannot produce, and the lane Step that inherits the block
through that test's failure. The Parallelization section now says this in one
place, as a discovered ordering constraint beside the others, because a
dependency recorded three times is the defect this entry is about.

### three-sections-claimed-to-be-the-current-position-and-only-one-was | medium | The first two consolidated positions asserted precedence with no forward pointer; a reader arriving at either was told the wrong thing

The same restatement measurement that found three duplicated arguments in the
plan was turned on this record. It reports something better: two hundred and
sixty-six findings and no near-duplicate pair, with the similarity distribution
topping out at 0.33 against the plan's 0.74 before repair. Findings here are not
restating one another.

One structural defect did surface, and only through that measurement. The
audit carries three consolidated positions. Each later one says it supersedes
the one above it, so the chain is complete read backwards. Read forwards it was
not: the first section says "this section states the current position and takes
precedence where they differ", with nothing on it to say that two later
revisions exist, and the second carried no marker at all. A reader arriving at
either from a search or a link - which is how anyone reaches a section in a
document this long - was told it governed. Both now carry a forward pointer, and
the first's precedence claim is stated in the past tense, because the claim
rather than the content is what had gone false.

A measurement of my own measuring is owed here too. The first count of markers
in this record said two, which would have made the gap look systemic; the true
count is fourteen. The regex anchored on a line start, and this record's
convention puts the marker in the heading line instead. The class was already
known and had already been worked - a finding several iterations back records
three headings being pointed at their corrections - so what remained was one
family the earlier sweep had not reached, not a record that never marks its
supersessions. Reporting the first number would have condemned a convention that
was being followed.

### the-selection-probe-erased-the-one-case-it-was-built-to-show | high | A retry that rescued the answer also cleared the refusal, so the single undecidable coordinate reported like any other row

Checking the plan's temporal criterion against the live registry rather than
against the audit produced a suspicious answer: 441 probes across 58 modelos,
zero not resolving to themselves, zero refusing. A screen that finds nothing is
worth one more question, and the answer was in the screen rather than the
registry. Asking the authority directly for modelo 308 at filing year 2011
raises `AmbiguousRevisionSelectionError` at every grade, exactly as it should -
the windows split at the end of June, so the year alone cannot choose - while
the probe reported that coordinate as resolved.

The mechanism was two lines. The probe retries an ambiguous year with a date
inside the revision's own window, which is right: the year alone is an
under-specified question and refusing it is the registry being correct. But the
retry set `refusal = None` on success, and the row was then built with
`refusal=None if resolved else refusal`, so the ambiguity was cleared twice and
nothing downstream could tell a coordinate the year cannot decide from one it
decides outright. The probe's own docstring explains the 308 split as its
motivating example, and the probe could not report it.

The flag is now carried on the result and counted in the summary, and the
corpus-wide figure is one: modelo 308, filing year 2011, answered by a date.
A test pins it with the replacement instruction the pin owes, and says that if
the corpus ever holds no such pair the flag must still be proven against a
constructed one, because an erasure returns silently.

The plan's criterion said two coordinates failed this test. It now carries the
measured figures instead - 441 probes, zero refusing, one undecidable by year
alone - because the earlier number could not be reproduced by the instrument the
criterion names, and a criterion whose evidence cannot be re-run is a claim
rather than a check. This is the second screen in this campaign found reporting
a clean result because it could not see its own subject, and both were found the
same way: by asking whether a zero was the tree being clean or the instrument
being blind.

### a-pin-held-by-count-failed-when-its-screen-succeeded | high | The sibling-scale gate went red because it found a second defect, which is the one outcome a detector proof must not punish

Running the registry tooling directory whole reports 37 failed, 964 passed and
22 errors in twelve minutes. Twenty-six of the failures are one parametrised
reproducibility test over the manifest-stale trees already recorded here. One is
this campaign's own gate, and it failed for the best possible reason.

The sibling-scale comparison is proven against a live defect rather than a
fixture, and its test asserted that exactly one field in the corpus disagreed
with its siblings. Two now do: modelo 200's casilla 03594 and modelo 353's
casilla 10, each emitting unscaled beside siblings emitting cents. The screen
detected the second exactly as intended and the test reported that as a failure
of the screen.

A count over a live corpus is a ratchet wearing a proof's clothing. It fails on
the arrival of the very condition it exists to detect, and the obvious repair -
bump the number - teaches the reader that the way to handle a new filing-
correctness defect is to edit the test that found it. This one had already been
edited once that way: it originally named modelo 200 and now named modelo 353,
which means the count survived a substitution that should have made it a set.

It is now held by identity. Each known coordinate is named, a subset assertion
says every one is still reported, and a superset assertion says nothing outside
the named pair is - which still catches an over-firing comparison without
freezing the population. The docstring says what each half means when it breaks:
a name that stops being reported is a correction landing and should be dropped
from the set; a coordinate arriving from outside it is a new defect and belongs
in the record before it belongs in the test. Nine tests pass, exit 0.

The general rule this campaign keeps arriving at from different directions: a
gate may assert what it knows by name, and may assert that nothing else appears,
but it must not assert how many things there are. The first two survive the
corpus changing. The third is the corpus, restated in a place nobody thinks to
update.

### the-count-rule-applied-to-this-campaign-s-own-screen-tests | medium | Two more frozen live-corpus counts found and replaced by identity; the other three were relational and already correct

The rule that a gate may name what it knows but must not assert how many things
exist was applied to the tests this campaign wrote, rather than left as a lesson
in the record. Ten screen test modules were swept. Two carried the defect and
three carried its correct form.

The continuity module asserted that exactly one singleton chain exists and that
modelo 714's absent-continuity detail says "5 revisions". Both are live figures.
The first fails the day a second singleton appears - the screen succeeding - and
the second fails the day modelo 714 gains a revision, though nothing about its
absent continuity would have changed. The chain is now named (`dr303-112`) with
the instruction its pin owes, and the revision-count assertion is replaced by
the part of the detail that carries the claim: that no casilla carries a chain.
Six tests pass, exit 0.

The three others were already right and are worth naming as the pattern to copy:
`len(grammars_seen) > 1`, `len(transitions) <= len(typed_endpoints)`, and
`len(census) > len(modelo_ids)`. Each states a relationship the corpus cannot
violate without something being genuinely wrong, and none of them changes when
the corpus grows. That is the difference between a count and an invariant: an
invariant compares two things the tree produces, a frozen count compares the
tree to a number somebody typed.

One class was deliberately left alone. The modelo 200 reconciliation tests
assert figures in the thousands, and those run over a tree copied into a
temporary directory rather than the live registry - a frozen snapshot being
described, not a live population being fenced. Applying the rule there would
have been the same error as the heuristics this campaign has already got wrong
twice: taking one shape of a concept for the whole of it.

### two-criteria-verified-live-and-two-figures-in-my-own-prose-found-stale | medium | The monetary criterion reproduces exactly; the explanation beside it had drifted, and the eligibility figure has no reproducer at all

The plan's monetary criterion says twenty-six fields fail the first test and two
fail the second. Both reproduce from a live command: the screen reports
`money_without_scale=26` and `sibling_scale_disagrees=2`. A criterion that can
be re-run is worth more than one that was true when written, and this one can.

Checking it turned up a discrepancy that was not one. The screens runner reports
33 findings for this screen while the screen's own CLI reports 165, which looked
like two entry points disagreeing about the same measurement. It is deliberate
and documented at both ends: the runner excludes `money_split_representation`,
which is the official integer-and-decimal part split and not a defect, and 165
less those 132 rows is 33. The fourth hypothesis this campaign has killed by
reading the code rather than trusting the shape of the numbers.

What was wrong was the explanation. The runner's docstring said the split was
"132 of the 158 rows"; the live totals are 132 of 165. The argument it supports
- that counting them would overstate the work several-fold as the first number a
maintainer reads - is still exactly right, and only the frozen pair had drifted.
The proportion is now stated as the argument rather than as two numbers, with a
line saying why: the same defect this package exists to find, occurring in the
explanation of a screen rather than in a declaration.

The second figure is worse and is now labelled. A screen's docstring states that
correcting the eligibility predicate makes 183 fields newly eligible. Nothing in
this tree reproduces that: the predicate still reads the old way, so re-running
the measurement requires making the correction first, and no module scripts it.
The number is quoted in the plan as well. It is not withdrawn - it was measured,
and it is the order of the work - but the docstring now says it was measured
once, is not reproducible from here, and must be re-measured as part of the
correction rather than trusted afterwards. A figure whose reproducer does not
exist should say so where it is quoted, not be discovered to be unverifiable by
the next person who needs it.

### the-nine-screen-property-gates-exist-and-the-gate-total-had-moved | medium | The named criterion verifies function by function; the figure beside it was three behind

The verification criterion listing nine properties every screen must hold was
checked against the module rather than read: enrolment in the runner, presence
in the contributor README table, a test module, a non-empty population, a run
over the whole corpus, leaving the shipped registry untouched, naming every
emitted kind in its own docstring, stating a condition count that matches, and
every symbol those READMEs name still resolving. All nine exist as separate test
functions. The criterion is accurate, and it is accurate in the way that matters:
each property is one function a reader can run, not a claim about the module's
character.

The figure in the plan's description had drifted. It recorded sixteen gates with
two detector proofs; the module holds twenty-one functions, of which three are
detector proofs showing a gate bites. Twenty-one pass, exit 0, in two minutes
fifteen.

The correction is not the new number. The same sentence already handles the
screen count properly - "whatever `SCREENS` in the analysis package enumerates,
ten at the time of writing" - naming the source first and the figure second, so
a reader who finds eleven knows where to look and knows nothing is wrong. The
gate figures were written the other way round, as bare totals, and so went quietly
stale beside a count that could not. Both now name their source, and the sentence
says both moved during execution and neither was wrong when written, because a
figure that drifts is not evidence of an error - it is evidence that the work
continued after the sentence was finished.

### the-accessor-criterion-claimed-three-drop-proofs-and-two-exist | medium | Both are the right two, and naming them is stronger than the sentence that rounded up

The criterion protecting the resolved export surface said the accessor is proven
by a test asserting it fails if any of its three linkage paths is dropped.
Checking the module rather than the sentence: four tests sit beside the
accessor, one asserting all three paths are returned and two dropping a path and
asserting the casilla it carried disappears. Four pass, exit 0. The third drop
proof does not exist.

Its absence is defensible and is now written down rather than papered over. The
two that exist cover the projection reference and the row-field mapping, which
are precisely the paths every hand-walk in this campaign actually missed - four
published figures were wrong for that reason, each correction restoring one of
them. A walk omitting the direct field path does not produce a plausible
under-count; it fails visibly at once, which is why nobody wrote a proof for it
and why the surface it protects is not at risk.

The criterion now names which two paths are proven and why those two. That is a
longer sentence than "any of its three", and better: a reader who trusts the
round claim and later needs the direct-path proof would find it missing and
conclude the gate had rotted, when in fact it was never there and did not need
to be. An overstated proof costs more than an honest gap, because the gap can be
filled by whoever finds it and the overstatement sends them looking for a defect
that does not exist.

### the-restatement-count-this-plan-rests-on-is-now-data-instead-of-prose | high | Six year-level temporal sites are declared, each gated against the live schema, with the boundary stated

This plan opens by counting how many places one fact is restated - temporal
validity at eight sites, a citation at eleven, applicability at seven. Those
figures justify the whole campaign and none of them could be re-derived from the
tree. An attempt to recover the temporal one mechanically failed in the way this
campaign's heuristics keep failing: scanning the revision model for fields whose
name or annotation carries a date or a year returns six, and two of them are
`continuidad_validation`, matched because its name contains "valid", and
`reviewed_at`, which is a review stamp rather than a filing-temporal claim. A
count built that way would have been the fourth heuristic in this campaign to
encode one shape of a concept and miss the rest.

The sites are now declared where the screen that compares them lives, as dotted
paths from the revision, with the definition written beside them: a year-level
claim about which years the revision serves. Six qualify - `valid_from`,
`valid_to`, the selector's `year_from`, `year_to` and `years`, and a deadline
window's `filing_year`. The revision directory name is a seventh site and is
deliberately excluded, because it is not a declared field and the
name-against-window comparison belongs to the sibling screen; counting it here
would give one condition two owners.

The exclusion that matters most is the one a bare count would have got wrong. A
deadline window also carries `opens_on`, `closes_on` and `payment_cutoff_on`.
Those say when within a year a filing is due, not which years the revision
serves, so they cannot disagree with the window and folding them in would have
inflated a restatement measurement with facts that are not restatements. A test
asserts they stay out, so the boundary is enforced rather than remembered.

A second test resolves every declared path through the model definitions rather
than an instance, so a field renamed in the schema fails here instead of leaving
the list naming a site that no longer exists. Seven tests pass, exit 0. The
figure is still six rather than the eight the description quotes, and that gap is
now a readable difference between two definitions rather than an unverifiable
number: whoever wrote eight counted something this list names its reasons for
excluding.

### the-validator-family-is-not-all-reconciliation-and-one-screen-condition-is-a-canary | high | The fifty-one figure verifies exactly, but only a minority of the family exists because a fact is stated twice

The description cites the registry's validator modules as evidence that
detection after the fact is the wrong shape. The count verifies: the
`_validate*` family in the registry package holds fifty-one modules, and the
sentence now names the family so a reader can re-derive it rather than trust it.

Reading their docstrings refines the argument rather than supporting it as
written. Most are structural closure validators - reference closure, section
shape, formula graphs, producer inventory - and would exist whatever the
declaration strategy. A readable minority exist specifically because one fact is
declared twice and the copies must be made to agree: the revision-id window
agreement, the `valid_from` ejercicio convention, layout coverage against the
official design, a claim needing its backing layout, previous-filing year
coverage. A clean count is not available at module granularity, because some
modules validate both kinds - the revision-rules module checks window overlap
and reconciliation-total closure in one place - and a number produced by
classifying whole modules would be a judgement wearing a measurement's clothes.
So the finding is the shape, not a figure: reconciliation is a substantial
minority of that surface, not the whole of it, and the campaign's argument is
better for saying which validators it means.

One of those agreement validators turned out to own a condition this campaign's
own screen also declares. `_validate_revision_id_window_agreement` refuses an id
asserting open-endedness over a window closed on either axis, at build time. The
name-window screen declares exactly that condition as `name_claims_open_ended`,
and it reports zero - not because the corpus is clean, but because no loaded
authority can contain one. The division is correct and was undocumented: the
validator refuses the direction it can refuse, the screen reports the directions
it cannot. The screen now says so, and says what a finding there would mean -
that the upstream refusal stopped happening, which is a larger fact than the
finding. A condition reporting zero for a reason nobody wrote down is
indistinguishable from a condition that no longer works, which is the state this
campaign has now found twice in its own tooling.

### one-declared-condition-was-silent-and-unexercised-and-is-now-proven | high | Four of the five silent conditions already had constructed proofs; the fifth had none, and it works

Every screen was measured for conditions it declares but never emits, on the
reasoning that a condition reporting zero is either a canary or dead and a
reader cannot tell which. The sweep needed two corrections before it meant
anything. `casilla_id_grammar`'s apparent silences - `dotted`, `kebab`,
`numeric`, `page_qualified`, `token` - are grammar names, matched because the
docstring lists them in the same shape as finding kinds. `money_split_representation`
appeared silent because the measurement ran through the census wrapper, which
filters that kind deliberately; the screen emits 132 of them.

Five genuine cases remained. Four already carry constructed proofs, each moving
a real revision's field and asserting the kind appears: `name_misstates_closing`,
`window_sources_disagree`, `deadline_year_outside_window`, and
`claims_filing_without_layout`. Their zeros are the corpus being clean, and that
is checkable rather than assumed.

`selector_dual_form` had none. It is declared, emits nothing, and its name did
not appear anywhere in its test module - the state where a condition and a
broken condition look identical from outside. It works: constructing a selector
that carries both an explicit `years` tuple and a `year_from` bound makes it
fire with the detail naming both. That shape is this package's whole subject in
one field, two statements of which years a revision serves with no rule for
which wins, and no shipped revision does it.

It now has two tests rather than one, and the pair is the point. The constructed
case says the condition can fire; the unmodified revision says it does not. Each
alone leaves a reader unable to distinguish a clean registry from a dead check,
which is exactly the position this sweep started from. The count assertion in
the constructed case is over a fixture with one planted disagreement, not over
the corpus, which is the distinction this campaign drew two iterations ago and
is worth keeping straight: a count of what a fixture produces is a proof, a
count of what the tree contains is a ratchet. Nine tests pass, exit 0.

### two-detector-proofs-were-named-for-the-screen-and-never-ran-it | high | They asserted the index beneath the screen, which shows a defect is visible without showing the screen reports it

An attempt to gate the reverse of an existing rule - every condition a screen
declares must be emitted live or proven by a constructed defect - was abandoned,
and the abandonment found the defect the gate was meant to catch.

The gate needed to know which conditions a screen declares and which have
proofs. The first half is already solved: the condition-count gate enumerates
the bullets that follow a screen's "N conditions are reported" claim, and
deliberately excludes the fact bullets before it, which is the discrimination a
naive read of the docstring gets wrong. The second half is not solvable the way
it looks. Searching a test module for the kind's name flags two continuity
conditions as unproven, and they are proven - by tests that never name the kind.
Building the gate on that signal would have made two correct tests look like
gaps and taught the next author to paste the string in to silence it. That is
the fifth heuristic in this campaign to encode one shape of a concept and miss
the others, and the first caught before it was written into a gate rather than
after.

The flag was right for a different reason. `test_screen_detects_a_chain_spanning_two_identifier_grammars`
and its sibling construct their defects correctly and then assert against
`chain_index`, the index the screen reads. The index showing two grammars is the
precondition; the finding is the claim. Both tests are named for the screen and
neither ran it, so nothing connected the constructed defect to the row a
maintainer would see - and the screen had no per-unit entry point to run,
because `screen_authority` takes the authority and walks every modelo, while the
sibling screens all expose a per-revision function their proofs use.

The screen now has `definition_findings`, matching the shape its siblings
already had, and `screen_authority` is a loop over it. The census is unchanged
at twenty-six findings across the same kinds, which is what makes the extraction
safe to believe. Both proofs now assert the kind the screen reports, one of them
matching the finding's full detail text. Six tests pass, exit 0.

### a-gate-recovered-its-own-subject-with-four-regexes-and-now-reads-a-declaration | high | Each regex was added when a new assignment shape appeared, which is the failure the sibling gates refuse by design

Sweeping every screen test module for the defect found last iteration - a test
named for the screen that never runs it - returned three candidates. Two are
correct: the site-list tests added earlier gate a declaration rather than screen
behaviour, and calling the screen would not make them stronger.

The third was worse than the defect being swept for. A gate asserting that every
documented condition is reachable recovered the emitted set by matching the
screen's source with four separate regexes: a plain keyword argument, a
conditional expression, an else-branch, and a docstring scan. Each was added
when a new assignment shape appeared and the previous set under-read. That is
exactly the technique the sibling gate's docstring refuses and says why -
"a static extractor silently under-reads every shape it does not know" - and it
is worse in this direction than in the one that warning was written for. Both
sides of this comparison were derived from the same file: an under-read set
compares equal to a docstring that lost the same entry, so the gate reports
agreement between two wrong answers and reports it as a pass.

The screen now declares its eight kinds as data, beside the pattern it uses to
read a name, with a note saying what the declaration replaces. The gate compares
the docstring to that declaration and separately asserts what fires on the
corpus is a subset of it. Fourteen tests pass, exit 0, and the census is
unchanged at fourteen findings across five kinds.

The residual coverage is worth stating rather than glossing. The declaration is
checked against live findings for the five kinds that fire and against the
constructed cases in the same module for two more. The eighth is
`name_claims_open_ended`, which the shipped registry refuses at build time, so
nothing can exercise it here - the canary recorded two iterations ago. Seven of
eight kinds are therefore pinned by something that would fail if a literal
drifted from the declaration, and the eighth is pinned by a validator in another
package. That is a complete account, which is more useful than a claim of full
coverage would have been.

### the-central-invariant-was-guarded-by-a-substring-that-punished-documentation | high | A module explaining why it must not call the binding derivation would have failed the gate protecting that rule

The gate holding this campaign's central invariant - no screen rebuilds the
resolved export surface - detected a reach by searching each module's text for
the derivation's name. Two consequences, and the second is the serious one. It
would miss nothing it was built to catch, but it fires on any mention: a screen
whose docstring said "this must not call `derive_export_layouts_from_bindings`;
it asks the accessor" would be reported as an offender. The gate that exists to
teach a rule made stating the rule an offence.

It now reads the syntax tree. An import naming the derivation, a bare name, or
an attribute access is a reach; the same characters inside a docstring, a
comment or a string literal are not. The walk also moved from a flat glob to a
recursive one, so a screen in a subpackage is no longer outside the rule.

A paired proof sits beside it, because each half fails differently. Without the
first the gate protects nothing; without the second it makes the rule
undocumentable, and a rule nobody may explain is one the next author re-breaks.
The proof asserts both directions on constructed sources: an import and an
attribute call are caught, a docstring and a comment naming the same symbol are
not. Twenty-two tests pass in that module, exit 0.

### the-ci-lane-selection-re-measured-to-a-reconciling-total | high | 177 failures and 109 errors of 3,941 collected, and the duration is not comparable

The criterion quoting 167 failures and 72 errors of 3,881 tests was re-run over
the same eighteen directories. It reports 177 failed, 3,653 passed, 2 skipped
and 109 errors, which sum to the 3,941 collected - the reconciliation being the
point, since a headline that does not add up to its own collection is the defect
this campaign opened with.

The duration is deliberately excluded from the comparison. The earlier reading
took six and a half minutes; this one took forty. The host carried a hundred and
eighty-nine python processes at full CPU throughout, and several of this plan's
own suites ran beside it - by my own hand, which is the honest way to say it.
Reporting six-to-forty as a regression would repeat the error already made once
here with a per-test timeout, where a ceiling struck under saturation was nearly
recorded as a property of the test. A wall-clock measured against contention
measures the contention.

### fourteen-of-the-lane-errors-are-one-authority-that-never-finishes-compiling | high | A 2.5 MB input takes more than ten minutes, which no amount of host contention explains

The lane criterion requires every failure in it to be named and attributed. Of
the 109 errors, 21 sit in terminology resolution, 17 in deployment search parity
and 14 in the registry tree, the rest scattered; the registry fourteen are this
plan's to account for.

They are not assertions. All fourteen are the same fixture failing at the
per-test timeout ceiling while compiling the modelo 200 blocker authority, and
the traceback shows why the work is large: the compile calls a partition check,
which compiles a second authority, which audits bundled restorations, which
loads a 75-fragment semantic map - and the outermost call sits inside an
equality comparison against a freshly compiled authority, so the whole chain is
rebuilt to decide whether it equals itself.

The attribution needed a measurement that contention could not distort, because
the host has been saturated for hours and this campaign has twice nearly
recorded a contended wall-clock as a property of a test. Two were taken. The
input is 75 TOML fragments totalling 2.5 MB, which is fixed regardless of load.
A single compile then failed to complete in ten minutes. Twenty-four cores at
ninety percent still leave several times the capacity that parsing 2.5 MB needs,
so the gap between the input and the duration is structural rather than
environmental - a conclusion drawn from the ratio, not from the clock.

The remedy is not this work's to apply: the module belongs to another campaign
and the shape - recompiling an authority inside a comparison against itself -
needs its owner. What this plan owes is the attribution, and it now has one that
does not depend on a quiet machine.

### the-recompile-shape-is-in-three-sibling-modules-and-a-collision-gate-caught-a-new-name | high | One anti-pattern written three times, and a gate red for exactly the reason it exists

Sweeping the development tree for the shape behind the lane's fourteen errors -
a comparison whose operand is a freshly compiled authority - returns eleven
sites. Eight are tests comparing a value against a freshly loaded file, which is
what those assertions are for. Three are production analysis modules, and they
are the same function written three times: `promoted_candidate_ids` in the
blocker, same-template and unique adjudication modules, each comparing its
authority against a fresh compile, each then calling the same verification, each
returning the same frozenset comprehension over its own rows. One concept, three
spellings, three separate recompiles - and the cost of one of them is the
fourteen errors already attributed.

They sit outside this work's ownership, so the finding is recorded rather than
repaired. What is worth naming is that the campaign's subject and the lane's
slowest failure turn out to be the same defect seen from two ends: the
restatement is why the work is done three times, and doing it inside a
comparison is why it is done at all.

The sweep also caught a live gate red. The public-name collision census reports
a same-layer collision the dispositions file did not carry -
`availability_label`, defined in both the declarations and ledger TUI
controllers - so the gate failed exactly as designed on a name that arrived
through somebody else's commit. It is adjudicated `distinct_by_design`: the two
take unrelated availability enums, read different locale catalogues, are
exported by their own modules and imported by neither, and the shared name is
the convention that lets a reader move between sibling workspaces. Collapsing
them would mean inventing a union over two unrelated enums for a function with
no shared caller. Five tests pass, exit 0.

One correction to my own reading. The dispositions file appeared to hold zero
rows, which would have meant the gate had been emptied; it holds them under
single-bracket table headers rather than the double-bracket form I grepped for.
The gate's own failure message showed a populated set and corrected me before
the mistake reached this record.

### the-documentation-privacy-gate-was-red-on-two-operator-home-paths | high | Committed audit prose carried the operator's home directory; the quality directory is green again at 335 tests

Running this campaign's quality gates as a directory - the discipline that
caught a live collision last iteration - found one failure across 335 tests. The
documentation privacy gate refuses operator-identifying tokens in tracked text,
and two audit files carried absolute paths under the operator's home directory:
a scratch script path in the restrictive-default sweep audit, and a temporary
repository copy path in the object-name rehearsal audit.

Both belong to other campaigns, and the first thing checked was whether this
campaign's own records were among them. They are not: neither this audit nor
its plan contains the pattern. That check came first because the honest order is
to establish whether you are a contributor to a defect before deciding what to
do about someone else's.

They were scrubbed rather than allowlisted. The gate offers both routes, and the
allowlist is for a genuine functional survivor - a token the text needs. Neither
of these is: one names a temporary agent job directory and the other a temporary
copy of the repository, and both sentences say what they meant to say once the
machine-specific prefix is replaced by what it was. Machine-specific paths in
committed examples are forbidden by the project's own documentation rule, so
this is a correction rather than a preference, and it was applied to records
that carried no pending diff.

The directory now passes at 335, exit 0. The general point is small and worth
keeping: a gate that has been red for a while stops being read as a gate. This
one was refusing exactly what it was written to refuse, on files nobody in this
campaign had touched, and it would have gone on doing so unnoticed because the
failure belonged to no one who was looking.

### the-step-id-gate-fired-on-a-name-that-arrived-hours-after-it-was-written | high | It is red, correctly, and the right repair is not the one that makes it green

Running `dev/tests` as a directory reports 33 failures across 610 passing. One
of them is this campaign's own gate, and it is the reason the gate exists. The
step-id assertion - redeemed to an empty expectation two iterations ago after
four renames - is red again on
`test_compiles_the_closed_disjoint_s14_s15_cohort_and_live_bytes`, which arrived
in a commit after the gate was written. The gate caught a regression within
hours, which is the only real evidence that a gate works.

The repair is deliberately not the obvious one. Renaming that test would make
the gate green and remove nothing: the owning module calls the same thing "the
reviewed, disjoint M200/2024 S14/S15 compiler" in its module docstring, "the
closed S14/S15 declarations" in a function docstring, and names the cohort by
those ids in two refusal messages. The step ids have become that campaign's
vocabulary for the cohort, so the test name is the visible end of a leak that
runs through the module. Renaming only what the gate can see is the move that
teaches the next author to satisfy detectors rather than remove defects, and a
gate whose stated purpose is preventing that must not be repaired that way.

What this work owns is making the failure act on the reader. The assertion now
names the offending symbol rather than only its file, and says both wrong
repairs explicitly: do not add the coordinate to an exemption, and do not rename
only the test when its module carries the same id in its prose. A Step records
the real remedy, which belongs to the owning campaign because renaming a cohort
requires knowing what distinguishes it - here, target-only evidence, closed and
disjoint, which are properties the ids do not carry.

That leaves a gate red on purpose, against the lesson recorded last iteration
that a long-red gate stops being read. The two do not conflict as long as the
red is legible: the privacy gate had been red on a defect nobody owned, and this
one is red on a defect with a named owner, a written remedy and a Step. The
difference is not the redness, it is whether anyone can tell from the failure
what to do.

### this-campaign-added-eight-of-the-violations-it-was-triaging | high | The UTF-8 gate was flagging my own files, and truncated output hid it from me twice

Triaging the 33 failures in `dev/tests` began with the right question - whether
any were caused by this campaign's own changes - and then answered it wrongly.
The UTF-8 enrolment gate reports 83 bare literals across non-ratcheted `dev/`
files. Grepping its output for the files this session touched returned two hits
in a module whose docstring I had edited but whose flagged lines predate me, so
the first conclusion was that none were mine.

That conclusion came from a truncated read. The grep carried a context limit
smaller than the violation list, so it never reached the tail where this
campaign's own files sit. Asking the gate's checker directly, rather than
searching its output, reports eight violations in three modules I wrote or
extended this session: one in the marker-pattern gate, one in the render-check
tests, and six more in the declaration invariant gates, all of the form
`read_text(encoding="utf-8")` written at each call site.

This is the same failure mode this campaign has now recorded four times, and the
third time it has cost me a wrong conclusion rather than merely a wrong figure.
Truncating a measurement is not a shortcut with a small error term: the part
that is cut is exactly as likely to hold the answer as the part that is read,
and here the cut part held my own name.

All eight are fixed the way the gate asks - a module-level constant naming the
encoding once, used at every read site, so a typo becomes a NameError rather
than a silent decode change. Thirty-three tests pass across the three modules,
with the single remaining failure being the step-id gate held deliberately red
on another campaign's file, for the reasons recorded beside it.

The rule underneath is one this campaign keeps arriving at: a gate's output is
evidence, and evidence read through `head` or `tail` is not evidence. Ask the
checker, not its transcript.

### the-held-file-constraint-has-lifted-and-was-hiding-a-different-one | high | Seven pending paths in the whole worktree; what blocks the remaining Steps now is this executor's scope, not another contributor's diff

The plan's strongest ordering constraint says a Step whose scope names a file
another contributor has modified waits, and at authoring time that blocked the
whole of Wave two's residue and predicate Phases. The plan also instructs a
re-check rather than an assumption, and the re-check was owed.

It has lifted. The worktree carries seven pending paths in total, one of them
under `src/`, and every path those Steps name is clean: the application closure
module, the export schema, the filing export proof, the modelo 151 and 185
revision directories, the justfile, the import-linter contract and the project
file. The import refactor that held them is finished.

Those Steps are still not done, and the reason has quietly changed underneath
them. This execution is scoped to `dev/` and `.vault/`, so a Step naming `src/`,
the justfile or the project file is outside what may be written here whatever
its git state. The two blocks are worth separating precisely because they
produce the same appearance and want opposite responses: a held file means wait
and re-check, a scope limit means hand off and say so. Left conflated, a Step
blocked only by scope reads as one that will clear itself, and nobody picks it
up.

Two smaller observations from the same check. The four remaining pending paths
belong to the modelo 200 campaign, and one of them is the very module flagged
here for carrying step ids as cohort vocabulary and for recompiling an authority
inside a comparison - so that work is in hand, and the Step this plan raised for
it should stay with its owner rather than be taken up here. And the single
`src/` path is one casilla file, which is a measure of how quiet this tree has
become compared with the state the constraint was written against.

### the-screens-package-declared-one-helper-ten-times | high | Byte-identical copies in all ten screen modules, now one defining module, census unchanged at 1,651

This plan opens by counting how many places the registry states one fact. The
same count was never taken of the tooling written to make that argument. Taken
now, the screens package declares `_bundled_modelo_ids` - three lines returning
every bundled modelo code as a sorted tuple - in all ten screen modules. The
bodies hash identically: one implementation, ten copies.

They are replaced by `corpus.py`, a defining module named for what it holds
rather than for being shared, since the architecture rule this campaign works
under forbids a generic bucket as much as it forbids the duplication. The
function is public because ten consumers reach it; the copies were private, and
a private symbol imported by nobody and rewritten ten times is the shape a
missing home takes. The lazy application import is kept and the reason written
down: a screen module should cost nothing to import until it is asked for the
corpus.

The evidence that the collapse is safe is that nothing moved. The runner reports
the same 1,651 findings across the same ten screens, and the twenty-two
declaration invariant gates pass, exit 0 - including the ones that discover
screens by signature, list them against the contributor README, and require each
to carry a test module, none of which mistake the new module for a screen.

A measurement artefact from the same iteration is worth recording beside it. A
tree-wide parse gate ran while these ten files were being rewritten and reported
a file it could not parse; re-run afterwards it passes. The failure was real at
the instant it was taken and meaningless a second later, because the thing being
measured was being written by the same session doing the measuring. Comparing
the two runs by identity rather than by count is what made it legible - the
failing set was otherwise unchanged, so the single new entry stood out as an
event rather than a regression.

### the-pipeline-duplicated-two-guards-and-one-algorithm-and-only-the-guards-were-collapsed | high | A drifting sum is a wrong number; a drifting guard is a route into the tree that stops refusing

Sweeping the registry tooling for identical function bodies across modules -
the technique that found one helper written ten times - returns three more pairs
in the pipeline package. Two are refusals: the check and validation paths both
refused a link-like or absent location, and the check and publication paths both
asked whether one location sits inside another. The third is a generic
duplicate-finder over an iterable, in two unrelated modules.

Only the guards were collapsed, and the asymmetry is the point. A duplicated
computation that drifts produces a wrong number, which a test catches. A
duplicated guard that drifts produces one route into the generated tree that
refuses a symlink and another that does not, and the second is the route an
accident arrives through. That is worth a defining module even at five lines
apiece; the duplicate-finder is not.

The guards live in `_tree_paths.py`, private to the pipeline package. The
shipped `link_safety` module owns what a link IS, and these compose it into the
two refusals this pipeline makes - a dev-side guard does not belong in the
product's core, and the core is outside this work's scope in any case. The
duplicate-finder stays where it is, and the reason is written here rather than
left as an omission: a module named for finding duplicates in a sequence would
be the generic bucket the architecture rule forbids, and inventing one to satisfy
a symmetry would trade a small duplication for a permanent misnamed home.

Two publication tests fail after the change and failed before it, with the same
two refusals - a journal candidate that is not a staging sibling, and a
provenance file the fragment loader will not accept without a TOML suffix. They
appear in the pre-change suite run and are unrelated to the guards; the three
edited modules import cleanly and twenty-nine tests pass beside them.

### one-filename-three-declarations-and-one-value-under-two-names | high | The inverse of the constant-agreement gate: not one name with two values, but one value with several names

Chasing a publication refusal - a loader rejecting `_generation.provenance.json`
inside a revision directory - found the filename declared three times: the
pipeline's provenance module, which nine other modules import from; the shipped
loader cache, outside this work's scope; and the render-check module, which
restated the literal privately. The restatement was in a file this campaign has
been extending all session, which is the honest way to say where it came from.

Measuring the class rather than the instance found five more inside the registry
tooling. A manual-source sha256 declared in three modelo 200 modules under one
name. A registry package path in two census modules. A serializer convention
token in two pipeline modules. A sha256 pattern in two. And the pre-rename
provenance filename declared twice under two DIFFERENT names -
`_LEGACY_EXPORT_FRAGMENT_PROVENANCE_FILENAME` in the module that skips the file
and `_LEGACY_SIBLING_MANIFEST` in the module that removes it.

That last one is the worst shape in the set and the reason it was fixed first.
One value under one name is greppable: a reader searching for the string finds
every use. One value under two names is not - searching either name finds half
the uses, and the half that is missed is invisible rather than merely
inconvenient. The reader who renames the file will find one of them.

The provenance filename now has a single public declaration that the publisher
and the reader both import, and render-check imports rather than restates. The
tests that cover those modules report 31 passing with the same two failures they
had before the change, reporting the same two refusals, which is how the edit is
known to be neutral to them.

This class is the inverse of the constant-agreement gate this campaign already
built. That one refuses a public constant carrying two values; this is one value
carried by several constants, and no gate sees it. A general gate would be
wrong - this tree deliberately requires each module to declare its own encoding
constant, so the pattern is sanctioned in one place and a defect in others - but
the distinction is worth stating rather than leaving as an omission the next
sweep rediscovers.

### the-registry-tooling-now-states-each-of-those-values-once | high | Three more restatements collapsed, and the digest one is the reason the class matters

The remaining one-value-many-names instances inside this work's scope are
closed. The registry package path was declared in both load-census modules and
is now stated by the census and imported by its classification. The serializer
convention token was declared by the tree renderer and restated by the render
check; the renderer's is now public and the check reads it. The lowercase-hex
digest shape was declared identically in the provenance module and the
publication module, and now lives where digests are validated.

The digest is the one that justifies the effort. The other two would produce a
mismatch if they drifted - a comparison failing, a census missing a module -
which is noisy and self-announcing. Two modules deciding separately what a
sha256 looks like is different in kind: a relaxation applied to one leaves the
other still refusing, so the tree gains a route that accepts a digest another
route rejects, and nothing fails until something is published that should not
have been. A duplicated validator is a duplicated decision about what is
acceptable, and those do not announce their disagreement.

Forty-three tests pass across the four affected modules with three failures,
each of which predates this change and appears in the pre-change suite run: the
two publication refusals already recorded, and a census classification whose
rules name seven members no longer in its universe. That third one is this
campaign's own subject in another module - a declaration outliving what it
describes - and belongs to the load-census work rather than to constants.

### the-seven-stale-rules-are-not-stale-the-census-went-blind | high | Six of the seven targets still exist; the resolver stopped following a dynamic import and the symptom surfaced a directory away

The load census fails with seven classification rules said to describe nothing
in its universe, which reads as a table gone stale - the very defect this
campaign spends its time removing, in this campaign's own tooling. Checking each
target before deleting anything: one is genuinely gone, `registry.snapshot`,
refactored into `_snapshot_internals` and siblings. The other six all still
exist. Modules that still exist do not leave a census universe on their own.

The renta rule explains why not, and it was written to be read at exactly this
moment. It records that `_snapshot` imports the cross-domain check modules by
NAME from a module-level tuple, that no AST import graph can see that edge, and
that the census recovers it by reading the tuple. Asking the resolver what it
finds today: it locates the site in `_snapshot_internals` and returns
`target=None`. The site is now `tuple(dict.fromkeys(REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES.values()))`
- names derived from another module's mapping rather than written as literals -
and the static resolver cannot read that shape. `dynamic_reach` skips a site it
cannot resolve, so renta and its upstream left the universe, and the rules
describing them began reporting as stale.

The rules are correct. The instrument stopped seeing what they describe. Had the
seven been deleted as the failure invited, the census would have gone quiet
while covering less, and the reviewed decisions about a package the snapshot
path certainly reaches would have been thrown away to silence a symptom.

The census already knew. `unresolved_dynamic_sites` is on the report, the CLI
prints it, and five sites sit in it today - but nothing asserted on the field,
so the blindness had no failure of its own and surfaced one directory away as
somebody else's stale table. A gate now asserts the registry package has no
unresolved dynamic site, scoped to the registry because a gate failing on all
five at once would not say which one broke the census. It is red, correctly, and
its message says what to do and what not to: teach the resolver this shape or
restore a readable one, and do not delete the rules.

### the-census-can-follow-the-snapshot-edge-again-by-asking-instead-of-parsing | high | The resolver evaluates the declaration in a separate interpreter; renta is back in the universe and the stale count fell from seven to six

The blinded resolver is repaired, and deliberately not by teaching it the shape
that blinded it. The tuple of cross-domain check modules was a literal when the
scan was written and is now built from another module's mapping values; a scan
taught to read `X.values()` would go blind again at the next construction, and
its own docstring already declines to guess at computed names for that reason.

It now asks. An unresolved loop constant is evaluated by importing its module
and reading the name, in a separate interpreter - for the reason every other
measurement here uses one: importing the module in this process would add it and
its imports to this process's module set, and this is a census of what gets
imported. The instrument stays out of its own reading. Any failure returns None,
so the caller still records an unresolved site rather than receiving a guess.

One correction to the first attempt, caught by its cost rather than by a test.
The evaluation was placed before the check for an actual `import_module` call,
so every ordinary loop in the tree spawned an interpreter to resolve a constant
nothing imported; the census stopped completing in ten minutes. Finding the
import sites first and evaluating only when one exists takes 17.4 seconds over
sixteen sites. A fallback that fires on every candidate rather than every case
is not a fallback, it is a scan.

The result is measured: `_snapshot_internals` resolves to the two renta
routing-integrity modules, renta is back in the universe, and the stale count
fell from seven to six. The registry-scoped gate added alongside now passes. The
remaining six entries name modules that still exist and are no longer reached,
and each needs the same question asked separately - whether the load genuinely
narrowed or another edge stopped being followed - which is why they are left
standing rather than deleted in a sweep.

### the-census-is-clean-and-the-six-were-stale-after-all-but-only-provably-so-afterwards | high | Eight tests pass; the same deletion refused two iterations ago is now the right one, for a reason that did not exist then

The six classification entries left standing last iteration are retired and the
load census is clean: eight tests pass, exit 0, no unclassified module, no stale
rule.

The deletion is the same one the failure invited two iterations ago and it was
right to refuse it then. What changed is not the entries, it is what can be
proved about them. With the resolver blind, "not in the universe" had two
possible causes and no way to tell them apart, and one of them - the census
having stopped following an edge - would have been concealed rather than fixed
by deleting the rules that noticed. With the resolver repaired, the second cause
can be ruled out by measurement: every remaining unresolved dynamic site sits
outside the load closure, and `dynamic_reach` only follows sites inside it, so
none of them can contribute a module to the universe however they resolve. The
five surviving modules are therefore genuinely unreached, and the sixth,
`registry.snapshot`, is genuinely deleted - refactored into
`_snapshot_internals`, `snapshot_coordinate` and `validate_cross_domain_snapshot`,
all three of which the table already carried.

The edits follow the shape of each entry rather than a rule about entries. Three
member names were dropped from lists that keep other live members. The
categories prefix was dropped from a rule whose remaining member is still in the
universe. The auth rule carried nothing but its dead prefix, so the rule went
whole rather than being left as an empty shell that reads like a considered
decision. And the deleted module's entry was one bare package-relative name
beside the three modules it became.

The general form is worth keeping, because this campaign will meet it again: a
finding that says "X no longer describes anything" is a claim about two things -
the tree and the instrument - and it can only be acted on once the instrument is
known to be sound. Fixing the instrument first cost two iterations and turned an
unsafe deletion into a provable one.

### the-evaluator-is-proven-and-the-four-remaining-unresolved-sites-are-correctly-unresolvable | medium | Ten tests pass; every refusal path is exercised, and the residue is accounted for rather than left open

The resolver added last iteration was public and untested, which this campaign
refuses of any other declaration and should refuse of its own. It now carries
two proofs. The first resolves the live non-literal construction and asserts the
names it recovers are the renta routing-integrity modules - the property that
matters, since a literal and a mapping-derived tuple must answer identically or
the next construction blinds the census again. The second exercises every
refusal path: a module that does not exist, a name the module does not carry,
and a name that holds a callable rather than a sequence. Each returns None.

The refusals are the half worth proving. The caller records an unresolved site
and a gate reads that record, so a fallback that returned a partial or invented
answer would populate the universe with modules nothing imports, and the census
would report itself complete while describing a tree that is not there. A
resolver that cannot fail loudly is worse than one that cannot resolve.

The four unresolved sites that remain were checked rather than assumed to be
fine. Two sit in the CLI and two in development tooling, and both dev ones are
genuinely unresolvable by any means: one imports a module named by a function
parameter, the other a name computed from a path. Neither has a value to read.
All four also sit outside the load closure, and `dynamic_reach` follows only
sites inside it, so none can affect the census whatever becomes of them. Ten
tests pass in that module, exit 0.

### the-load-census-now-has-a-criterion-and-it-carries-the-instrument-condition | medium | A coverage number means nothing unless the thing counting can see, and the plan now says so where the number is quoted

Three iterations of work stood behind the load census and the plan's
verification section never mentioned it. It does now, and the criterion is
written in two halves deliberately.

The first is the coverage: every module the registry load reaches carries
exactly one reviewed classification, which holds today at 411 modules in the
universe, none unclassified and no stale rule. The second is the condition that
makes the first mean anything: the census must be able to see what it is
measuring. Those halves are not separable here, because the census reports an
unclassified module and a stale rule by the same absence it reports when its own
resolver has stopped following an edge. A clean result from a blind instrument
and a clean result from a sound one are the same text.

That is not a general observation appended to a criterion; it is what happened.
The resolver followed a literal tuple, the same names were rebuilt from a
mapping, and the census lost a package while reporting the loss as somebody
else's stale table. The criterion therefore names the gate that holds the
instrument sound - no dynamic import inside the registry package left
unresolved - beside the number it qualifies.

Reviewing the other criteria against the same test, most already carry one: the
screens must search a non-empty population and complete over the whole corpus,
the conformance criterion requires an absent vector to refuse rather than read
as unmeasured, and the temporal criterion now names the flag that stopped its
probe erasing its own subject. The pattern was already the section's habit; the
census criterion was the one that had never been written down at all.

### the-consolidations-are-verified-against-every-screen-and-the-census-is-byte-stable | high | 79 tests pass across the ten screen modules, exit 0, and the corpus still reports 1,651 findings

This session moved a good deal of structure: a helper collapsed from ten copies
into a defining module, two duplicated path guards into one, four constants onto
single declarations, a screen's kinds turned into data, a per-definition
function extracted so two detector proofs could assert what the screen reports,
and a dynamic-import resolver rewritten to evaluate rather than parse. Each was
verified where it landed. This is the check that they hold together.

All ten screen test modules run green: 79 tests, exit 0. The runner reports the
same 1,651 findings across the same ten screens it reported before any of it,
and the declaration invariant gates - which discover screens by signature, hold
them against the contributor README, require a test module each, and assert no
screen rebuilds the resolved surface - pass at 22.

The unchanged total is the evidence that matters, and it is worth being precise
about what it does and does not prove. It proves the consolidations were
behaviour-preserving: the same corpus, read through moved and renamed
declarations, still produces the same findings. It does not prove the findings
are right, and no census total ever will. A refactor that changed the number
would have needed an explanation; one that does not is simply a refactor, which
is the whole of what was intended.

### the-gate-that-excluded-fact-bullets-left-a-miscount-standing-in-them | high | A screen said four facts decided its answer and listed five; twenty-three gates pass now

The condition-count gate counts the bullets following a screen's "N conditions
are reported" claim, and its implementation carries a comment explaining that
it deliberately stops before the FACT bullets several screens list first -
counting those had made it fail on a docstring whose stated number was right.
That exclusion was correct for the claim it checks and left a second claim
unchecked entirely. One of them was wrong: the capability screen opened with
"Four facts decide it" and listed five.

The miscount matters for the same reason the sibling gate exists. A wrong count
tells a reader the list is complete, so the item they never find is the one they
conclude does not exist - and here the fifth fact is the deadline window, the
one that decides whether a revision can say WHEN a filing is due. A reader
counting four would have taken the capability answer as settled without it.

Both claims are now gated, separately, because they count different bullet runs
in one docstring and a gate conflating them would be wrong in whichever
direction it guessed.

The new gate was wrong on its first run and the failure was mine to read. It
counted bullets opening with a backticked name, which is how the conditions gate
does it and how every condition bullet is written; fact bullets are prose, so it
reported five facts as one. The pattern was copied from a sibling without asking
whether the thing being counted had the same shape - which is the fourth time
this campaign has carried an assumption across from a neighbouring case, and the
first where the gate I had just written caught me inside a minute. Twenty-three
tests pass in that module, exit 0.

### the-count-gate-was-keyed-to-one-spelling-and-read-four-screens-of-five | high | A screen saying "disagreements" instead of "conditions" was never checked

The condition-count gate triggered on the literal phrase "N conditions are
reported". Four screens write it that way. The temporal screen writes "Four
disagreements are reported", and was therefore not checked at all - its count is
in fact right, which is the only reason this cost nothing beyond the gap.

The gate now reads the claim rather than one spelling of it: any number word,
any noun, followed by "are reported". Enumerating the synonyms would have been
the same defect written longer, and this campaign has already recorded four
heuristics that encoded one shape of a concept and missed the rest. Five screens
are now checked where four were, and no count is wrong.

Two of my own errors are worth recording against this. The first attempt matched
a docstring anchor that did not exist and made no change, which the assertion
caught. The second wrote the regex through a shell heredoc that turned the
word-boundary escape into a literal backspace byte, so the pattern matched
nothing and the gate failed with "no screen stated a condition count, so this
gate checked nothing" - the guard the gate carries against exactly this, written
by whoever built it, catching the person who broke it. A gate that asserts it
found something to check is worth the extra line every time; without it the
broadened pattern would have passed silently while reading zero screens.

### two-absence-gates-could-not-prove-they-had-looked-and-most-already-could | medium | The sweep flagged thirteen, then nine, and the answer was two

The guard that caught a broken regex last iteration - a gate asserting it found
something to check - was audited across all twenty-three declaration invariant
gates. Two crude sweeps produced two wrong answers before the question was asked
properly, which is worth recording because the wrongness had the same cause both
times: the sweep encoded one shape of "proof that the gate looked".

The first flagged thirteen by looking for a truthiness assertion, and missed
that an equality against a populated import cannot be vacuous - if the discovery
side empties, `defining == enrolled` FAILS rather than passing, so those gates
need no separate guard. The second flagged nine by looking for absence
assertions without a truthiness guard, and missed the comparison form: the
package-initialiser gate proves it looked with `checked > 1`, and the vault
citation gate with `scanned > 100`, both of which are stronger than the
truthiness the sweep was hunting for.

Two gates genuinely could not prove they had looked, and both walk the
filesystem, which is where an empty discovery is realistic - a moved package or
a changed suffix rather than an empty tree. The reassembly gate, rewritten this
session onto the syntax tree and given a recursive walk, counted no modules; the
screen-test-module gate built its set from a glob and asserted nothing about it.
Both now assert the walk found something before asserting what it found. Twenty
three tests pass, exit 0.

The pattern in the corrections is the same one this campaign keeps meeting from
new angles: a check for a property is only as good as its account of how that
property can be expressed. Three spellings of "this gate looked" were in use
here - a truthiness assert, a minimum count, and an equality whose other side is
known non-empty - and any sweep recognising fewer than all three reports gaps
that are not there.

### the-phase-heading-described-half-its-contents-and-my-first-correction-said-a-tenth | medium | Counted: 80 records, 83 tooling Steps, two source, three other

The decisions Phase is named for authoring four architectural decision records
and holds 168 Steps. That mismatch is this campaign's own subject in its own
plan - a declaration that stopped describing what it names - so the description
under the heading now says what the Phase actually contains.

The first version of that correction was wrong in the direction this campaign
warns about constantly. It said the heading described a corner of the Phase, on
no measurement at all, because 168 Steps under a four-record heading feels like
a heading describing almost nothing. Counting them says otherwise: 80 name a
decision or record under `.vault`, 83 name development tooling, two name `src`
and three name something else. The heading describes about half of what is
there, and the honest correction is smaller and duller than the one I reached
for first.

The heading itself is left alone. The Steps carry its identifier, and renaming a
container whose children are addressed by that name would orphan every reference
to them - the same reasoning that kept the plan from renaming Steps whose ids
appear in other campaigns' records. A container that has outgrown its name is
repaired by describing it accurately, not by renaming it after the fact.

One strand inside the tooling half has no heading anywhere and is now named in
that description: proving an instrument can still see what it measures. It was
never planned. It exists because a figure this plan quoted was wrong four
separate times, and each correction found a screen, a probe or a gate reporting
a clean result it was no longer able to earn.

### the-two-modules-this-session-created-had-no-tests-and-no-gate-asked-for-any | high | The screen-test gate requires a test module of screens only, so a defining module slips past it

Collapsing duplication produced two new defining modules - the corpus accessor
ten screens had declared privately, and the two path guards duplicated across
three pipeline modules. Both were verified where they landed, by the census
being unchanged and by the tests of the modules that import them. Neither had a
test of its own, and nothing asked for one: the gate that requires a test module
requires it of screens, identified by their `screen_authority` signature, and a
defining module has none.

That is the same shape this campaign keeps finding. A gate covers the population
it was written for, the tree grows a member outside that population, and the
absence of a complaint reads as coverage. The remedy here is the tests rather
than a broader gate, because widening the screen-test gate to every module in
the package would demand a test module for every private helper and teach
authors to write empty ones.

Six tests now stand behind them. The corpus accessor is held against the
authority's own modelo set rather than a count, so a stale list fails instead of
silently shrinking every screen's sweep, and its ordering and member types are
asserted because the screens' rows are compared line by line.

The path guards get the branch that matters. A real directory passes, so the
refusals are not vacuous; a missing path is refused by subject name; and a
symlink is refused THOUGH IT EXISTS, which is the case a guard checking only
`exists()` would admit and the way a publication writes outside the tree it
believes it is in. Containment is asserted in both directions, including that a
parent is not inside its own child. Ten tests across the two modules, exit 0.

### eighteen-twelve-eight-one-and-only-the-last-was-true | high | Three wrong ways of asking which modules lack tests, and the answer was one module

Generalising last iteration's finding - a module outside the population a gate
was written for reads as covered - produced four answers in succession, and only
the last was right. The sequence is the finding.

Eighteen, by matching a module against a test file of the same name. Wrong: the
pipeline's modules carry a leading underscore that their test files drop, so
every one of them looked untested. Twelve, after stripping the underscore.
Wrong: the tests here are named for the SUBJECT rather than the module -
`_tree_check` is covered by `test_generated_tree_check` - and the conformance
package keeps its tests in its own directory, which the sweep never looked in.
Eight, by asking which modules no test imports. Wrong again, and more subtly:
the extractor collected the module of a `from X import Y` but not its names, so
every module imported as a name rather than a path counted as untested. One,
after collecting both forms.

The corrected instrument is also the simpler one. Coverage by import is exact
and convention-free, while every filename rule encoded a naming habit that this
tree only partly follows. Three of the four attempts failed for the same reason
the campaign keeps recording - a check for a property that recognises one way of
expressing it - and here that reason produced a seventeen-module phantom backlog
before it produced a fact.

The one real case is `m303_orden_anual`, whose public surface is a generator
with a `--check` mode that refuses a stale or missing artefact. Nothing ran it,
which makes a current artefact and an unrun generator look identical. It runs
now, in 9.6 seconds, exit 0, so the committed manifest and census artefact are
proved to reproduce from their pinned sources. A second test asserts the
refusing flag rather than the writing default is the one under test, because the
distinction is one keystroke wide and the wrong side of it regenerates registry
artefacts from a test run.

### the-coverage-question-is-now-a-gate-rather-than-a-sweep-somebody-remembers-to-run | high | Twenty-five gates pass; the measure that took four attempts is now standing, with a planted proof

The import-coverage measure that took four attempts to get right is now a gate.
It asks the only question that survived those attempts - which public modules no
test imports - and it asks it the only way that proved reliable, by reading both
import forms out of every test module under the registry tree rather than by
matching filenames against a convention this tree follows in three different
ways.

It carries two non-vacuity guards rather than one, and the second is specific to
how this measure failed before. The first asserts a public module was found. The
second asserts some test import was read at all, because an extractor returning
nothing makes every module in the tree look untested - which is not a
hypothetical, it is the seventeen-module phantom this sweep produced twice
before the extractor was right.

The proof is planted under an injectable root: two modules with a public
function, one imported by a test module written beside them in the temporary
tree and one not, with the gate asserting it sees exactly the orphan. Both
directions matter. Without the first it protects nothing; without the second it
would flag every module reached through the import form the earlier extractor
could not read, which is precisely the failure the guard above exists to catch.

The helpers are shared between the live gate and its proof rather than
reimplemented for each, so the thing proved is the thing that runs. A detector
proved against a reimplementation of itself proves the reimplementation.

### the-proof-i-wrote-two-iterations-ago-was-proving-its-own-copy | high | The principle stated last iteration indicted it immediately; one shared walk now serves both

Writing that a detector proved against a reimplementation of itself proves the
reimplementation was a statement about a proof written in this campaign two
iterations earlier. The reassembly gate walks each analysis module's syntax tree
for a reach at the binding derivation; its proof defined a local `reaches()`
that walked the same three node kinds in the same order. Drop the attribute
branch from the gate and the proof stays green, because the proof was never
looking at the gate.

There is one walk now, called by both. The gate passes it each module's source;
the proof passes it four constructed sources - an import and an attribute call
that must be caught, a docstring and a comment naming the same symbol that must
not be. Twenty-five tests pass, exit 0.

Sweeping the module for the same shape flagged one other test, and reading it
cleared it: the untouched-registry gate defines a local `fingerprint()` and
calls it twice, before and after the screens run. That is a measurement taken
twice within one test, not a detector reimplemented beside itself, and the
distinction is the whole point - a helper that produces the OBSERVATION is fine
to define locally, a helper that makes the JUDGEMENT the gate makes is not,
because only the second can silently disagree with what ships.

### every-constructed-screen-proof-asserts-through-its-screen-and-the-readme-needs-nothing | medium | Two negative results, one of which is a decision not to write documentation

Extending last iteration's principle to the ten screen test modules: does any
proof construct a defect and then assert on something other than the screen it
proves? None does. Every test that copies a real revision and mutates it calls
the screen's own entry function on the result. The two that did not were the
continuity proofs repaired earlier in this campaign, when the screen was given
the per-unit function its siblings already had, so the sweep confirms a repair
rather than finding a new gap.

The second result is a decision not to act. The two defining modules created
this session are absent from the contributor README, and adding them would have
been the obvious tidy. The README documents this package at directory
granularity - one line per subdirectory, plus a section naming the declaration
screens because those are the things a contributor runs - and both new modules
sit inside directories it already describes. An entry for each would have been
the first module-level line in a file that has none, which trades a small
completeness for a documented shape nobody can follow afterwards.

Recording the decision matters more than the decision. A README left unchanged
looks identical to a README nobody thought about, and the next contributor
adding a defining module here will face the same question with no record that it
was asked.

### the-plan-s-opening-figures-cite-this-audit-and-this-audit-does-not-contain-them | high | Searching finds them only where a later entry quotes the sentence that cites them

The plan's first paragraph justifies the whole campaign with five figures - a
revision's temporal validity at eight sites, a citation at eleven, applicability
at seven, capability grade in five encodings, an amount's semantics at six - and
attributes them to the governing audit. They are not in it. "Five encodings"
appears nowhere at all; the other phrasings appear exactly once each, in an entry
written during this campaign that quotes the plan's own sentence back. Searching
the rest of the vault finds no sibling record carrying them either: the one ADR
that matches on "eight sites" is talking about something else.

The circularity is what makes this worth recording rather than quietly fixing. A
grep for the figures succeeds, which is what anyone checking would do, and the
hit is the plan's claim reflected back from a record that cites the plan. A
citation that resolves to a quotation of itself is indistinguishable from a
citation that resolves to evidence, unless the reader looks at what the matching
line actually says.

The figures are not withdrawn. They came from a measurement made before this
plan and not carried into the record that survived, which makes them history
rather than evidence, and the Description now says so instead of pointing at a
document that cannot support them.

One has since been re-derived and the result argues for doing the rest. The
temporal sites are declared as data now, with their boundary written down: six
year-level sites rather than eight, because a deadline window's opening, closing
and payment dates say when within a year a filing falls due rather than which
years the revision serves, and counting them inflates a restatement measure with
facts that cannot disagree with what they are counted against. Six against eight
is two definitions, not an error - and that is only apparent because one of them
is finally written down.

### the-grade-figure-cannot-be-re-derived-and-the-grade-looks-declared-once-today | high | One optional field, a documented reading and a documented distinction - the shape this plan recommends, not the defect it alleges

Attempting the same re-derivation on the second breadth figure - capability
grade in five encodings - fails at the first step, and the failure is the
result. The temporal figure could be re-derived because a boundary could be
stated: a year-level claim about which years a revision serves, which admits six
declared fields and excludes three deadline dates for a reason anyone can check.
No such boundary survives for the grade. What counts as an "encoding" of it was
a judgement the original measurement made and did not record, so there is
nothing to count against.

What is there can still be measured, and it does not look like five of anything.
The schema carries exactly one grade-bearing field on a revision and none on a
modelo: `authority_grade`, optional by design. Beside it sit
`effective_authority_grade`, which is the reading when the field is absent, and
`is_graded`, which preserves the distinction between an ungraded revision and
one explicitly graded at the floor - with a sentinel for the absent case. The
schema's own docstring explains why each exists and why the field is not simply
defaulted.

That is a declared fact with a derived projection and an explicit absence, which
is precisely the pattern this plan exists to move the registry towards. Counting
it as five encodings of one concept would count a well-formed accessor family as
duplication - the same error this campaign made when it read a screen's grammar
names as finding kinds and a runner's deliberate filter as a silent screen.

So the figure is recorded as unre-derivable rather than confirmed or withdrawn.
It may have counted something else, or described a state since repaired; both
are consistent with what is there. What matters for the next reader is that
"grade in five encodings" should not be treated as a live defect on the strength
of this plan's opening sentence, because nothing in the tree today supports it
and nothing in the record explains what it meant.

### the-citation-surface-is-25-types-and-48-fields-where-the-plan-said-eleven | high | Re-derivation moved this figure the other way, and the symmetry it exposed is the more useful half

The third breadth figure re-derives cleanly, unlike the grade, and it moves
against the plan rather than towards it. Counting every declared field on a
registry declaration type whose name pairs `ref` with `legal` or `source` - a
boundary that can be checked, which is what the original figures lacked - a
citation can be restated across 25 declaration types and 48 fields. The plan
said eleven.

The direction matters. The temporal figure came down from eight to six because
a stated boundary excluded within-year deadline dates that cannot disagree with
a year window. This one goes up by a factor of four, so the plan has been
understating its own case, and a reader who trusted eleven would have taken the
citation surface for something a single afternoon could reconcile.

The symmetry is worth more than the total. Twenty-four fields are `legal_refs`
and twenty-four are `source_refs`, so nearly every declaration type able to cite
a law is separately able to cite a source, in parallel fields declared beside
each other. That is not one concept restated 48 times; it is one PAIR of
concepts declared 24 times, which is a different defect with a different remedy.
A campaign that collapsed citations into one home would have to decide whether
the pair travels together or apart, and the count alone does not answer that.

Three of the five figures now have a status: temporal re-derived and narrowed
under a written boundary, citation re-derived and widened under another, grade
not re-derivable because no boundary survives. What separates the two that
worked from the one that did not is only that a boundary could be written down -
and in every case the boundary, not the number, is what a later reader needs.

### applicability-is-three-or-ten-and-the-plan-said-seven | high | The clearest of the four re-derivations, because both defensible answers are defensible and neither is the one on record

Ten declared fields in the registry schema name applicability: one on the
revision, five inside the rule definition that field holds, two on a deadline
window and two on a live cross-reference decision. That is the count a
name-based sweep returns, and it is wrong for the question this plan asks.

The revision's `applicability` field holds a tuple of rule definitions, so the
rule's five `applicable_*` fields are the CONTENTS of one declaration rather
than five places a fact is restated. They cannot disagree with each other about
whether a modelo applies; they compose one answer. Under the boundary that asks
which declarations can independently state that a thing applies, the answer is
three: the revision's rules, a deadline window's conditions, and a
cross-reference decision's predicates.

So this figure has two defensible answers, three and ten, depending on whether
the question is about places that can disagree or fields that carry the word.
The plan said seven, which is neither, and that is the useful result. A number
between two defensible boundaries is not a rounding of either - it is evidence
that a third boundary was used and not written down.

All four re-derivable figures now behave the same way. Temporal narrowed from
eight to six, citation widened from eleven to twenty-five, applicability
resolves to three or ten against a stated seven, and grade could not be derived
at all. In none of the four was the original number reproducible, and in every
one the boundary was the thing that decided the answer. A restatement count
without its boundary is not a measurement that later turned out wrong; it is a
measurement nobody can repeat, which is a different and worse thing to build a
campaign's opening argument on.

### the-last-figure-matches-and-the-match-is-the-least-informative-thing-about-it | high | Six declared fields, two under a stricter boundary, and the fact that decides a monetary scale is declared in none of them

The fifth breadth figure re-derives to six, which is what the plan says. It is
the only one of the five whose number survives, and the agreement is the least
useful part of the result.

Six declared fields state how an amount is written: rounding on a formula and on
a verification expectation, a unit on each of two parameter types, and decimals
and signed on an export field. Under a stricter boundary - how an amount reaches
the WIRE rather than how it is computed - only the last two qualify, because a
formula's rounding and a parameter's unit describe a value being calculated
rather than a value being emitted. So this figure has the same two-boundary
shape as applicability; its broad reading simply happens to land on the number
already written down.

What neither reading contains is the fact that has actually gone wrong. The
scale of a monetary field is decided by its wire type, and the `money` wire type
multiplies by one hundred in the renderer's codec rather than in any
declaration. It is not a field, so no count of declared places can include it -
and it is the semantic behind both live filing-correctness defects this campaign
has pinned, modelo 200's casilla 03594 and modelo 353's casilla 10, each
emitting unscaled beside siblings emitting cents.

That is the closing argument for this whole re-derivation. Four of the five
figures could not be reproduced, and the fifth reproduces while omitting the
only place the defect it describes has actually occurred. A restatement count
measures declarations, and the thing that hurt here was an undeclared behaviour
in a codec - which a count of declarations is structurally unable to report,
however carefully its boundary is written.

### the-undeclared-scale-cannot-be-pinned-from-here-either-and-the-attempt-is-the-finding | high | A gate for it needs a hand-built field stub or a private renderer import, both of which this project refuses

The previous entry ended by noting that the fact behind both live
filing-correctness defects - a `money` field's value being multiplied by one
hundred in the renderer's codec - is stated in no declaration, so no count of
declared places can see it. The obvious next move was to pin it with a gate, so
that the screen's documented reasoning fails loudly if the factor ever changes.
The attempt failed, and the way it failed says more than the gate would have.

Reaching the behaviour means calling `_render_money`, a private function taking
a private field protocol. A test can only do that by importing the private name
and handing it a hand-built object carrying whatever attributes the renderer
happens to touch - the first attempt supplied a length and an id and was told it
also needed `signed`. That object is a fake standing in for a real export field,
and discovering its shape by reading failures is exactly how a fake drifts from
what it imitates. This project's own rules refuse both halves: no private
cross-package imports, and no stubs standing in for the thing under test. The
attempt was withdrawn rather than completed; nine tests pass in that module,
exit 0, and no partial gate was left behind.

So the fact stays unpinned, and the reason is now precise rather than assumed.
It is not that nobody has written the gate. It is that the scale is reachable
only through a private renderer, so a development-side gate would have to fake
the input, and a faked input proves the fake. The gate belongs beside the codec,
where a real export field is available and the factor is a fact of the module
being tested rather than an assumption about somebody else's.

That is a better outcome than a stub-backed green test, which would have
reported the factor as guarded while proving only that a hand-made object
behaves as it was hand-made to.

### the-step-id-leak-is-a-public-api-migration-not-a-test-rename | high | Five files, two exported function names, five refusal messages, seven docstrings and one test name

The gate refusing a plan step id in a development test name has been red for
several iterations on one symbol, and the owning campaign has committed twice
since without addressing it. With its files now clean rather than mid-edit, the
question of whether this work should simply do the rename was worth asking
again. The answer is still no, and now for a measured reason rather than a
cautious one.

The vocabulary is not a test name. `S14/S15` names the cohort across five files:
two exported function names - `check_m200_2024_s14_s15` and
`publish_m200_2024_s14_s15` - five refusal messages, seven docstrings, and the
one test name the gate can see. Renaming the symbol the gate reports would leave
every other site standing, which is precisely the repair the gate's own message
forbids, and renaming all of them is a public-API migration across another
campaign's surface with its CLI and tests attached.

The Step now carries that scope instead of the word "rename", because a Step
saying "rename the vocabulary" reads as an afternoon and a Step naming two
exported functions and five refusals reads as what it is. That difference
decides whether the owner picks it up or defers it again, and the previous
wording was quietly arguing for deferral by understating the work.

The gate stays red, legibly: one symbol named, both wrong repairs stated, and a
Step describing the real remedy at its real size.

### i-closed-a-step-nobody-had-done | high | The codec-side scale gate was marked complete in the same breath as being authored, and is re-opened

A Step authored this iteration - pin the money wire type's hundredfold scale
beside the codec that applies it - was marked closed minutes after being
written. Nothing was done to satisfy it. It is scoped to
`src/cadrumo/domain/calculations/registry/tests`, which this execution cannot
write, and it exists precisely because the gate could NOT be built from here.
It is re-opened.

The mistake has a shape worth naming, because it is the reverse of the one this
campaign has been chasing all session. Every other finding here has been an
instrument reporting a clean result it could not earn; this was a record
reporting completed work that had not happened. Both produce the same
appearance - a green line - and both are only visible by asking what actually
ran.

The immediate cause was mechanical: closing Steps at the end of an iteration
became a habit, and a habit does not distinguish between a Step this work
finished and a Step this work authored for somebody else. The plan now carries
both kinds in the same Phase, which makes the distinction easy to lose and worth
stating: a Step naming a scope outside `dev/` and `.vault/` cannot be closed by
this execution, whatever else happened in the iteration that wrote it.

Caught by re-reading the closing command's own output rather than by any check,
which is the honest account - no gate in this tree would have noticed, because
no gate can know whether a plan row describes work that happened.

### the-false-closure-was-isolated-and-four-sampled-closures-verify | medium | Twenty-three Steps closed outside this execution's reach; the sample holds against the tree

Having closed one Step nobody had done, the obvious next question is whether
that was a habit or an accident. The plan carries twenty-three closed Steps
scoped to `src/`, the justfile or the project file - all outside what this
execution may write, and all closed before it began. Who closed them cannot be
recovered from the record, but whether the work exists can be checked, which is
the better question anyway.

Four were sampled on the strength of being verifiable by existence rather than
by reading. The plan step identifiers a closed Step says were removed from the
modelo 200 revision declarations are gone. The ledger bindings parent module a
closed Step says was deleted is absent. The resolved-surface accessor a closed
Step says was promoted is defined in the module it names. The non-copying
identifier accessor another closed Step adds is present, and this campaign has
been calling it all session. Four of four hold.

So the false closure was an accident rather than a pattern, and the record it
sits in is otherwise sound on this axis. That is worth stating plainly rather
than leaving the doubt open: an error found in one's own work invites suspicion
of everything adjacent, and the honest response is to sample the adjacent work
rather than either assume it is fine or imply it is not.

No gate follows. A check that a plan's closed rows match the tree would be code
reading the vault, which this project forbids in that direction for good reason
- the plan is scaffolding and the tree is the product, and a gate depending on a
plan row would make the scaffolding load-bearing. The verification is a thing a
person does when they have reason to, and the reason is recorded here.

### the-largest-screen-already-reports-the-unit-somebody-acts-on | medium | 1,389 of the corpus's 1,651 findings come from one screen, and the number is the collapsed one, not the raw one

Provenance consistency contributes 1,389 of the 1,651 findings the runner
reports - eighty-four per cent of the total - which is exactly the shape that
turned out to be a reporting artefact when the monetary screen's part-split rows
made up 132 of its 165. The same question was worth asking here, and the answer
is that this screen already asked it.

The raw measurement is per citing child and there are 31,608 of them. The screen
collapses those onto the reference that is actually outside its manifest,
because one missing reference is cited by many children and the thing a person
fixes is the reference. The runner reports the collapsed count. Both numbers are
printed in the screen's own summary beside a third - 314 distinct references
across 1,389 revision-and-kind keys - so a reader can see the raw surface, the
actionable set, and the identities without reading the code.

That is the pattern the monetary screen had to be given and this one was built
with. The docstring even states the ratio: site count exceeds the number of
things to fix by roughly nineteen to one.

Nineteen is also the most defensible answer this campaign has found to the
plan's "one citation can be restated at eleven". It is measured on live data
rather than schema shape, it counts the thing the phrase describes - how many
places repeat one citation - and it comes from the screen that owns the
question. The schema-shape answer of 48 fields across 25 types remains true of
the SURFACE; nineteen is true of the corpus. Neither is eleven, and the pair is
more useful than either alone: one says how many places could restate a
citation, the other how many typically do.

### no-screen-hides-a-raw-count-behind-an-actionable-one-and-the-two-that-looked-like-it-were-my-key | medium | The finding shapes differ because the screens do, which is correct and which a generic check cannot assume

With two screens found reporting collapsed counts deliberately - monetary after
being given the treatment, provenance having been built with it - the remaining
seven were checked for the same gap: does any report a raw site count where a
smaller actionable one exists?

None does, and the check had to be corrected before it could say so. Keying
every finding on modelo, revision and kind reported wire-type compatibility and
provenance as collapsing twenty-nine and 1,389 rows onto one coordinate each,
which would have been a spectacular gap. Neither finding type has a `kind`
field: provenance carries `ref_kind`, wire-type carries a `divergent` flag, and
the missing attribute read as None for every row. The seventh instrument error
of this campaign, same shape as the rest.

The reason those two lack the field is the useful part. A screen reporting ONE
condition needs no discriminator - a kind column would be a constant - so the
absence is a property of the screen rather than an omission in the finding.
Monetary reports thirty-three rows across eleven coordinates because several
fields in one revision each need their own scale, and the field is what a person
fixes, so per-field is already the actionable unit.

The conclusion for anyone building across these screens: their finding types
share modelo and revision and nothing else, deliberately, because the coordinate
that identifies a defect differs by condition. A cross-screen tool that assumes
a common shape will silently mis-read the screens whose conditions do not have
one, which is what happened here and would have been reported as a finding had
the numbers been less absurd.

### the-contract-i-wrote-was-wrong-and-its-own-gate-said-so-within-a-minute | high | A runner row is not a finding, and writing the contract as though it were is what seven mis-reads had in common

Seven instrument errors in this campaign share one cause: assuming a uniform
surface where the tree has variety. The structural answer is to write down what
IS uniform, so a cross-screen tool knows what it may assume. That is now
declared beside the runner: every finding type these screens define identifies
its modelo, and nothing more is promised.

The first version of the gate asserted the contract over the rows the runner
emits and failed immediately on two screens. That failure was correct and the
contract was wrong. The runner deliberately collapses two entries onto a
different unit - a reference sitting outside a manifest, a wire-type transition
- and those rows are a REPORT, not a finding. A caller reading the runner gets
whatever the entry chose; a caller calling a screen gets a finding, and a
finding names its modelo.

That distinction is the thing seven mis-reads had in common, restated at the
level of the contract rather than the level of any one check. A report and a
finding look identical - both are rows with attributes - and the difference is
whose question they answer. Every cross-screen key that has failed here failed
by keying a report as though it were a finding.

Both are now written down: the contract says what a finding promises, and says
in the same breath that the runner's rows are not covered by it. The gate reads
the finding types rather than the rows, because a caller keying on a field wants
to know the type declares it, and twenty-six tests pass in that module, exit 0.

One field, deliberately. Eight of the nine types also carry a revision and one
does not, because a continuity chain spans revisions and pinning one would name
a revision the defect does not belong to. Promising the revision would have
promised a shape one screen correctly does not have - the same over-reach in a
smaller font.

### the-runner-called-every-row-a-finding-including-the-two-that-are-reports | medium | One word in two output lines, and it was the conflation the contract had just been written to separate

Having declared that a screen's finding names its modelo and that the runner's
rows are not covered by that promise, the runner was still printing
`findings=N` on every line - including for the two entries whose rows are a
collapsed reference and a wire-type transition. The distinction had been written
into a constant and a gate while the user-visible output went on erasing it.

The output now says `rows`. Each line already carried a `counts` label naming
what that screen's rows are - references cited from outside their manifest,
transitions that diverge, revisions whose grade and machinery disagree - so the
honest reading was always available and the word above it contradicted it. The
summary reads `screens=10 rows=1651`.

Nothing depended on the old wording: no test, no recipe and no documentation
matched `findings=`, which is worth checking before changing an output string
and worth recording once checked, because the next person to consider this will
otherwise repeat the search.

The change is one word in two lines and it closes the last place this package
said finding where it meant row. That matters more than its size: seven
cross-screen mis-reads in this campaign began by treating a report as a finding,
and the runner's own output was teaching exactly that.

### two-labels-named-revisions-and-counted-disagreements | medium | 67 rows over 53 revisions, and 36 over 34, each label promising the smaller number

With the runner's rows renamed, the labels beside them were checked against what
they count. Eight are exact: a screen whose label says modelos emits one row per
modelo, one saying revisions emits one per revision, one saying fields emits one
per field, and the two collapsed entries say references and transitions, which
is what their rows are.

Two were not. The capability label said "revisions whose declared filing rung
and the machinery behind it disagree" and counted 67 rows across 53 revisions,
because a revision failing on two axes produces two rows. The grade label said
"declared grades that do not match what their prerequisites support" and counted
36 across 34. Both promise the smaller number in the label and print the larger
beside it.

The labels now name disagreements rather than revisions or grades, which is what
the rows are. The alternative - collapsing the rows onto their revision - would
have been wrong: a revision failing on layout and on deadline needs both facts,
and merging them into one row would hide the second the way counting sites
instead of fixes hides the first. When a label and its count disagree, which one
moves depends on which is the useful unit, and here the count was already right.

This is the smallest instance of the pattern this campaign keeps finding and the
easiest to dismiss: a fourteen-row overstatement in a screen nobody gates on. It
is worth fixing for the same reason the runner's wording was - the labels are
where a reader learns what these numbers mean, and a label that names the wrong
unit teaches the mis-reading that has cost this campaign seven measurements.

### the-readme-taught-the-conflation-too-and-a-gate-for-it-was-declined | medium | One sentence corrected; the label check is left to a person because gating it means parsing prose

The contributor README opens its screens section by saying each one "prints one
greppable row per finding" - the wording corrected in the runner an iteration
ago, in the document a contributor reads first. It now says one row per result,
and names the exception: two screens collapse theirs onto the unit somebody
fixes, so their rows are a report rather than a finding, and the runner's label
on each line says which.

The table below it was left alone on purpose. It paraphrases each screen's
condition in the README's own words rather than repeating the runner's labels,
which is a duplication that could drift - and it is the right one to keep, since
the table answers "what does this screen look for" while the label answers "what
is one row of its output". Two different questions about the same screen deserve
two sentences, and collapsing them would make the table useless for the question
it exists to answer.

A gate for the labels was considered and declined. All ten now name the unit
their rows are, which is exactly the state where a regression guard is
attractive, but checking it means parsing a prose label for its head noun and
comparing that against a count - a heuristic over English, and this campaign has
recorded seven measurements lost to heuristics that recognised one shape of a
thing. A check whose own correctness cannot be established is not a gate, it is
a second thing to maintain.

### the-screens-criterion-listed-nine-properties-and-there-are-twelve | medium | Written properties-first this time, because the total has moved twice while the properties have not

The verification criterion holding the screens to account named nine properties
and opened with the number. Three gates have joined them since it was written -
that a screen module's public surface is imported by some test, that a finding
type declares the modelo the identity contract promises, and that a screen
stating how many facts it reads lists that many - so the sentence undercounted
its own subject by a third.

The count is now written after the properties rather than before them, which is
the same repair applied to the gate figures in the description earlier in this
campaign and for the same reason: a number leading a sentence reads as the
claim, so a reader who finds twelve where nine is promised suspects the gates
rather than the sentence. A number trailing the thing it counts reads as an
observation, and an observation that has aged is easy to correct.

The three additions are each a hole this campaign fell into rather than
anticipated. The import gate exists because two modules created while collapsing
duplication had no test and no gate asked for one. The identity gate exists
because seven cross-screen measurements were mis-read by assuming a field two
finding types do not carry. The fact-count gate exists because the
condition-count gate deliberately skipped the fact bullets, and one screen said
four where it listed five. None was designed; each was the shape of a specific
mistake, made durable.

### i-added-three-properties-and-left-the-nine-in-front-of-them | high | The same stale-count defect, committed inside the edit correcting it, plus two ordinals pointing at positions that had moved

Updating the screens criterion to name three gates it had not caught up with, I
appended the properties and left the sentence opening "Nine gates cover this".
The paragraph then listed twelve things behind a promise of nine, which is worse
than the understatement it replaced: an undercount invites a recount, while a
number contradicted by the list beneath it tells the reader one of the two is
lying and does not say which.

Two further references were broken by the same edit and are the reason this is
worth recording rather than quietly fixing. The paragraph explained why "the
seventh" gate reads by running rather than parsing, and why "the eighth" exists
because the seventh was not enough. Those ordinals addressed positions in a
list, so appending to the list silently re-pointed them - the seventh became a
different gate than the sentence describes. They now name the gates: the
kind-naming gate and the condition-count gate.

Positional references into a list that can grow are the same defect as a frozen
count, in a form that fails more quietly. A stale number is visibly wrong to
anyone who counts; a stale ordinal still resolves, to the wrong thing, and reads
as correct. The criterion now names properties and puts its total behind them,
and refers to gates by what they do.

### one-more-positional-reference-into-a-list-that-can-grow-and-the-rest-are-safe | medium | "The tenth screen" now names itself; the other ordinals are local pairs and stay

Having broken two ordinal references by appending to the list they indexed, the
plan was swept for the same shape. Seven ordinal phrases appear in it and six
are safe: they are local pairs - the first half and the second half of a
criterion stated in the same sentence, the first and second of two defects named
in the line above - where the referent is fixed by the sentence rather than by a
position in a list somebody can extend.

One was not. The description opened a paragraph with "the tenth screen answers
the question that opened this work", indexing into an enumeration that grows
whenever a screen is enrolled. It now names the capability screen, and says why:
it was the tenth when written, and an eleventh would have re-pointed the sentence
at a screen answering something else, silently and while still reading as
correct.

The development tooling carries none of this shape - no docstring in the
registry package refers to a screen, gate, condition or rule by position. That
is worth recording as a negative result, because the sweep was cheap and the
absence is not obvious: prose describing a numbered list naturally reaches for
ordinals, and this package's docstrings consistently name their subjects
instead.

The distinction that makes six of seven safe is worth keeping: an ordinal is
fine when its list is in the same sentence and cannot grow, and dangerous when
it indexes something enumerable elsewhere. The test is not whether the phrase
looks positional but whether anything outside the sentence can change what it
points at.

### three-capability-figures-drifted-by-one-each-and-a-qualifier-went-vacuous | medium | 23 not 22, 4 not 5, 69 not 68, and every filing-grade revision now carries a layout

The description's capability paragraph quotes five figures from the capability
census. Re-derived by running it: 58 modelos holds, 31 layouts spelling an
envelope as a record holds, and three have moved by exactly one each - 23
modelos declaring applicability only where the plan said 22, 4 declaring
calculation only where it said 5, and 69 revisions at filing grade where it said
68.

The applicability and calculation moves cancel, which is what one modelo
changing its declared rung looks like from outside. The filing move is a
revision that reached filing grade since. None of the three changes the
paragraph's argument, and that is the point of recording them as movement rather
than as errors: a figure quoted from a live census is a reading, and a reading
taken twice at different times differs without either being wrong.

The fifth is more interesting than a number. The plan said sixty-eight revisions
"reach filing grade with a layout", a phrasing that implies some reach filing
grade without one. None do: all 69 carry a layout. The qualifier was load-bearing
when written and is vacuous now, which is a better fact than the count - there is
no filing-grade revision today with nowhere to put its answer - and a sentence
that keeps a qualifier after it stops distinguishing anything quietly tells the
reader a distinction still exists.

The paragraph now names the census as its source before quoting it, records what
the figures were, and says plainly that they move. The alternative - restating
them each time they drift - is the maintenance this campaign has been removing
everywhere else.

### the-step-s-population-holds-at-twenty-five-and-two-of-them-have-shipped-bytes | high | Modelos 185 and 222 carry a committed export tree while declaring applicability

An open Step proposes resolving twenty-five revisions that carry an export
layout while declaring a grade below filing. Re-measured from the capability
census: twenty-five, exactly, which is the first premise this campaign has
checked and found unmoved.

The breakdown the Step lacked is where the work is. Twenty-two sit at
applicability and three at calculation, so the contradiction is not one shape
but two - a revision saying it can only tell you whether the modelo applies, and
a revision saying it can compute but not file, both carrying the machinery for
rendering a fichero.

Two are sharper than the rest and are now named in the Step. Modelo 185's and
modelo 222's 2025 revisions each carry a COMMITTED generated tree while declaring
applicability. For those two the contradiction is not a declaration disagreeing
with a capability, it is bytes that exist for a revision whose own declaration
says it cannot produce them. Whatever the resolution is - raise the grade or
withdraw the tree - it cannot be "the layout is aspirational", which is available
for the other twenty-three.

That is the value of measuring a premise rather than confirming it. The count
was right and told nobody what to do first; the census answers that in the same
query, and the Step now names the two coordinates where the evidence is already
on disk.

### two-more-step-premises-hold-and-one-of-them-only-under-the-boundary-it-never-stated | high | Five deadline-less filing revisions exactly; four formula-less filing claims under a narrow reading and thirty-five under a wide one

Two further open Steps were measured against the census rather than trusted.

The deadline Step holds exactly: five revisions reach filing grade while
declaring no deadline window, and they are the five modelos it names. The Step
now carries their revision identifiers, which it did not - modelo 145's
2012-01-31-y-siguientes, 151's 2015-2022, 165's 2016-2022, 308's
2019-y-siguientes and 309's 2023-y-siguientes - because a Step naming five
modelos leaves the next person to find which revision of each, and the census
answers that in the same query that verified the count.

The formula Step holds only under a boundary it never wrote down. Read as
"revisions claiming a filing calculation class with no formula behind it", the
population is thirty-five revisions across eighteen modelos. Read as revisions
that ALSO reach filing grade, it is four, and they are exactly the modelos the
Step names: 296, 308, 349 and 360. The Step meant the narrow reading and its
count proves it, but a reader applying the sentence as written would find nine
times the work and conclude the Step was stale.

The wider population is left recorded and unexamined. Thirty-one revisions claim
a filing calculation class while not reaching filing grade, which may be
entirely correct - a revision can be able to compute what it cannot submit - or
may be the same defect at a rung where nobody has looked. Deciding that is not
this Step's job, and saying so is better than letting the number sit in a
measurement nobody wrote down.

### the-multi-axis-step-said-four-and-three-and-the-live-answer-is-one-and-two | high | Fourteen revisions fail several axes; exactly one of them reaches filing grade

The Step proposing to resolve "the four filing-grade revisions failing more than
one capability axis, modelo 308 failing three of them" measures differently
today. Fourteen revisions fail more than one axis. Exactly one of them reaches
filing grade - modelo 308's 2019-y-siguientes - and it fails two axes, not
three: it claims a calculation class with no formulas, and it files without a
deadline window.

Both numbers in the Step moved, which is a stronger signal than either alone. A
count changing suggests the corpus moved; a count AND a per-item figure changing
together suggests the measurement did. This one cannot be settled from here -
whether three axes became two because a defect was repaired or because the axis
set changed is not recoverable from the plan, and the screen that measures it
has had two of its own conditions corrected during this campaign.

What replaces it is a Step naming the coordinate and the two axes, plus the
question the old wording hid: thirteen further revisions fail multiple axes
below filing grade, mostly the same pair - an envelope spelled as a record
beside a layout without filing grade, across modelos 490 and 604 - and the Step
now asks whether they belong with the filing-grade one or are a separate
condition. The original sentence excluded them silently by saying "filing-grade"
and gave no sign that a larger population sat just outside it.

This is the third Step premise re-measured this session and the first to have
moved materially. Two held exactly and one held only under a boundary it never
stated. That distribution is worth keeping in view: most premises in this plan
are sound, which is precisely why the one that is not would have been believed.

### the-registry-suite-after-the-session-s-changes-introduced-nothing | high | 35 failed, 1,048 passed, one failure cleared and none new by identity

The registry tooling suite was re-run whole after a session that moved a good
deal of it: a helper collapsed from ten copies, two path guards into one, four
constants onto single declarations, a screen's kinds turned into data, a
per-definition function extracted, a dynamic-import resolver rewritten to
evaluate rather than parse, three new gates, three new test modules, and a
vocabulary correction across the runner and the contributor README.

It reports 35 failed and 1,048 passed. Compared with the previous run by
IDENTITY rather than by count, one failure cleared - a modelo 200 source rebind
its owning campaign fixed - and none is new. The passing total rose by
sixty-four, which is this session's tests plus that campaign's.

The comparison method is the point and has been all session. Thirty-six to
thirty-five says almost nothing: two failures could have been repaired while one
appeared, and the count would read as progress. The failing SETS say what
happened, and here they say nothing was broken by work that touched a dozen
modules.

The duration is deliberately not compared. This run took fifteen and a half
minutes where the previous took twenty-eight, and the machine has been carrying
other sessions throughout; a wall-clock measured against contention measures the
contention, which this campaign has recorded twice and will not record a third
time as an improvement.

### twenty-eight-of-the-thirty-five-registry-failures-were-attributed-and-two-more-now-are | high | Both new ones are other campaigns' work tripping this campaign's gates, which is the gates working

The lane criterion requires every failure to be named and attributed, so the
thirty-five the registry suite reports were grouped. Twenty-eight already have
entries here: twenty-six are the one parametrised reproducibility test over the
manifest-stale trees, and two are the publication refusals - a journal candidate
that is not a staging sibling, and a provenance file the fragment loader will not
accept without a TOML suffix.

Two more are now characterised, and both are the same kind of thing: another
campaign's new code meeting a gate this one built or extended.

The regulatory-prose parser channel refuses four undeclared parsers, among them
a modelo 200 reconciliation module and a borrador extractor for the modelo 100
summary. The channel exists so that every module parsing regulatory prose is
declared in one place; new parsers arrived without being enrolled, which is
precisely the condition it was written to catch, and the enrolment is the owning
campaigns' to make.

The static-inspection boundary refuses `RegistryRevisionInspection` reaching
into `application/modelo/work_addressing` and its test. That gate asserts the
inspection API cannot cross from static authority into runtime, and the crossing
is new.

Four remain uncharacterised and are named rather than glossed: two in the modelo
200 semantic casilla candidates, one in the modelo 303 generated envelope proof,
one in the generated-tree CLI. All four sit on surfaces belonging to the modelo
200 and 303 work, which has been committing throughout this session. Naming them
without reading them is the honest position - "attributed" means somebody knows
what a failure is, and for these four nobody here does yet.

### every-registry-failure-is-now-attributed-and-three-of-the-last-four-are-this-campaign-s-own-anti-patterns | high | Two frozen counts, one refusal pinned by its prose, one manifest-stale tree

The four failures named but unread last iteration are read. All four are in
other campaigns' modules and three are defects this campaign has spent the
session documenting elsewhere.

Two are frozen corpus counts drifting. The modelo 200 semantic casilla
candidates assert `map_owner_mismatches` at 185 where the corpus now yields 181,
`orphaned_declarations` at 2 where it yields 154, and a zero-padding disposition
count that has moved with them. These are the ratchet shape exactly: a number
typed into a test, compared against a live corpus, failing when the corpus moved
and telling nobody whether the movement was good.

One is a refusal pinned by its wording. The generated-tree CLI test asserts the
string "does not declare record-design source" and the CLI now says "no source
'...' exists for bootstrap target selection". The refusal still fires - the
command still exits 1 and still refuses the undeclared source - and only the
prose changed. This plan's own verification section records fixing that exact
defect in the emitted-byte acceptance suite, which now asserts the structured
refusal and names which channel is empty rather than the sentence a rephrasing
once broke.

The fourth is the manifest staleness already on record, reaching a second test:
the modelo 303 envelope proof reports `_generation.provenance.json` as the one
record whose meaning differs from the shipped tree. Same cause as the twenty-six,
different assertion.

So the criterion is satisfied for this directory: thirty-five failures, all
attributed. The distribution is worth noting as the session closes on this
thread - twenty-seven are one cause, and of the remaining eight, five are
patterns this campaign named while working on something else.

### the-lane-criterion-now-carries-causes-instead-of-a-range | medium | "Between fifteen and forty-two, dated and attributed" replaced by what the thirty-five actually are

The criterion holding the registry lane said the failure count had moved between
fifteen and forty-two and that every failure was dated and attributed. Dating a
failure establishes when it arrived, which was the right instrument when the
question was whether this plan had caused one. It is a weaker claim than
attribution and the two were being used interchangeably.

The criterion now says what the thirty-five are. Twenty-seven share one cause -
manifests a generator refactor left stale - and the remaining eight are four
undeclared prose parsers, one inspection boundary crossed, two frozen corpus
counts drifting, and one refusal pinned to wording the command no longer uses.

That reads longer and is shorter to act on. A range plus a promise of
attribution tells a reader the work was done somewhere; the causes tell them
there is one repair worth twenty-seven failures and seven smaller ones, three of
which are patterns with entries already in this record. A criterion that lists
causes also fails honestly: if a new failure appears it will not fit the list,
where a range absorbs it silently as long as the total stays under forty-two.

The distinction between dated and attributed is worth keeping from this. Dating
answers whether a failure is yours. Attribution answers whether anyone can act
on it, and a lane where every failure is dated but none is attributed is a lane
nobody is fixing.

### the-publication-limb-is-reachable-and-has-been-since-september-second | high | The constraint blocking the twenty-seven-failure repair was true when written and false the next day

The plan carries an ordering constraint saying the generator's publication
authority exists and nothing can reach it - "a worse state than absence because
it reads as capability" - and a Step proposing to give it an invocable entry
point. Both are false today.

`python -m dev.registry.pipeline publish` is a registered verb. It prepares a
candidate, runs the same read-only check the `check` verb runs, and calls
`publish_validated_generated_export_tree` with the validated result. The commit
that added it - "add the operator invocation surface for one generated export
tree" - landed on 2026-09-02, the day after the constraint was written and the
day this plan was authored.

That matters beyond the correction. Twenty-seven of the thirty-five failures in
this directory share one cause, manifests a generator refactor left stale, and
the repair is republication. The plan said republication was unreachable, so the
twenty-seven read as blocked on machinery nobody had built. They are blocked on
nothing but scope: the verb exists, and running it writes generated trees under
`src/`, which this execution may not do.

The Step now asks for the publication rather than for an entry point, and the
constraint records that it was written twice and wrong both times - first
because the verb was thought to need building, then because it was thought
unreachable after it had become reachable. A constraint asserting an absence
needs re-checking on the same schedule as a figure quoting a count, and this one
had been carried for a day past its truth while the failures it explained
accumulated.

### the-other-absence-claim-is-real-and-now-says-what-is-present | high | Nine official corpus directories, none of them a filled fichero

Having found one absence claim false a day after it was written, the plan's
other one was checked on the same reasoning. It holds.

The Step gating the whole proof-vector Phase asks for one official emitted-byte
reference for a single modelo revision. The official corpus contains nine
directories - record designs, forms, instructions, manuals, calendars, e-invoice
record schemas, historical retired modelos, GROI servlet response samples, and a
Renta WEB Open page. None is a filled fichero. The GROI samples are verbatim
fragments of a consultation servlet's responses, which is evidence about a
different exchange entirely, and the record designs describe the layout that
emitted bytes would have to satisfy rather than an instance of them.

So the chain this campaign has been recording as blocked - the official
reference, then vector enrolment, then the modelo 151 closure rewrite, then the
single-channel authority's deletion - is blocked on evidence that genuinely is
not in the repository, and no amount of engineering closes it.

The Step now lists what the corpus does hold. An absence stated alone invites
the next reader to search for what might already be there, which is the search
just performed; an absence stated beside the neighbouring evidence tells them
where not to look. That is the difference between the two absence claims checked
today: one was carried a day past its truth, and this one was true but silent
about its own neighbourhood.

### three-absence-claims-checked-two-stale-and-the-pattern-is-the-same-each-time | high | A blocker recorded once outlives the condition that made it true

Three claims in this plan assert that something cannot be done. All three were
re-checked against the tree today rather than carried.

The publication limb was said to exist unreachably. It became reachable on
2026-09-02 and the claim survived a day past its truth, blocking the repair
behind twenty-seven of this directory's thirty-five failures.

The release-eligibility criterion said the predicate lives in contributor
tooling "behind a held file". The predicate is still there - that half holds -
but the file carries no pending diff and neither does its destination in the
shipped application. What blocks the move is this execution's scope, not another
contributor's work in progress, and those want opposite responses: a held file
means wait and re-check, a scope limit means hand off. The criterion now says
which it is.

The official emitted-byte reference is genuinely absent, and the corpus around
it is now listed so the next reader knows where not to look.

Two of three were stale and both went stale the same way: a blocker true when
observed, recorded as a property, and then not observed again. A count that
drifts is visibly a count and invites re-measurement. A blocker reads as a fact
about the world, and nothing about the sentence suggests it has a shelf life -
which is why the two found stale here had each been carried through every
iteration of this campaign without anyone, including me, thinking to look.

### the-deferral-step-asks-for-a-rationale-and-there-is-nowhere-to-put-one | high | Seven reason fields exist in the schema and none of them is on a revision

The Step proposing to author "the missing deferral rationale" for three
layout-bearing revisions was checked before being left alone. Its population
holds exactly: modelos 189, 280 and 345 each have a 2025 revision carrying one
export layout at applicability grade, with no committed tree.

The rationale has nowhere to go. The revision model declares no field that could
hold one - no deferral, reason, rationale or exemption slot of any kind - so the
Step as written asks for data to be authored into a shape the schema does not
have. Its scope named the registry data directory alone, which reads as an
afternoon of writing three sentences and is actually a schema change first.

The registry does know how to state reasons, which is what makes this a design
question rather than an omission. Seven fields carry one: a casilla explains why
it is exempt from export, an applicability rule explains why it applies and why
it does not, a schema-family disposition and an XML path override each carry
theirs, and a completeness manifest explains a manual extraction. The nearest
analogue is the casilla's `export_exemption_reason` - a declaration explaining
why an expected capability is absent - and what is missing is its mirror at the
revision level: why a present layout does not imply the filing grade a reader
would infer from it.

The Step now asks for the slot before the sentences and names that analogue. A
Step that assumes a place to write is the same defect as a constraint that
assumes a limb is unreachable: both describe the tree as it was imagined rather
than as it is, and both are cheap to check and expensive to inherit.

### the-714-envelope-offsets-are-not-gaps-in-a-record-they-are-past-its-end | high | The footer declares one field over offsets 1 to 18 and no length at all

The Step naming modelo 714's envelope fields at offsets 93 to 96 and 101 to 109
holds, and holds differently than it reads. Those offsets are uncovered - but so
is everything from 19 onward, because the envelope-footer record declares a
single field, `modelo-714-envelope-close`, spanning offsets 1 to 18, and nothing
else. The ten page records of the same revision cover 90 to 111 completely, so
the two spans are absent only from the footer.

"No field covers them today" therefore describes a record that stops long before
them rather than a record with holes in it. Whoever authors those fields is
extending a declaration, not filling gaps, and the two are different jobs: a gap
has neighbours on both sides that fix its meaning, and an extension has to
establish where the record ends.

Which is the second half of what this check found. The footer declares no
length. A record without one cannot be measured for coverage at all - the gap
arithmetic that produced this finding had to bound itself artificially, and any
completeness gate over that record is measuring against nothing. The Step now
asks for the length alongside the fields, because authoring nine characters of
developer identity into a record whose extent is undeclared leaves the next
reader exactly where this one started.

### no-export-record-declares-a-length-and-my-previous-entry-asked-for-one | high | All 419 records omit it by design, because the official design is the authority on extent

The entry above observed that modelo 714's envelope footer declares no length
and asked the Step to add one so its coverage becomes measurable. Measuring the
corpus first would have prevented that: all 419 export records declare no
length, because neither the record model nor the layout model has such a field.
The footer is not deficient; it is shaped like every other record in the
registry.

The extent of a fixed-width record is fixed by the official record design, and
the shipped validator already enforces exactly that - an authored fixed-width
layout must cover its official design. So the question "where does this record
end" has an authority, it is simply not the registry declaration, and asking the
Step to declare a length would have created a second statement of a fact the
official design already fixes. That is the defect this campaign exists to
remove, requested in a correction written by this campaign.

The Step now names the official design as the authority for the record's end
rather than asking for a declared length. What survives from the previous entry
is the part that was measured rather than inferred: the footer's single field
spans offsets 1 to 18, the two spans the Step names lie well beyond it, and the
ten page records of the same revision cover 90 to 111 completely - so the work
is an extension of one record, not a repair of a gap.

The lesson is the one this campaign keeps paying for in a new currency: a
property observed on one instance is a property of that instance until it is
counted. One record without a length looked like an omission; 419 without one is
a schema.

### the-coverage-validator-accepts-modelo-714-while-its-own-design-declares-an-uncovered-required-position | high | Position 93 is "Versión del Programa" in the 2025 design the layout cites, and no authored field covers it

Chasing the modelo 714 envelope Step into the official design produced a
tension worth resolving rather than a conclusion.

Established by reading: the 2025 layout cites source `aeat-dr-714-2025`, which
resolves to `DR714_2025.xls` in the bundled corpus. That design declares, at
position 93 for 4 alphanumeric characters, "Versión del Programa", footnoted as
completed by the developing entity. The authored footer record covers offsets 1
to 18 and no authored field covers 93. The layout coverage validator reads that
same design, defaults every position to required, and admits omissibility only
where the design marks a position administration-reserved or fill - neither of
which applies to a developer-completed field. And the registry validates: the
authority loads, so the validator accepts this layout today.

Those four facts cannot all be right about the same position, and which one
gives way is not established from here. The validator may match authored records
to design records by identity and skip a design record with no authored
counterpart - which would be the exact hole its own docstring cites modelo 714's
two unauthored records as the motivation for closing. Or the position may belong
to a design record the page fields do cover, making the footer irrelevant to it.
Distinguishing those needs the validator's matching logic read properly, and
that module is outside this execution's scope to change though not to read.

A Step now carries the question. What is recorded here is the evidence and its
limit: the design says the position exists and is not omissible, the layout does
not cover it, the validator passes, and the reason has not been read. Stating
which of those is measured and which is inferred is the whole of what this entry
can honestly claim.

### the-714-step-asked-for-a-field-the-product-must-not-write | high | The coverage validator classifies it omissible for a reason the Step contradicts, and reading the validator settled it

The tension recorded last iteration is resolved, and it resolves against the
plan. The coverage validator carries an explicit rule for exactly this position:
`_eedd_delegated_reason`. A position whose note delegates it to the entidad
desarrolladora is omissible, and the reason is stated in the module rather than
implied - this product holds no EEDD registration, so writing one would invent a
regulatory identity, and writing blank would assert an empty EEDD rather than an
absent one.

Position 93 in the 2025 design is "Versión del Programa" carrying the footnote
"A cumplimentar por las entidades desarrolladoras (EEDD)". The validator's rule
requires two signals to agree - the field cites a note, and that note's printed
body delegates to the EEDD - and both hold. So the layout is correct to omit it
and the registry is correct to validate.

The Step asked for those offsets to be authored as "the mandatory developer
identity". They are mandatory for a developing entity to fill at emission and
must not be present in this registry's declaration. Authoring them would have
done the one thing the validator's docstring says must not happen, in a Step
whose scope named only the registry data directory, and the four facts that
looked contradictory were three facts and one wrong premise.

Reading the module settled in one pass what three iterations of measuring around
it could not. The constraint that this execution may not WRITE outside `dev/`
and `.vault/` says nothing about reading, and the reasoning that resolves a
registry question is frequently in the module that implements it rather than in
any record about it. The evidence was one grep away throughout.

### one-step-s-symptom-is-another-step-s-cause-and-the-plan-does-not-connect-them | high | 31 record-spelled envelopes against 20 typed ones, and modelo 714 is in the first group

The envelope is declared two ways in this corpus. Twenty revisions use the typed
`filing_envelope` slot, which carries record identity, prefix extent, total and
closer derivations, a schema version, a source reference with its digest - and a
`product_identity_requirement`. Thirty-one revisions across sixteen modelos
spell the same thing as an ordinary record, where those facts have no slots and
survive only as offsets.

Modelo 714 is in the second group, which explains the Step that has occupied the
last three iterations. Its developer-identity positions appear as uncovered
offsets in a record because its envelope is spelled as a record; had it used the
typed slot, the same fact would be a `product_identity_requirement` - a
declaration the export boundary can read, rather than four bytes at position 93
that this product must not write and cannot express its reason for omitting.

So the migration Step is not tidying. It is the remedy for a class of question
the plan has been answering one modelo at a time: a record-spelled envelope
cannot say what it requires, so every question about it becomes an argument
about offsets against an official design, which is where three iterations went.

Both Steps now carry the connection - the migration names the twenty revisions
already using the typed slot as the pattern and the product-identity requirement
as the thing the record spelling cannot express. Neither Step was wrong. They
were unconnected, and the smaller one could not be resolved on its own terms
because its subject was a consequence of the larger one.

### the-description-now-carries-an-example-that-can-be-counted-today | medium | Twenty typed envelopes against thirty-one record-spelled ones, with the cost of the difference measured in this campaign's own iterations

The plan's opening argument rested on five figures that turned out to be
attributed to a record not containing them, of which four could not be
reproduced and one reproduced while omitting the defect it described. The
argument was never wrong; its evidence was unusable.

It now carries an example that anyone can count. Twenty revisions declare their
filing envelope in the typed slot; thirty-one across sixteen modelos spell the
same envelope as an ordinary record. Both numbers come from the capability
census in one query, both move visibly as the registry changes, and the
difference between the two forms is not stylistic: the typed slot has a field
for a product-identity requirement and the record spelling has nowhere to put
one.

The cost is stated in the currency this campaign actually spent. Three
iterations went into whether four bytes at position 93 of modelo 714's envelope
should be authored - a question that only exists because that envelope is
record-spelled, and whose answer is a single field in the form it does not use.
An argument about declaration duplication is more convincing measured in the
hours it took to answer one question twice than in a count of sites nobody can
re-derive.

That is the closing state of the description's evidence: the original five
figures remain, marked as history and as unreproducible, and beside them sits
one example that is current, countable, and carries its own cost.

### the-typed-envelope-s-advantage-is-declared-eighteen-times-not-merely-available | high | A field that exists and nobody uses would have made the whole argument theoretical

The description now argues that the typed envelope slot can state a
product-identity requirement where the record spelling cannot. That argument
would have been worthless if the field existed and sat empty, which is the
shape of half the defects this campaign has recorded - a declaration available,
unused, and quoted as though it were a capability.

It is used. Eighteen typed envelopes declare
`aeat-product-software-identity-v1` as their product-identity requirement,
across modelos 151, 200, 202 and others. So the fact modelo 714 spent three
iterations failing to express is a fact eighteen of its peers state in one
field, and the difference between the two forms is a difference in what can be
said rather than in how tidily it is said.

Checking this before leaving the claim in the plan is the discipline the rest of
this session has been about, applied to my own new sentence rather than to
somebody else's old one. The claim was written from reading the schema, which
establishes that a field exists; the count establishes that the field carries
something. Those are different claims and only the second supports the argument
the description makes.

### one-revision-field-of-thirty-five-has-never-been-populated | high | The governance stamp's other three members are used by 122 of 128 revisions

Sweeping the revision schema for declared fields nothing uses - the shape behind
half this campaign's findings, a slot available and quoted as capability -
returns one of thirty-five. The schema is otherwise fully in use, which is worth
recording as a negative result of some size: 128 revisions populate 34 fields
between them.

The exception is `engineered_by`, one of a four-member governance stamp. Its
siblings are used: `reviewed_by` and `reviewed_at` are set on 122 of 128
revisions, and `review_status` reads `agent_reviewed` on the same 122 and
`pending_review` on the remaining six, which is the fail-closed default the
schema documents. So the stamp is adopted, thoroughly, and one of its four
fields has never carried a value.

That leaves a decision rather than a defect, and the decision needs somebody who
knows what the field was for. It may duplicate `reviewed_by` - who engineered a
revision and who reviewed it are the same person in an agent-authored registry -
in which case it is a second spelling of one fact and belongs deleted under this
plan's own thesis. Or it may record something the reviewer is not, in which case
122 revisions are missing it and the omission is the finding.

A Step carries the question with the counts attached. What this measurement can
settle is that the field is unused and its neighbours are not; what it cannot
settle is which of those two readings is right, and guessing between them is how
an unused field acquires 122 hastily-authored values.

### the-unused-alias-field-is-unused-on-all-29678-casillas-and-the-export-field-is-fully-used | high | A retirement Step's premise verified independently, and a second sweep that found nothing

Extending the unused-field sweep from revisions to the types beneath them. The
casilla declares twenty-three fields across 29,678 instances and one of them,
`aliases`, carries a value on none. The export field declares its fields across
25,031 instances and every one is used somewhere.

The alias result confirms a Step this plan already carries, independently and
from the other direction. That Step asks to retire "the restated casilla number
field and the unused alias field", and "unused" was an assertion nobody had
counted; it is now 0 of 29,678, and the Step carries the figure. A retirement
argued from a count is harder to defer than one argued from an adjective.

The export-field result is the more interesting half and it found nothing. Every
declared field on the type that carries the most instances in this registry is
populated somewhere, which says the export surface has been authored rather than
inherited - a schema accumulates unused fields when it is designed ahead of its
data, and this one has not. Recording a clean sweep matters because the next
person asking this question should not have to repeat it, and because two of the
three types swept came back with one unused field each while the largest came
back with none.

Three sweeps, two findings, both already known to the plan in prose and neither
previously counted. That is the pattern this session has settled into: the plan's
instincts have been sound and its evidence thin, and the work is mostly turning
the second into the first's equal.

### the-restated-casilla-number-is-a-restatement-on-24524-casillas-and-load-bearing-on-5154 | high | Retiring it as the Step asked would have deleted a fact for one casilla in six

The retirement Step pairs two fields: the unused alias, now measured at 0 of
29,678, and "the restated casilla number field". The second half does not
survive measurement as stated.

The `number` field is derivable from the identifier on 24,524 casillas - the
identifier contains it, so the field restates what the id already says, which is
exactly the defect the Step names. On 5,154 it is not derivable, and the reason
is visible in any of them: a casilla identified semantically, like
`act.actividad-descripcion`, carries number 400, and nothing in the identifier
encodes 400. For one casilla in six the field is the only place the form's
printed number appears.

So the Step would have been lossy. Retiring `number` deletes a fact for 5,154
casillas while removing a duplication for 24,524, and the two populations are
not separable by anything the Step mentions. It now asks to retire the alias and
DECIDE the number, with both figures attached, because the remedies differ:
derive it where the identifier carries it and require it where the identifier
does not, or keep it everywhere and gate agreement on the derivable majority.

A second observation for whoever takes that decision: the casilla declares
`form_number` as well as `number`. Two number fields on one declaration is the
shape this campaign exists to remove, and no Step mentions the pair. Whether
they are the same fact under two names or two facts sharing a word is not
settled here, and the 5,154 make it likely that at least one of them is
carrying the printed form number that the identifier cannot.

### the-two-casilla-number-fields-are-two-facts-and-the-defect-is-the-name | high | Both set on 138 casillas, 134 of them different, because one holds a range and the other a printed box

The pair raised last iteration is resolved, and against the guess that raised
it. `number` and `form_number` are both set on 138 of 29,678 casillas. On 134 of
those they differ, and the examples say why in one line: `conyuge.deduccion`
carries `number=238-254` and `form_number=574`. One is a RANGE of positions, the
other the single box number printed on the form. The four that agree are
coincidence - a one-position range reading as its own number.

Everywhere else, 29,540 casillas carry `number` alone and none carries
`form_number` alone. So this is not one fact under two names, which is what a
count of two number-like fields suggests before anyone looks. It is two facts,
one of which is needed by a sixth of the corpus and 138 of which need both at
once.

The defect is therefore the naming, not the duplication. A field called `number`
that sometimes holds `238-254` is telling a reader it holds a number, and the
plan's own retirement Step read it that way - "the restated casilla number
field" - which is how a measurement of derivability from the identifier came to
be the wrong question for a sixth of the corpus.

That closes this thread with the opposite of what it opened with. The sweep for
unused declarations found one genuinely dead field, one field the plan wanted to
retire that carries a fact for 5,154 casillas, and a pair that looked like a
duplication and is a naming problem. Three results, one retirement, and two
Steps that would have removed information had their premises not been counted.

### the-casilla-number-field-holds-three-different-kinds-of-value | high | 25,615 box numbers, 2,002 position ranges, and 2,061 slugs that are not numbers

Quantifying the naming defect found more than a naming defect. The casilla
`number` field carries three shapes across 29,678 declarations: 25,615 plain
digit strings, which are box numbers; 2,002 ranges like `238-254`, which are
spans of positions; and 2,061 values that are neither, the first of them
`act-sin-local-codigo-provincia` - a kebab-case slug in a field called
`number`.

One field, three kinds of thing, and the type system permits it because the
field is a string. A consumer reading `number` cannot know whether it will get
something it can compare numerically, a span it must parse, or an identifier
that will fail every numeric operation applied to it. Nothing declares which to
expect, so every consumer either handles all three or breaks on the ones it did
not anticipate.

This is the same defect the plan's opening argument describes - one name
carrying facts that should be distinguished - measured on the field the plan
proposed to retire as a mere restatement. A Step now carries the split with its
counts, in the migration Phase rather than the decisions Phase, because what to
do is clear once the shapes are named: a box number, a position range and an
identifier are three declarations, and the 5,154 casillas whose number the
identifier cannot derive are exactly the ones this distinction matters for.

The measurement took one query. The plan had carried "the restated casilla
number field" through every iteration of this campaign, and one query would have
shown at any point that a sixth of its values are not restatements and a
fourteenth are not numbers.

### five-fields-looked-heterogeneous-and-one-is | high | A segment identifier of the form 714-02 matched a range pattern, which is the eighth instrument error of this campaign

Sweeping every string field on the casilla for more than one value shape
returned five: `number`, `id`, `segmento`, `binding` and `semantic_role`. Only
one of the five is the finding it appeared to be.

`number` stands. It carries digits, ranges, kebab slugs, dotted identifiers and
prose across 29,678 declarations, and the previous entry records the split.

`id` is already owned. The casilla identifier grammar screen exists precisely to
report which grammars the corpus uses and which modelos mix them, so the four
shapes my classifier saw are a condition with a screen, a test and a place in
the runner.

`segmento` is an artefact of my own pattern. Its 530 apparent ranges are values
like `714-02`, which is modelo 714's page-02 segment identifier and matches
`digits-digits` for the same reason a date matches it. Reading three values
settled what the regex could not, and the finding was withdrawn before it was
written down as one.

`binding` and `semantic_role` are unexamined. Each shows a small "prose" tail
against a large regular population - 45 against 720, and 415 against 23,633 -
and "prose" in my classifier means only "none of the four patterns matched",
which is where the segmento error came from. Whether those tails are a defect or
a legitimate second form is not established, and stating that is better than
counting them as findings on the strength of a bucket named after what it is
not.

Eight instrument errors now, and this is the first caught by inspecting the
VALUES rather than by a contradiction in the numbers. A shape classifier is a
heuristic over syntax, and a corpus that names its segments after its modelo and
page will defeat any pattern chosen without reading it.

### the-two-tails-are-one-artefact-and-one-accented-identifier | high | 415 became 6, and the six are a single role name that kept an accent its own transliteration dropped

Both unexamined tails from the shape sweep are examined, and between them they
show the two ways a heuristic goes wrong in one pass.

The `binding` tail is my pattern being too narrow. Its values look like
`modelo-232-2018.page_01.144-158.vinculada-1-nif` - a structured path mixing
dots, underscores, dashes and a position range - and no single character class
I chose would have admitted it. Forty-five values, no defect.

The `semantic_role` tail is real but a seventieth of its apparent size. My
classifier reported 415; counting non-ASCII characters directly reports six
occurrences of one distinct value, out of 24,048 semantic roles. The value is
`irpf_re_atrib_act_eco_provisiones_dif´cil`, and what makes it a defect is
internal rather than stylistic: the rest of the identifier is transliterated
Spanish - `atrib`, `act`, `eco`, `provisiones` - so the accent survived in one
word of a name whose own convention is to drop them. A key that is
inconsistently transliterated cannot be typed reliably by anyone reading it
aloud or from a form.

A Step carries the transliteration, scoped to modelo 100 where all six sit.

The arithmetic is the lesson. One sweep produced five candidates; on inspection
one was already owned by a screen, two were artefacts of the patterns I chose,
one was real at full size, and one was real at a seventieth of the size
reported. The pattern that produced 415 and the count that produced 6 differ
only in that the second asked the question directly - `str.isascii()` rather
than a bucket named for what did not match.

### exactly-one-accented-identifier-in-the-corpus-and-the-rest-of-the-non-ascii-is-correct-prose | high | Two fields carry non-ASCII; one is a reason written in Spanish and the other is the defect already found

The direct question - which casilla string values carry a non-ASCII character -
was asked of every field rather than only the one where the accent turned up.
Two fields answer.

`semantic_role_cardinality_reason` carries thirty-one such values across sixteen
distinct ones, and they are correct. It is a prose field explaining why a
semantic role's cardinality reads as it does, written in Spanish, and a reason
about `declaración` that spelled it `declaracion` would be worse rather than
more consistent. Accents belong in prose about a Spanish tax form.

`semantic_role` carries the six occurrences of one value already recorded. So
the finding is bounded: across 29,678 casillas and every string field they
declare, exactly one identifier retains an accent, and every other non-ASCII
character in the casilla surface is prose doing its job.

The boundary is what makes this worth recording rather than the count. A sweep
for non-ASCII that did not separate keys from prose would have reported
thirty-seven findings and been wrong about thirty-one of them, which is the same
arithmetic as the 415 that became 6 - and the separation is not something a
pattern can do, because both populations are Spanish text and only their role in
the declaration distinguishes them. `id` carries no non-ASCII at all, which is
the reassuring half: the identifiers this registry keys on are clean, and the
exception is a semantic role rather than a casilla identity.

### the-export-surface-sweeps-clean-on-every-question-asked-of-it | high | No non-ASCII in 25,031 fields, one encoding across 419 records, no layout mixing line endings, and six record-less layouts explained by their format

Four direct questions were asked of the surface that produces filing bytes, and
all four came back clean. Recording that matters more than recording a defect
would, because this is the surface where a defect reaches a taxpayer's return.

No non-ASCII anywhere. Across 25,031 export fields, no declared string carries a
character outside ASCII, so nothing in the declarations can emit a byte the
iso-8859-1 codec would have to guess at. The accents that will appear at emission
come from taxpayer data, which is what the encoding is for.

One encoding, declared 419 times. Every record says iso-8859-1 and no modelo
declares two, so there is no record whose bytes would be written under one
assumption and read under another.

No layout mixes line endings. Fifty-nine layouts terminate no record, twenty-nine
terminate every record with CRLF, and none does both - which is the defect worth
looking for, since a file whose records disagree about termination is malformed
in a way no single record is.

Six layouts declare no records, and all six are modelo 100's XML dictionary
layouts for 2020 through 2025. That format carries its content in the cited
dictionary rather than in fixed-width records, so record-lessness is what the
format means rather than an omission - the same distinction that made the
capability screen count XML-dictionary layouts separately.

Four questions, four clean answers, and each was cheap. The value is in having
asked: an export surface that has never been swept for these is
indistinguishable from one that has, and the difference only becomes visible when
a filing is wrong.

### the-three-clean-export-properties-are-gated-now | high | Twenty-nine gates pass; a clean sweep that nothing holds is a fact about one afternoon

The export surface swept clean on four questions last iteration. Three of them
are now gates, because a sweep result is a statement about the day it ran and a
gate is a statement about every day after.

No export declaration carries a character outside ASCII, over 25,031 fields. No
modelo declares two record encodings, over 419 records. And no layout mixes
terminated with unterminated records, over the 88 layouts that have records at
all - the six that do not are skipped rather than counted as agreeing, because
modelo 100's XML dictionary layouts have no termination to disagree about and
including them would let a future record-less layout satisfy a gate about
records.

Each carries the non-vacuity guard this campaign learned to require: a count of
what was read, asserted before the absence is asserted, so a walk that finds
nothing fails instead of passing. That guard has already caught one broken
pattern in this module and would have caught a second.

The fourth question is deliberately not gated. "Six layouts declare no records"
is not a property to preserve or forbid - it is a consequence of the XML
dictionary format, and a gate asserting the number would break the day a
seventh dictionary layout is authored, while a gate forbidding record-less
layouts would refuse the format outright. A measurement that explains itself
needs no gate; the three that could regress silently are the three that got one.

### the-three-export-gates-now-have-the-teeth-the-plan-requires-of-them | high | Thirty gates pass, and the proof calls the same helpers the gates do

The three export gates written last iteration were unproven, which this plan's
own verification section forbids: each declaration gate must demonstrate
detection of a representative defect from a constructed fixture. They were green
over a clean corpus, which is the state where a gate and a gate that cannot fire
look identical.

The judgements they make are now two named helpers, and the gates and the proof
both call them. That ordering matters and cost this campaign a correction
earlier: a proof that reimplements the walk it verifies proves the
reimplementation, and a branch dropped from the gate leaves the proof green.

The planted defects are constructed by copy from real declarations. A field's
identifier gains an accent and must be reported; the fixture field is asserted
clean first, so the planted defect is the only thing the report can be
responding to. A layout gains a record carrying the opposite line ending and
must be reported as mixing; the fixture layout is asserted to agree with itself
first, for the same reason. And a record-less layout is asserted to declare no
ending at all, which is the skip the line-ending gate depends on - without it a
future record-less layout would satisfy a gate about records.

Thirty tests pass in that module, exit 0. The encoding gate is proven by the
same layout fixture agreeing with itself; a modelo declaring two encodings
cannot be constructed by copy without building a second revision, and the
agreement assertion over 419 live records is the stronger evidence anyway.

### the-export-gates-are-in-the-criterion-that-governs-them | medium | A gate not named by any criterion is a gate nobody is accountable for

The three export-surface gates are recorded in the declaration-gate criterion
that governs them. Until now they existed in the suite and in this record, and
the criterion a reader consults to know what holds this plan's claims together
did not mention them.

That gap is small and worth closing precisely because these gates were written
from a clean sweep. A gate born from a defect explains itself - somebody
remembers the failure it prevents. A gate born from a clean measurement has no
such story: it exists so a property that is true stays true, and if no criterion
names it, the next person weighing whether it earns its runtime has only its own
docstring to go on.

What the criterion now says is the pair of facts a reader needs: the properties
gated, with the populations they were measured over, and the one skip the
line-ending gate depends on. The skip is the part worth writing down at this
level rather than only in the test, because it is the kind of exception that
looks like an oversight from outside - a gate about records that ignores six
layouts - and is in fact what keeps the gate honest about a format that has no
records to terminate.

### the-deadline-windows-sweep-clean-and-the-one-apparent-duplicate-was-my-key | high | 843 windows, no inverted span, no stray cutoff, and modelo 210's four windows per coordinate are four different results

Three direct questions of the surface that decides when a filing is due, across
843 declared windows.

None opens after it closes. None carries a payment cutoff outside its own span.
Both are the kind of defect that would be invisible until a deadline passed, and
both are absent.

The third question looked like it found something. Two coordinates - modelo
210's annual periods for 2025 and 2026 - each carry four deadline windows, which
keyed on year, period and period kind reads as a fourfold ambiguity about when
one filing is due. The window identifiers say otherwise in four words:
`arrendamiento-ingreso`, `cuota-cero`, `devolucion`, `renta-imputada`. Modelo
210's deadline depends on what the return produces - rental income with a
payment, a zero quota, a refund, imputed income - and the schema carries
`resultado_scope` and `tipo_renta_scope` for exactly that. Keyed with those, the
duplicates are zero.

Ninth instrument error of this campaign, and the second in three iterations
caught by reading the identifiers rather than the numbers. The pattern is now
consistent enough to state as a rule for this corpus: when a coordinate appears
to be declared twice, the declarations usually differ on an axis the key
omitted, and the axis is usually named in the identifier. Reading four ids cost
less than the sweep that produced them.

### the-keying-rule-is-in-the-readme-now-with-the-nine-errors-that-bought-it | high | Two rules kept that suite honest; the third is the one this campaign paid for

The contributor README carried two rules for keeping the screens honest: read
the resolved surface rather than the authored one, and gate invariants rather
than counts. Both were written from defects. A third now sits between them,
written from nine.

It says to key a measurement on every axis the declaration has, and gives the
reason a reader will actually meet: a coordinate that appears declared twice
usually differs on an axis the key omitted, and that axis is usually named in
the identifier. Modelo 210's four deadline windows for one annual period are the
worked example, with the four identifiers quoted, because reading them is what
settled the question and reading them is the behaviour the rule asks for.

The evidence is the nine errors themselves, three of them named: a key over
modelo and revision that reported two screens collapsing every row onto one
coordinate, a shape pattern that read `714-02` as a numeric range, and a bucket
named for what did not match that reported 415 findings where six were real. The
rule closes with the cheapest version of the advice - prefer a direct question
like `str.isascii()` to a pattern that infers one - because that single
substitution is the difference between the 415 and the 6.

Putting it in the README rather than only in this record is the point. This
audit is removable scaffolding and the README ships with the tooling it
describes; a lesson that cost nine measurements should be where the next person
writing a screen will meet it, not where somebody has to go looking.

### 156-declared-localization-keys-resolve-in-no-locale | high | Every one is a modelo 200 2024 casilla, and the gap is identical in Spanish, English, Catalan and Hungarian

Every casilla in the corpus declares localization keys - 29,678 of them, 35,768
keys in total - and the crossing question is whether those keys resolve in the
catalogues that ship beside them. All but 156 do.

The 156 are all modelo 200's 2024 revision, plain casilla identifiers like
`00067`, `00093` and `00814`, and the shortfall is identical in all four
locales: 3,329 keys declared for that revision, 156 unresolved in Spanish,
English, Catalan and Hungarian alike. A gap uniform across locales is not a
translation backlog, which would show as one locale trailing the others; it is
casillas declared before any label was written for them.

The attribution is visible in the worktree. Casilla `c00093.toml` under modelo
200's 2024 revision is one of the few files carrying a pending diff, and the
modelo 200 reconciliation work has been committing throughout this session. So
these are casillas under active construction whose labels have not caught up.

What makes it worth recording rather than leaving to that campaign is that
nothing notices. A declared key that resolves nowhere renders as a blank label
or a fallback, and no gate compares the registry's declared keys against the
catalogues that must answer them. A Step now carries both halves - author the
labels, or gate the crossing so the next 156 fail loudly - and the second is the
durable one, because a revision can always be declared faster than it is
translated.

### the-localization-crossing-is-complete-and-only-the-casilla-labels-are-short | high | 58 official names, 58 titles, 128 revision keys and 181 construct keys all resolve; 156 casilla labels do not

Five declaration families carry a localization key, and the crossing is now
measured for all five rather than the one where the gap turned up.

Everything but the casillas resolves. Fifty-eight modelo official-name keys,
fifty-eight title keys, one hundred and twenty-eight revision keys and one
hundred and eighty-one construct keys all answer in the shipped Spanish
catalogue. The casilla keys answer 35,612 times out of 35,768, and the 156 that
do not are the modelo 200 2024 labels already recorded.

The shape of that result is worth as much as the gap. The families whose keys
are authored one per declaration - a modelo's title, a revision's name, a
construct's label - are complete, and the only shortfall is in the family
authored 29,678 times. A crossing that must be maintained per casilla falls
behind; a crossing maintained per modelo does not. That is an argument about
where to put a gate rather than about whose backlog this is.

And the gate is deliberately not written yet. The README rule this campaign
added earlier says conditions still carrying findings are not gated, because
gating them needs a tolerance and a tolerance is the ratchet this project
retired. One hundred and fifty-six findings is exactly that condition. The Step
records the gate as due when the labels land, which is the same discipline
applied to every other screen here - and writing the gate now, against my own
rule, would have been the more satisfying and less defensible move.

### the-casilla-labels-are-restated-per-revision-11286-times-and-the-fix-is-derivation-not-translation | high | 38 per cent of the Spanish label corpus is the same text under a second revision, and the operator said so before the measurement did

The 156 unresolved labels were recorded as work to author. That framing was
wrong and the operator corrected it: cross-revision localization must be
DERIVED, and hand-translating three thousand casillas per revision is not work
anybody should do. Measuring what the catalogues actually hold proves the point
at a scale the original finding hid.

Modelo 200 declares two revisions. Their catalogues share 3,173 labelled
casillas, and the text is byte-identical on every one of them - 3,173 identical,
zero differing. Corpus-wide, the Spanish catalogues carry 29,522 casilla label
strings of which 11,286 are the same text repeated under a second revision.
Modelo 100 alone restates 4,733. Multiply by four shipped locales and roughly
forty-five thousand strings exist to say what eleven thousand already say.

Two of my own readings were wrong on the way here and both are worth recording.
I first proposed authoring the 156 by hand. I then found that all 156 casillas
carry no continuity chain and framed the gap as a continuity problem - but no
casilla in that revision carries a chain, the 3,173 resolved ones included, so
chaining does not distinguish the labelled from the unlabelled and the framing
had no support.

What the numbers do support is the operator's reading. A label is a property of
a casilla, not of a casilla-in-a-revision, and the catalogue keys it by
revision, so every new revision costs a full re-translation of text that has not
changed. The tooling to fix it is already there - `dev.locales` carries
`scaffold`, `move-revision` and `set-batch`, and a revision-drift module that
already recognises a rename as a MOVE rather than a translate. What is missing
is the derivation: one label per casilla per modelo, with a per-revision
override only where the official text genuinely differs, which for modelo 200 is
zero casillas out of 3,173.

## The restatement measurement, made durable and corrected

The ad-hoc query behind the previous section is now a module,
`dev/locales/revision_label_restatement.py`, and running it corrected two of its
figures. Recorded as a correction rather than an update, because the earlier
numbers were published in this audit and in the plan's Description.

The Spanish catalogue carries **27,569 casilla label strings, of which 10,586
are the surplus of a label restated under a further revision** - not the 29,522
and 11,286 stated earlier. The per-modelo top of the list is unchanged where it
matters (modelo 100 restates 4,733, modelo 200 restates 3,173, both figures
reproduced exactly), and the discrepancy is concentrated in modelo 390, reported
earlier as 1,057 and now as 280. The 280 is checkable and checks: modelo 390
carries 102 labelled casillas spread over up to five revisions, distributed
10 at five revisions, 72 at four, 4 at three and 16 at two, and the surplus of a
population like that is 10x4 + 72x3 + 4x2 + 16x1 = 280. The earlier figure was
measured on some other basis and cannot be reproduced; it should not be cited.

The corpus-wide figure is also lower than the extrapolation. Across all four
shipped locales the surplus is **28,129 strings**, not the ~45,000 that came
from applying the Spanish rate to every locale. The rate does not carry, because
the other three catalogues are less complete than the source:

| locale | label strings | restated surplus | divergent casillas | single-revision |
| ------ | ------------- | ---------------- | ------------------ | --------------- |
| es | 27,569 | 10,586 | 1,091 | 5,451 |
| ca | 19,953 | 6,022 | 1,620 | 5,594 |
| en | 19,917 | 5,832 | 1,800 | 5,512 |
| hu | 19,859 | 5,689 | 1,933 | 5,522 |

## Translations diverge where the official text does not

The table above carries a finding the duplication count does not. The Spanish
source diverges across revisions on **1,091** casillas; Hungarian diverges on
**1,933**, Catalan on 1,620, English on 1,800 - every translation diverges on
more casillas than the text being translated does. That is impossible as a
translation of divergent source text, so the excess is divergence the
translations introduced.

Measured directly rather than inferred from the difference: the casillas whose
Spanish text is byte-identical under two or more revisions while the
translation's text differs number **931 in Hungarian, 807 in English and 687 in
Catalan**. Each one is two different renderings of one official string, under
two revisions of one modelo, and a reader looking at one revision has no way to
tell which rendering is current or that another exists.

This reclassifies the derivation. Keying labels per revision was described here
as a cost - strings retyped that a generator could carry. It is also a
correctness defect: the per-revision key does not merely permit the duplication,
it permits the copies to disagree, and roughly 2,400 of them across the three
target locales already do. A per-modelo label with a per-revision override where
the official text genuinely differs removes the cost and makes the disagreement
unrepresentable in the same change.

The module reports and gates nothing, deliberately: a gate on a condition
carrying five figures of findings needs a tolerance, and a tolerance is the
ratchet this project retired. Its classification is proven on constructed input
holding one restated, one divergent and one single-revision casilla, with a
second constructed case whose revisions all differ - present because the first
case alone would pass an implementation that returned the restated count from
the revision count. The live assertions are orderings, not figures, so a landing
revision or translation cannot fail them without changing the property.

Every root, catalogue path and flattening step is borrowed from the tooling that
owns it - `_paths.LOCALES_DIR`, `manager.discover_locale_codes`,
`manager.locale_catalogue_source`, `manager._flatten_raw_locale_leaves`. The
first draft of this module lived under `dev/registry/analysis`, re-derived
`REPO_ROOT` from its own parent count, wrote a fourth catalogue flattener beside
the two the manager already has, and reached the catalogues with a glob for one
directory shape. That glob is the mistake `discover_locale_codes` documents in
its own docstring as the more dangerous of the two available: a hardcoded path
raises, while a glob for a shape the tree does not carry returns empty, and
empty reads exactly like a clean corpus. The module was moved into
`dev/locales`, where those helpers are same-package, before it measured
anything.

## The derivation is lossless, and it removes 30,049 of 87,298 strings

`dev/locales/casilla_label_derivation.py` builds the form the previous sections
argued for - a label keyed by casilla with a per-revision override only where
the text genuinely differs - and expands it back over the revisions each casilla
is labelled under. The expansion reproduces the shipped mapping byte-for-byte in
every locale:

| locale | stored | derived | removed | override casillas | lossless |
| ------ | ------ | ------- | ------- | ----------------- | -------- |
| es | 27,569 | 15,192 | 12,377 | 1,091 | yes |
| ca | 19,953 | 13,897 | 6,056 | 1,620 | yes |
| en | 19,917 | 14,025 | 5,892 | 1,800 | yes |
| hu | 19,859 | 14,135 | 5,724 | 1,933 | yes |

Across the four locales the derived form stores **57,249 strings where the
catalogues store 87,298**, removing **30,049**. That exceeds the 28,129
restatement surplus measured earlier, and the excess is not a contradiction: the
surplus counts only casillas whose revisions agree completely, while the
derivation also collapses a partially-divergent casilla onto one canonical text
plus the smaller set of revisions that differ from it. Spanish shows this most
clearly - 10,586 of its removals are pure restatement and a further 1,791 come
out of casillas that do diverge somewhere.

The residual is the override population, and it is the number that matters for
any future key-shape change: **1,091 Spanish casillas, and 1,620 / 1,800 / 1,933
in Catalan, English and Hungarian**, must stay expressible per revision. A
derived key shape that cannot carry them is not an improvement, and the earlier
finding says why the target figures exceed the source: roughly 2,400 of those
overrides are translations disagreeing where the official text does not, so a
key-shape change should not be read as ratifying them.

The collapse cannot land in this campaign. The key shape the runtime reads is
generated from the registry, which is outside this execution's scope, so what
lands is the evidence that the collapse is safe to make. That is deliberately
the more useful half to have first: a derivation that drops a string drops
taxpayer-facing text, and the loss surfaces as a missing translation rather than
as a generator bug.

Losslessness holds by construction, which is exactly why the round trip is not
left to assert itself. The reconstruction is shown failing on a derived form
with one override removed - the shape a generator bug produces - and the failure
is asserted to land on the casilla whose override was dropped rather than merely
somewhere, since an inequality caused by anything else would satisfy a weaker
test while proving nothing. The canonical choice is separately shown to be
independent of revision ordering, because a derivation whose output depends on
the order the catalogue was written in cannot be checked by re-running it, and
an evenly split casilla is where that dependence would hide. The constructed
cases travel the same `derived_from` path the corpus does rather than a
reimplementation of the choice.

One test in the first draft of that suite asserted `derived is None` against a
probe for an attribute that does not exist, which is a tautology dressed as a
precondition. It was removed rather than repaired, and the case it was meant to
cover - a fully restated casilla collapsing to one string with no override at
all - now asserts the override set is empty as well as the canonical text being
right. A derivation that picked the correct canonical text and then recorded it
as an override too would reproduce the corpus perfectly and save nothing.

## The fields whose wire fact sits behind a footnote, and what the notes say

`dev/registry/analysis/footnote_only_wire_facts.py` screens every revision that
can produce render inputs for workbook content cells holding nothing but a
footnote pointer. The eligibility predicate reads a non-blank content cell as
the design stating the field's wire fact, so such a cell admits a field to the
renderer on the strength of a cross-reference nobody followed.

The population is **41 cells across 5 modelos**: modelo 200 carries 32, modelo
303 carries 6, and modelos 202, 222 and 353 carry one each. Modelo 200's 32 is
an independent reproduction of the thirty-two footnoted corporate-tax amounts
measured separately when the monetary-scale screen landed, which is the first
time those two counts have been produced by different code.

Membership is decided by the shipped predicate rather than by restating its
clauses: each field is put through `project_render_profile_eligibility` twice,
once as it stands and once with its content cleared, and only a field rejected
now and admitted then is reported. A second copy of the numeric,
absent-naturaleza and reserved clauses would have been the copy that stopped
agreeing.

## The reading aid under-reads, and it nearly became a finding

The screen classifies a resolved note by whether its wording uses the
vocabulary of how a value is written. On the first run that returned **0 hits
against 39 resolved notes**, which reads as the design supplying no wording to
ground a reviewed rule in - and that reading would have undercut the premise of
the whole rules-authoring step.

It is wrong. Modelo 200's nota 1, cited by 31 of the 32 fields, states a filling
rule outright: "En caso de tipo de gravamen unico se rellenaran los dos primeros
digitos con el tipo, y los dos ultimos con 00. Ej: 25% se rellenara como 2500."
That is a complete representation rule. The vocabulary list - decimal, signo,
coma, alinead, ceros, derecha, izquierda - misses it because the note says
digitos and rellenaran instead. This is the same instrument error this campaign
has now made repeatedly: a fixed list recognises one wording of a concept and
reports its own blind spot as an absence.

The list is not this screen's. It belongs to the pointer-note module that landed
earlier to resolve a pointer to the note it names, where it is documented as a
reading aid; the defect is that a consumer can read its output as a verdict, and
this screen's first draft did exactly that. The conditions are now named for
what they measure - `pointer_resolves_vocabulary_hit` and
`pointer_resolves_vocabulary_miss` - and the docstring carries the
counterexample. A test pins nota 1's wording and asserts it contains none of the
words the aid looks for, so the miss-as-absence reading cannot be reintroduced
quietly.

The two notes reachable outside modelo 200 were read directly and the miss is
correct for both: modelo 303's nota 5 is a Lorca value enumeration and modelo
353's nota 4 says only "Solo para periodos 02 y siguientes." Neither states a
representation. So the honest position is that of 39 resolved notes, at least
one states a wire fact in full, two demonstrably do not, and the remaining 36
are unread - not that none of them ground a rule.

Two further observations came out of the notes themselves. Modelo 200's "nota 1"
is not one note: its transcribed text runs several unrelated table notes
together, covering accounting-statement codes, identifier types and the rate
filling rule in one blob, so a field citing it receives far more text than
governs it. And two pointers name notes their design never defines, which is a
transcription gap rather than a rule gap and is reported as its own condition.

## The step figures for the rules this makes due do not reproduce

The plan's rules-authoring step states one hundred and forty-nine newly eligible
fields across "the six modelos that carry a render profile", with thirty-four
more falling due when two further modelos gain one. None of the three figures
reproduces against the live tree.

Measured through the shipped predicate over the 31 revisions that can produce
render inputs: **6,434 fields are already eligible**, **41 would be newly
admitted by refusing a bare pointer as a stated fact**, and **4,184 would be
newly admitted if any content cell stopped counting** - which is the much larger
change the step is not asking for. `dev/registry/render_profiles` holds
seventeen modelo directories, not six.

The step is not therefore wrong; its figures are unreproducible, which is a
different defect and the one this campaign keeps finding. Recorded here rather
than corrected in the step, because 149 may have been measured against a
narrower population - width-17 fields, or one epoch - that is worth recovering
before the number is replaced. Until it is recovered, 41 is the count that a
reader can reproduce with one command.

## A note label is scoped to its sheet, and the reader made it global

The blob observed in the previous section is not a transcription defect. It is a
parsing defect, and it had a second consequence nobody could have seen.

A workbook record design prints one sheet per page and numbers each page's notes
from one, so `Nota 1` names a different note on every sheet. Modelo 200's 2025
design has seventy-seven sheets and defines `Nota 1` on **six** of them. The
reader keyed definitions by label alone, and on meeting the second definition it
did not overwrite or refuse - it appended. Every field in the design citing
`Nota 1` therefore received all six notes concatenated: accounting-statement
codes, identifier types, a rate filling rule and a domiciliation condition in
one 1,290-character entry.

Scoping definitions by sheet separates them cleanly - 459, 69, 305, 251, 97 and
109 characters - and locates the rate filling rule, the one piece of genuine
wire wording found in this whole population, on sheet **DP200014** alone. Every
other sheet's `Nota 1` says something else entirely. The test written last
iteration to pin that counterexample named the wrong sheet on its first draft,
which the design-wide reader had made impossible to notice: every sheet returned
the same merged text, so any sheet name looked right.

The second consequence is the one that matters for filing evidence. One field -
modelo 200, `DP200020B!A38`, offset 472, length 17 - cites `Nota 1` on a sheet
that **defines no `Nota 1`**. Under the design-wide reader it resolved happily,
against a note printed on another page, and was reported as a resolved note
whose wording merely lacked wire vocabulary. It is now reported as
`pointer_unresolved`, which is what it is. Resolving to another page's text is
strictly worse than not resolving: an unresolved pointer is reported and chased,
while a wrongly resolved one reads as evidence and would have been carried into
a reviewed representation rule.

The screen's census moved accordingly, from 39 vocabulary misses and 2
unresolved to 38 and 3. The population of 41 fields across 5 modelos is
unchanged, because eligibility never depended on the notes.

`note_definitions` now requires its sheet rather than defaulting. A default
would have to choose between the design-wide reading just removed and one
arbitrary sheet, and both are wrong silently, which is the property that let
this survive. The sheet key is not inferred: the transcription's headings were
checked against the parser's own `field.sheet` values first, and all seventy-six
sheets carrying fields match exactly.

Two tests hold the correction. One asserts that a label defined on several
sheets yields several DISTINCT texts - distinct wording rather than distinct
keys, because a parser that scoped the keys while still accumulating one text
would satisfy a key-count assertion - and that the rate rule belongs to exactly
one sheet. The other asserts that `DP200020B` defines no `Nota 1` while other
sheets do, which is the shape that used to resolve wrongly. Both run against the
shipped design rather than a fixture: the merge only appears where a label
repeats, and constructing that would prove the parser handles a case the corpus
is the reason to care about.

## The blast radius of the design-wide note reading

The sheet-scoping correction was found through one modelo. Screening the whole
corpus with `dev/registry/analysis/note_label_scope.py` shows how much of it the
design-wide reading covered.

Of **215 bundled design transcriptions, 38 repeat a note label across sheets**,
and those repetitions account for **225 definitions past the first** - notes a
design-wide reader absorbed into another note's entry. The count is the surplus
rather than the number of definitions involved, because the surplus is what was
lost: three sheets sharing one label merged two notes, not three.

Modelo 200 was not the worst case and was not even close to it. Modelo 303
carries the condition in **every one of its revisions**, its 2024 design
defining seven repeated labels across seven sheets - `nota 1` on six of them,
`nota 2` on five, `nota 3` on four - for sixteen merged definitions in one
design. Modelo 220's 2025 design defines `nota 2` on twelve of its thirteen
sheets. Any pointer into either design returned a concatenation before this
week.

A repeated label is not a corpus defect. It is AEAT's own page numbering, and
each page numbering its notes from one is ordinary. The defect was reading the
label without its sheet, which is why the correction landed at the reader and
why this screen reports rather than gates: there is nothing here to demand
anyone fix.

The census also records that **136 of the 215 transcriptions define no note at
all**. That is deliberately a census figure and not a row per design. Most of
those designs genuinely have no notes, and 136 rows carrying no work would bury
the 87 that do - but a design whose notes failed to transcribe is
indistinguishable from one that has none, so the count stays visible for a
pointer to chase later.

The screen's detector is proven on constructed designs rather than on the
corpus: one where a label repeats across two sheets, one where the labels are
unique and nothing may be reported, one carrying no notes, and one where three
sheets share a label so the surplus is two rather than three. The corpus
assertion then holds by shape - every row names more than one sheet and its
surplus equals the sheet count less one - and not by figure, since those move
whenever a design is added or re-transcribed.

## Two reader defects, one of them introduced by the sheet-scoping correction

Measuring how many pointers still fail to resolve turned up two parser defects.
The first is mine, from the correction recorded above.

**Multi-word sheet names went unrecognised.** The heading pattern captured a
single non-space token, which holds for `DP200001` and fails for every sheet
whose name carries a space. Modelo 202 names its sheets `dr M202 (0)`, `(1)`,
`(2)`, so none of its headings matched, every note in the design landed under an
empty sheet name, and no field could ever match it. The failure is invisible from
outside the parser: a design whose headings are unrecognised looks exactly like a
design whose notes are undefined, which is why the first measurement of this
reported modelo 202 as simply lacking the notes it cites. The pattern now takes
the heading to end of line.

**The corpus separates a note label from its wording in three ways, and the
reader accepted one.** Modelo 200 writes `Nota 1:`; modelo 202 writes `Nota 4.`
for most of its notes and `Nota 1 |` for one. Requiring the colon made every note
of modelo 202 invisible - including the three that state, in plain language, how
each AEAT type is written to the wire. The pattern now accepts a colon, a full
stop or a table pipe.

The two fixes together change what the corpus is understood to contain:

| measure | before | after |
| ------- | ------ | ----- |
| designs repeating a note label across sheets | 38 | 75 |
| definitions a design-wide read would merge | 225 | 357 |
| transcriptions defining no note at all | 136 | 114 |
| pointer cells citing a note their sheet omits | 9 | 7 |

Twenty-two designs whose notes were wholly invisible are now read. The earlier
figures in this audit for the design-wide merge should be read as measurements of
a reader that could not see two thirds of the corpus's note formats.

## The wire conventions exist, and no field points at them

The reason no pointer in this corpus resolves to representation wording is not
that the designs are silent. It is that they state the convention once, by type,
and never repeat it per field.

Modelo 202's design defines three notes that settle the wire representation
outright: `nota 3` for alphanumeric fields ("Deberan estar alineados a la
izquierda, rellenando con blancos por la derecha"), `nota 4` for numeric fields
("alineados a la derecha rellenando con ceros por la izquierda"), and `nota 5`
for signed numeric fields. Alignment, padding character and sign handling, in
full, for every field of the design.

**No field cites any of them.** The only notes cited by a field in that design
are `nota 12` and `nota 7`, and neither is defined anywhere in it.

This reframes the rules-authoring step. It has been treated as a per-field
research task - read the pointer, follow it to a note, ground a rule in what the
note says - and on that route the grounding is empty, which is what the
vocabulary census kept reporting. The grounding is instead design-level and
type-keyed: a reviewed representation rule for a numeric field of modelo 202 has
authoritative wording available to it, in the design's own general notes, reached
by the field's AEAT type rather than by anything the field's own cell points to.

Whether every design states its conventions this way is not yet measured, and
that measurement is the next thing worth having: it decides whether the rules for
the newly eligible fields are authored one by one or derived from a handful of
per-type conventions. On the evidence of this one design the second is likely,
which would make the authoring task an order smaller than the field count
suggests.

## The conventions are stated once per type, across most of the corpus

The question left open by the previous section - whether modelo 202's per-type
notes are a quirk or the corpus's habit - is answered.
`dev/registry/analysis/type_convention_notes.py` reports design notes that name
an AEAT type code the design's own fields carry. **Seventeen of the thirty-one
designs that produce render inputs carry such a note**, fifty-eight notes across
eight modelos: 303 with thirty-five, 390 with nine, 202, 222 and 322 with three
each, 232 and 353 with two, 151 with one.

Those fifty-eight notes resolve to **forty-nine distinct design-and-type pairs**,
and the fields they govern number **5,232**.

The type set is read from the parsed fields rather than from a list kept in the
screen. A list would be a second declaration of the type vocabulary and would be
the copy that stopped matching the day a design introduced a code nobody had
seen. Parentheses are required, because an AEAT type code is a short token - `N`,
`An`, `Num` - and matching one bare fires on ordinary Spanish; the anchoring also
keeps `(Num)` from satisfying a search for `(N)`, which matters because sign is
precisely what those two conventions differ on.

The screen deliberately does not classify whether a matched note states a
convention. It finds the notes worth reading and says which types they name. A
keyword classifier has already reported the plainest wire wording in this corpus
as absent, and the remedy for that is not a longer keyword list.

### What this does to the rules-authoring step

The step has been sized by counting fields. On the pointer route the grounding
for those fields is empty, and that emptiness was very nearly written down as
the designs being silent about representation. They are not silent: they state
it once per type, and a field does not cite what governs its whole class.

Forty-nine conventions stand behind 5,232 fields. Reading forty-nine notes is a
different task from researching several thousand fields one at a time, and it is
the task the corpus actually supports. Whether every newly eligible field falls
under one of those forty-nine is not yet established and is the next thing to
measure; fourteen of the thirty-one designs state no per-type convention at all,
so some fields will still need their own grounding.

### A count corrected before it was published

The screen first reported coverage as 20,711, summing each note's governed-field
count across notes. Modelo 303 alone carries thirty-five such notes, so every
numeric field in that design was counted once per note naming its type. The
figure is now computed over distinct design-and-type pairs and is **5,232**, four
times smaller. The per-note count is kept on the finding, but decomposed per
type, so a consumer can count a type once per design rather than once per
mention - which is the only reason the corrected figure is computable at all.

## The residual authoring task is two conventions, not thirty-two fields

`dev/registry/analysis/rule_grounding_coverage.py` joins the two halves: the
fields whose content cell states no wire fact, and the design notes that state a
convention for a whole AEAT type. The join is by type, because that is how the
designs key these conventions - a field does not cite the note governing its
class; the note names the class and the field belongs to it.

Of the **41 fields needing a reviewed rule, 9 are grounded by a type convention
and 32 are not**. Every grounded field belongs to modelo 202, 222, 303 or 353.
Every ungrounded field belongs to **modelo 200**, and they resolve to just **two
modelo-and-type pairs**: thirty fields of type `Num` and two of type `N`.

That is the number the rules-authoring step should have been sized by. The
residual is not thirty-two field-by-field research tasks; it is two conventions
to establish for one modelo. The step's own figure of one hundred and forty-nine
does not reproduce, as recorded earlier, and neither does any reading of this
work as thousands of fields.

One caution against reading the grounded side as free: the nine grounded fields
name **twenty-one distinct notes** between them, because modelo 303 carries
thirty-five type-naming notes and several name `Num`. More notes than fields is
not a saving on the reading, and the honest claim is about the ungrounded side -
that it collapses to two conventions - rather than about the grounded side being
cheap.

## Modelo 200 does state its convention, in a shape the reader cannot see

The two ungrounded pairs are not a silence in the design. Modelo 200's 2025
design carries the line

    NOTA: Los importes son de 15 enteros (o N + 14) y 2 decimales

which settles integer width, sign carriage and decimal places for its amounts -
precisely the wire fact its thirty `Num` fields need. The reader cannot see it,
because the definition pattern requires a digit after `Nota` and this note has
none.

That is the third note shape this corpus uses that the reader was not built for,
after the separator and the multi-word sheet heading. Unnumbered notes are not
rare: **52 of the 215 transcriptions carry one, 103 lines in total**.

They differ from numbered notes in a way that matters for where the fix belongs.
An unnumbered note cannot be cited by a pointer - there is no label to point at -
so it is not evidence for pointer resolution. It is a design-level or
sheet-level statement, which is the same shape as the per-type conventions, and
that is where reading it belongs. Recorded rather than implemented here, because
the retrieval question - whether such a note governs its sheet, its design, or
only the table beneath it - has to be settled from the corpus before a reader
can key it to anything.

## Unnumbered notes are readable; their scope is not settled, and is not claimed

The step opened for this asked what an unnumbered `NOTA` governs - its sheet,
its design, or only the table beneath it - before reading one. The measurement
does not answer it, and the reader now says so rather than picking.

The evidence that looked decisive is not. Every design carrying these carries at
most one per sheet, which appeared to rule out the table-level reading. But
**forty-seven of the fifty-two designs carry exactly one note in total**, so
"at most one per sheet" is satisfied trivially and distinguishes nothing. Of the
five carrying several, two repeat identical text across sheets and three differ.
Modelo 200 is the case that matters and it cuts the other way: it prints its
amounts convention once, on the first of seventy-seven sheets, while the
thirty-two fields that convention would govern sit on other sheets. Keying that
note to the sheet it appears on would put it out of their reach.

So the mapping is returned by sheet because that is where the note was FOUND,
which is a fact. What it governs is a judgement this evidence does not support,
and the docstring states that rather than letting the return type imply an
answer.

### The reader claims only the plainest shape

Reading these turned up that the corpus marks a note at least seven ways:
`Nota N:`, `Nota N.`, `Nota N |`, `NOTA:`, `NOTA*`, `(*) NOTA.` inside a table
cell, and `(NOTA1)` as a bare pointer with no space. Three widenings of the
pattern were tried and each absorbed a neighbour somewhere: the first pulled a
`NOTA*` line and two table rows into modelo 200's amounts note, and the second
pulled `NOTA 2:` into modelo 220's, producing "El NIF es obligatorio NOTA 2: El
valor de esta casilla..." as if it were one statement.

The reader therefore gathers nothing after the note's own line. That
under-reads a note that wraps - four of the hundred and three lines found this
way have their text only in a continuation and are now dropped, leaving
ninety-nine - and it is the right trade. A clause missing from a note is
visible to whoever reads it; another note's words presented as this one's are
not, and read as authority.

The invariant is asserted over the whole corpus: **no unnumbered note text
contains another note marker**. Over a sample it would have passed while the
absorption sat in one design out of fifty-two.

Unnumbered notes are kept in their own mapping rather than merged with the
labelled definitions, for two reasons that both matter. A pointer names a
number, so an unnumbered note can never answer one, and offering it in the same
mapping would offer it as an answer to a question it cannot answer. And it has
no label to key it by, so it would need a placeholder - which would then repeat
on every sheet carrying one and be read by the label-scope screen as a single
label defined many times, manufacturing exactly the ambiguity that screen exists
to detect.

## The unnumbered note is design-level, and the corpus is unanimous about it

The scope question left open is now answered, by two measurements that agree.

**The direct refutation.** Modelo 200's unnumbered note states how *importes*
are written - fifteen integers, sign carriage, two decimals, which is a
seventeen-character amount field. The sheet it is printed on, `DP200001`,
carries 113 fields and **not one amount field of that width**. The 5,665 fields
the note describes sit on **74 other sheets**. A note cannot be a statement about
a sheet that contains nothing it describes, and reading the printing sheet as
the scope would put this note out of reach of every field it governs.

**The corpus-wide shape.** `dev/registry/analysis/unnumbered_note_scope.py`
reports the structure around every such note. Of **51 designs carrying one, 47
print exactly one note across a multi-sheet design and 4 repeat one identical
text across sheets. None carries differing text on different sheets.** Neither
observed shape supports reading the printing sheet as the scope: the first
cannot, by the argument above, and the second is one statement printed by a
repeating page template.

So the sheet is where these notes are *found*, and the design is what they
govern. The reader continues to return them keyed by sheet, because that is the
fact it observes, and this screen is what a consumer reads before keying a rule
to one.

### An earlier reading here was an artifact of a defect since fixed

A measurement taken before the reader stopped gathering continuation lines
reported three designs whose unnumbered notes differed across sheets, which
would have been direct evidence for sheet scope. It was wrong. The differences
were absorbed neighbours: modelo 220's four "distinct" texts were one note, "El
NIF es obligatorio", plus varying amounts of a following `NOTA 2:` swept into
it. With the reader claiming only a note's own line, that design's sheets all
carry the same text and the differing condition has no instance in the corpus at
all.

The condition is kept and is proven on a constructed design rather than deleted.
It is the one shape where a sheet would genuinely distinguish, and a screen whose
third condition had quietly become unreachable is a screen that would stop
reporting a real change without anyone noticing. The corpus assertion is paired
with a check that both observed conditions do occur, so it cannot pass
vacuously if the reader ever stops reading.

## Every field needing a reviewed rule now has official wording to read

With the scope of an unnumbered note settled, the grounding join admits them.
The result closes the question this thread opened with:

| grounding | fields |
| --------- | ------ |
| a convention naming the field's own AEAT type | 9 |
| a design-level note, which has to be read | 32 |
| nothing | 0 |

The thirty-two that were ungrounded are modelo 200's, and the wording available
to them is the note stating that its amounts carry fifteen integers, a sign
position and two decimals - which is exactly the integer width, sign carriage
and decimal placement a representation rule for those fields has to state.

The two grounded conditions are kept apart rather than summed, and the weaker
one is named for what it is. A type convention names the field's class, so a
field of that type is certainly covered. A design note names nothing: modelo
200's settles its amounts, and another design's says only that the NIF is
mandatory, and the row cannot tell them apart. Collapsing the two would report a
field as grounded on wording that may say nothing about it, which is the same
error as reading a vocabulary miss as a note stating no wire fact - made twice
now, in the same corpus, from the same impulse to turn a located piece of
evidence into a verdict about it.

Where a field has both, the type convention is reported. A design note is
available to every field of its design, so without that precedence the weaker
condition would swallow every field that also had a convention naming its type,
and the census would understate the grounding actually present.

### The empty condition kept its proof

`ungrounded` now has no instance in the corpus. It is kept, because a design
carrying neither kind of wording is precisely the case an author must not
discover halfway through authoring, and a condition with no instance and no
proof stops reporting without anyone noticing. It is the second condition in
this work to be emptied by a correction and kept with a constructed proof rather
than deleted as unreachable.

The first draft of that proof reached into the screen and replaced the functions
it imports, so that its sources returned nothing. That is the globally
monkeypatched production module this project's gate rules refuse, and it also
tests a screen nobody runs. The classification is now a function taking the
fields, the per-type conventions and the design notes as explicit arguments, so
every condition - including the precedence between the two grounded ones - is
reached with input written in the test.

## The enrolment gate caught the screens this work added

Three of the modules built for the note-evidence thread define a
`screen_authority` and were never enrolled in the runner. The standing gate
failed on exactly that, naming all three, which is the first time in this
campaign a gate written earlier has caught the author's own omission before any
reader saw it. The README-table gate then failed in turn once enrolment was
fixed, and the two together left no way to enrol a screen and forget to
document it.

The runner now carries thirteen screens and completes in twenty-three seconds.

### A row that would have read as a second opinion

Enrolled naively, the grounding screen reported forty-one - the same number as
the pointer screen beside it, because its population is by construction the
fields that screen finds. Two adjacent rows carrying the same count read as one
measurement taken twice, and a reader has no way to tell that they agree by
definition rather than by evidence.

It is enrolled instead on its residue: the fields for which no official wording
was located at all, through a projection beside the other two the runner already
uses for this. That number is nought today, and it is the one worth watching,
because it rises the moment a design arrives carrying neither a type convention
nor a design note. The screen's full breakdown stays available to anyone running
it directly; what the runner shows is the part that can change without the
population changing.


## The enrolment gate had the campaign's own blind spot

The gate that caught three unenrolled screens last iteration was itself
incomplete, and passing was how it hid that. It discovered a screen by looking
for `def screen_authority(` in a module. Two of the screens built for this
thread read the design corpus rather than the loaded authority - a transcription
belongs to a design, not to a revision, so they take no authority and no modelo
set and present `screen_corpus` instead. The gate never saw them. It reported
its own blind spot as absence, which is precisely the instrument failure this
campaign has now recorded against a keyword vocabulary, a filename convention, a
`kind` attribute assumed universal, a static kind extractor, and a duplicate
coordinate key.

It is worth saying plainly that a gate is not exempt from the defect class it
was written to catch.

The gate now discovers either entry point, and both tables count as enrolment:
`SCREENS` for screens taking the authority, `CORPUS_SCREENS` for screens taking
the corpus. The second is a separate table rather than a widened first because
the signature genuinely differs, and forcing a corpus screen through the
authority entry would mean passing it arguments it ignores. The README gate
takes the union too, since a reader looking for a screen does not care which
table it sits in.

The enrolment assertion is two-sided, which is what makes it a proof rather than
an agreement: `defining == enrolled` fails if a module presents an entry point
and no table names it, and equally if a table names a module that has stopped
presenting one. The corpus screens being enrolled and the gate passing is
therefore evidence that the widened discovery really does find `screen_corpus`,
not merely that the two sides were written to match.

The corpus runner reports 128 designs where one note label is defined on more
than one sheet, and 51 carrying an unnumbered note.

Recorded also: the edit that widened this gate was written twice. The first
script asserted its way to the README replacement, failed on an escaping
mistake, and never reached its own write - so the enrolment widening it had
already computed was discarded while its sibling import change, applied by a
later script, made the file look edited. The gate then failed with its ORIGINAL
message text, which is what gave it away. A script that computes several edits
and writes once loses all of them when any assertion fails, and the half-applied
result is harder to see than an outright error.


## The same blind spot was in five gates, and it is now in one declaration

Widening the enrolment gate to notice a corpus screen was the visible half. The
other half is that the narrow test was not written once. Five separate gates
carried their own copy of "a screen is a module containing `def
screen_authority(`", each written when that was the only entry point, and every
one of them silently stopped covering a whole class of screen the day the second
appeared. Two enrolment-shaped gates read the module tree; three more iterated
the authority table alone, so the corpus screens' emitted kinds, condition
counts and finding identity were never checked at all.

The knowledge now lives in `SCREEN_ENTRY_POINTS` beside the tables, with
`screen_module_names()` for the gates that inspect modules and
`enrolled_screen_findings()` for those that inspect what screens emit. Adding a
third entry point widens all six together. Discovery and enrolment agree at
fifteen.

### Widening the finding-identity gate found a real contract breach

With the corpus screens in scope, the identity gate failed: neither
`NoteLabelScopeFinding` nor `UnnumberedNoteScopeFinding` declared the modelo the
contract promises every caller. That is exactly what the gate is for, and it had
been unable to see them.

The choice was to widen the contract or to satisfy it. Satisfying it is right
here: a design transcription lives in its modelo's corpus directory, so the
modelo is a fact about the file rather than something the screen would have to
invent. Both findings now carry it, read by walking up to the first `modelo_`
ancestor rather than at a fixed depth - two hundred and fourteen designs sit
under `modelo_NNN/files/` and one sits directly under `modelo_210/`, and a fixed
parent count would have returned `disenos_registro` for that one and reported it
as a modelo.

A transcription outside any modelo directory raises rather than receiving an
empty or invented modelo. That refusal immediately failed three constructed-design
tests writing into a bare temporary directory, which is the guard working: the
fixtures now build `modelo_999/files/` and are as faithful about where a design
lives as about what it contains.


## Repeated literals are not a usable signal, and one stated convention is a minority practice

The five-copy entry-point defect prompted a search for the same shape elsewhere.
Two measurements, one of which is a dead end worth recording so it is not
repeated.

**Repeated string literals do not separate duplication from ordinary use.**
Across `dev/registry`, 235 string literals of eight characters or more appear in
three or more modules. The top of the list is `registry` in 50, `revisions` in
38, `__main__` in 34, `source_ref` in 25 - dict keys naming registry fields and
one Python idiom. These are the same string because they name the same field,
which is correct, and no rule over literal text separates them from the case
that matters. A gate here would have a population that is overwhelmingly right,
which this campaign has already established is not a gate. Abandoned
deliberately.

**A convention the tree states about itself holds in a minority of its
modules.** One gate module declares its encoding constant with the comment
"Named once per module, as this tree requires, rather than repeated at each read
site where a typo would be a silent decode change". Measured: `dev/registry`
passed a raw `"utf-8"` at 146 `encoding=` sites across 48 modules, against 35
sites using a named constant. The convention is real and the reasoning is sound;
what is not true is "as this tree requires", which describes an aspiration as an
established rule.

This is not gated, for the same reason as above inverted: a gate would fail 48
modules, nearly all owned by other campaigns and outside this execution's scope,
and a gate that cannot be made green by the person who adds it is a gate that
gets suppressed.

What was in scope was this work's own contribution to the count. Six modules
written during this thread passed the raw literal - two analysis modules and
four test modules, against four analysis modules that followed the convention -
so the same author was on both sides of it within one campaign, which is a fair
measure of how much an unenforced convention travels. Those six are corrected;
the tree now stands at 138 raw sites in 42 modules against 44 named.


## Finishing the audit of which gates see which screens

Six gates were widened when the entry-point declaration landed. Three more had
not been looked at, and two of them were narrow in the same way.

**The whole-corpus gate ran only the authority runner.** Its docstring says a
screen that crashed on one revision would otherwise surface only when somebody
ran the runner by hand - and the corpus screens were in exactly that position,
since the gate called `run_screens` and asserted the result length against
`SCREENS`. It now runs both runners and asserts against both table lengths, so
the count itself proves the corpus screens ran.

**The no-mutation gate fingerprinted the shipped tree and then ran half the
suite.** The design transcriptions the corpus screens read live inside that same
tree, so the half of the suite that touches those files was never checked for
writes. Both runners now run between the two fingerprints.

**The non-empty-population gate makes a claim wider than its evidence.** It is
named for every screen and checks four named populations. That is a defensible
design - several screens share a population and a few have none separable from
the authority - but the docstring did not say so, and an unstated narrowing is
the same defect this campaign has recorded twice in screens' own docstrings. It
now says what it covers and why.

Two populations were added to it, and the first is the one most easily lost: the
design transcriptions are found by a filesystem walk, so a corpus moved or
renamed would return an empty tuple and leave both corpus screens silent and
healthy. The second asserts that those files parse into notes, because a
transcription set that loaded and yielded no note at all would produce the same
silence for a different reason.

That completes the pass. Every gate in the suite has now been checked for which
screen population it actually sees, and the three that were narrow are recorded
here rather than quietly fixed - the pattern across all nine is one worth naming:
a check written when the world had one shape keeps passing after the world grows
a second, and passing is exactly how it hides.


## The count of narrow gates was right; the breakdown was not

"Five separate gates carried their own copy" was written into this audit, into
the declaration's own comment and into the plan's verification prose before it
was counted. Counting it: **two** gates carried the module-walk literal, **four**
iterated the authority table, **two** ran only the authority runner, and **one**
claimed a scope its body did not have. Nine in total, which is the figure the
prose already used, reached by a breakdown that does not add up to it.

The correction is small and the manner of finding it is not. The number was
derived from memory of the editing rather than from the tree, and it survived
three separate writings because each restated the previous one. It was caught by
asking the file which functions now call each shared traversal - a question that
takes one command - before letting the sentence stand in a durable document.
That is the same discipline this campaign has applied to registry figures all
along, and the gate suite turns out to deserve it too.

## A gate on the gap between enrolment and execution

Enrolment and execution are separate facts, and every narrowing recorded above
lived in the gap between them: a table gains a row, a runner is written for one
table, a gate asserts against that runner's table, and everything passes while a
class of screen goes unrun.

A new gate closes the gap at its narrowest point. The names the runners actually
emit must equal the names enrolled, so a third table added without a runner
fails, and a runner that stops emitting a screen fails too. It asserts NAMES
rather than counts, because two tables of the same size can still disagree about
which screens they hold - the same reason a set comparison replaced a count
comparison when this campaign compared failing tests months of iterations ago.

It runs the corpus runner and takes the authority screens from the table they
are iterated from, rather than running both: what the screens FIND is asserted
by the whole-corpus gate, and running them twice would double the slowest work
in the suite to check something already checked. The suite now holds
thirty-one gates.


## The hundred and forty-nine is retired, and here is what was tried

The rules-authoring step rested on a figure of one hundred and forty-nine newly
eligible fields "in the six modelos that carry a render profile", with
thirty-four more falling due when two further modelos gained one. The step asked
to recover the figure or retire it. Five bases were measured through the live
predicate, and none produces it:

| basis | count |
| ----- | ----- |
| newly eligible when a bare pointer stops counting as a stated fact | 41 |
| the same, restricted to width-17 amount fields | 30 |
| content cells holding only a pointer, whatever their eligibility | 80 |
| newly eligible if any content cell stopped counting | 4,184 |
| fields carrying an absent naturaleza | 95 |

The last was the most promising hypothesis and is the one worth writing down as
refuted, because it is the kind of near-miss that invites a second guess. The
absent-naturaleza admission is a real earlier widening of this same predicate,
so a figure from that era would have been a plausible provenance for a number
this one inherited. It is 95, across four modelos, and those fields are ALREADY
eligible - the predicate admits them today - so they were never a pending
authoring population at all.

Neither 149 nor 183 is reachable from any of these, and the step's other two
figures are refuted directly: seventeen modelo directories carry a render
profile, not six, and the two modelos named as lacking one are not distinguished
from the rest by anything the live tree shows.

The figure is therefore retired rather than corrected. Its provenance cannot be
recovered from the tree as it stands, and a number whose basis nobody can state
is worse than no number: it sizes work, it survives restatement, and it cannot
be checked. What replaces it is 41, which any reader can reproduce with one
command, together with the grounding split that actually decides the effort -
nine fields covered by a convention naming their type and thirty-two by modelo
200's design-level amounts note.


## The grounding screen never asked what the field itself cites

Testing whether modelo 200's amounts note really settles the thirty-two fields
credited to it found that it settles twenty-nine. The note states fifteen
integers, a sign in place of one of them, and two decimals - a seventeen-
character amount - and twenty-nine of the thirty-two declare exactly that width.
Three do not: two of width one and one of width four, and no reading of "15
enteros y 2 decimales" fits a one-character field.

Chasing those three found the omission. Every one of them is settled, and each
by the note its OWN content cell points at, on its own sheet: `DP200001B!A24`
by an accounting-statement code table at width one, `DP200002B!A150` by a
document-type enumeration at width one, and `DP200014!A36` by the rate filling
rule at width four - "se rellenaran los dos primeros digitos con el tipo, y los
dos ultimos con 00", which is four digits exactly.

The screen had asked only what governed a field's CLASS - a convention naming
its type, or a note governing its design - and never what the design pointed at
for the field itself. That is the strongest grounding available and it was
absent from the hierarchy. Corpus-wide it covers **38 of the 41 fields**: they
cite a note that resolves on their own sheet, which is possible at all only
because note labels were scoped to their sheet earlier in this work.

The grounding now reads:

| grounding | fields |
| --------- | ------ |
| a note the field's own cell cites, defined on its sheet | 38 |
| a convention naming the field's AEAT type | 2 |
| a design-level note | 1 |
| nothing | 0 |

The reading load falls with it, from twenty-two distinct notes to **thirteen**
for forty-one fields, because a note cited by several fields of one sheet is one
reading rather than one per class.

An unresolved citation is deliberately not grounding. A field that cites
something a classifier reading the citation alone would call grounded; what
makes it grounding is that the citation RESOLVED, and the three fields whose
pointer names a note their sheet does not carry fall through to the weaker
conditions. That distinction has its own test, because it is the one a
plausible-looking implementation gets wrong.

The condition-count gate caught the docstring still saying three conditions
inside the same edit that added the fourth. That is the second time this
campaign a count in a screen's own opening line went stale in the edit that
made it wrong, and the second time the gate written for precisely that caught it
before a reader did.


## The authoring task is eleven readings, and one of them covers twenty-six fields

The grounding join now emits a worklist: the grounded fields grouped by the note
that grounds them, ordered by how many each covers. That is the artifact the
rules-authoring step needs, because the cost is notes to READ and not fields to
visit - one note read covers every field citing it.

**Forty-one fields resolve to eleven work items.** The largest is modelo 200's
`DP200019:nota 1`, covering twenty-six fields, all of width seventeen and all
typed `Num` - one reading, one rule, twenty-six fields settled. Modelo 303's
`DP30302:nota 5` covers six, all of width one. The remaining nine items cover
one field each.

Each item carries the declared widths and types among its fields, and the widths
are kept as a set rather than summarised. A note stating a seventeen-character
amount cannot settle a one-character field, so an item spanning two widths is the
signal to read before assuming one rule serves the group - which is precisely how
modelo 200's three oddly-sized fields were found in the first place. That has its
own test, constructed rather than sampled.

### The census was measuring one concept two ways

Adding the worklist exposed a disagreement inside a single summary line. The
reading load was counted as distinct `(modelo, revision, note)` triples and
reported thirteen, while the worklist grouped by `(modelo, note)` and produced
eleven. Both were in the same output. Several revisions of a modelo share one
design, so a note common to them is one reading and not two; the census now
counts work items, and the two figures cannot drift because there is only one.

This is the campaign's own target defect appearing in a summary line written
within the same hour: the same concept expressed twice in different forms, in
adjacent output, by one author. It was visible only because the second
expression was built beside the first.


## Reading the eleven notes: twelve fields are settled, not forty-one

The worklist was built so the eleven notes could be read. Reading them changes
the answer, and corrects an impression this audit has been building for several
sections.

"Zero ungrounded" was true and is not a readiness signal. Grounding established
that official wording exists and that the design pointed at it; it never
established that the wording answers the question a representation rule asks.
Read, the eleven divide:

**Seven notes state representation, covering twelve fields.** Modelo 200's
amounts note gives fifteen integers, sign carriage and two decimals; its rate
note gives the four-digit filling rule; two of its notes enumerate the permitted
values of a one-character field; modelo 303's Lorca note enumerates three values
at width one, covering six fields; and modelos 202 and 222 each carry the same
alignment and padding sentence for numeric fields.

**Four notes state something else entirely, covering twenty-nine fields.** The
largest work item in the whole list - modelo 200's `DP200019:nota 1`, twenty-six
fields - reads "A cumplimentar exclusivamente por entidades que pertenezcan a
grupos mercantiles". That is who must fill the field, not how it is written. Two
more of modelo 200's notes state when a casilla may carry content and how it
must agree with another casilla; modelo 353's states a period applicability. All
four are real official statements about their fields and none of them settles a
byte.

So the rules-authoring step faces **twelve fields with wording that answers it
and twenty-nine with wording that does not**, and the twenty-nine are not
ungrounded in the sense of nothing being found - they are fields whose only
located wording is about something else. That is a different remedy: the
representation for those has to come from the field's own extent and type
together with the design's general conventions, or the capability stays
advisory.

The screen said this would happen. Its docstring has carried the sentence "a
grounded row is not an authored rule; the note still has to be read, and it may
turn out to settle less than the field needs" since it was written. What the
sentence could not do is say which rows, and the number turns out to be most of
them by field count and four notes of eleven by reading.

No attempt is made to classify these automatically. Separating "how a value is
written" from "who must write it" is a reading of Spanish prose, and a keyword
list attempting it is the instrument error recorded four times in this audit
already - most sharply when a vocabulary list reported the plainest wire wording
in the corpus as absent. The worklist puts eleven notes in front of a reader in
coverage order; the reading is the reader's.

### A false finding caught before it was written down

The first pass over these notes reported three of the eleven as resolving to
empty text, which would have been a defect in the reader and a serious one. It
was an artifact of the query: it looked each note up in the first revision of
the modelo that produced render inputs, rather than in the revision the finding
came from. Modelo 303's note belongs to its 2023 revision and modelo 353's to
`2026-desde-02`; read there, every one of the eleven carries text, between
thirty-five and four hundred and fifty-nine characters. The correction cost one
command and the wrong version never left the session.


## A note is identified by its design as well as its sheet

The near-miss recorded above - looking a note up in the wrong revision and
briefly seeing three of eleven as empty - was treated as a query mistake. It was
also a gap in the artifact. The worklist named a note by modelo, sheet and
label, which is exactly enough information to open the wrong file. It now
carries the transcription, so a reader has the document rather than a hint
towards it.

Carrying it changed the count, and the change is the finding. The worklist
reported **eleven** items grouped by modelo and label; grouped by design it
reports **thirteen**. The two extra are modelo 303's `DP30302:nota 5`, which
appears in three of that modelo's design transcriptions.

The merge was not harmless. Ten of the eleven notes carry identical text
wherever they appear, so for those the grouping was a fair economy. The eleventh
does not: `DP30302:nota 5` carries **three hundred and thirty characters in one
design and two hundred and nine in another**. A reader handed one row for it
would have read one of the two texts and applied it to fields governed by the
other - which is precisely the failure mode of reading a note from the wrong
page, arrived at by a different route.

This is the sheet-merge defect one level up. A label identifies a note only
together with the sheet that prints it and the design that sheet belongs to, and
each level of that was learned by finding a merge that had already happened. The
justification written for the eleven - "several revisions of a modelo share one
design, so a note common to them is one reading" - is true of modelo 200 and
false of modelo 303, whose revisions carry separate transcriptions. It was
written from the case in front of me and generalised without checking the other.

Both halves are now tested: two revisions sharing one design produce one work
item, and one label in two designs produces two.


## Note wording drifts between a modelo's designs, and now that is visible

Modelo 303's one drifting note was found because it happened to ground a field
in this campaign's population. `dev/registry/analysis/note_text_drift.py` asks
the question of the whole corpus.

Across the bundled transcriptions there are **194 sheet-and-label keys**, of
which **111 appear in more than one design of their modelo**. Of those, **87
carry identical text everywhere and 24 do not**. Modelo 303 accounts for fifteen
of the twenty-four, modelo 202 for five, and modelos 490, 200 and 322 for the
rest.

The largest is modelo 200's `DP200001:nota 1`, which appears in ten designs
carrying two texts - six of 315 characters and four of 459. A rule grounded in
that note under one design and carried forward by name is, after the rewrite,
grounded in wording that no longer says what it said.

This is the last level of the identity question this package has worked through,
and each level was learned the same way - by finding a merge that had already
happened. A label does not identify a note, because a workbook numbers each
page's notes from one. A sheet and label do not identify it either, because a
modelo's designs are separate documents. What identifies a note is the design,
the sheet and the label together.

The screen reports and does not gate, deliberately. Rewording a note between
revisions is AEAT's to do and is usually the point: a rule changed, so its note
changed. Twenty-four findings are not twenty-four defects. What must not happen
is a reviewed rule carried forward while its grounding moves underneath it, and
that is what this makes visible.

Its detector separates three states that look alike from a distance - a label
appearing once, appearing several times with one text, and appearing several
times with different texts - each on constructed designs, plus a case proving
that two sheets numbering from one are not one key. Without that last one the
screen would report most of the corpus as drifting. The live assertion holds by
presence and by the two populations being different sizes, not by the figures,
which move whenever a design is re-transcribed.


## Four of the thirteen groundings rest on wording that changed

Joining the worklist against the drift screen answers the question the two
raise together: **four of the thirteen work items are grounded in a note whose
wording differs between the designs of its modelo, and they cover seven of the
forty-one fields.** Three are modelo 303's `DP30302:nota 5` in its 2023, early
2024 and late 2024 designs; the fourth is modelo 202's `dr M202 (1):nota 4`.

For those seven, a rule read once and carried forward is grounded in text that
no longer says what it said. They have to be authored per design, and the
worklist now says so on the row rather than leaving it to an author to know
that a second screen exists and to run it.

The flag is passed into the grouping rather than computed inside it, so the
function stays one of its arguments and a test can reach both states with input
it writes. It defaults to false, and the default is documented as meaning "not
reported as drifting" rather than "checked and found stable" - the two read
identically in output and only one is evidence. That distinction has its own
test, because a default that quietly asserts a clean state is the shape of
several findings already in this audit.

The census carries both figures: four notes and seven fields. Neither is
derivable from the other, since the items cover different numbers of fields.


## The eligibility correction cannot land honestly, and the reason is structural

The pointer correction and the rules it makes due have been treated throughout
as one change waiting on research. They are waiting on something the render
profile cannot currently express.

A render profile must cover **exactly** the eligible fields: the validator
compares the governed set with the eligible set and refuses on any difference in
either direction, naming what is missing and what is unknown. And a rule's
evidence carries an authority discriminator admitting exactly two values,
`official_source` and `reviewed_policy` - 196 and 965 uses across the shipped
profiles, and no third. Nothing in the module expresses an unsupported or
deferred representation; the one occurrence of the word "unsupported" is prose
in a docstring.

Put together: making a field eligible obliges an author to assert, for that
field, either an official source or a reviewed policy. There is no third answer
available.

For twelve of the forty-one fields that is exactly right - the wording settles
them and a rule states what it says. For the other twenty-nine the only located
wording is about who must fill the field, when it may carry content, or which
period it applies to. An author faced with the gate as it stands has two moves,
and both are bad. Write a `reviewed_policy` justification anyway, which asserts
an authority that was not found and buries the gap in exactly the place a reader
would trust. Or leave the predicate uncorrected, so a bare footnote pointer goes
on counting as the design stating a wire fact.

That is a conflict with this project's own rule against silent under-declaration,
which requires unsupported and deferred to stay distinct from a proven value. The
gate is right to demand exhaustive coverage; what it lacks is a way for coverage
to include the answer "no wording settles this field". A third authority kind
carrying that, with the renderer refusing such a field rather than emitting
padding for it, would let the eligibility correction land with an honest account
of all forty-one - twelve stated, twenty-nine declared unsupported - instead of
either forty-one assertions or none.

This is recorded rather than implemented. It changes what a render profile means
and what the renderer does when it meets a field nothing settles, which is
filing-affecting behaviour and belongs to a decision rather than to an execution
step reasoning from a screen's output.


## Half the provenance population is one omission repeated, not drift

The provenance screen carries by far the largest population in the suite -
31,608 findings, an order above every other screen - and its runner row shows
1,389 because it is enrolled through an index that collapses per-child sites
onto the reference actually outside a manifest. That collapse already existed
and its docstring already stated the insight, which is why no second one was
built: the reduction from sites to references is done, and doing it again would
have been this campaign's own target defect.

What the index cannot answer is what kind of correction each row needs, because
it is keyed per revision and both shapes look the same there. Reduced once more:
the 1,389 rows are **414 distinct (modelo, kind, reference) triples**, of which
**213 are absent from every revision of their modelo and 201 from only some**.

Those are different corrections. A reference the modelo never declares anywhere
is one omission - the manifest convention was never applied to it - and is
plausibly fixed once for the modelo. A reference present in some revisions and
missing from others is drift between manifests that were meant to agree, and
each gap is its own fix. The largest systemic case is modelo 100's
`ley-35-2006:art-77`, absent from all six revisions and cited by 4,340 children.

The composition is worth recording beside it. The findings divide 23,475 legal
against 8,133 source references, and by citing child 21,596 casillas against
2,683 evolutions, 2,638 bindings, 2,101 formulas and 2,014 export fields.
Modelo 100 accounts for 14,838 and modelo 200 for 7,696, so two modelos carry
seventy per cent of the population.

The projection is built on the index rather than on the findings, so there is
one collapse from sites to references and this asks a further question of its
result. Its agreement with the index is asserted: no site lost, none invented,
and the reference set identical. And a modelo missing from the revision counts
yields no claim rather than a false one - defaulting an unknown denominator to
zero would make any single row match and report it as systemic, which is a claim
built out of ignorance and has its own test.


## Nothing in the provenance population is a dangling reference

A citation outside its manifest could be either of two things, and the screen's
own docstring says so: the child citing something outside the revision's scope,
or the manifest under-declaring. Before either, there is a worse possibility
worth ruling out - a reference cited and declared nowhere at all.

It is ruled out. All **414** modelo-and-reference pairs resolve in their
catalogue: 1,374 legal ids and 499 source ids are declared, and every cited
reference is among them. Nothing here is broken; every one is a declared
reference simply not listed in a manifest. That bounds the severity of the whole
population and is recorded as a negative finding, because a reader looking at
31,608 citing sites has no way to tell that from the count.

### Where to look first, and why

Direction is not decided by this screen, but the site count is evidence about
it. A reference cited by one child and absent from the manifest is as likely to
be a citation reaching outside its revision as a gap in the manifest. One cited
by hundreds of children across every revision of its modelo is the manifest
under-declaring; the alternative would have hundreds of authors independently
citing something out of scope.

The distribution splits cleanly. **Seventeen references are cited by exactly one
child** - sixteen legal, one source - and those are the small set worth reading
one at a time. At the other end, **ninety-nine are cited by a hundred children
or more**, fifty-five of them absent from every revision of their modelo. The
middle bands hold the rest: 175 references in the ten-to-ninety-nine band and
123 in two-to-nine.

The CLI now prints the reference scope beside the per-revision rows, and the
census carries the three figures a reader needs: 414 pairs, 213 spanning every
revision, 17 cited by a single child.

### Two counts named the same thing

The summary line briefly carried `distinct_references=314` and
`references=414`. Both are real and they are different questions - 314 distinct
reference IDS appear, forming 414 modelo-and-reference pairs, so about a hundred
references sit outside the manifests of more than one modelo. Named as they
were, a reader had two reference counts in one line and nothing to tell them
apart. They are now `distinct_reference_ids` and `modelo_reference_pairs`.

That is the third time in this campaign one output line has carried two figures
for what looked like one concept. The previous two were the same concept
measured twice and were resolved by deleting one; this one is two concepts
sharing a name and is resolved by naming them.


## Reading the seventeen reverses the hypothesis, and the screen measured half a disagreement

The seventeen single-child references were separated as the set where a child
might be citing outside its revision's scope. Reading them says otherwise, and
decisively.

Six of them are one series: modelo 100's estimacion objetiva agraria formula
citing, in each year, the orden that sets that year's indices - 2020 to
`orden-hac-1164-2019:art-4`, 2021 to `orden-hac-1155-2020:art-4`, and so on
through 2025 to `orden-hac-1347-2024`. Six consecutive years, each formula
citing its own year's authority. That is not a citation reaching outside its
scope; it is the most precise grounding in the population. The rest read the
same way: a binding named `renta-2025-modelo-184-atribucion` citing modelo 184's
design, a modelo 100 casilla citing the corporate-tax articles it computes from.

So the direction hypothesis recorded last iteration - that a low site count
suggests over-citation - is wrong, and it was reasoning from the shape of the
number rather than from the content. On reading, every one of the seventeen
points the same way as the heavy cases.

### The manifest is not a smaller version of the citations

Chasing why the manifest omits these found the real relationship. Modelo 100's
2020 manifest declares **fifteen** legal references, all `ley-35-2006:art-N`,
and contains neither the orden nor `ley-27-2014` in any form - so this is not a
granularity mismatch between `orden:art-4` and `orden` either.

Across the corpus a manifest declares a median of four legal references while
its children cite a median of six, and the two sets relate in both directions:
**59 of 128 revisions declare a manifest that is a subset of what their children
cite, and 69 declare references that no child cites at all.**

That matters more than the finding count. The screen asks whether children stay
inside the manifest, which is one possible contract, and the corpus was not
authored to it in either direction. Before anyone corrects 414 references, what
a manifest is FOR relative to its children's citations has to be decided; until
then the population measures a disagreement between two surfaces rather than a
defect in one.

### The mirror condition now exists

The unscreened direction is now screened: **263 manifest references that no
child cites, 121 legal and 142 source**, concentrated in modelos 308, 184, 763
and 194. It reads the authored families only and not resolved export fields,
because a derived field's citations are copied from its template and would make
a manifest reference look cited by a child that never declares it - which would
hide exactly the disagreement being measured.

The two populations are disjoint by construction, one cited-not-declared and the
other declared-not-cited, and a test asserts they do not intersect. Another
asserts that revisions in which the surfaces agree exist, so the condition is
discriminating rather than universal.


## The mirror condition is now a screen, because a condition nobody runs is invisible

The mirror landed last iteration as a function beside the provenance screen and
was reachable only by reading that module's source or its CLI output. The runner
showed `provenance_consistency: 1389` and said nothing about the 263, which is
the exact failure this package has corrected five times in other places and had
just reproduced in its own newest code.

The runner enrols one screen per module and the enrolment gate asserts that
correspondence both ways, so enrolling the mirror meant giving it a module:
`dev/registry/analysis/manifest_uncited_references.py`, with its own entry
point, test module and README row. The gates required all three before the suite
would pass, which is the machinery doing its job on the fifth screen added since
it was widened. The runner now carries seventeen screens.

Keeping the two in one module would have been defensible on subject - both
measure manifest against children - and was rejected on visibility. The
condition that only a reader of the source can find is the one that stops being
true without anyone noticing.

The split is not a copy: the function was moved, its duplicate deleted from the
sibling, and the sibling's CLI now calls the new screen rather than a local
copy of it. Their populations are asserted disjoint - one cited-not-declared,
the other declared-not-cited - which is also the check that would fail if either
started reading the other's surface.


## Two modelos ship published filing bytes while declaring they cannot file

The capability screen's 67 findings divide into five conditions:
`envelope_spelled_as_record` 31, `layout_without_filing_grade` 25,
`files_here_without_deadline` 5, `claims_calculation_without_formulas` 4, and
`tree_ships_below_filing_grade` 2. The last three are small enough to read, and
all three are declaration contradictions of the kind this campaign exists for.

The most serious is the smallest. **Modelos 185 and 222, revision
`2025-y-siguientes`, each carry a published export tree - four fragment files and
a `_generation.provenance.json` attesting the generation - while declaring
`applicability` grade.** The registry says these revisions cannot file, and the
repository ships their filing bytes. Modelo 296, 308, 349 and 360 declare a
filing calculation class with no formula in the revision, and modelos 145, 151,
165, 308 and 309 reach filing grade with a layout and declare no deadline
window, so they cannot say when the filing is due.

### Three wrong readings on the way, and the third was a repeat

Verifying the shipped-bytes claim rather than trusting it was right; the
verification was wrong three times.

First I read the `export/` directory as holding only authored layout fragments,
and concluded the finding's wording overstated - a declared layout is not
shipped bytes. Second I concluded the condition was subsumed by
`layout_without_filing_grade`, which reports the same two revisions. Both fell
to the same fact: publication writes the generated tree INTO that directory, and
the provenance manifest is what distinguishes a published tree from an authored
declaration. Both revisions carry one. The finding is exact and the two
conditions are properly distinct - one reports a layout declared below filing
grade, the other reports bytes published below it, and the second is strictly
graver.

The third error is the one worth recording. I listed modelo 303's export
directory with `head -6` and read the absence of `_generation.provenance.json`
as evidence that authored-only directories exist. The filename sorts after
`0004-...` and `head` cut it off. That is the truncation failure recorded near
the start of this campaign - a measurement piped through `head` or `tail` is not
a measurement - made again, in the middle of correcting two other misreadings.
Measured properly: **all 28 export directories in the corpus carry a manifest**,
so every one is a published tree.

### The predicate was right by luck

`_committed_tree` tested whether the export DIRECTORY exists. Since all 28 carry
a manifest, that agrees exactly with testing the manifest, and the screen has
never reported a false positive. But they are different claims: the directory is
where authored layout fragments live, and a revision that declared layouts
without ever being published would have the directory and no manifest, and would
be reported as shipping bytes it had never produced. The predicate now tests the
manifest. The census is unchanged at 67, which is the evidence that the tightening
altered nothing about the corpus and only about what the code claims.


## Two screens were reporting one fact under two names

The capability screen's second-largest condition, `layout_without_filing_grade`
at 25 findings, turned out to be a duplicate.

Every one of its 25 revisions is also reported by the grade screen as
`under_declared`, and the grade screen names the prerequisite that drives each
finding. Split by prerequisite, its 31 under-declared findings are
`export_layout` 25 and `completeness_manifest` 6 - and the 25 export-layout
findings are **exactly** the 25 capability findings. Set equality both ways,
nothing on either side.

They are the same fact: a revision carrying an export layout while declaring a
grade below filing. The capability screen stated it as a symptom; the grade
screen states it as a conclusion - the declared grade is lower than its
prerequisites support - and says which prerequisite. The second contains
everything the first said and generalises past it, so the first was retired.
The capability screen now reports 42 findings across four conditions, and the
25 revisions are unchanged in the suite because the sibling reports them.

This is the project's own rule applied to its own tooling: overlapping gates are
justified when they catch distinct failure modes, and these did not. It is also
the second consolidation this campaign has made after measuring rather than
assuming - the first, a suspected duplicate between the pointer screen and the
grounding screen, turned out on measurement to be two genuinely different claims
and was kept.

### The condition-count gate caught the retirement mid-edit

Removing the condition left the docstring's replacement prose sitting between
two bullets, which split the list. The gate reported "says 5 conditions and
documents 1" - not five, one - because the list it could parse ended at the
paragraph. That is a better failure than a count off by one: it named a
structural break rather than an arithmetic slip. The prose now sits after the
list.

That is the third time this gate has caught a stale or broken condition count
inside the very edit that caused it.


## The duplicate was the only one, and the sweep that proved it is not a gate

Retiring one duplicated condition raised the obvious question: are there others?
Swept across every screen, comparing each condition's population of
`(modelo, revision)` pairs, the answer is no. **No two comparable conditions
report identical populations.** The one retired was the only one.

Two things about that sweep are worth keeping, and neither is a gate.

**The first attempt measured its own blind spot.** It read populations from the
runner, which returns whatever each entry chose to project - two entries collapse
their screen onto a different unit and return objects that are not findings at
all. Everything lacking a `modelo` attribute fell to one empty key, and two
unrelated screens duly appeared as an IDENTICAL pair of population size one.
That is the same instrument error recorded four times in this audit, and the
declaration it violated is a comment sitting in the screens module warning
exactly this: a caller reading the runner gets whatever the entry chose, while a
caller calling a screen gets a finding. Redone against each screen's own
findings, restricted to those carrying a revision coordinate, the false pair
disappeared.

**Subset relationships at revision granularity are not a signal.** The sound
sweep reports forty-four of them, and they are arithmetic rather than meaning: a
condition holding five revisions is inside one holding sixty-five whenever the
five are among them, which says nothing about whether the two describe the same
thing. `grounded_by_own_note` inside `provenance_consistency` is two unrelated
facts about overlapping revisions.

So this is not becoming a gate. Population identity between two conditions is
not an invariant - two genuinely different conditions may legitimately coincide
on a corpus this size, and a gate asserting they never do would be asserting a
coincidence. The duplicate that was found was found by reading what two
conditions MEAN; the set comparison only confirmed it, and confirming is all a
comparison of populations can do.


## A helper added to widen the gates was narrowing one of them

The instrument error in the duplicate sweep - reading the runner's projections
as though they were findings - was not only a mistake in a throwaway query. The
helper that made it available, `enrolled_screen_findings`, was added three
iterations ago to widen six gates onto the corpus screens, and its name and
docstring promised findings while it returned whatever each table entry
projected.

The kind-naming gate reads it. Measured: **four kinds a screen emits never
reached that gate.** The monetary screen's `money_split_representation` is
filtered out by the projection that keeps only findings needing action. And all
three grounded kinds of the grounding screen were invisible, because its entry
projects onto the ungrounded residue - a population that is empty, so not one of
that screen's four kinds was ever checked against its docstring. That projection
is mine, added deliberately two iterations ago so the runner would not carry two
adjacent rows agreeing by construction. It was right for the runner and wrong
for a gate.

The helper is replaced by `screen_findings`, which calls each screen's own entry
point. Thirty `(screen, kind)` pairs now reach the gates, and the four
previously hidden are among them - verified by name rather than by the count
going up.

### A gate that asserted the wrong direction, and said so by failing

The first guard written against recurrence demanded that no projection hide a
kind. It failed immediately on the two legitimate projections, which is the
correct outcome for an incorrect invariant: dropping findings is what a
projection is FOR, and a gate forbidding it would forbid the design it exists to
serve.

The invariant that does hold is the other direction. A projection may narrow its
screen's findings and may never invent one, so the gate now asserts that no
runner entry reports a kind its screen does not emit - which would mean a
finding derived in the table, where no test looks for it and no docstring
describes it. That the kinds are hidden from the kind-naming gate is a separate
problem, fixed at the reader rather than by constraining the projections.

The suite now holds thirty-two gates.


## Eleven filing-grade revisions cannot say when a filing is due

The temporal screen's 36 findings are `no_deadline_windows` 27 and
`window_year_without_deadline` 9. The second was unexamined, and it is the more
interesting: a revision whose CLOSED window spans years its deadline windows do
not cover.

**Six of those nine are filing grade** - modelos 123, 131, 180, 202, 347 and
353. Modelo 347's window runs 2011 to 2024 and carries no deadline for seven of
those years. Together with the five filing-grade revisions that declare no
deadline window at all, **eleven filing-grade revisions cannot state a due date
for at least one year they claim to serve.** The other three year-gap revisions
sit below filing grade, where saying nothing costs nothing.

The capability screen now reports the filing-grade six, as it already reported
the filing-grade five. It narrows the temporal screen rather than restating it,
and a test asserts the strict subset - equality would mean one fact under two
names, which this screen retired a condition for two iterations ago.

### The same duplication, reintroduced by me, caught by measuring

The first version reported eight, and the eight were not a subset of the nine.
Modelos 151 and 165 declare NO deadline window at all, so the undated-year
computation returns every year of their window, and both of this screen's
deadline conditions fired on them. That is the identical defect retired two
iterations ago, reintroduced within the same file, by the author who retired it.

It was found by checking containment rather than by reading the count. Eight
looked plausible next to nine. The precedence now mirrors the temporal screen's
own: a revision with no windows at all is reported once, not once per year.

### And a second implementation in disguise

The first draft obtained the undated years by parsing them back out of the
temporal screen's finding PROSE - splitting its detail string on a bracket. That
is the anti-pattern this campaign has refused elsewhere in the same words, and
it would have returned an empty tuple, silently, the first time that sentence
was reworded. The computation now lives once, as
`temporal_site_agreement.undated_window_years`, used by the screen that reports
it and by the screen that narrows it. A test asserts the census agrees with that
function for every revision, so a future second implementation fails rather than
drifts.


## Every unscaled monetary field sits in a revision that can be filed

The monetary screen emits 165 findings; the runner shows 33 because its entry
projects onto those needing action. The 132 excluded are
`money_split_representation`, the official integer-and-decimal part split, which
is the design rather than a defect.

Of the 33 that remain, the largest condition is **26 fields rendered as text -
applying no scale - and declaring no decimals. All 26 are in revisions declaring
filing grade**: modelo 347 with eight and six across its two revisions, modelo
184 with four and four, modelo 200 with two, and modelos 296 and 353 with one
each. Five more declare four decimals where the corpus otherwise uses two, and
two are the known sibling-disagreement defects.

The plan's verification criterion already carried the figure 26. What it did not
say is that not one of them sits below filing grade, where an undetermined
magnitude would cost nothing. That is now stated.

## A guard that would have been wrong, measured before writing it

Having twice created two conditions of one screen that both fire on one
revision, the obvious guard is a gate forbidding it. Measured first, and it
would have been wrong: within-screen overlap is normal and legitimate. The
monetary screen has seven revisions carrying several kinds at once because its
findings are per FIELD and the coordinate is the revision - one revision can
hold a field without scale, a part split and a sibling disagreement, and all
three are true. The pointer, grounding and capability screens overlap for the
same reason.

The exclusivity that was violated is narrower and cannot be derived: it holds
between two conditions that both key on the revision ITSELF and describe the
same property of it, which is the pair of deadline conditions and nothing else.
That is where the test was put. A screen-wide gate would have failed on four
screens reporting correctly, which is the second methodological guard this
campaign has declined after measuring rather than after it broke something.


## Which findings a filer would actually meet

The question that has reordered every population examined in this campaign -
does this sit in a revision that can be filed? - has been asked by hand four
times, of the deadline conditions, the unscaled monetary fields, the published
trees and the grade findings. `dev/registry/analysis/filing_exposure.py` asks it
of every condition at once.

Across **34 conditions**, 23 carry findings in filing-grade revisions and the
corpus declares **69 filing-grade revisions**. The exposure is dominated by two
screens: the provenance screen's 31,608 findings include **27,498 in filing-grade
revisions across 50 of its 65**, and the wire-type screen's 13,624 include
11,911 across 59 of 84. Below those, the monetary screen's 26 unscaled fields
and the grounding screen's 38 cited-note fields are wholly filing-exposed.

It is a reading order and not a severity verdict, and the corpus makes the point
itself: the monetary part-split condition is 132 findings, all 132 in
filing-grade revisions, and every one is the official design rather than a
defect. High exposure says read this first, not fix this first.

This is deliberately not a screen. Its unit is a condition rather than a modelo,
so it declares no screen entry point and joins no runner table - the identity
contract those tables enforce would not fit it, and forcing it in would have
meant inventing a modelo for a row that is about a screen.

### The first run reported eight conditions as safe that had never been asked

Eleven conditions came back with no filing exposure, which reads as eleven
populations a reader can defer. Three of them were measured: the grade screen's
under-declared findings, which are below filing by definition, the two published
trees, likewise, and two revision names.

The other **eight carry no revision at all**. The identifier-grammar screen
reports per modelo, the continuity screen deliberately omits a revision because
a chain spans several, and the four corpus screens report per design because a
transcription belongs to no revision. None of them had been graded; all of them
displayed as though they had.

That is the same defect this audit has recorded against a drift flag and against
a grounding default: an absent measurement rendering as a measured negative. The
report now counts unmeasured findings separately and refuses the deferral claim
where nothing was measurable, so the honest split is **three conditions safe to
defer, eight not asked, twenty-three exposed** - and the eight are visible as a
gap rather than as a clean result.


## Correction: the exposure report overstated one screen by a factor of five hundred

The previous section reported that filing exposure "is dominated by two
screens", naming the provenance screen's 27,498 exposed findings and the
wire-type screen's 11,911. The second figure is wrong, and the error is in the
report rather than in the wire-type screen.

`wire_type_compatibility.screen_authority` does not return findings. It returns
a **census** of every casilla-to-wire-type transition it examined - 13,624 rows -
each carrying a `divergent` flag, and 29 of them diverge. Its runner entry
filters to those 29, which is why the suite has always shown 29 for it. The
exposure report read the unprojected population and counted all 13,624 as
findings.

Measured across the suite, three relationships exist between a screen's entry
point and its runner row, and nothing in the code distinguishes them:

| shape | screens | example |
| ----- | ------- | ------- |
| every row is a finding | eleven | 263 to 263 |
| findings projected onto another unit | provenance | 31,608 to 1,389 |
| a census with a flag | wire-type | 13,624 to 29 |

The provenance figure is NOT of this kind and stands: its 31,608 rows are
findings, one per citing child, and the 1,389 is an index over them. Only the
wire-type row was wrong.

The report now carries the runner's count beside the population it measured, so
a reader sees `findings=13624 runner_findings=29` and can tell a census from a
finding set without knowing which screens are which. That is a disclosure rather
than a fix: there is no declaration to read the difference from, and inventing
one would mean asserting a contract the screens were not written to.

The corrected reading is that filing exposure is dominated by **one** screen -
the provenance screen's 27,498 findings across 50 filing-grade revisions - with
the monetary screen's 26 unscaled fields and the grounding screen's 38 cited-note
fields wholly exposed beneath it.

This is the third instrument error in this report's short life: it counted rows
that carry no revision as measured-safe, it counted a census as findings, and
both were found by reading its output against the thing it claimed to describe
rather than by the report failing.


## What a screen's entry point returns is now declared rather than inferred

Three instrument errors in one report, all from one root: nothing said what a
screen's entry point returns, so a consumer had to infer it, and inferring it
wrongly counted 13,624 examined transitions as defects.

The runner table now declares it. `ScreenEntry.entry_returns` is either
`findings` - every row is one - or `census`, meaning the entry returns everything
it examined with a flag and only flagged rows are findings. One screen declares
`census` today; the rest declare findings, which is also the default, so the
declaration is only written where it is not the ordinary case.

**Nothing verifies it, and the docstring says so.** No mechanical test
distinguishes a census from a finding set: both are sequences of dataclasses, and
the ratio between the entry point and the runner row cannot decide it, because
several findings screens project onto small subsets too - the grounding screen
projects 41 findings onto an empty residue, a larger ratio than the census's. So
this is an author's statement, and its value is that a consumer reads it instead
of guessing. A gate asserting it would be asserting the guess this replaces.

With the declaration read, the exposure figures correct:

| figure | before | after |
| ------ | ------ | ----- |
| filing-exposed findings | 39,831 | 27,920 |
| conditions with filing exposure | 23 | 22 |
| census rows examined, reported apart | - | 13,624 |

The 27,920 is the honest total: findings, in filing-grade revisions, from screens
whose entry points return findings. The census's 11,911 filing-grade rows are
still reported, on their own row, as transitions examined.

The declaration is also the smaller lesson of this campaign restated. Every time
a consumer has had to infer a producer's contract - which entry point a module
presents, whether a note label identifies a note, whether a finding carries a
revision, what an unnumbered note governs - the inference has been wrong at least
once, and the fix has been to declare the thing once and read it. This is the
same shape at the level of the tooling's own interfaces.


## Five revisions claim a filing grade their prerequisites do not support

Working down the corrected exposure order, the grade screen's `under_supported`
condition is small and points the dangerous way. Its five findings are all
filing-grade revisions **declaring filing while missing the completeness
manifest**: modelos 145, 165 in two revisions, 308 and 360. Every other grade
finding in the corpus points the other way - a revision declaring less than it
supports - and these five declare more.

Several of those names recur. Modelo 308 also declares a filing calculation
class with no formula and reaches filing grade with no deadline window; modelos
145 and 165 also carry the deadline gap. That recurrence is the finding, and it
suggested an axis nothing measured.

## Sixty-seven of sixty-nine fileable revisions carry a declaration contradiction

Exposure asks which CONDITION a filer would meet. The other question is which
REVISION carries the most of them, and the two disagree about what to do first.

**Sixty-seven of the sixty-nine filing-grade revisions carry at least one
condition.** Choosing work by condition therefore means touching almost every
fileable revision; choosing by revision clears several conditions at a time. The
ranking is led by modelo 200's `2025-y-siguientes` with **nine distinct
conditions**, then modelo 347's `2011-2024` and modelo 353's `2026-desde-02`
with six each, and modelo 308's with five.

The row names its conditions rather than only counting them, because a count is
not a severity: one filing-correctness defect outweighs four declaration
untidinesses and nothing here weighs them. Census screens are excluded, since
their rows are transitions examined and including them would rank a revision by
how many fields it has - the same error the entry-point declaration exists to
prevent, arriving by a second route, and it has its own test.


## The worst revision's nine conditions are seven, and one screen was counted twice

Modelo 200's `2025-y-siguientes` led the pressure ranking with nine conditions.
Reading them found two pairs that are one fact each.

The pointer screen reports 31 fields citing a note; the grounding screen reports
the same 31 as grounded by a note they cite. The pointer screen reports one
field whose citation does not resolve; the grounding screen reports that same
field as falling back to a design note. Not a coincidence - **the grounding
screen calls the pointer screen** and emits one finding per field it returns.
Measured across the corpus: 41 findings each, over the same 41 cells, in the
same revisions.

So every revision carrying pointer fields gained a second condition
automatically, and the ranking overstated all five of them. Corrected, modelo
200 carries **seven** independent conditions, modelo 347 six, and modelos 308
and 353 five.

The remaining seven on modelo 200 are genuinely distinct: three separate
monetary-scale problems, three uncited manifest references, and 4,022 provenance
citations reaching outside its manifest, of which the largest names the modelo's
own 2024 manual.

### Declared, and gated as far as a gate can reach

`ScreenEntry.derives_from` now names the source a screen is built on, and the
pressure ranking skips derived screens because their findings are a
re-description rather than independent evidence.

Half of this declaration is verifiable and is now gated: whatever a derived
screen reports must name a revision its source also reports. The other half is
not - no test can decide whether a screen that happens to agree today was
actually built on the other - so the declaration stays an author's statement and
the gate does not pretend to confirm it. That distinction is written into both
the field's comment and the gate's docstring, because the previous declaration
added for the same reason carries no gate at all and a reader is owed the
difference.

This is the second undeclared producer contract found by a consumer getting it
wrong, in two consecutive iterations, in tooling written during this campaign.


## Sweeping for other undeclared derivations found none, and a weak instrument

Having found one screen derived from another by reading, the obvious next move
is to sweep for others mechanically: which screen modules import another
screen's entry point? Two rows came back and neither is a missed declaration.

**The provenance screen imports the manifest screen inside `main()`**, to print
both populations from one command. Its `screen_authority` never touches it, so
nothing about its findings derives from that screen. The sweep flagged it because
it read module text rather than what the entry point calls.

**The grounding screen reaches three screens and declares one.** That is correct
and the distinction is the useful part: `fields_needing_rules` supplies its
POPULATION - the fields it reports are exactly the fields that screen returns -
while the convention screen supplies an attribute of each row and the drift
screen supplies a flag in `main()`. A screen derives its population from at most
one source; consuming others for attributes is not derivation and must not be
declared as it, or the ranking that reads the declaration would drop findings
that are independent.

So the sweep is a prompt and not a verdict, like the population-identity sweep
before it. Import-reach over-reports because a screen may consume another for
enrichment, and the property that matters - where a screen's population comes
from - is not visible in an import. The declaration stays an author's statement
with the containment half gated.

### An asymmetry introduced and removed in the same iteration

`derives_from` was added to `ScreenEntry` and not to `CorpusScreenEntry`, so the
sweep crashed reading the corpus table. The two entry types now declare the same
things. An asymmetry between them is a place where a consumer must know which
table a screen sits in before it can ask a question about it, which is the shape
of several defects already in this audit and was worth removing rather than
working around.


## Thirty-one filings can carry no product identity, and the export path proves it

The capability screen's largest condition is `envelope_spelled_as_record`: 31
revisions whose layout smuggles its envelope into the record tuple as an
`envelope_header` pseudo-record instead of the typed `filing_envelope` slot.
Twenty of the 31 declare filing grade. The claimed consequence - that the export
boundary then refuses the product and software identity an enveloped filing must
carry - was verified rather than taken from the screen's own docstring.

**The declaration side is unanimous.** Eighteen layouts across seven modelos use
the typed slot, and **all eighteen declare a `product_identity_requirement`**.
There is no counter-example of a typed envelope that omits it. The 31
record-spelled layouts cannot declare one, because the pseudo-record carries no
such field.

**The consumer side confirms the consequence exactly.** In
`application/filing/export.py`, `renders_filing_envelope` is set from
`layout.filing_envelope is not None`. Where it is true the export REQUIRES both
the prior domiciliation election and the product software identity, raising a
`FilingExportError` if either is absent, and renders the envelope with them.
Where it is false the branch is skipped entirely: nothing demands the identity
and nothing stamps it.

So a record-spelled envelope does not fail. It exports, silently, without the
identity an enveloped filing is supposed to carry, and twenty of the thirty-one
revisions in that state can be filed today. That is the same failure shape as
this project's rule against silent under-declaration, expressed in a layout's
spelling rather than in a value.

### The step's figure for the healthy side is wrong

The migration step describes the typed slot as one "twenty others already use".
Measured: **eighteen** layouts, in eighteen revisions, across seven modelos -
151, 200, 202, 222, 303, 322 and 353. Not twenty, and the figure matters because
it is the population a migration would follow as its worked example.


## Modelo 322's newest revision lost the envelope its predecessor carried

Checking the rest of the migration step's sentence - "thirty-one revisions across
sixteen modelos" - confirmed both figures, and turned up one modelo appearing on
both sides of the split. Modelo 322 uses the typed `filing_envelope` slot in
`2008-2022`, `2023` and `2024-2025`, and spells its envelope as a record in
`2026-y-siguientes`.

That is not a migration waiting to happen. It is a **regression**, between two
consecutive filing-grade revisions:

| | `2024-2025` | `2026-y-siguientes` |
| - | - | - |
| declared grade | filing | filing |
| typed `filing_envelope` | yes | no |
| `product_identity_requirement` | declared | absent |
| first record | `m322-page-01` | `modelo-322-envelope-header` |

The newest revision of a modelo that files lost a capability its immediate
predecessor had, and gained a pseudo-record in its place. By the export path
verified above, its filings now render through the plain-records branch: nothing
requires the product software identity and nothing stamps it, where the 2024
revision would refuse to export without it.

The record naming changed at the same time - `m322-page-01` became
`modelo-322-page-01` - which suggests the 2026 revision was authored fresh rather
than carried forward from the one beside it. That is consistent with the
regression being an oversight rather than a decision, and it is the more useful
reading for whoever repairs it: the shape to copy is three revisions back in the
same modelo.

Modelo 322 is the only modelo carrying both spellings, so it is also the only
place the migration has a worked precedent inside its own directory.

### Why the screen could not say this

The capability screen reports each record-spelled revision on its own row, which
is right - each is a defect. What it cannot see is that one of them sits directly
after three revisions of the same modelo that did it correctly. Continuity
between revisions is not this screen's unit, and nothing else compares a
revision's capability with its predecessor's. That is a gap worth naming even
though this instance was found by hand.


## The gap that hid modelo 322 is now a screen, and it found one more thing

Every other screen judges a revision alone. None compared a revision with the one
it succeeds, which is why modelo 322's regression - a typed filing envelope
present in three consecutive revisions and absent from the fourth - reported as an
ordinary row about the fourth and had to be found by hand.

`dev/registry/analysis/capability_continuity.py` compares consecutive revisions,
ordered by `valid_from`. It reports three findings across two modelos, and the
two conditions it separates are the reason it is worth having.

**Modelo 322 is a regression.** Its `2026-y-siguientes` lost the typed envelope
and the product-identity requirement while staying at filing grade. Nothing about
the claim got smaller, so the capability was dropped rather than renounced. The
screen rediscovers this independently of the hand analysis that prompted it.

**Modelo 165 is not.** Its `2023-2025` loses an export layout, and the grade goes
from filing to applicability at the same time: two casillas, no layout, sitting
between two filing revisions. That is what a deliberate placeholder looks like,
and collapsing the two conditions would have filed an intention beside an
oversight under one name. The distinction is `capability_lost_at_same_grade`
against `capability_lost_with_grade`, and each has a test naming the modelo it
holds.

Three choices in the screen are worth stating because each excludes a larger and
worse population:

- **Capabilities are directional and never counts.** A revision with fewer
  casillas than its predecessor is not weaker, and reporting count decreases
  would bury the cases where something stopped being expressible at all.
- **Consecutive pairs, not comparison against the newest.** A capability dropped
  and restored two revisions later is still a gap in the years between, and those
  years are filed.
- **The grade ladder is taken from the shipped enum at import**, not respelled.
  Comparing grades needs an order that a string enum does not carry, and a second
  spelling of its members is the drift this package exists to find. A test
  asserts the tuple equals the enum's own member order.

The screen reports and does not gate. A modelo may lose a capability because the
law removed what it served, and nothing here can tell that from an oversight -
what it can do is stop the difference being invisible, which for modelo 322 it
was.


## An ordering constraint that no longer protects anything

The plan's parallelization section carried a constraint discovered by
measurement: correct the eligibility predicate before publishing any further
export tree, because publishing first converts the rules it makes due from
authoring into a correction of shipped filing data. It sized that at one hundred
and eighty three fields, eighty-seven of them in designs not yet published.

Both halves are now wrong, and the second one matters more.

The figure is the retired one. One hundred and eighty three is one hundred and
forty nine plus thirty four, the pair this audit established cannot be
reproduced from any basis. The live predicate admits **forty-one**. That the
retired number was still standing in a third place is its own small lesson: it
was corrected in the step that owned it and in the verification criterion, and
survived in the parallelization prose because nothing links the three.

**The constraint itself is spent.** Every one of the forty-one fields sits in a
revision whose export tree is already published - thirty-two in modelo 200's
`2025-y-siguientes`, six across three revisions of modelo 303, one each in
modelos 202, 222 and 353, and **none** in an unpublished design. The conversion
the constraint existed to prevent has already happened in full, so ordering the
predicate ahead of publication protects nothing that is still protectable.

The section now says so, and points at the blocker that does still bind: the
correction cannot land honestly until a render profile can declare a field
eligible with its representation unsupported, because twenty-nine of the
forty-one have no wording that settles them. A spent constraint left in place
reads like a live one, and a reader sequencing work by it would be sequencing
around nothing.

## Widening the continuity screen's capability set would find nothing

The capability-continuity screen judges five directional capabilities. Five more
were measured against it - the completeness manifest, relations, bindings,
parameters and continuity evolutions - and **no consecutive pair loses any of
them anywhere in the corpus**.

The zero was checked before being believed: all five attributes exist on a
revision and carry real values, so this is a measured absence rather than a
`getattr` returning `None` on a name that was never there. That check is worth
naming because the same shape - a probe for an attribute that does not exist,
reporting clean - is a defect this audit has recorded more than once.


## Re-measuring the other two ordering constraints

Finding one constraint spent made the other two worth checking, since all three
were "discovered by measurement" and measurements age.

**The generator-verb constraint is stated correctly and still holds as written.**
`python -m dev.registry.pipeline` registers both `check` and `publish` today, so
the section's own account - that the constraint was written twice, wrong both
times, and is lifted - is accurate. Verified rather than assumed, because that
paragraph has already been wrong twice and a third reading was cheap.

**The external-artefact constraint still binds.**
`CANONICAL_FILING_EXPORT_CONFORMANCE_VECTORS` is the empty tuple. Three Steps in
three Waves still wait on one reference nobody in this execution can acquire.

**A figure inside the first is stale.** It gates "the two enrolled trees that
render successfully and have never been committed". Measured: **three** -
modelo 308's `2019-y-siguientes`, modelo 360's `2010-y-siguientes` and modelo
390's `2022`. Twenty-eight revisions produce render inputs and carry a
publication manifest; those three produce them and carry none. The constraint
prose and the step that acts on it both said two.

Modelos 308 and 360 are becoming familiar. They over-declare their grade against
the completeness manifest, they declare a filing calculation class with no
formula, and they render a tree nobody published. Three screens, three
independent conditions, two modelos - which is the argument for the revision
ranking added earlier, arriving from a fourth direction.

### Three figures wrong in one section, and none of them linked

The parallelization section carried the retired field count, a spent ordering
constraint, and a tree count of two where the corpus has three. Each was true
when written. Nothing in the plan connects a figure to the measurement that
produced it, so each aged independently and silently, and each was found only by
someone re-running the measurement by hand.

That is the same defect this campaign screens the registry for, in the plan that
directs the screening: a declaration with no link to its authority drifts, and
nothing reports it.


## The directory's failure figures, re-measured

The last figure in the parallelization section was "twenty-seven of this
directory's thirty-five failures". Measured on 2026-09-03, the whole of
`dev/registry` runs in twelve minutes forty-five seconds: **1,152 passing, 36
failing**.

The failures group cleanly. **Thirty of the thirty-six sit in the four
generated-tree modules** - twenty-six in the tree comparison itself, two in its
publication proof, one in its CLI and one in the modelo 303 envelope proof. The
remaining six are spread one apiece across static inspection, the prose-parser
channel, embed classification, the modelo 200 candidate suite (two) and the
conformance directory.

So the proportion the constraint expressed survives - most of the directory's
failures are one repair - while both of its numbers have moved. **Exactly one
failure sits in the conformance directory**, which is what the third constraint
asserts about the modelo 151 closure test, so that figure holds unchanged.

None of the thirty-six is in a module this campaign has written or edited.

### Counting from progress output gave exactly double

The first attempt at this count read pytest's progress characters, because the
run had been backgrounded and its summary was not yet written. It returned
seventy-two failures. The authoritative summary says thirty-six.

The doubling is the tell: the log held the progress stream twice, and counting
characters across it counted every test twice without anything looking wrong -
seventy-two of fourteen hundred is as plausible a failure rate as thirty-six of
eleven hundred. A count derived from a progress display is not a measurement,
and the summary line exists precisely because the display is not one.

That is the same shape as the truncation rule this audit recorded early - a
measurement piped through `head` or `tail` is not a measurement - reached from a
different direction, and it cost nothing this time only because the real summary
arrived a minute later.


## The "single repair" is three repairs, and two of them are not republication

The parallelization constraint attributes most of this directory's failures to one
repair: republishing generated trees. Reading the assertions rather than the
count, the twenty-six tree failures are three classes with three different
remedies, and only the first is republication.

| class | count | remedy |
| ----- | ----- | ------ |
| manifest-only staleness: records reproduce byte-for-byte and only `_generation.provenance.json` differs | 23 | republish |
| record drift: `0002-record-m347-declarado.toml` differs as well | 2 | **must not** republish |
| enrolled, renders, never committed | 1 | publish, which is not the same act |

**The twenty-three are the constraint's case and it is sound for them.** A
generator refactor invalidates every manifest at once, which is why the
disposition ledger deliberately declines to record them: twenty-three rows saying
"a refactor moved the generator" would be churn rather than explanation.

**The two are modelo 347's revisions and republishing them would ship worse
bytes.** They are exactly the two rows the disposition ledger does carry, whose
reason says the shipped declarado record repeats over binding rows and a fresh
render would not - so the committed bytes are correct and the current inputs are
not. A repair that treated all twenty-six alike would overwrite them.

**The one is modelo 390's `2022`.** Its assertion says it plainly: enrolled with
no committed export tree though the fresh render succeeded, and it names the
remedy - publish through the publication authority, do not retire the row. That
is an independent confirmation, from a failing test rather than from a
filesystem walk, of the unpublished renderable trees measured in the previous
section.

So the constraint's proportion is right and its unit is wrong. Twenty-three of
thirty-six failures share one repair; two share a refusal to apply it; one needs
a different verb. Naming them apart matters because the ledger already exists to
stop exactly the mistake the merged figure invites.


## Two committed export trees have no reproduction gate

`dev/registry/analysis/generated_tree_state.py` classifies every renderable
revision by what repairing it would take, so the three-class split found by
reading a test log stays available without reading one. Across **29 renderable
trees**: 1 reproduces exactly, **25 are manifest-only stale**, 2 carry record
drift, and 1 has never been committed.

The reproduction test reports 26 failures over **27 enrolled targets**. The
difference is the finding: **`m210-2026-y-siguientes` and `m303-2022` are
committed trees that the test does not enrol at all.** Both carry a stale
manifest today, and neither has a gate that would notice if their records drifted
instead.

That is this campaign's most repeated defect, arriving in the generated-tree
tests: an explicit enrolment table is the right design - discovery by convention
hides a typo - and its cost is that a row can be forgotten, which is
indistinguishable from a clean result until something else counts the population
independently.

### The classifier's first version inverted its own advice

Written naively it reported **27 trees as record drift and none as
manifest-only** - the exact opposite of the truth, and advice that would have
blocked the republication of twenty-five safe trees.

The comparison reports a file as differing when its bytes differ, including when
only its serialisation form changed, and carries those separately in
`serialization_only`. Modelo 322's 2023 tree lists six differing files of which
five are reformattings and one is the manifest. Subtracting the serialisation
differences first is what the reproduction test does and what the classifier now
does; without it, every reformatted record reads as drifted filing data.

It was caught by the numbers disagreeing with the test log measured an hour
earlier - 27 against 23 - which is the only reason a plausible-looking census
did not go into this audit as fact.


## The two unenrolled trees now have a gate, and it fails as predicted

`m210-2026-y-siguientes` and `m303-2022` are enrolled in the reproduction test.
Their fields were derived from the registry rather than guessed: the source
reference and design epoch come from the revision's own render inputs, the filing
year from its window, and the period from the convention its siblings use - full
year revisions of modelo 303 carry `4T` and modelo 210 carries `0A`. The
derivation was checked against an existing row first: run against `210/2025` it
reproduces that row's four values exactly, which is what makes it a derivation
rather than a plausible guess.

Both new targets fail, with `['_generation.provenance.json']` and nothing else -
**the manifest-only staleness the classifier predicted for them before they were
enrolled**. That is the report and the test agreeing from opposite directions
about two trees neither had jointly examined.

### On deliberately raising the failure count

This takes the directory from 36 failures to 38, and the two are not new defects.
They were true before and unreported, and they now fail in exactly the way
twenty-five of their peers already fail - the manifest staleness a single
republication clears for all of them at once. The alternative was leaving two
committed trees with no gate at all, where a drift in their RECORDS would have
been silent, which is the condition this whole section exists to remove.

The count is worth stating plainly rather than leaving a reader to discover that
a campaign about declaration integrity added two failing tests. A suite that
reports 38 true failures is in better repair than one reporting 36 while two
trees go unwatched.


## The enrolment gap is now an invariant

With both trees enrolled the populations reconcile: **28 committed trees, all
enrolled; 29 enrolled targets**, the extra being modelo 390's `2022`, which is
enrolled deliberately without a committed tree so that its absence keeps failing
until somebody publishes it.

A gate now holds the direction that matters: every committed export tree has a
reproduction target. It asserts that containment one way only, because the other
direction has a legitimate exception in modelo 390 and a symmetric gate would
have to special-case it - which is how a gate acquires an exemption list and
stops meaning anything.

The suite holds thirty-four gates. This one exists because the gap it closes was
found by accident: a report written for another purpose counted the renderable
population and disagreed with the test's target count by two. Nothing was
watching for that, and nothing would have been.


## One modelo's authored render content is validated by nothing

Applying the technique that found the tree gap - count an enrolment
independently and see whether the numbers agree - to the two directory-based
enrolments in this package.

`dev/registry/render_profiles` and `dev/registry/mappings` each hold seventeen
modelo directories and the two sets are **identical**: no mapping without a
profile, no profile without a mapping. That symmetry is worth recording as a
clean result, since neither is gated and nothing would have reported a
divergence.

Sixteen of the seventeen modelos produce render inputs. The seventeenth is
**modelo 840**, whose single revision `2003-y-siguientes` sits at applicability
grade and declares **no export layout at all** - so the render path raises rather
than loading anything. It nonetheless carries an authored semantic map of four
files (records, two paginas and an anexo) and a numeric-representation profile.

**Nothing validates that content.** A render profile is checked against the
eligible field set of a layout it renders; with no layout there is no check, and
the eligibility and coverage gates never see it. No test names the modelo either
- the three files matching "840" in the test tree match offsets, not a modelo id.
Its correctness is therefore unknown and unknowable from the suite as it stands.

This is the mirror of what this campaign usually finds. The common defect is a
declaration with no authored support behind it; this is authored support with no
declaration in front of it, and it is invisible for the same reason - the gate
that would judge it is only reached through the thing that is missing.

No gate is added. The population is one, and the two available repairs are to
author the export layout the content anticipates or to retire the content, both
of which are decisions about a modelo rather than defects in tooling. A gate
asserting every authored directory belongs to a modelo declaring a layout would
fail on landing with no correction available inside this execution's scope,
which is the shape this campaign has refused twice already.


## Four enrolments cross-checked, and one figure moved because of this work

The independent-count technique applied to every enrolment this package carries:

- **Screens** - gated both ways since the entry-point declaration landed;
  discovery and enrolment agree at eighteen.
- **Generated trees** - the two unenrolled ones are enrolled and the containment
  is gated; twenty-eight committed trees, all enrolled.
- **Render profiles and semantic maps** - seventeen directories each, identical
  sets, one of them (modelo 840) belonging to a modelo that declares no export
  layout and is therefore validated by nothing.
- **The disposition ledger** - its two rows are exactly the two trees measured as
  record-drifting, `347/2011-2024` and `347/2025-y-siguientes`. Verified rather
  than assumed, since the ledger's own header claims the gate refuses in both
  directions and that claim had not been checked against a measurement.

Three of the four agree with their populations. The fourth, modelo 840, is
recorded above.

### A figure in this audit moved, and this work moved it

The exposure correction recorded earlier gave 27,920 filing-exposed findings
across 34 conditions. Re-measured today: **27,922 across 36**, with
wholly-below-filing conditions rising from three to four.

The cause is the capability-continuity screen added since - two new conditions,
two of its three findings in filing-grade revisions, and one condition (a
capability lost together with the grade) that sits wholly below filing. The
earlier table remains accurate as the before-and-after of the correction it
described; this is what the same measurement says now.

Recorded rather than silently left, because an audit that reports a figure and
then changes the thing measured has the same drift problem it screens the
registry for - and this campaign has now found that shape in a plan's step, its
verification prose, its parallelization constraints, and here in its own audit.


## Both provenance screens were missing a citing family

Reading the uncited-manifest population rather than counting it found the same
reference at the top of the list five times over: `aeat-calendario-contribuyente`
for 2022 through 2026, each reported as uncited by eight or nine revisions.

The taxpayer calendar grounds a revision's DUE DATES. No casilla, formula or
binding would ever name it - but a deadline window does, and
`ModeloRevision.deadline_windows` carries `legal_refs` and `source_refs` like any
other authored child. Both screens read seven families and neither read that one.

The omission cuts both ways and the numbers are not small:

| screen | before | after |
| ------ | ------ | ----- |
| manifest references nothing cites | 263 | **159** |
| citing sites reaching outside a manifest | 31,608 | **31,851** |
| modelo-and-reference pairs outside | 414 | **472** |

**One hundred and four of the 263 were manufactured by the screen itself** - a
manifest reference that a deadline window does cite, reported as cited by
nothing. That is worse than under-reporting: it invented work, and the work
looked like the tidiest kind, a declared source nobody uses.

**Two hundred and forty-three citing sites were invisible** in the other
direction, from windows citing an orden or a calendar their manifest does not
apply. A revision whose due-date grounding reaches outside its own manifest read
as consistent.

The two screens were built a fortnight apart and inherited the same family list,
the second from the first. The family list is written out longhand in both, which
is why the omission propagated: a single declaration of what a revision's citing
children ARE would have been wrong once rather than twice, and correcting it
would have been one edit. That is the same finding this campaign has recorded
against the screen entry points, the note identity and the grade ladder, now in
the provenance pair.

Both screens now read the eighth family, and each carries a test naming it: one
asserts no reference a window cites is reported uncited, the other that a
window's outside citations are reported at all.


## The citing families are declared once

`provenance_consistency.citing_children` is now the one statement of what a
revision's citing children are, and the mirror screen consumes it rather than
keeping a second list. Only those two modules walk the families, so the
consolidation is complete rather than partial - checked before doing it, since a
third walker would have made this a rename with a straggler.

The refactor is behaviour-preserving and that is the evidence it was a
consolidation and not a change: both screens report exactly what they reported
before it - 159 uncited references and 31,851 citing sites. A refactor of a
measurement that moves the measurement has done something else as well.

Two properties are asserted rather than assumed. The walked families must equal
the declared `ProvenanceChildKind` vocabulary less `export_field`, which is the
one kind deliberately not walked here because it exists only after derivation
and carries citations copied from a template. And a reference cited by any
walked family must not be reported as uncited by the mirror, which is the
propagated defect stated as an invariant rather than as a fixed instance.

Resolved export fields stay out of the shared declaration and are added by the
screen that needs them, with its reason attached. Folding them in would have
made the list shorter and the mirror wrong: a manifest reference cited only by a
derived field would read as cited when no author ever wrote it.


## A ratio with three answers, written as a bare number in two places

Correcting the citing-site figure after the deadline-window fix meant correcting
the ratio beside it, and the ratio turned out to have three answers:

| quantity | value |
| -------- | ----- |
| findings, one per citing child and kind of reference | 31,851 |
| references outside a manifest | 1,459 |
| citing children summed over those references | 55,065 |
| citing children per reference | **37.7** |
| findings per reference | 21.8 |

The claim both places make - a citation is repeated by N children for every one
place a fix lands - is the fourth row, 38. The plan said nineteen; the index's
own docstring said nineteen; and the correction first written for the plan said
twenty-two, which is the fifth row and counts a child once per KIND of reference
rather than once per reference.

**Three of the four numbers in play were wrong, including the one written to
replace a wrong one.** The reason is that "the repetition" is ambiguous between
three ratios and none of the three sites said which it meant, so each author
computed whichever was to hand and none of them disagreed visibly.

Both places now state the definition with the figure. That costs a sentence and
removes the ambiguity that produced four different numbers for one idea - the
same remedy this campaign applies to the registry, where a value without its
units is exactly this defect in a declaration rather than in prose.


## The reference worklist, re-measured, and a second annual series

The reference-scope figures were measured before deadline windows joined the
walk and are the ones somebody would act on, so they are re-measured here:

| figure | before | after |
| ------ | ------ | ----- |
| modelo-and-reference pairs outside a manifest | 414 | **472** |
| absent from every revision of their modelo | 213 | **224** |
| cited by exactly one child | 17 | **55** |

The single-child population more than tripled, and **38 of the 55 are cited by a
deadline window** - the family that was missing. The remainder divide as ten
formulas, three casillas, three parameters and one binding.

Those 38 are the same shape as the seventeen read earlier, arriving through a
different family. Modelo 100's deadline windows cite, year by year, the campaign
orden that sets that year's filing period at article 8: `orden-hac-248-2021` for
2020, `orden-hfp-207-2022` for 2021, `orden-hfp-310-2023` for 2022,
`orden-hac-265-2024` for 2023. Each window names the orden that governs its own
due date, which is the most precise grounding a deadline could carry, and each
modelo 100 manifest omits it.

That is the second independent series pointing the same way. The earlier one was
the estimacion objetiva formula citing its year's orden; this is the deadline
window citing its year's campaign orden. Both are exact, both are single-child,
and both sit outside a manifest - so the reading recorded earlier holds and now
rests on two populations rather than one: **where a single child cites something
its manifest omits, the manifest is the under-declared side.**

It also means the earlier conclusion was reached on a population missing its
largest contributor. Seventeen single-child references were read and found
sound; thirty-eight more existed and were invisible because a citing family was
not walked. The conclusion survived the population more than tripling, which is
worth more than the original reading was.


## The schema declares nineteen authored families; the provenance walk covers eight

The deadline-window omission was found by reading a population. Asking the
question systematically - which of a revision's attributes carry citations at
all - answers it far more broadly, and the answer is not one missing family.

`ModeloRevision` annotates **nineteen** fields with `SCHEMA_FAMILY`, which is the
registry's own declaration of what an authored family is. The shared
`citing_children` walk names **eight** of them. Nine of the eleven unwalked
families carry citations in the corpus today:

| family | outside-manifest citations it would add |
| ------ | --------------------------------------- |
| `constructs` | 969 |
| `extraction_profiles` | 191 |
| `dependency_classifications` | 169 |
| `verification_expectations` | 164 |
| `verification_predicates` | 105 |
| `filing_schedules` | 57 |
| `projection_endpoints` | 12 |
| `live_cross_references` | 10 |
| `workbook_parity_refs` | 7 |

**They would also clear 141 of the 159 remaining uncited findings** - eighty-nine
per cent of that population is a manifest reference some unwalked family cites.

These are authored, not derived. `projection_endpoints` has its own authored TOML
files under each revision directory, and it carries the same `SCHEMA_FAMILY`
annotation the walked eight carry; so does `constructs`. The distinction the walk
already draws - authored families in, resolved export fields out - puts all nine
firmly on the authored side.

### The fix is to derive the walk, not to extend the list

Adding nine names would leave the same defect in place: a list of families
restated in the tooling, one edit behind a schema that declares them. The
correction is to enumerate the `SCHEMA_FAMILY` annotation, so a family added to
the registry is walked without anyone remembering to add it - which is the
remedy this campaign has applied to the screen entry points, the note identity,
the grade ladder and the citing families themselves, each time after the restated
copy drifted.

Recorded rather than done. The change moves both screens substantially - the
mirror's population falls by nearly nine tenths and the citing screen gains
sixteen hundred citations - and a change of that size wants its own verification
rather than the tail of an iteration. It is the largest tooling finding this
campaign has made, and the four preceding corrections to these two screens were
each a smaller instance of it.


## The walk now follows the schema, and three more assumptions failed on the way

`citing_children` enumerates the `SCHEMA_FAMILY` annotation instead of naming
families. Seventeen families are walked for a modelo 303 revision where eight
were before, and both screens move accordingly:

| figure | eight families | derived |
| ------ | -------------- | ------- |
| citing sites reaching outside a manifest | 31,851 | **33,385** |
| references outside a manifest | 1,459 | **1,555** |
| modelo-and-reference pairs | 472 | **520** |
| manifest references nothing cites | 159 | **57** |

**The estimate was the right order and the wrong number.** It predicted 1,684
citations added and 141 uncited findings cleared; the change delivers 1,534 and
102. The estimate counted distinct references per revision while the screens
count one finding per child and reference kind, and it could not include two
families whose shape broke the probe. An estimate that agrees with the outcome
to within an order is worth making; quoting it as the outcome would not have
been.

### Widening the walk broke three assumptions the narrow list never tested

Each was invisible while the eight hand-picked families all happened to satisfy
it, and each is a real fact about the registry rather than a defect:

- **A family may carry one reference kind and not the other.** An applicability
  rule cites law and names no source. Both readers assumed both fields existed.
- **A family may not name its members.** A verification predicate carries no
  `id`. Children without one are now identified by family and position, which is
  honest about being a location; inventing an id would have put a value in a
  finding that no declaration carries.
- **A family may be empty in a given revision.** The walk reports it as absent
  rather than present-and-empty, so a screen counting families sees what the
  revision actually declares.

The eight families were not chosen to avoid these - they were chosen because
somebody listed the obvious ones, and the schema had nine more all along. That a
list of eight satisfied three assumptions the full nineteen do not is the clearest
argument in this campaign for deriving a walk from its declaration: the hand-list
was not merely incomplete, it was uniform in ways the real population is not, and
the uniformity read as a contract.


## A figure restated three times, now written with its provenance

The provenance repetition ratio has been corrected three times in three
iterations: nineteen, then twenty-two, then thirty-eight, and the last two
corrections were mine. The registry did not change. What changed is that the
screen twice learned to read families it had been skipping - deadline windows,
then the nine the schema declares and the walk omitted - so the population it
measures grew twice underneath a sentence that quoted a number.

Both places carrying it now state three things instead of one: the figure, the
definition it answers to, and the date and command that produced it. On
2026-09-04, `python -m dev.registry.analysis.provenance_consistency` reports
59,184 citing children over 1,555 references outside a manifest, which is 38 per
reference; its own finding count is 33,385, which counts a child once per KIND
of reference.

The point is not the number. It is that "nineteen", written without a
definition, a date or a way to re-derive it, survived three corrections of the
thing it described - and each time a reader had no way to tell a figure that
still held from one that had been overtaken. This audit has now recorded that
same failure in a step, a verification criterion, three parallelization
constraints, a screen's docstring and its own pages; the remedy has been the
same every time, and applying it to prose costs a sentence.


## Every filing-grade revision carries a declaration contradiction

Re-measuring after the walk began following the schema, on 2026-09-04:

| figure | eight families | derived |
| ------ | -------------- | ------- |
| filing-exposed findings | 27,922 | **29,502** |
| filing-grade revisions carrying at least one condition | 67 of 69 | **69 of 69** |
| conditions on the worst revision, modelo 200 `2025-y-siguientes` | 7 | 7 |
| conditions on modelo 347 `2011-2024` | 6 | 5 |

The two revisions that had been clean are clean no longer, and nothing about
them changed: the walk that judges them widened. That is worth stating carefully,
because "every fileable revision now carries a contradiction" sounds like a
regression and is not one - it is the same corpus, more completely read.

Modelo 347's count fell while the population grew, which is the other direction
and equally uninteresting on its own: one of its conditions cleared because a
manifest reference it was reported as failing to cite turned out to be cited by a
family the walk had been skipping.

Both movements say the same thing about the figures this campaign has been
publishing. They measured what the tooling looked at, not what the registry
declares, and the gap between those was nine families wide until this week.


## The other hand-written list is complete

Having found one hand-written list of schema fields to be eight of nineteen, the
obvious question is whether the package's other one is any better.
`YEAR_LEVEL_TEMPORAL_SITES` names six dotted paths that state which years a
revision serves. Enumerated from the schema instead - every field on a revision
or one level below it whose name carries "year", plus `valid_from` and
`valid_to` - the answer is **exactly those six**. No gap.

A second pass looked for year-stating fields under other names, since the first
check and the hand-list could share a blind spot by both keying on the word
"year". The only near-miss is `relations.source_period_offset_from_target`,
which states how many periods separate a relation's source from its target
rather than which years the revision serves. It is a temporal declaration and it
is correctly outside this screen's stated boundary, which the docstring already
draws at year-level claims.

This is the result that makes the citing-families finding worth trusting. A
campaign that suspects every hand-written list and then finds one incomplete has
demonstrated a prior, not a defect. Applying the same check to the other list and
finding it sound is what separates the two - and it took one command, which is
the argument for asking rather than assuming in either direction.

The list keeps its hand-written form. It is complete, its docstring states the
boundary it draws and why, and deriving it would mean encoding "states which
years a revision serves" as a rule over field names - which is the heuristic this
package has refused repeatedly, and which would be less trustworthy than the six
names it would replace.


## What the nine newly-walked families actually cite

With the walk following the schema, twenty families report a citation reaching
outside a manifest. The eleven that were invisible until this week contribute
1,534 findings between them:

| family | findings |
| ------ | -------- |
| `projection_endpoints` | 760 |
| `constructs` | 214 |
| `application_links` | 184 |
| `verification_predicates` | 132 |
| `verification_expectations` | 74 |
| `dependency_classifications` | 60 |
| `applicability` | 33 |
| `filing_schedules` | 32 |
| `extraction_profiles` | 23 |
| `live_cross_references` | 15 |
| `workbook_parity_refs` | 7 |

The eight already walked still dominate - casillas alone carry 21,596 - which is
why the omission was survivable for as long as it lasted: the shape of the
population did not change, only its completeness.

### The dangling-reference result survives the population growing

An earlier section established that nothing in the provenance population is a
dangling reference: every one resolved in its catalogue. That was measured over
414 modelo-and-reference pairs. The population is now **520**, a quarter larger
and drawn from eleven families that measurement never saw, and it still holds -
**zero pairs fail to resolve**.

That is worth re-running rather than assuming, because a negative result is
exactly the kind that quietly stops being true when its population changes, and
this one had grown by a quarter through a route nobody checked it against. The
top construct citation, `lirpf-cuota-chain-authority`, is a declared authority id
rather than a law article and resolves like the rest - so even the reference that
looks least like a legal citation is catalogued.


## The manifest is a summary of its children's citations, not a constraint on them

An earlier section concluded that a manifest and its children's citations "relate
in both directions" and that "the corpus was not authored to [either contract] in
either direction". That was measured with seven citing families. With all of
them, the relationship is far more one-sided, and the earlier reading was wrong.

Across 128 revisions the four cases partition cleanly:

| relationship | revisions |
| ------------ | --------- |
| manifest is a strict subset of what children cite | 65 |
| the two agree exactly | 37 |
| manifest carries references nothing cites, and nothing more | 14 |
| each side has something the other lacks | 12 |

**One hundred and two of the 128 have a manifest contained in what their children
cite**, and thirty-seven of those are exact equality. Only twenty-six carry
anything in the manifest that no child cites, where the earlier figure suggested
sixty-nine did.

So the corpus was authored to a contract after all, and it is the opposite of the
one the citing-side screen tests. That screen asks whether a child stays INSIDE
its manifest, which almost no revision satisfies; the corpus behaves as though
the manifest is a SUMMARY of what its children cite - a subset, often the whole
of it, occasionally with a stray addition.

That reframes the open decision. The question is not "which containment did the
authors intend", which looked unanswerable when both directions had large
populations. It is whether the manifest is meant to be the complete union of its
children's citations - which thirty-seven revisions already achieve and
sixty-five approach from below - or a deliberately shorter statement of the
authorities that govern the revision as a whole.

The earlier conclusion was reached honestly on the population then visible, and
it is wrong for the same reason several figures in this campaign were: the walk
that produced it saw eight families of nineteen. A conclusion drawn from a
partial walk is not merely imprecise; this one pointed the opposite way.


## The reference worklist, measured on the complete walk

This worklist has been published three times on three different populations. The
figures below are the first measured with every family the schema declares, taken
on 2026-09-04 from `python -m dev.registry.analysis.provenance_consistency`:

| figure | 8 families | + deadline windows | complete walk |
| ------ | ---------- | ------------------ | ------------- |
| modelo-and-reference pairs | 414 | 472 | **520** |
| absent from every revision of their modelo | 213 | 224 | **256** |
| absent from only some | 201 | 248 | **264** |
| cited by exactly one child | 17 | 55 | **38** |
| cited by a hundred children or more | 99 | - | **104** |

**The single-child population moved in both directions and ended below its
middle value**, which is the figure worth understanding. Widening a walk adds
references - families that cite something their manifest omits - and
simultaneously removes references from the single-child bucket, because a
reference thought to have one citer turns out to have several once the families
citing it are read. The first widening added more than it moved; the second moved
more than it added.

The 38 divide by citing family as 14 deadline windows, 7 constructs, 6
applicability rules, 3 casillas, 2 parameters and the remainder singly. That the
deadline windows still lead is consistent with the two annual series read
earlier: a window cites the orden governing its own year, and no other child has
reason to name it.

This is the last of the provenance figures to be re-measured on the complete
walk. Every one of them moved, three of them twice, and none moved because the
registry changed.


## Reading the misnamed revisions: one name hides a fourteen-year gap

The revision-name screen reports seven findings on filing-grade revisions, and
the plan already carries a rename Step for each of the three that matter -
modelos 151, 720 and 322. Reading them rather than counting them adds one fact
those Steps did not have.

**Modelo 322's `2008-2022` serves only 2022.** Its `valid_from` is 2022-01-01
and its `valid_to` is 2022-12-31. The modelo's other revisions open in 2023,
2024 and 2026, so its earliest coverage of any kind begins in 2022 - and **no
revision serves any year from 2008 to 2021.** The name is the only thing in the
registry claiming those fourteen years.

That changes what the rename is. Correcting the name to `2022` does not lose
coverage, because there is none to lose; it removes the appearance of coverage.
Whether those years should be served is a separate question the registry cannot
answer, but a reader looking for modelo 322 in 2015 currently finds a revision
directory named for that year and would have to read `valid_from` to learn it
does not apply.

The other two are narrower and point the opposite way - a revision serving more
than its name claims. Modelo 151's `2025-y-siguientes` opens in 2023, so 2023 and
2024 are served by a directory named 2025; modelo 720's `2013-y-siguientes` opens
in 2012. In both, selecting by name understates reach, which is the safer
direction and is why the screen's docstring says it attracts less attention.

Three of the seven are modelo 369's `esquema-exterior`, `esquema-importacion` and
`esquema-union`, which carry no year token because they are not temporal at all -
the non-temporal scheme axis sitting in the revision slot, which the plan already
tracks as its own Step.


## No modelo has a hole in its coverage, and modelo 322's is not one

The previous section came close to calling modelo 322's fourteen unserved years a
coverage gap. Measured across the corpus, that framing is wrong and the
distinction matters.

**No modelo has a year inside its own span that no revision serves.** Thirty-three
modelos carry a closed window and every one of them has more than one revision;
between them they serve 199 distinct modelo-years, and the interior of every
modelo's span is continuous. Where one revision closes, the next opens.

Modelo 322's 2008 to 2021 is not interior. Its earliest coverage of any kind
begins in 2022, and years before a modelo's first revision are outside the
registry's reach rather than missing from it - the corpus's earliest coverage
runs from 2003 to 2026 depending on the modelo, and nothing says every modelo
must reach back to the same year.

So the finding stands but its name changes. It is not a hole in coverage; it is a
**revision directory named for years the registry does not claim to cover**, and
the only thing asserting those years is the name. That is a naming defect, which
is what the rename Step already calls it, and the addition this measurement makes
is the certainty that renaming loses nothing - there is no coverage behind the
name to preserve.

The check was proved non-vacuous before its zero was believed: thirty-three
modelos examined, all multi-revision, 199 served years between them. A continuity
check that quietly examined nothing would report exactly the same zero.
