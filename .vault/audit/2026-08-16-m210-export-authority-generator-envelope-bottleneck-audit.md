---
tags:
  - '#audit'
  - '#m210-export-authority'
date: '2026-08-16'
modified: '2026-08-18'
body_schema: 'body-v1'
body_hash: 'sha256:33711a8f8884c8ac95b9c67741e3a73636bb4ec5ea0d2269670e124fe56b7f59'
related:
  - "[[2026-08-16-m210-export-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---

# `m210-export-authority` audit: `Per-modelo envelope contracts block ten of thirteen remaining generatable revisions`

## Scope

Every modelo revision that declares no export layout, is not operator-scoped-out, is not
held by the in-flight Modelo 303/390/200/220/222 generator work, and declares at least
one record-design source with a `record_design_epoch`. Measured by loading the registry
tree and parsing each design through the shipped parser. Modelo 210 is excluded: its
export tree was generated during this campaign leg and is committed.

The question asked was narrow and mechanical: which of these can be generated today, and
what exactly stops the rest.

## Findings

### Modelo 210 was the only envelope-free target, and that is why it generated

Of thirteen candidate revisions, exactly one carried neither a variable envelope nor an
auxiliary envelope header: Modelo 210. Its two fixed records generated without touching
any envelope mechanism. That is not a property of Modelo 210 being simple; it is the
single reason it was reachable, and it means the Modelo 210 result does not generalise on
its own.

### Ten revisions are blocked on a variable-envelope composition contract that recognises only Modelo 303

`render_complete_export_tree` refuses any joined design carrying a variable envelope
unless `joined.m303_variable_envelope` is populated, and `_join_record_design_semantics`
populates that field only for a record whose `record_identity` equals the literal
`DP30300`. Every other modelo's envelope record therefore cannot be composed, whatever
its shape.

The blocked set, with the envelope record each declares: modelo 036 revision
`2025-02-03-y-siguientes` (`Pag. 0`), 151 `2025-y-siguientes` (`M15100`), 202
`2019-2022`, `2023-2024` and `2025-y-siguientes` (`dr M202 (0)`), 322 `2008-2025`
(`DR32200`), 353 `2008-2025` and `2026-y-siguientes` (`35300`). Modelo 202's envelope
record carries thirteen fields, the same count as Modelo 303's.

### Modelo 232 is blocked by two cosmetic differences in a pinned content tuple

Modelo 232's `DR23200` is an auxiliary envelope header structurally identical to Modelo
390's page zero: thirteen fields, no declared total, terminal extent exactly 328 bytes,
and its fields align one-to-one with all thirteen declared header roles, ending
`auxiliary_closing_tag`. It nonetheless fails classification, so the generator reaches
`_require_exact_record_geometry` and refuses the record for having no declared total.

The rejection comes from `_validate_auxiliary_header_content`, which compares the sheet's
content cells against `_M390_AUXILIARY_HEADER_CONTENT`. The two designs differ in exactly
two respects, neither of which is a wire fact:

- Index 1 is the modelo's own constant, `Constante "390"` against `Constante "232"`.
- Indices 3, 8 and 10 carry AEAT's footnote marker in the CONTENT cell on Modelo 390
  (`Nota 2`, `Nota 1`, `Nota 1`) while Modelo 232 leaves those cells empty and puts the
  same footnote in the description instead (`Versión del Programa (Nota 1)`,
  `NIF Empresa Desarrollo (Nota 1)`).

The geometry check, the role check and every emitted literal already agree. The footnote
placement varying between designs is independently recorded elsewhere in this project as
a known trap for anything keyed on the string `Nota 1`.

### The developer identity block recurs here, unchanged

Modelo 232's header carries the `@93+4 Versión del Programa` and `@101+9 NIF Empresa
Desarrollo` pair, making it a twentieth registry revision short exactly those two
positions. The semantic map authored in this leg names both slots with producer keys
(`entidad_desarrolladora.version_programa`, `entidad_desarrolladora.tax_id`), which
records where the values belong without inventing them. What value Cadrumo emits there
remains the standing owner decision it already was; nothing here changes it.

### Modelo 232's map and profile are authored and validated, and are not the blocker

Both artefacts exist and pass `validate_semantic_map` against the hash-pinned design and
the real revision: three records, 263 entries, exact anchor bijection, every casilla,
binding, legal and source reference resolving. Ownership was derived rather than guessed
— the revision's own bindings encode the byte range they were authored against, so 167
anchors claimed a binding by exact range and 50 more resolved to the casilla the
binding's suffix names, leaving 19 hand-authored, 20 literals transcribed from the
design's own Contenido cells and 7 fillers the design itself declares reserved.

### CORRECTION: two of the three PDF designs are generatable, and the exclusion was mine

An earlier pass in this same campaign recorded Modelos 184, 360 and 840 as
"acquisition gaps" because their record designs are `.pdf` rather than workbooks.
That was wrong, and the error was in the census, not in the registry: the census
filtered candidates on a `.xls/.xlsx/.xlsm` suffix, which is a constraint I
introduced. The shipped parser dispatches on content and exports
`extract_record_design_pdf` alongside the workbook readers.

Measured through the real parser and then through `load_record_design_intermediate`:

- Modelo 184 revision `2015-y-siguientes` (`aeat-dr-184-2025`) reads COMPLETE: three
  records, 132 anchors, no variable envelope, no auxiliary header. The revision
  already declares the design among its own source_refs, and carries 6 casillas and
  4 bindings.
- Modelo 360 revision `2010-y-siguientes` (`aeat-dr-360-2010`) reads COMPLETE: two
  records, 262 anchors, no envelope, no auxiliary header, 2 casillas and 5 bindings.
- Modelo 840 (`aeat-dr-840`) is the only genuine gap of the three, and it is a
  PARSE gap rather than an acquisition one: the read is incomplete with one
  unidentified record body beginning at source row 246, undeclared, so
  `require_complete` correctly refuses it.

AEAT publishes all three as PDFs on its own Diseño de registro index, so there is no
workbook edition to acquire and nothing to fetch. 184 and 360 need only a semantic
map and a render profile, exactly like Modelo 210 did, and neither depends on the
envelope work this audit's other findings are blocked behind.

The general lesson is the one this audit already makes elsewhere and then fell for:
a census that filters on a proxy reports the proxy, not the property. Coverage was
read off a filename suffix instead of off the parser.

### 184 and 360 are blocked on CASILLA authoring, not on the export mechanism

Correcting this audit's own earlier framing a second time. Having removed the
suffix-filter error, the natural next reading was "184 and 360 need a semantic map
and a render profile, exactly like Modelo 210 did". Measured against the design,
that is wrong too, and the difference matters because it is the difference between
a day's mapping and a grounded casilla-authoring campaign.

Modelo 184 revision `2015-y-siguientes` authors SIX casillas. Its official design
declares 132 anchors across three records, of which 117 carry no casilla, no
binding, no literal and no filler. The bulk sits in the `Tipo 2 - Registro De
Rentas` record: 78 positions enumerating the attributed-income breakdown --
ingresos íntegros, gastos, renta atribuible, porcentaje de reducción, renta
atribuible con derecho a reducción, ganancias y pérdidas, régimen de determinación
de rendimientos, tipo de actividad, epígrafe IAE, valor de adquisición, fechas, and
the cesionario identity. Every one is a value the entidad declares, so each needs a
casilla carrying its own grounding under Ley 35/2006 arts. 88 and 89, not a
producer key and not a mapping decision.

A semantic map cannot be authored ahead of those casillas: the map binds an anchor
to a canonical owner, and for these anchors the owner is a casilla that does not
exist yet. Authoring the map first would force the alternative -- inventing
producer keys for what are plainly declared casilla values -- which would put the
attributed-income breakdown outside the casilla provenance chain that carries
`legal_refs` to the operator.

Modelo 360 is the same shape at a smaller scale: two casillas against 262 anchors,
with five `refund-row` bindings covering the repeated detail.

So the remaining per-modelo cost is NOT uniform, and the campaign should not plan it
as though it were. Modelo 210 was cheap because its 28 numbered casillas were
already authored and only the party surface was missing. Modelos 184 and 360 are
expensive for the opposite reason: the mechanism is ready and the tax content is
not.

### Modelo 184's casillas are authored; it is now blocked on PDF group-header nesting

Sixty-six casillas were authored for Modelo 184 revision `2015-y-siguientes` from the
bundled design's own printed byte ranges, taking its casilla coverage of the design
from 5 anchors to 53. That closes the tax-content gap this audit recorded above:
its only remaining blocked family is `export_layouts`.

It still cannot generate, for a different and precisely located reason. The
export-tree geometry contract requires each record's fields to be strictly
contiguous from offset 1 and names an out-of-order offset "an overlap" defect.
Modelo 184's parsed design carries five anchors that overlap their own neighbours,
and all five are GROUP HEADERS whose bytes their leaf fields already cover:
ordinals 12 (`@145+2`) and 15 (`@147+9`) on the declarante record, and 17
(`@117+8`, the fecha de adquisición over its año/mes/día parts), 33 (`@266+130`,
the actividades-económicas gasto block over its eleven categories) and 57
(`@397+101`, the capital-inmobiliario block over its ten) on the entidad record.

The workbook parser already has the mechanism for exactly this: `RecordDesignField`
carries a `components` tuple, documented as additive so that "the parent's
offset/length continue to span the WHOLE group" and geometry consumers see only
top-level spans. The PDF path does not populate it, so a group header arrives as a
sibling of its own leaves instead of as their parent.

Measured for contrast, so the scope is not overstated: Modelos 210, 232 and 360 all
parse with ZERO overlapping anchors. This is not a general PDF-design problem and
not a Modelo 184 authoring problem -- it is five anchors in one design needing the
nesting the workbook path already performs.

Modelo 360 is therefore the cheaper of the two: geometrically clean, needing only
casillas (it authors 2 against 262 anchors), a semantic map and a render profile,
with no parser change and no dependency on the envelope work.

### Modelo 360 needs the deferred address vocabulary, not casillas

Modelo 360's remaining surface is party and address, not tax content, so the casilla
authoring that Modelo 184 needed does not apply to it. Its `Pág. 1` spends anchors
16 to 30 on a Spanish-coded address -- tipo de vía, nombre de la vía pública, tipo
número, número de casa, calificador, bloque, portal, escalera, planta, puerta,
complemento, localidad, código postal, municipio, provincia -- and anchors 31 to 34
on a foreign address in free text. Its detail page is the repeated operation block
its five `refund-row` bindings already cover.

That is component-for-component the pair of shapes the Modelo 210 record already
declares, where the ADR accepted the duplication as known debt and named it "the
natural first candidate for a later consolidation into a canonical core address
type". Modelo 360 is that second consumer arriving, and it makes the trade concrete:
minting a third and fourth copy under an `iva.` or `m360.` scope would put the same
fifteen AEAT components in the enum three times over.

The consolidation is now the cheaper path, and it is a decision rather than a
transcription: lift one canonical Spanish-coded address vocabulary and one foreign
vocabulary into core, re-point Modelo 210's `irnr.representante.domicilio.*` and
`irnr.inmueble.situacion.*` and `irnr.contribuyente.foreign_address.*` at them, and
give the adapter-side `CensalDomicilio` the same treatment the original ADR
deliberately left out of scope. It should be ruled on before Modelo 360's semantic
map is authored, not after, because the map binds anchors to whichever vocabulary
exists at the time.

### Modelo 360's blocker is its Contenido column, and it is NOT a general PDF gap

Modelo 360 now has everything the registry side needs: 146 bindings covering both
repeated blocks, 70 party producer keys, 11 casillas, an applicability rule, and a
semantic map that validates at 262 entries with an exact bijection. Its render
profile authors 28 rules. Generation still refuses, at the first literal.

The cause is that the PDF extractor recovers this design's POSITIONS but not its
Contenido column. Measured across four designs, content is populated on:

- `aeat-dr-210-2022` (workbook): 81 of 167 fields, 48 per cent
- `aeat-dr-232-2018` (workbook): 138 of 250, 55 per cent
- `aeat-dr-184-2025` (PDF): 128 of 132, 96 per cent
- `aeat-dr-360-2010` (PDF): 5 of 262, 1 per cent

So this is NOT "PDF designs lose their Contenido" -- Modelo 184's PDF carries it
better than either workbook. It is one design's layout the extractor does not read
the column from, and the earlier framing in this audit that generalised it to PDFs
was wrong.

Two consequences follow, and the second is the one that matters. Every generator
contract that cross-checks a declared value against official content behaves
differently for this design: `_literal_derivation` refuses because it cannot find
the constant the description plainly states, and `_numeric_derivation` would refuse
for the same reason. Less visibly, render-profile eligibility treats blank content
as "the design leaves this unstated", so Modelo 360 reports 28 eligible anchors that
are eligible only because the column was not read. A profile authored against that
set records reviewed policy decisions for slots the design may in fact state --
which is a quieter defect than a refusal, because it produces a profile that looks
complete.

The fix is in the PDF extractor, not in either modelo's authoring, and it should
land before Modelo 360's render profile is trusted. Modelo 184 is unaffected by
this one; its own blocker remains the five overlapping group-header anchors.

### The 184 group-header fix is one line, with a measured 46-anchor blast radius

`_matching_component_parent_index` nests a desglose under its parent only when the
component carries a DOTTED ordinal (`19.1` under `19`). That discriminator exists
for a real reason -- Modelo 303's `14bis` has no dot and is a genuine peer, not a
component of `14` -- but it means a design that desglosa with plain sequential
ordinals never nests, and its group headers arrive as siblings of their own leaves.
That is exactly Modelo 184: its five headers overlap the bytes their leaves cover,
and the export geometry contract refuses the overlap.

The candidate relaxation is to nest on STRICT span containment as well: a field
whose span falls inside the immediately preceding field's, and is strictly shorter.
Strictness matters -- an equal span is a duplicated row rather than a desglose, and
Modelo 100 carries several, which an inclusive test wrongly claimed (12 of the
first measurement's 58 hits vanished once the test required a proper subset).

Measured across all 121 bundled designs, the relaxation would reclassify 46 anchors
in 9 designs: `enrolled-modelo-038-layout` 11, `aeat-dr-280-2022` 9,
`aeat-dr-165-2026` 6, both Modelo 184 editions 5 each, `aeat-dr-181-2022` 4,
`aeat-dr-187-2022` 4, `aeat-dr-188-2023` 1, `aeat-dr-349-2020-current` 1. Every
sampled case is a clean parent/component pair.

This is NOT a change to make unilaterally, and the blast radius is why. Modelos 187
and 188 are operator-scoped-out of registry authoring, and 038 likewise; altering
how their designs parse changes top-level field counts for modelos nobody is
currently authoring and cannot easily verify. It belongs to whoever owns the
record-design parser, with the nine designs re-checked after.

### CORRECTION: three of the "blocked" modelos are complete at their declared grade

This audit's candidate set was built from "declares a design and no export layout",
which conflates two different states. A revision declaring
`authority_grade = "applicability"` makes a scheduling-reach claim only; the grade
validator returns immediately for it, because there is no coverage claim to outrun.
Such a revision is a deliberate backlog entry that VALIDATES, not an incomplete one.

Surveying the candidate set by grade:

- `036/2025-02-03-y-siguientes`, `763/2011-y-siguientes` and `840/2003-y-siguientes`
  are at `applicability`. All three validate. Raising any of them to filing grade is
  a scope decision about authoring that modelo's content, not a defect to repair,
  and the grade docstring is explicit that the rung must not be read off the content
  a revision currently has.
- Several candidate modelos already carry an export layout on a SIBLING revision
  that the "no export layout" filter hid: `151/2015-2022` has one and 541 casillas,
  `322/2026-y-siguientes` has one and 222 casillas. Their unlayouted siblings
  (`151/2025-y-siguientes` at 8 casillas, `322/2008-2025` at 10) are the real gaps,
  and they are much smaller than a from-scratch modelo.

The genuinely incomplete filing-grade revisions without a layout are therefore:
`151/2025-y-siguientes`, `184/2015-y-siguientes`, `202` (three revisions),
`232/2016-2017`, `322/2008-2025`, `353` (two revisions) and `360/2010-y-siguientes`.

This is the fifth correction this campaign has had to make to its own measurements,
and they share one shape: a census keyed on a convenient proxy -- a filename suffix,
a missing directory, an absent layout -- reports the proxy rather than the property.
Grade is declared data and was available the whole time.

### STATUS: the variable-envelope blocker has been resolved

This audit's headline finding -- ten revisions blocked because the composition
contract recognised only Modelo 303's `DP30300` -- no longer holds. The contract is
now modelo-neutral: `VariableEnvelopeSemantic.record_identity` is a plain string
the reviewed map declares, `JoinedRecordDesign` carries a
`variable_envelope_contract` rather than an m303-specific field, the compiler is
`compile_filing_envelope_definition`, and no `DP30300` literal remains in either
the join or the export renderer. The generator's refusal now reads on the presence
of a contract, not on the identity of one modelo's record.

Modelos 151, 202, 322 and 353 are therefore unblocked at the MECHANISM level. What
each still needs is ordinary authoring: a semantic map declaring its envelope's
thirteen prefix anchors, body, closer and total; whatever bindings its repeated
blocks require; and a render profile. Modelo 353's `2026-y-siguientes` is the
cheapest of them -- two fixed records at 134 and 9 anchors plus the 13-anchor
`35300` envelope, against 13 authored casillas -- and its bulk is a repeated
entidad-del-grupo list, which is the same binding-row shape Modelos 232 and 360
already use.

Recorded as a status change rather than left standing, because the earlier finding
is what a reader would otherwise plan around.

## Recommendations

Generalising the auxiliary header is the smallest change with a real payoff and should be
taken first: replace the pinned modelo constant with the sheet's own modelo and treat a
footnote marker in a content cell as equivalent to an empty one, keeping the geometry,
role and literal checks exactly as they are. That is a change to a validator the proven
Modelo 390 contract depends on, so it belongs to the campaign that owns that contract and
must land with a proof that Modelo 390 still classifies unchanged and that a non-header
sheet still refuses. Modelo 232 generates the moment it lands, both revisions, with the
map and profile already committed.

Generalising the variable-envelope composition is the larger and more valuable move,
unblocking ten revisions across five modelos. It is squarely the in-flight campaign's
mechanism and should not be attempted alongside it; the finding is recorded here so the
sequencing is deliberate rather than discovered again.

Neither recommendation should be actioned by loosening a refusal without the
corresponding proof. The refusals in question are the ones that stop a structurally thin
fixed-width return being written behind a valid digest, which is the failure this whole
generator exists to prevent.

## Modelo 353: the first envelope-bearing modelo outside 303, and what it found

The variable-envelope generalisation landed, so Modelo 353 was authored end to end
against it: both revisions now generate, validate and reproduce byte-for-byte, and both
are enrolled in the one parameterised generated-tree gate. Authoring it surfaced four
defects in shared generator machinery, each of which would have blocked the NEXT
envelope-bearing modelo identically.

### The envelope sheet was joined to a body record

`_validate_export_layout_coverage.py:804` decided the envelope branch AFTER the content
join. The join matches on declared constants, and an envelope opens with the same `<T`
and modelo bytes its page records do, so it agrees with every one of them. With a single
body record that agreement is trivially a unique maximum, and the envelope was "joined"
to a page whose fields sit at unrelated offsets - reporting the page's identificación
block as intruding on the envelope's own reserved run, at 82.2% coverage.

Modelo 353's 2008-2025 edition, which has exactly one body record, is what exposed it.
The 2026 edition passed only by luck: with two body records the agreement TIED, the join
failed, and the weaker any-record fallback covered the envelope's bytes from page 1.
A passing verdict reached through a tie is not a verdict.

The fix decides `is_envelope_sheet` before the join and skips the join entirely for it.
Proven by two runtime probes from outside the repo: the envelope sheet never reaches the
join, and emptying the bytes the envelope branch reports as written reds the gate with
the gap attributed to the envelope itself.

### Render-profile evidence could not read a legacy `.xls`

A `Width17MembershipRule` REQUIRES `OfficialSourceEvidence` by schema, and the evidence
resolver accepted only OOXML. AEAT still publishes many diseños as pre-OOXML `.xls`, and
the record-design parser already reads them through xlrd - so every such modelo's render
profile was unauthorable while its design parsed perfectly. The resolver now dispatches
on suffix and reads the same binaries the rest of the pipeline does.

### Every signed width-17 amount was unrepresentable

`_profile_width_17_derivation` passed `decimals=rule.decimal_digits` unconditionally,
while the schema refuses a field declaring decimals beside any data_type but `decimal`.
A signed rule maps to `money`, so EVERY `N` width-17 amount raised at build. Modelo 200's
committed profile carries 45 such fragments and has no generated tree yet, so nothing had
executed the path.

### One closed value set, a third spelling

`1 -Sí, 2 -No` - no space after the dash - fell outside the dash-enumeration reader and
refused as ambiguous content. Widened to admit no space while still refusing a digit on
the dash's right, because `01-12` is a RANGE and reading it as a set would emit two
members where the design means twelve. Both directions are gated.

## A recargo omission carried from Modelo 322 into Modelo 353

Modelo 322's ledger-direct `iva.cuota-devengada-total` sums the general, reducido and
super-reducido repercutido tiers plus the autorepercutido cuota, and NO recargo de
equivalencia tier. `aeat-calculation-grounding` requires an IVA total cuota devengada to
enumerate the recargo tiers of LIVA art. 161 alongside the rest. Modelo 353's 2008-2025
revision carries the same chain, and its group aggregate sums 322's results, so the
omission propagates from the member's return into the group return that reconciles
against it.

This is recorded, not fixed: closing it means binding 322's recargo boxes into the chain
on both modelos and both editions, and it is a distinct change from the export-authority
work above. It is named here so it is actioned rather than rediscovered.

## What the standing goal still asks that this segment did not deliver

Modelo 322's 2008-2025 revision still declares no export layout. It cites TWO editions of
its diseño, has 240 anchors across four records and only ten casillas authored, so it
needs the full casilla, binding, map and profile pass rather than a mirror of a sibling.
Until it lands, check mode refuses for both Modelo 353 trees - not because 353 is
incomplete, but because 322 is staged beside it as the modelo 353 folds in. Both entries
are recorded in the gate's pending table with that exact reason, so closing 322 is what
removes them.

## Modelo 322's 2008-2025 layout, carried rather than re-decided

The gap named above closed in the same session. 322's 2008-2025 revision now
generates, validates and reproduces byte-for-byte, and is enrolled in the same gate.

The method is worth recording because it is reusable and because the alternative was
worse. 322's 2026 sibling already holds a complete REVIEWED answer for what every anchor
of its record design means, in its authored export layout. Its 2024-2025 edition prints
the same 188 bracketed boxes (a strict subset of 2026's 189; only [112] is new) at nearly
the same geometry. So the semantic map was derived by carrying the 2026 decision across
on each anchor's own printed DESCRIPTION, rather than by re-reading AEAT's prose and
reaching a second, possibly divergent conclusion about the same box.

That claimed 224 of 240 anchors outright. Two descriptions carried conflicting decisions
across pages and were DROPPED rather than guessed. The remaining sixteen were resolved
explicitly: eight record identifiers read from the design's own printed tag, and eight
anchors AEAT reworded between editions - the identificación flags moved from questions
("¿Está inscrito en...?") to statements ("Sujeto pasivo inscrito en..."), and [68] and
[70] gained terms this edition does not have ([77] and [112] respectively). Each is keyed
by its exact position on THIS edition's design, with the reason written beside it.

The casilla mirror was scoped the same way: a casilla lands on 2008-2025 only where this
revision's own design prints a slot for it, or where a landed casilla's formula reads it.
Nothing was carried merely because the sibling declares it.

Authoring it surfaced three more spellings in shared generator machinery, all in the same
class as 353's: a record's opening tag printed BARE as well as its closing tag; a third
enumeration spelling with the label FIRST ("Si=1, No=2"); and a note reference written
parenthesised with a verb on its own line ("(ver Nota 5)"), which the trailing-note peel
did not recognise, so a perfectly ordinary "15 enteros + 2 decimales" refused as
ambiguous. Each was widened at the single canonical site with its negative case gated.

## Where all four generated modelos now stand, and the one wall left

210, 232 (both revisions), 353 (both revisions) and 322's 2008-2025 all generate,
validate, and reproduce byte-for-byte under the one parameterised gate. Check mode
refuses for every one of them for exactly ONE reason now: `review_status =
"pending_review"` on the revision itself. A filing-grade snapshot requires a REVIEWED
revision, and that stamp is a human tax reviewer's judgement against official sources -
not an authoring step, and explicitly not one an agent may make under the operator's
name. The gate's pending table records that reason per tree, so the day a revision is
reviewed its entry fails and forces the upgrade.

That is the honest statement of completeness for this segment: the authoring is done and
the review is not, and no amount of further authoring moves it.

## A gate that had stopped gating on this platform

`test_export_header_key_naming.py` shells out to `git grep` with `text=True`, which
decodes with the platform's locale codec. On Windows that is cp1252, where the second
byte of a UTF-8 "Á" is undefined - so the decode raised, `.stdout` came back `None`, and
the gate ERRORED at setup instead of gating. Modelo 322's committed "Álava" line is what
does it, and it has been committed for some time.

With the decode pinned to UTF-8 the gate ran, and both its HEAD assertions turned out to
be stale pins on a moment rather than on a property:

- It required MORE THAN TWENTY header_key tokens at HEAD. The count fell to eighteen when
  nineteen modelos' export layouts were retracted, so a healthy corpus read as a broken
  scan. Replaced with the property that distinguishes a real read from a broken one: the
  scan returned something, and everything it returned is in the closed producer
  vocabulary.
- It asserted the offender set EQUALS `(presenter_tax_id, presenter_nif)` - pinning a
  live defect as the contract. That gate would have failed for having been FIXED, and
  while it stood it could never have caught a second offender appearing beside the first.
  Replaced with the real contract: the committed corpus carries no dual spelling. The
  detector's own anti-tautology proof already lives in a sibling test against a
  hand-built corpus, so nothing was lost.

Both are worth naming beyond this modelo: a count and a known-offender list are the two
shapes that make a gate look green while measuring nothing.

## Modelo 202, all three revisions, from first principles

202's three revisions had no export layout and no sibling layout to carry from, so
each map was built from its own diseño. All three now generate, validate and
reproduce byte-for-byte: 95 anchors each on 2019-2022 and 2023-2024, 103 on
2025-y-siguientes, with EVERY anchor claimed and every casilla addressed - 54, 54 and
61 respectively.

Two things made it tractable and are worth reusing. First, the bracket sets and the
casilla sets agree exactly and in BOTH directions on all three revisions, which was
measured before any authoring: no bracket without a casilla, no casilla without a
bracket. That turns the liquidación block into a mechanical claim. Second, everything
the brackets do not cover is the identification and régimen block, which files FACTS
rather than boxes, and each is claimed by exact byte range with one entry per concept.

The 2025 edition restructures that block wholesale - the foral flag moves to the front,
devengo shifts a byte, the tipo de gravamen slot widens from five positions to fifteen,
and one cooperativa-or-multiple-tipos enumeration splits into three markers - so it
carries its own complete fact table rather than an adjustment to the earlier one.

Reading the FULL labels rather than the truncated ones caught two errors before they
shipped: `@121` is Ley 49/2002 and `@122` is Ley 11/2009, the opposite of what the
shortened descriptions suggested, and `@124` names LIS art. 101 (empresa de reducida
dimensión), not art. 29.2. A key named for the wrong article would have rendered the
wrong régimen flag with nothing able to refuse it.

### Eleven boxes AEAT prints without numbering

The design gives eleven 17-position amount slots under "Información adicional (5)" and,
unlike every liquidación slot on the same record, prints no bracket beside any of them.
They carry declared amounts and have their own slots, so the export must be able to
write them - which makes them casillas. Their ids are SLUGS taken from AEAT's own label,
never invented box numbers: this registry already keys unnumbered concepts that way, and
a number would assert an official identity the design does not print.

Their grounding is deliberately partial and says so. LIS art. 40 - the provision that
establishes the pago fraccionado this record files - is a valid foundation home for a
slot on it. The specific provisions AEAT names in the remaining labels (LIS arts. 17.2,
33, 34 and 109, Ley 19/1994 arts. 26 and 44, Ley 20/1990 art. 24) are NOT in the legal
catalogue, and the registry refuses a ref it cannot resolve to bundled corpus text. They
are left uncited rather than cited unbacked; adding them means fetching and verifying
each consolidated article against BOE, which is its own change.

### A deadline this session refused to write

202's remaining blocked family is `deadline_windows`, and it is empty on purpose. The
pagos fraccionados of LIS art. 40.3 open on the 1st and run to the 20th of April,
October and December, but the exact close moves for weekends and holidays and AEAT
publishes it per year in the Calendario del Contribuyente. Those calendars are bundled
from 2023 onward, and the 202 entry was located in both - but the close date sits under
a "Hasta el N" heading that this pass could not read back from the PDF reliably.

A draft of this work had the six 2023-2024 windows written out with a comment claiming
they were read from the calendar. They were not; they were written from memory. That is
the exact shape `aeat-calculation-grounding` forbids, and a wrong filing deadline is a
filing-grade harm. They were removed and the family declared as a deferral naming the
heading extraction as its unblocker - and, for 2019-2022, the additional fact that those
years' calendars are not bundled at all.

`filing_schedules` is a different kind of claim and DID carry: it declares the period
SHAPE, not dates, and LIS art. 40 fixes the same three pagos fraccionados every year.

### Four more content spellings, one canonical site each

- a record's OPENING tag printed bare, not only its closing tag (Modelo 322 prints both)
- a note reference written parenthesised with a verb on its own line, `(ver Nota 5)`,
  which made an ordinary `15 enteros + 2 decimales` refuse as ambiguous
- a quoted enumeration with a FREE-TEXT label per value, `"0" No consta, "1" Cooperativa`
- an over-eager reading of my own earlier `Si=1` rule: it accepted any non-digit before
  the `=`, so `"1" (>= 10 M y < 20 M €)` parsed `>= 10` as the value 10 - three
  two-character values for a one-character slot. The label must now START WITH A LETTER,
  which excludes a comparison and a formula alike.

That last one is the useful lesson: widening a reader to admit a new spelling is exactly
where a reader starts accepting things that are not that spelling, and it was caught only
because the width check downstream refused. Both directions are gated.

## A manifest-schema addition silently stales every committed tree

`dev/registry/_semantic_map.py` gained an `ordinal_absent` anchor field, and
`_SEMANTIC_MAP_ANCHOR_KEYS` in `dev/registry/_provenance_manifest.py:112` was versioned
to admit it. Both halves are correct. What neither carries is the consequence: the field
is emitted into `_generation.provenance.json`, so every committed generated tree's
manifest became stale the moment the field landed - including Modelo 210 and both Modelo
232 revisions, whose registry data nobody had touched.

The delta was verified to be exactly the new key and nothing else: a fresh render into an
isolated candidate reproduced every TOML fragment byte-for-byte on all nine trees, with
`field_derivations.semantic_entry.anchor.ordinal_absent` the sole structural difference in
the JSON. All nine manifests were regenerated through the generator; no TOML changed.

The finding is the coupling, not the field. A manifest-schema change is a tree-wide
regeneration event, and there is no verb that performs it: the only thing that reports the
staleness is the per-tree byte-equality assertion in
`dev/registry/tests/test_generated_export_trees.py`, which reds for every enrolled tree at
once and names none of them as the cause. A tree NOT enrolled in that gate would carry a
stale manifest indefinitely with nothing to say so. Enrolment is therefore the only
staleness detector this repository has, which is an argument for enrolling every generated
tree the day it lands rather than when its check-mode reason is known.

## Modelo 202 is blocked by its neighbour, not by itself

202's three trees generate, validate and reproduce byte-for-byte, but check mode refuses.
The candidate registry must admit Modelo 200 - 202's pagos fraccionados ARE the Sociedades
annual return's instalments, so 200 is a supporting modelo, not an optional one - and 200
declares no export layout at all while claiming `filing` authority grade. That refusal is
200's, and 200 is 3250 casillas of peer-held work.

Pinned in `_CHECK_MODE_PENDING` on 200's own message rather than the generic
`registry validation failed` envelope, deliberately: when 200's layout lands, the pin
fails, and 202's remaining blocker has to be looked at rather than inherited. That
remaining blocker is 202's per-revision singleton semantic roles - roughly twenty
`is_pf_mod_40_*` roles each appearing on exactly one casilla within a revision. They are
present at HEAD, predate the layout work, and are untouched by it; the layout commits add
one derived `export_refs` line per addressed casilla and nothing else. Whether a role that
names one specific box is a defect or the correct shape for this modelo is a registry
question, not an export question, and is left open here rather than answered by silence.

## Modelo 151: a hand transcription that was two positions short

151/2015-2022 already carried a complete hand-transcribed `export_layouts` tree, so it
was not a coverage gap and it validated. Regenerating it through the generator found
what a transcription cannot check about itself: the envelope was **two positions short**
of AEAT's own. The transcription wrote the AUX block's surrounding blanco fillers but
omitted `Version del Programa` (@93, 4 positions) and `NIF Empresa Desarrollo` (@101, 9
positions) between them. The generated envelope carries both, because the modelo-neutral
13-role prefix contract has a role for each. This is one of the nineteen revisions
already known to be short exactly those two positions; it is the first where the fix
fell out of regeneration rather than needing its own edit.

The map was DERIVED from that transcription rather than re-decided -- it is a reviewed
artefact, and its per-record field counts already agreed with the parser's reading of
the design -- with the join asserted on offset and length at every one of the 600
positions. So the regeneration keeps every human judgement it encoded and drops only its
omission.

### Four content spellings this design needed, three of them AEAT's own errors

- **Bracketed clause.** 151 writes `[15 enteros + 2 decimales]` where 202, 303 and 322
  write it bare, across 220 money slots per edition. Peeled once, before the value
  grammars, and only when the brackets wrap the ENTIRE content.
- **`Formato: "dd/MM/yyyy"`.** A quoted separator-bearing date pattern in the
  programmer's vocabulary rather than the Spanish token. Folded into the SAME policy
  table `ddmmaaaa` already keys on, so a second table cannot drift from the first. Kept
  case-sensitive: `MM` is the month and `mm` the minute, and a slot spelling minutes is
  not a date this grammar should accept.
- **Bare comma-separated enumerations** (`1,2,3`, `0,1,2`, `1,2,3,4`) -- the same closed
  set the quoted grammar already read, written without quotes or labels.
- **`decmales`.** AEAT's typo, shipped once per edition beside eighteen correctly spelled
  siblings of the same shape. Admitted by naming that exact misspelling, never by
  loosening the word: the reading is proved independently anyway, because the declared
  3 + 2 digits must equal the slot's own 5 positions.

### A representation the machinery could not express

The 2015 design types its 100-position `Descripcion del elemento patrimonial` slots
`Num`, eleven of them. AEAT's own Nota 1 defines that column as "A (Alfabetico) An
(Alfanumerico), Num (Numerico sin signo) o N (Numerico con signo)", so this is a
publication error, not a convention -- the whole block below each page identifier is
typed `Num` uniformly, money and prose alike. `SingletonNumericRule` had no way to say
so: its nearest kind, `identifier_digits`, renders unpadded because an identifier must
fill its slot exactly, which prose does not.

Added `ExportValuePolicy.MISTYPED_ALPHANUMERIC_TEXT` with its projector, wire validator,
canonical wire shape (text, blank-filled, left-justified) and a `semantic_kind` that
declares zero digits in both positions, because the slot has no numeric reading at all.

The reading was then **independently confirmed by AEAT**: the 2023 edition types those
same slots `An`. AEAT fixed it, which is why the 2023 profile needs no such rule. The
existing hand transcription had it wrong in the other direction -- `data_type = "text"`
with `padding = "left_zero"`, which would zero-fill a description.

### 151/2025-y-siguientes: 8 casillas to a filing-grade revision

This revision declared 8 casillas against a 714-position design and no layout at all.
A description carry from the 2015 sibling was measured first and reached **76%** -- high
enough to look authoritative, far too low to build on -- because the 2023 edition
renumbered the printed box references, repeats several blocks more times, and adds two
whole records. So it was authored from its own design, which is the better authority: it
prints an explicit bracketed box number on nearly every data row.

616 casillas and the semantic map were emitted from ONE walk, so a casilla id cannot
disagree with the export field addressing it. The six liquidacion boxes the revision
already modelled (base liquidable general [17] and del ahorro [18], both cuotas integras
[19] [20], retenciones [33], resultado [43]) keep their authored ids, formulas and
bindings; the walk binds the design's boxes to them rather than minting parallel
casillas beside them.

Two findings fell out of the authoring:

- **The printed box number cannot be a casilla `number`.** A page repeats one block up to
  nine times and prints the SAME box numbers in each repeat, so the printed number is
  unique only within a block while `number` must be unique within the record. The byte
  range is used, matching the 2015 sibling; the box number is preserved verbatim in each
  entry's comment.
- **AEAT transposes the municipio and provincia labels** -- and their printed box numbers
  with them -- in the 2023 Representante block, against the Contribuyente block a few
  hundred positions earlier. The widths do not move: an INE provincia code is two digits
  and a municipio code five, in both blocks and both editions. Width decides, and the
  generator counts and prints each transposition rather than silently correcting it.

### Grounding

Four legal entries were added, each read out of the bundled consolidated corpus before
authoring: art. 2 (obligados) and art. 3 (plazo) of both Orden HAP/2783/2015 and Orden
HFP/1338/2023. Art. 3.1 of each fixes the plazo BY REMISSION -- "sera el mismo que se
apruebe cada ejercicio, con caracter general, para las declaraciones del IRPF" -- which
is precisely why this modelo's deadline windows are a per-year factual claim its own
orden cannot supply.

For 2023-2025 that remission resolves: those windows are authored citing both the Renta
campaign orden that fixes the dates and the remission article that makes it apply. The
payment cutoff is this modelo's OWN, from art. 4.2 ("cinco dias antes de que finalice el
plazo"); computed by that rule it independently reproduces the cutoff Modelo 100 declares
for all three campaigns -- two derivations agreeing, not one copied. For 2015-2022 it
does not resolve: five of those eight years have no in-repository authority at all, so
the family is a named deferral rather than a partial guess.
