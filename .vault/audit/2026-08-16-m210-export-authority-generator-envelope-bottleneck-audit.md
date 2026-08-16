---
tags:
  - '#audit'
  - '#m210-export-authority'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:0f93eaf8427a4ce29e6cd16db9d64cff913107a5caf94a48d057b8614ecda1f9'
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
