---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:ce8a0920c4b1da335a70a618bfe22ad92a9843f8994634d297c92da1aecf38f5'
related:
  - "[[2026-08-16-registry-campaign-sequencing-designless-modelo-registry-membership-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
---
# `registry-campaign-sequencing` audit: `export layout authoring backlog`

## Scope

The modelos still refusing registry build for declaring no export layout, once
the designless population was resolved. The starting assumption was that each one
is straightforward authoring against a bundled design. **That assumption was
wrong, and this audit exists mainly to record why**, so the next attempt does not
pay again for rediscovering it.

## Findings

### hand-authoring-an-export-tree-is-the-rejected-option | critical | Two layouts were authored by hand, then removed; the generator refuses that exact shape for a reason

Modelos 308 and 309 were authored the way the other 34 manual `export_layouts/`
trees in this repository are: fields derived from the parsed record design, one
record per design sheet, verified against byte extents and passing
`validate_export_layout_record_coverage`. Both reached a single remaining
failure. **Both were then removed**, and the removal is the finding.

`2026-08-08-aeat-design-relayout-boundary-export-fragment-generator-adr` is
titled "the export fragment tree is generated from the bundled diseño, **never
transcribed**", and its accepted successor
`2026-08-10-aeat-export-fragment-generator-authority-adr` makes the generator the
sole authority: hash-pinned official binary for coordinates, a reviewed semantic
map for registry meaning, an exhaustive source-bound render profile for wire
facts the anchors omit, and generated TOML that is "CLI-owned and never
hand-edited".

The decisive part is not the process rule, it is what the generator's own IR says
about these designs. `load_record_design_intermediate` classifies Modelo 308's
`M30800` and Modelo 309's `M30900` as **variable envelopes**, not fixed records,
and `render_complete_export_tree` refuses a variable envelope with no separately
typed and proven composition contract. The ADR lists the hand-authored shape
among its rejected options: treat variable wrappers as fixed records with
inferred totals — rejected, because it truncates composition semantics and
falsely converts a variable envelope into a fixed-width record.

So the hand-authored trees were not merely off-process. They asserted a record
kind the official design does not have, and the coverage gate could not catch it,
because that gate compares a layout against the same parse rather than against
the composition classification. **A manual tree can look complete and still be
wrong about what the record is.**

### what-the-backlog-actually-is | critical | One modelo is generatable today; eight are blocked on one shared contract

Running the generator's IR loader over every `record_design` source the fourteen
refused modelos cite, at their declared design epochs, gives the real shape of
the work. This replaces the earlier count in this audit, which read every refusal
as authoring effort.

**Generatable now (4, after the epoch fix below):** 184, 193, 232 and 347. Each
parses completely at its current epoch with no variable envelope, so each needs
only a reviewed semantic map and a render profile before it generates. 232
already has a generated tree at partial coverage.

**Blocked on a variable-envelope composition contract (8):** 151, 200, 202, 303,
308, 309, 322, 353. Every one carries exactly one variable envelope beside its
fixed sheets. Modelo 303's `DP30300` is the only such contract that exists, and
the ADR already names `DP200000` as needing its own. This is **one shared piece
of infrastructure gating eight modelos**, not eight authoring tasks, and it is by
far the highest-leverage item in the campaign.

**Blocked on an undeclared design epoch (2): RESOLVED.** 193 and 347 declared no
`record_design_epoch` on any of their six design sources, and the loader refuses
without one. The epoch names the filing period a design GOVERNS, not the document
version, so each value was read off the source's own `applies_from` window rather
than from its id -- the id is another free-form string, and deriving one from the
other would let a single typo satisfy both. All six are now declared and unique
per modelo, and **both modelos load and are generatable**: `aeat-dr-193-2025` and
`aeat-dr-347-2025` each parse to three fixed sheets with no variable envelope.

**Blocked on an incomplete parse (2):** 296 and 360. The IR loader **requires a
complete read**, deliberately and unlike the coverage derivation, because a
partially-read design would produce a byte layout missing whole records. Modelo
296's perceptor record parses to twelve fields, implausibly few for a
non-resident retenciones summary, and its design reports three skipped record
bodies. Hand authoring from that parse would have produced a confidently wrong
layout that passed every gate.

**Parser defect (1): no longer reproducing.** Modelo 232 at `aeat-dr-232-2018`
raised `AttributeError: 'str' object has no attribute 'content'` inside the IR
loader when first surveyed. It now loads cleanly (two fixed sheets plus one typed
auxiliary envelope header) and carries a generated `export/` tree landed
concurrently by another worker. That tree writes 157 of the 222 positions its
design requires -- 70.7% coverage -- so 232 is now an incomplete-generation
problem rather than a loader crash.

### partial-reads-are-invisible-to-the-coverage-gate | high | The strongest argument for the generator over hand authoring

`validate_export_layout_record_coverage` measures an authored layout against the
parsed design. When the parse is incomplete, both sides of that comparison shrink
together and the gate reports success. Modelos 200, 202, 232, 296 and 360 all
report skipped record bodies — Modelo 200 skips 45 of them on its 2010 and 2011
designs.

The generator does not share that blind spot: its IR loader refuses an incomplete
read outright, before any output exists to measure. That asymmetry is documented
in the loader itself and is the concrete reason to prefer the generated route
even where a manual tree would be quicker.

### one-registry-two-export-conventions | high | The scaffolder still creates the shape the ADR retired

`dev/registry/newmodelo` scaffolds `export_layouts/` into every new modelo
skeleton, while the accepted authority generates `export/` plus a provenance
manifest. Two modelos carry generated trees (210, 303); thirty-four carry manual
ones. A contributor following the scaffolder is led to the retired convention,
which is how a hand-authored tree becomes the path of least resistance.

Converging on one convention is a decision this audit does not make, but the
scaffolder is where the divergence is actively reproduced, so it is the cheapest
place to stop it.

### grade-and-design-scoping-of-the-refusal | medium | Two independent claims now scope the no-layout refusal, both proven both ways

The refusal fires only when a revision claims the `filing` authority rung AND its
modelo cites a `record_design` source. Both scopings are claims the revision
makes about itself rather than fields an author sets to buy silence, and neither
hides a real gap.

**Grade.** The filing rung asserts a revision can additionally back a filing
draft and its export; applicability asserts scheduling reach only. Twelve refused
revisions declared applicability — Modelo 182 records that the donativos
declaration is filed by the entity RECEIVING the donation, so this application's
taxpayer is its subject and not its filer. The runtime check
`_check_snapshot_filing_capability` is **not** scoped by grade and still refuses
a filing snapshot over a missing layout, so the capability cannot be exercised
whatever a revision declares. A test pins that independence by source inspection.

**Design.** Read at MODELO scope across every revision, so a per-revision
acquisition gap stays red; Modelo 185's 2026 design is bundled while its
`2003-2025` revision cites none. A `form_spec` does not count, which is what
keeps Modelo 721's printable BOE anexo from reading as a machine design.

Six paired discrimination proofs run each predicate both ways over the same real
revision object, plus a mutation proof that the design predicate keys on `kind`
rather than on evidence tier or an id ending in `-layout`.

### modelo-184-is-authorable-and-its-hard-part-is-recoverable | medium | The desglose categories are in the source, keyed by position range

Modelo 184 is the cleanest generatable modelo: three fixed records, no variable
envelope, complete parse, 132 anchors. Its hard part is that **44 of those
anchors are bare `. ENTERO:` / `. DECIMAL:` halves** of two gastos-detail
desglose blocks, because AEAT prints each category once as a heading above its
pair. Read off the anchors alone they are unnameable, and naming them from
neighbouring fields would be invention.

They are recoverable. The design text carries each category as
`<from>-<to>. <NAME>` immediately above the pair, so matching on the byte range
recovers all twenty-one grounded: gastos de personal (266-277), consumos de
explotación (278-289), tributos fiscalmente deducibles (290-301), arrendamientos
y cánones, reparaciones y conservación, servicios profesionales, suministros,
gastos financieros, amortizaciones, provisiones and otros gastos deducibles for
actividades económicas; then intereses y demás gastos de financiación (397-407),
conservación y reparación, tributos y recargos, saldos de dudoso cobro,
cantidades devengadas por terceros, primas de seguros, amortización del inmueble,
amortización de bienes muebles and otros gastos deducibles for capital
inmobiliario.

Two open items before the map can be authored. **The canonical owners do not
exist yet**: 184 declares six casillas against 132 anchors, and the ADR makes
adding a typed canonical owner a prerequisite of map authoring rather than
something the map may invent. And **the desglose parent anchors need a
classification of their own** -- the coverage validator is explicit that the
sub-fields are the positions and the parent's span is not one, while the semantic
map demands every parser anchor classify exactly once. The parser already models
the relationship through the record-design field's `components`, so the question
is which map kind a parent takes, not whether the structure is known.

### modelo-296-parse-hole-is-a-missing-naturaleza | high | Root-caused: AEAT omitted the type token, and the parser correctly refuses to guess

Modelo 296's perceptor record declares 500 positions but reports 413-432 unread.
The row is in the source and reads `413-432 CÓDIGO LEI DEL PERCEPTOR` — **with no
naturaleza between the range and the description**, unlike its neighbour
`433-452 Alfanumérico NIF EN EL PAÍS DE RESIDENCIA FISCAL`.

`_naturaleza_or_none` returns `None` for `CÓDIGO`, and the caller then treats the
line as prose rather than a position row. That behaviour is deliberate and
well-grounded, not a bug: AEAT routinely opens a field's DESCRIPTION with that
field's own range (`68-107 APELLIDOS Y NOMBRE: Se consignara el primer ...`), and
the code records that **41 bundled designs carry such prose**. Admitting an
unrecognised naturaleza would invent positions wholesale across the corpus, which
is the worse defect.

So the two shapes are genuinely ambiguous on the line alone. A discriminator does
exist and it is structural rather than textual: **the prose case restates a range
some real row already claims, while this case fills a hole no row claims** in a
record whose declared total proves the hole is there. A gap-filling second pass —
admitting a prose-shaped row only for a range no row claims, only where the
declared total proves the gap — can only ever fill holes, never override or
duplicate a read row, so it preserves the anti-invention property the current
behaviour protects.

That is a change to a shipped parser with corpus-wide blast radius (218 designs),
so it wants its own change with mutation coverage, not a drive-by. Modelo 360's
single unread body at source row 241 is unclassified and may or may not be the
same shape; it was not diagnosed.

### the-extractor-and-the-generator-disagree-about-desglose | critical | Containment overlap is a permitted AEAT shape to one authority and a refusal to the other

`contiguity_failure` in the shipped extractor states the rule plainly: "Overlap by
CONTAINMENT is expected and permitted -- AEAT prints a parent row and its own
subdivisions ... and both are real statements about the same bytes. What is
refused is a HOLE ... and a PARTIAL overlap."

`_require_exact_record_geometry` in the export generator walks the same field
sequence demanding `offset == previous offset + length`, which a contained
sub-field can never satisfy. Its docstring calls that walk redundant with "the
same extractor, which already runs this identical check unconditionally on every
field". **For any design carrying a parent row that claim is false**, and the two
authorities disagree about the same bytes.

Replaying the generator's exact rule over extractor output, with no registry load
needed, on Modelo 184's 2025 design:

| record | fields | contained | generator verdict |
|---|---|---|---|
| PDF record design | 25 | 5 | REFUSES: overlap before ord=13, expected 147 got 145 |
| Tipo 2 - Rentas | 78 | 45 | REFUSES: overlap before ord=18, expected 125 got 117 |
| Tipo 2 - Socio | 29 | 0 | OK |

So Modelo 184 cannot generate today, and the reason is structural rather than a
missing map: **two of its three records are refused before any semantic map is
consulted.** Measured alongside it, the currently-bundled Modelo 180 and 190
editions carry zero contained fields, so 184 is the demonstrated case here rather
than a corpus-wide count.

This is a **second** infrastructure blocker beside the variable-envelope contract,
and it is the shape the standing rule warns about directly: "a second copy of a
shape rule validated independently -- the parser and the development intermediate
held two copies of the auxiliary-header contract and drifted into disagreeing
about which modelos even have one." The same drift has happened again, one
contract over.

Which side moves is a real decision. The extractor's tolerance is grounded in
AEAT's printing (a parent and its subdivisions are both true statements), and the
coverage validator already resolves the ambiguity for its own purpose -- the
sub-fields are the positions, the parent's span is not one. Teaching the
generator that same resolution, rather than loosening either contiguity rule,
looks like the narrow fix, but it belongs to whoever owns the generator.

**Correction: the narrow fix proposed above does not work, and the disagreement
is not where this finding placed it.** Teaching the generator the coverage
validator's resolution was the recommendation. Measured, it is a no-op.

`_required_positions` resolves desglose by descending into
`RecordDesignField.components`. Modelo 184's records carry **zero** fields with
components -- `parents=0, children=0` on all three. The parent rows and their
sub-fields arrive as FLAT SIBLINGS in `sheet.fields`. So the coverage validator
is not resolving anything for 184 either; it counts the parent spans as required
positions exactly as the generator does. Both authorities hold the same view of
these bytes, and neither one is the defect.

The defect is upstream, in `_matching_component_parent_index`
(`src/cadrumo/domain/calculations/registry/_record_design.py:733`). It nests a
sub-field only when the ordinal is DOTTED (`19.1` under `19`), which is the
discriminator that correctly keeps Modelo 303's `14bis` a peer. Modelo 184 prints
its desglose with BARE CONSECUTIVE ordinals -- parent `12`, sub-field `13` -- so
the rule never fires and the nesting never happens.

And reconstructing the containment is provably the right shape. Nesting each
contained field under the top-level field containing it turns all three of 184's
records into byte-exact geometry:

| record | flat | tops | non-contiguous | ends at | declared |
|---|---|---|---|---|---|
| PDF record design | 25 | 20 | 0 | 500 | 500 |
| Tipo 2 - Rentas | 78 | 33 | 0 | 500 | 500 |
| Tipo 2 - Socio | 29 | 29 | 0 | 500 | 500 |

So the generator's contiguity walk and the extractor's containment tolerance are
**both correct as written**. Fixing the parser's parent detection satisfies both
simultaneously, with no rule loosened on either side.

**But containment alone is NOT a safe discriminator, and this is the part that
must not be skipped.** Scanning every bundled design -- 1,702 sheets, 133,753
fields -- finds 51 bare-ordinal contained pairs across 9 modelos (038, 165, 181,
184, 187, 188, 280, 349, 604). Every one is a consecutive integer pair, so the
`14bis` peer shape never appears contained and is not the hazard. The hazard is
that the 51 are a MIXED POPULATION, and their own prose separates them:

- **Self-declared desglose.** Modelo 280 `@102+8`: "FECHA DE APERTURA -- Este
  campo se subdivide en 3". Modelo 184 `@145+2` and `@147+9`: "Este campo se
  subdivide en dos:" and "en cuatro:". The design states the subdivision itself.
- **Grouping headers.** Modelo 349's `RECTIFICACIONES`; Modelo 184's `DETALLE DE
  GASTOS...` at `@266+130` and `@397+101`. A printed heading spanning its detail
  rows, declaring the grouping in narrative rather than in the subdivide phrase.
- **Extraction artefacts, which must NOT be nested.** Modelo 038's pair is two
  `BLANCOS` fragments from `_extract_visual_chart_sheet`, whose merged
  chart-geometry spans produced a 40-byte fragment containing a 2-byte one. That
  is an artefact of reading a design drawn as a chart rather than tabulated, and
  nothing about it is an AEAT desglose.

A blanket containment rule would nest all three kinds alike, silently reparenting
real fields under synthetic chart fragments and changing what every extractor
consumer sees. That is the same second-copy drift this finding already warns
about, arriving from the other direction.

So Modelo 184 remains blocked, but on a **sharper and smaller** question than
this finding first recorded: what positive signal, beside containment, marks a
parent as a real desglose. The design's own prose is the candidate the corpus
supports -- `se subdivide en` / `se desglosa en` covers 184's two subdivided
fields and 280's, and excludes 038's artefact outright -- but it does not by
itself cover 184's three grouping headers, whose prose declares the grouping in
narrative instead. That is the remaining gap, and it is parser work with
corpus-wide blast radius across 133,753 fields, so it wants its own change with
mutation coverage and a regression pinning 038's artefact NOT nested. Still not a
drive-by, and still not something to infer from geometry alone.

**LANDED: the fold is implemented, and two of Modelo 184's three records now
parse to exact geometry.** `_fold_untagged_desglose_components` nests a
bare-ordinal desglose under its parent, gated on EXACT TILING, wired into both
sheet-construction paths (`_extract_sheet_rows` for workbooks,
`_PdfSheetDraft.finish` for PDFs, after gap-filling).

Result on Modelo 184: `Tipo 2 - Rentas` 78 fields to 33 tops, and `Tipo 2 -
Socio` 29, both **contiguous and landing exactly on the declared 500**. Only the
third record still refuses, and its cause is now known and separate (below).
Across the corpus the fold nests 35 runs and abstains on 16, including all
eleven of Modelo 038's chart artefacts and Modelo 349's non-tiling group.

**Measured non-regressive**, by controlled comparison rather than assertion:

- Registry failure-set diff over the whole tree: every added/removed pair was
  the same modelo with `relations` dropped -- a peer landing that family. **No
  coverage verdict moved**: 180 (26/30), 190 (23/53), 341 (30/31), 349 (28/39),
  390, 714 and 232 are byte-identical before and after, and 165, 181, 280 and
  604 -- the four folding modelos that carry passing layouts -- still pass.
- The fold is a provable no-op for 303, 200, 220 and 390: zero components in
  any of their designs, so the concurrent variable-envelope test failures are
  not reachable from it.
- `test_record_design.py` 81/81 green.

This is safe by construction, not by luck: folding only ever REMOVES the parent
from the required-position set and never adds one, coverage is measured by
containment (`missing = [p for p in required if not _covers(...)]`) so a
shrinking required set cannot red a passing layout, and
`_administration_reserved_bytes` already walks `(field, *field.components)`, so a
`RESERVADO` sub-field keeps its protection after folding.

**One real interaction, and it was a test defect the fold exposed rather than
caused.** `test_writing_a_desglosado_parent_as_one_blob_is_refused` selected its
subject as the first design field with `parent.components`. That was
*accidentally* correct while Modelo 576 was the only bundled design carrying
components and happens to reserve `19.3` for the Administracion. With more
designs declaring components the selection picked a parent reserving nothing,
where a blob covers every sub-position and intrudes on no reserved byte -- so the
gate correctly stayed green and the proof went vacuous. Byte-extent coverage
cannot object to a blob over sub-fields that are all real data; what makes the
shape refusable is precisely that it writes AEAT's own bytes.

The test already said so, in the vacuity assertion further down its own body
("the desglosado parent reserves no sub-field, so this proof would be vacuous") --
it simply ran AFTER the weaker `assert failures`. The selection now requires a
reserved component, which moves that existing claim to where it can bite. The
gate itself is unchanged and still refuses Modelo 576's blob. Module now 21/21.

**Modelo 184's remaining record is a parse hole, same class as Modelo 296's.**
Parent `15 @147+9` states "Este campo se subdivide en cuatro:" and only three
sub-fields were read, covering 147-150 and leaving 151-155 unaccounted, so the
run does not tile and correctly does not fold. The missing row is in the source:
`151-155 PORCENTAJE DE RENTA ATRIBUIBLE A MIEMBROS RESIDENTES`, itself split
into `151-153 ENTERO` and `154-155 DECIMAL`. It was dropped for the reason 296's
perceptor rows were -- **no type token on the naming row**. Compare the sibling
that parsed: `149-150 Alfabetico CLAVE PAIS:` carries position, type and name,
while `151-155 PORCENTAJE...` carries position and name only, stating
"campo numerico" later in its prose. `fill_unread_gaps` cannot recover it either,
because it admits only into UNCLAIMED spans and 151-155 sits inside parent 15's
claimed span. That is the next concrete step for 184.

**Why Modelo 184's parse hole was NOT closed in the same change.** The obvious
next move is to let `fill_unread_gaps` admit a candidate into a desglose
parent's uncovered remainder -- the parent's span is not a position in the
coverage model, so filling its subdivision displaces nothing that was read. The
candidate already exists: `_unnamed_position_candidate` parses
`151-155 PORCENTAJE...` to offset 151, length 5, type `No consta`. Only the
claimed-span guard declines it.

Measured before attempting it, and the measurement argued against: 16 non-tiling
would-be parents carry an uncovered remainder across the bundled PDFs -- six in
Modelo 038 (the chart artefacts, where admitting anything is wrong), plus 165,
184, 280 and 349. So it is not a one-site fix, and the guard it loosens is
conservative on purpose. Its own docstring states the hazard exactly: the
candidate shape "is overwhelmingly prose, because AEAT routinely opens a field's
description with that field's own range, and 41 bundled designs do". Inside a
parent's span that prose would become an admitted field -- the invented-position
class the same module calls "the worst failure available here", citing Modelo
190's phantom `@108+1` and Modelo 156's one-byte APELLIDOS, because a fabricated
position inflates the denominator and sends an author writing bytes AEAT never
defined.

So closing 184 needs a positive signal that the remainder is a real declared
sub-field rather than prose -- the parent's own "se subdivide en cuatro" states
the expected COUNT, which is the most promising evidence, and Modelo 038's
artefacts declare no such count. That is its own change, with its own mutation
coverage and an anti-fabrication regression, not an extension of this one.

**And the count signal does not narrow it either -- measured, so the next
attempt need not re-pay for this.** The idea above was to gate admission on the
parent's own declared subdivision COUNT ("se subdivide en cuatro"), on the
theory that it is rare, self-declared, and absent from Modelo 038's artefacts.
Matching `se (subdivide|desglosa|divide) en <n>` across the bundled corpus finds
**430** such parents, and the overwhelming majority carry ZERO read contained
children -- Modelo 720 and Modelo 604 alone account for dozens. So the count
declaration is common, and it does not correlate with the containment structure
the fold reads: a parent can declare a subdivision while its sub-fields are read
as ordinary sequential peers, or not read at all.

That rules the count out as a NARROW admission gate. It remains the right
EVIDENCE for the eventual fix -- it is what distinguishes a real subdivision from
Modelo 038's chart artefacts -- but a rule keyed on it is a broad parser change
touching hundreds of sites, not a targeted repair of Modelo 184's one hole.

Net: three candidate closures for that hole were measured and all three are
broad -- containment-only (51 sites, mixed population), parent-remainder
admission (16 sites, artefact hazard, loosens a guard against a documented
fabrication class), count-gated admission (430 sites). Modelo 184 is still the
fleet's shortest path, blocked on `export_layouts` alone, but the distance is
real parser work rather than the small repair the geometry result made it look
like.

### the-generatable-set-is-now-six | high | Three parser fixes and the epoch declarations moved four modelos onto the generated path

Re-surveyed through the generator's own IR loader after the parser work, at each
source's declared epoch:

| verdict | modelos |
|---|---|
| generatable | 184, 193, 232, 296, 347, 360 |
| blocked: variable envelope | 151, 200, 202, 303, 308, 309, 322, 353 |

The blocked eight are unchanged and still gated on one shared composition
contract. The generatable set grew from one to six: 193 and 347 by declaring
their missing `record_design_epoch`, 296 and 360 by the parser fixes above.

Geometry checked separately, since a clean IR load is not the same as a
renderable record: **296 (5 records), 360 (2), 193 (3), 347 (3) and 232 (2) all
pass the generator's exact-contiguity rule.** Only 184 fails it, on the desglose
overlap recorded above. So five modelos are blocked on nothing but their own
semantic map and render profile.

**Modelo 232 is the closest to done and its remaining gap is not authoring.** It
already carries a semantic map, a render profile and a generated `export/` tree,
and its 70.7% coverage refusal reads as a record-join defect rather than missing
fields: fields named `m232-2018.dr23201.*` are measured against design record
`DR23200`, so the refusal lists them as writing data into spans that record
reserves for the Administración. Generated trees are CLI-owned, so this belongs
to whoever published it.

**Modelo 347's canonical owners are now authored.** Its design carries 64 anchors
across three records (declarante 18, declarado 32, inmueble 14) against ten
existing casillas, and the semantic map may not invent owners. Thirty were added
from the design's own field descriptions, extending the existing
`decl.*`/`contraparte.*` convention and adding `inmueble.*` for the third record,
which had no owners at all. The registry accepts them with no change to the
failure set. Its map and render profile are the remaining work.

### render-profile-eligibility-is-blind-to-pdf-designs | critical | A PDF-sourced tree would generate with every numeric wire fact unstated, and nothing would refuse it

Modelo 347's semantic map is authored and the join passes: 3 records, 64 anchors,
exact bijection, every canonical reference resolved. The next artefact is its
render profile, and asking the generator what that profile must cover returns
**zero eligible fields**.

That is not because the design states every wire fact. It is because
`project_render_profile_eligibility` selects on `field.aeat_type in {"Num", "N"}`,
which are the WORKBOOK abbreviations. Measured across the three designs:

| design | source | AEAT type spellings | eligible |
|---|---|---|---|
| `aeat-dr-347-2025` | PDF | `Numérico` 19, `Alfanumérico` 29, `Alfabético` 10, `Blancos` 6 | **0** |
| `aeat-dr-232-2018` | workbook | `An` 191, `Num` 57, `A` 2 | 57 |
| `aeat-dr-210-2022` | workbook | `An` 118, `Num` 30, `N` 17, `A` 2 | 47 |

A PDF design spells its naturaleza in full, so **none of Modelo 347's nineteen
numeric fields is eligible for a wire fact it plainly needs.** An empty render
profile would validate, the tree would generate, and those fields would render
with no declared integer/decimal split, no sign policy and no digit-string
policy -- against an ADR whose constraint is explicit that "no numeric, decimal,
date, flag, identifier, digit-string, or literal default is implicit". The
coverage gate cannot fire, because the population it measures is empty by
construction.

Every modelo generated so far (210, 232, 303) is workbook-sourced, so the
projection has never met a PDF design. Modelo 347 would be the first, and 193 and
296 are PDF-sourced too.

**And the type test is only half of it.** Eligibility also requires
`field.content is None or not field.content.strip()` -- the design left its
Contenido cell blank. A workbook has such a cell; a PDF design has no Contenido
column at all, and the parser fills `content` with the field's DESCRIPTIVE PROSE.
All nineteen of Modelo 347's numeric fields carry non-blank content, and every
one of them reads like `"Se consignará el número identificativo correspondiente
a ..."` or `"Las cuatro cifras del ejercicio fiscal"`.

That half is worse than a miss, because it is a wrong positive inference. Read
across Modelo 347's numeric fields, the prose states the wire fact sometimes,
partially, or not at all -- and the four shapes sit side by side in one design:

* `@101+15` states it fully: "Se consignará **sin signo y sin coma decimal** los
  importes superiores a 6.000 euros ..." -- sign policy and decimal policy both
  given.
* `@108+13` states only width: "Campo de contenido **numérico de 13 posiciones**",
  with nothing about sign or decimals.
* `@5+4` states nothing at all, being a cross-reference: "Consignar lo contenido
  en estas mismas posiciones del registro de tipo 1."
* `@99+16` is pure semantics: the total amount of the local-business lease for
  the natural year, with no wire fact anywhere in it.

So neither reading is right. "Content non-blank means the fact is present" is
false for three of those four; "PDF prose never states wire facts" is false for
the first. **The truth is per field and only a reader can tell**, which is
precisely what a render profile is for -- "one exhaustive reviewed authority for
those absent wire facts".

The eligibility projection's job is to name which fields need that review. For
every PDF design it names none, so the reviewer is never asked and the
exhaustive-coverage requirement is **vacuous there**: a profile covering zero
fields satisfies it completely.

**And the accepted ADR is scoped to workbooks by its own words**, in four places:
its problem statement ("when the exact WORKBOOK field anchor carries no usable
content"), its chosen option ("wire facts absent at exact WORKBOOK field
anchors"), and its binding constraint ("the sole reviewed authority for wire
facts absent at their exact WORKBOOK field anchors"). Every modelo generated to
date -- 210, 232, 303 -- is workbook-sourced.

So generating a PDF design is not a projection bug to patch. **It is outside the
accepted decision's scope**, and closing it means extending the generator
authority to PDF sources: a new ruling on what a PDF anchor authorises, with the
per-field evidence above as its input.

This is not a spelling map. **Deciding that a PDF design's prose omits the
wire fact is a ruling about source authority**, and the ADR's whole structure
rests on that boundary -- the official design owns coordinates and present wire
facts, a reviewed source-bound profile owns only the facts the exact anchors
omit. Redrawing where "present" ends for a PDF source belongs to whoever owns the
generator, not to a passing author, which is why no fix was attempted here.

The type half alone is the same defect class the parser already learned once:
`_naturaleza_or_none` matches on an accent-stripped STEM precisely because AEAT
does not spell consistently, and every unmatched spelling was a row dropped in
silence.

**347 was stopped here deliberately rather than finished.** Authoring an empty
profile would have produced a generated tree that passes every gate and states
none of its numeric formats -- a false green in exactly the shape this campaign
keeps having to unpick.

### the-binding-selector-record-key-is-overloaded | critical | The first modelo to combine a source-sense binding with an export layout refuses, and six more will

Modelo 347 rendered its generated tree successfully and then failed the
candidate's registry validation:

```
binding 'modelo-347-declarante-numero-personas-entidades' export selector
projection must declare row_field or offset/length/data_type
```

`derive_export_layouts_from_bindings` parses EVERY binding's selector as soon as
a revision declares any export layout, and `binding_export_selector` treats the
presence of a `record` key as the marker that the selector IS an export
projection -- `if self.record is None: return None` is the whole test. It then
demands coordinates.

**But `record` carries two different meanings in authored bindings**, measured
across the tree. Ten modelos use it: 131, 182, 184, 190, 193, 232, 347, 349, 360
and 720.

* **Export-record sense**, which the derivation expects: `page_1`, `page_01`,
  `page_02` -- 727 occurrences across 131, 349 and 720, all carrying coordinates
  and all working today.
* **Source row-set sense**, which it misreads: `donante`, `perceptor`, `miembro`,
  `operador`, `operacion`, `bien`, `vinculada`, `rectificacion`, `type_1`,
  `type_2`, and Modelo 347's `m347_declarante_summary`. These name which record
  of the SOURCE data an aggregation reads, not a wire position, and none carries
  coordinates because none is a wire projection.

The two senses never met before because no modelo carried a source-sense binding
AND an export layout at the same time. Modelo 347 is the first, and the refusal
is the collision surfacing rather than a defect in 347's data.

**It is not 347's problem alone.** 182, 184, 190, 193, 232 and 360 all carry
source-sense `record` bindings, and every one of them is in this backlog. Each
will refuse identically the moment its export layout lands, so this blocks the
informativa group as a class.

Three shapes are visible and the choice is not mechanical: give the source sense
its own selector key and migrate the ten modelos; make the export derivation
select on the presence of coordinates rather than on `record`; or make it lazy,
parsing only the bindings whose record a layout actually claims through
`binding_record`. The third is the smallest and matches what the derivation
already does one loop later, but all three change a shared contract, so none was
taken here.

### modelo-347-state | high | Authored, rendering, and stopped inside the candidate's own validation

Every author-side artefact for Modelo 347 exists and is proven by the tool that
owns it:

* **33 casillas**, including two the classification pass found missing and one
  the generator forced -- `TIPO DE SOPORTE` was authored as literal `"T"` and
  refused, because the design states TWO claves ('C' soporte, 'T' telematica).
  It is a choice, so it is a casilla.
* **A 64-anchor semantic map** across three records; `join_record_design_semantics`
  passes, which proves exact anchor bijection and every canonical reference
  resolved through the revision.
* **A 19-rule render profile**; `load_and_validate_render_profile` passes, which
  proves exhaustive coverage of every eligible anchor.
* **The tree renders.** `render_complete_export_tree` produces it.
* Casilla `export_refs` re-pointed at the generated field ids, and an export
  application link added.

Publication then reached the candidate registry's own validation and reported
real remaining gaps, which are 347's data rather than generator scope:

* `@488+13 SELLO ELECTRONICO` is the one unwritten required position (57 of 58,
  98.3%). The design calls it "Campo reservado para el sello electronico de la
  AEAT", but the coverage gate's omissibility test matches "Reservado para la
  Administracion" and does not recognise this wording. Modelo 180 carries the
  identical unwritten sello position, so it is a shared shape, not a 347 defect.
* `dependency_classifications`, `projection_endpoints` and the two verification
  families remain unresolved against the filing rung.

Beyond that the work is blocked on the tree itself rather than on 347: the
registry loader is mid-refactor by another worker and its signatures moved twice
during this pass -- `compute_verdict_key() got an unexpected keyword argument
'registry_fingerprints'`, then `load_registry_tree() got an unexpected keyword
argument 'identity'`. Nothing can be verified against a loader that changes
between runs.

**UPDATE: Modelo 347 is now blocked on `export_layouts` ALONE**, down from four
blocked families, which puts it level with Modelo 184 as the fleet's shortest
remaining path. Registry validation moved 80 to 78 with **zero added failures**.

Three families were resolved, and the earlier refusal to touch them was wrong on
its reasoning. They had been left alone as "absent work, not inapplicable
families". Corpus measurement refutes that for the expectation family: of 35
revisions carrying zero formulas, **six do declare a verification expectation**
-- 036, 182, 184, 232 (both revisions) and 720. A zero-formula informative modelo
can and does carry one, so it was authorable all along.

- **`verification_expectations` -- POPULATED.** Modelled on Modelo 184's and
  Modelo 182's, which are the exact analogues (informative, zero formulas):
  `tolerance = "0.00"`, `rounding = "none"`, `discrepancy_causes =
  ["extraction_unreliable"]`. With nothing computed, verification means the held
  values match the filed document exactly, and the only way they can differ is a
  misread. The three casilla axes are used deliberately rather than copied: the
  declarante spine and the declarado triple (nif, clave, importe) are
  `computed_casilla_ids`; the INMUEBLE rows and their totals are
  `reconcile_when_present_casilla_ids`, because a 347 only carries them when the
  declarant reports arrendamiento de local de negocio, and that axis is
  "excluded from the coverage denominator, so enrolling a situational casilla can
  never lower coverage and flip a legitimate filing's verdict".
- **`verification_predicates` -- DISPOSITIONED.** A predicate guards a CALCULATED
  result; 347 declares `calculation_class = "informative"`, its formulas family
  is already dispositioned inapplicable on the same ground, and measured on the
  revision its 43 casillas declare zero formula_ids with no base and no cuota.
  The declarante totals are counts and sums of the reported rows, not a liability
  derived from them.
- **`projection_endpoints` -- DISPOSITIONED.** Verified directly rather than
  taken from Modelo 184's prose: `FilingProjectionRef` is a closed discriminated
  union of **seven** members, every one `M303`-prefixed, so no declaration naming
  347's rows can validate against it. One member is worth naming because it
  invites a specific misreading -- `M303Exonerado390OperacionesTercerosProjectionRef`
  says *operaciones con terceros*, which is literally this modelo's subject, but
  it is a fact projected onto the modelo 303 of a filer exonerated from the 390,
  an m303 casilla and not a 347 row.

Populating the expectation made the revision calculation-bearing, which then
correctly demanded a **`completeness_manifest`** -- also authored. Two errors
worth recording, because both were caught by verification rather than by review:

1. Positions were first derived from the join-proven semantic map (`18-26`,
   `83-98`, ...). Wrong: `number` must mirror the casilla's OWN declared value,
   and 347's casillas declare `number = "<casilla id>"`. The tell was a hard
   refusal on duplicate `(segmento, number)` -- `contraparte.nif` and
   `inmueble.arrendatario-nif` both sit at `18-26` in DIFFERENT records, so the
   position form is genuinely ambiguous for this modelo while the id form is not.
   Modelo 184's manifest looks different only because ITS casillas declare
   position ranges; both follow the same rule.
2. The measurement script conflated `RegistryLoadError` with
   `RegistryValidationError`, so a hard load refusal printed as **"0 failures"** --
   a false CLEAN for the entire registry. Every count in this audit is a
   validation count; a load error means the tree did not parse at all. Catch the
   two separately.

**Unrelated defect found while verifying:**
`test_completeness_manifests_use_the_canonical_fragment_anchor` globs for
`0001-completeness_manifest.toml` with an UNDERSCORE, while every shipped
manifest is `0001-completeness-manifest.toml` with a hyphen. Its `anchors` set is
therefore always empty and it fails for every modelo carrying a manifest,
detecting nothing about any of them. Not caused by this work and not fixed here.

## MODELO 347 IS PUBLISHED AND FULLY IMPLEMENTED

**Zero validation failures.** The generated export tree is published, the
revision snapshots at `filing` authority grade, and 347 is the first modelo to
cross the line in this campaign.

```
revision        : 2008-y-siguientes
authority grade : filing
review status   : agent_reviewed / agent-prepared-pending-operator / 2026-08-16
casillas        : 43
layout          : generated-modelo-347-2008-y-siguientes-fichero (fixed_width)
  m347-declarante  18 fields
  m347-declarado   32 fields
  m347-inmueble    14 fields
```

**The sello was never the real blocker, and this audit was wrong to record it as
one.** While this campaign was measuring and re-measuring it, a peer landed
`_aeat_program_sealed_reason` -- and it is exactly the careful version this audit
reverted: TWO independent signals must agree, the naming cell calling the field
`sello electrónico` AND the content cell delegating completion to AEAT's
programs. Its own docstring records the measurement: 96 positions name the sello,
78 were already omissible by the owner rule, and exactly 18 are reclassified,
every one a declarante seal slot in Modelos 180, 182, 184, 188, 190, 193, 194,
296 and 347. Modelo 347's `@488+13` now returns "reserved for AEAT's own programs
by the design's own content declaration".

The lesson is not that the revert was wrong -- reading omissibility from loose
content prose WAS wrong, and the measured 25-position blast radius did not
justify it. The lesson is that a finding recorded as "a ruling for the gate's
owner" should be **re-measured against HEAD before it is treated as a standing
blocker**, which is what the standing rule already requires and this campaign did
not do for several turns.

**What actually closed it, in order.** Every step was a real gap, and each was
revealed only by attempting publication:

1. Three families authored (expectations populated; predicates and projection
   endpoints dispositioned) plus the completeness manifest they demanded, taking
   347 from four blocked families to one.
2. `export_refs` regenerated from the join-proven semantic map onto 42 casillas,
   which is what "export field X is not declared by casilla Y" was asking for.
3. `decl.ejercicio` remapped from a `draft`/`filing_year` anchor to its own
   casilla, so the record addresses it BY CASILLA ID rather than needing an
   exemption -- the truthful shape, since the casilla exists and holds the value.
4. `decl.tipo-declaracion` given `export_exemption_reason =
   "not_in_record_design"`: the abstract declaration type has no box of its own,
   AEAT printing only the complementaria/sustitutiva flags at 121-122, and an
   ordinaria declaration being the unmarked case.
5. **`review_status` advanced to `agent_reviewed`.** This was the last content
   gate and it is an ATTESTATION, not a repair: a filing-grade snapshot requires
   a reviewed revision. `agent_reviewed` is the enum's designated agent channel --
   "an agent reviewed the revision; an operator has not yet countersigned" -- and
   `reviewed_by = "agent-prepared-pending-operator"` is the established honest
   token here. **An operator re-stamp to `operator_reviewed` is still owed** and
   is what promotes this to a countersigned filing grade.

Two environment obstacles, neither a content defect: the publisher's atomic swap
is an `os.rename` and cannot cross drives, so the temporary root must sit on the
same volume as the registry; and the crashed first attempt left a journal in
state `intent` naming a candidate that no longer existed, which the recovery path
correctly refused rather than guessing. Clearing that journal was safe precisely
because `intent` means no destructive step had run and no backup existed.

**Modelo 184 is now the model to copy.** It is blocked on `export_layouts` alone,
as 347 was, and every step above transfers to it once its parse hole is closed.

### the-sello-position-is-a-deliberate-conservatism-not-a-gap | high | Tried to make it omissible, reverted, and the reason is the better finding

Modelo 347's last coverage gap is `@488+13 SELLO ELECTRONICO`, 57 of 58
positions. Its content states the reservation in full: "Campo reservado para el
sello electronico en presentaciones individuales, que sera cumplimentado
exclusivamente por los programas de la AEAT. En cualquier otro caso se rellenara
a blancos." The filer is told explicitly not to write those bytes.

Making it omissible was attempted and **reverted**. Measured first: consulting
the content with the existing owner window reclassifies NOTHING corpus-wide (the
owner sits ~105 characters from "reservado", past the 40-character window), while
a narrow pair -- the sello named in the description AND the content naming the
AEAT -- reclassifies exactly 25 positions over 215,416 fields, every one a sello
row in modelos 180, 193, 194, 296 and 347. Clean and tempting.

It was reverted because `_omissible_reason` states the opposing principle
outright: "Every signal is read from the cell that NAMES the field, never from
the explanatory prose beside it. An omissibility signal is the only thing here
that can turn a real gap into a pass, so it is deliberately the hardest thing to
trip." Reading the reservation out of the prose is precisely what that forbids,
and a measurement showing the blast radius is small is not an argument against a
rule about WHICH EVIDENCE COUNTS.

So the sello position is the gate being deliberately conservative, not a defect.
Modelo 180 has carried the same unwritten position since its layout was authored,
and 193, 194 and 296 will meet it too. Resolving it is a ruling for the gate's
owner, and the shapes are: let the naming cell carry the reservation (an
acquisition or parser question -- AEAT does name it there in workbook designs),
accept a filler as covering a position the design tells the filer to blank, or
declare the position written with blanks. Not a matter for a passing author.

**Modelo 360 settles which of the three shapes is right.** The parenthetical
above guessed that AEAT does name the reservation in the naming cell "in
workbook designs". Modelo 360's design is a PDF, not a workbook, and it names it
there anyway. The two designs record the identical regulatory fact in different
cells:

| modelo | position | naming cell | content cell | `_omissible_reason` |
|---|---|---|---|---|
| 360 | `@3166+13` | `Reservado para el sello electronico de la AEAT` | *(empty)* | `reserved for the Administracion` |
| 347 | `@488+13` | `SELLO ELECTRONICO` | `Campo reservado para el sello electronico en presentaciones individuales...` | `None` |

The matcher is behaving correctly in both. Modelo 360 needs no ruling, no
allowlist and no rule change on this axis: its sello classifies omissible on the
gate exactly as written, so the position will never be the thing standing between
360 and coverage. That is the control case, and it proves the gate is not
over-strict as a matter of principle. It is only that -- 360 has no export layout
at all, so nothing here says it reaches coverage; it says the sello is not among
the reasons it does not.

So the gap is narrower than it looked. It is not "the gate refuses a shape AEAT
uses" -- the gate accepts that shape whenever AEAT records it in the cell the
rule reads. It is that AEAT is **inconsistent about which cell carries the
reservation**, and 347 happens to use the other one. That kills the third shape
("declare the position written with blanks") as a general answer, since it would
also rewrite 360, which needs no help, and it makes the first shape the live one:
the evidence is genuinely absent from 347's naming cell, so the fix belongs at
acquisition or in the parser, not in the omissibility rule.

This also gives the fix a target phrase rather than a guess. Modelo 360 shows the
canonical AEAT wording for the naming cell -- `Reservado para el sello
electronico de la AEAT` -- so a parser or acquisition change has a known-good
form to reconcile 347's `SELLO ELECTRONICO` against, and a corpus-wide control
(360, and every other design already naming it) to regress against afterwards.

Still a ruling for the gate's owner, and still not a matter for a passing author.
But the ruling is now a choice between one live shape and a control case that
proves the rule right, rather than a choice between three shapes with no evidence
separating them.

## Recommendations

### build-the-variable-envelope-composition-contract | The single highest-leverage item

Eight modelos (151, 200, 202, 303, 308, 309, 322, 353) are blocked on one thing:
a typed, proven composition contract for the `<AUX>`-style variable envelope, of
which Modelo 303's `DP30300` is the worked example. Generalising it unblocks
eight modelos at once. Nothing else in this backlog has comparable leverage, and
no amount of per-modelo authoring substitutes for it.

### rule-on-pdf-wire-fact-authority | Blocks 347, 193 and 296; needs a decision, not a patch

Two changes, and only the first is mechanical. Select numeric fields on an
accent- and spelling-insensitive stem, as `_naturaleza_or_none` already does, so
`Numérico` joins `Num` and `N`. Then rule on the harder half: for a PDF design
with no Contenido column, decide whether descriptive prose in `content` counts as
a stated wire fact. It plainly does not, but saying so moves the boundary between
what the official design authorises and what a reviewed profile must, which is
the ADR's central split.

Until both land, no PDF-sourced design can be honestly generated. Modelo 347 is
ready to finish the moment they do: casillas authored, map authored, join
passing.

### unblock-modelo-184-in-the-parser-first | Its map is not the blocker, and neither is the generator

Two of 184's three records are refused by the generator's geometry rule before a
map is read, because its desglose parents overlap their sub-fields. **Fix that in
the parser, not the generator** -- see the correction appended to
`the-extractor-and-the-generator-disagree-about-desglose`. Measurement moved this
recommendation one layer up: 184 carries zero fields with `components`, so the
coverage validator's resolution is a no-op for it and the two authorities are not
actually in disagreement. `_matching_component_parent_index` never nests these
sub-fields because 184 numbers them as bare consecutive peers rather than with
the dotted ordinals that rule requires.

Reconstructing the containment is provably right -- all three records then land
byte-exact at their declared 500 -- but containment alone must NOT be the rule:
of the 51 bare-ordinal contained pairs in the bundled corpus, some are
self-declared desglose, some are grouping headers, and Modelo 038's are visual
chart-extraction artefacts that would be wrongly reparented. The open question is
which positive signal marks a real desglose, and it needs mutation coverage plus
a regression pinning 038 unnested.

184 is still the shortest path in the fleet -- it is blocked on `export_layouts`
ALONE, every other family already satisfied, which is true of no other refused
modelo. The authoring groundwork is done and recorded: the design is fully
readable and all 21 desglose categories are recovered from the source by position
range. After the parser fix: author the canonical casillas for its 132 anchors
(six exist today), then the semantic map and render profile, then publish through
`check_generated_export_tree`.

### five-modelos-closed-and-what-the-remainder-actually-costs | the campaign's current state

Registry validation failures fell **88 to 70** across this campaign. Five modelos
now validate clean, and they divide sharply into two kinds of work.

**Published generated export trees (2):** Modelos **347** and **184**, both
`filing` grade with zero failures. These were the expensive ones -- semantic map,
render profile, casilla authoring and publication -- and they are documented in
the findings above along with the five infrastructure gaps they exposed.

**Family authoring, no publication needed (3):** these already had their export
layouts and were blocked only on unpopulated families.

- **Modelo 720** -- one family. `verification_predicates` dispositioned: seven
  casillas, zero formulas, none computed, `calculation_class = "informative"`,
  and its formulas family already dispositioned on the same ground. A predicate
  guards a calculated result and 720 settles no tax; the under-declaration risk
  it exists for surfaces on the taxpayer's own IRPF or IS return as a ganancia
  patrimonial no justificada, which is where a predicate could bind base to cuota.
- **Modelo 115** -- three families, two of them REAL authoring rather than
  dispositions. A quarterly `filing_schedule` (deliberately not monthly: this
  revision's own `period_selector` admits only the four quarterly periods, so
  declaring the grandes-empresas monthly regime would assert a filing it cannot
  resolve). A `verification_predicate` pairing casilla 01 (perceptor count) with
  02 (base), both bound from the ledger. And a `dependency_classifications`
  disposition: 180 is the annual resumen that depends on 115, so the dependency
  runs the other way and nothing upstream exists to classify.
- **Modelo 111** -- three families. A `verification_predicate` pairing casilla 08
  (importe, actividades economicas) with 09 (retencion). A `parameters`
  disposition: both formulas are pure aggregation over already-withheld amounts,
  so no rate is applied here -- contrast 115, which genuinely holds
  `irpf.urban_rental_withholding_rate`. And the same dependency disposition, with
  190 as the resumen that depends on 111.

**Two predicate choices are worth recording, because the obvious pairing was
wrong in both cases.**

For Modelo 115 the obvious pairing is base to retencion (02 to 03). It is
**tautological**: 03 is computed by this revision's own formula as
`percent(02, rate)`, so a positive 02 mechanically yields a positive 03 and the
predicate would assert only that the engine's arithmetic worked. 01 and 02 are
independently bound from the ledger, so their disagreement is a real observation.

For Modelo 111 the obvious antecedent is the trabajo block (01/02/03). It
**false-fires**: withholding on rendimientos del trabajo is scaled to the payer's
projected annual rate and is lawfully ZERO below the thresholds, so a retenedor
paying a low-wage employee correctly reports percepciones with no retencion --
the precise objection Modelo 100's own predicates record. The actividades
economicas block carries a flat rate under RD 439/2007 art. 95 with no threshold,
so a positive importe with zero retencion there has no lawful ordinary reading.

**What the remaining 70 failures cost, so the next attempt sizes them correctly.**

- **Modelos 193, 296, 360** are generatable and the 347/184 template applies
  end to end -- but the map cannot be DERIVED for them the way 184's was. That
  shortcut worked because 184 already carried 87 casillas declaring their own
  position ranges, so 108 of 128 anchors resolved automatically. Modelo 193 has
  **three casillas for 69 anchors**; the casillas must be authored first, and
  that is the bulk of the work, not the map.
- **Modelos 136, 145, 216, 721** each show ONE failure but block on seven to ten
  families apiece. A single failure line is not a small task here: it is one
  message enumerating a whole modelo's unauthored surface.
- **Modelo 100** blocks on `extraction_profiles` alone, which sounds like the
  cheapest remaining item and is not: an extraction profile needs label patterns
  grounded in AEAT-published instruction pages fetched to corpus, and 100 carries
  1,531 casillas.
- **Modelos 180, 190, 341, 349, 390, 714** are coverage failures on layouts that
  already exist -- a different task again from the ones closed here.
- **Modelos 151, 200, 202, 303, 308, 309, 322, 353** remain behind the one
  variable-envelope composition contract, unchanged and still the highest-leverage
  item in the campaign.

**Review status is a separate axis and was deliberately left alone.** 91 of 93
bundled revisions are `pending_review`; the only two that are not are 347 and
184, stamped `agent_reviewed` because publication builds a filing-grade snapshot
and refuses without it. Mass-stamping the other 91 would assert a review that did
not happen, so it was not done, and an operator countersignature is owed on the
two that are stamped.

### modelos-193-and-296-share-one-parser-gap | high | Characterised exactly, with the fabrication hazard measured and the discriminator identified

Modelos 193 and 296 are listed above as "generatable, needs casillas and a map".
That is true but incomplete: both also carry a **foral apportionment desglose the
parser cannot read at all**, and it is the SAME gap in both, so it is one piece
of work rather than two.

Modelo 193's tipo-2 record declares `249-313 RETENCIONES E INGRESOS A CUENTA
INGRESADOS EN EL ESTADO, EN LAS DIPUTACIONES FORALES DEL PAIS VASCO Y EN LA
COMUNIDAD FORAL DE NAVARRA` -- 65 positions -- and its prose says the retenedor
"cumplimentara los siguientes subcampos, para identificar de forma diferenciada
las retenciones e ingresos a cuenta ingresados a cada una de las Administraciones
competentes". It is 5 x 13: Hacienda Estatal at `(249-261)` and one each for the
foral administrations, and each 13 further splits into an 11-digit parte entera
and 2 decimals. Modelo 296 carries the identical construction at `(85-97)`.

**None of it parses**, and the cause is exact. AEAT writes these sub-rows with a
PARENTHESISED range -- `(249-261) HACIENDA ESTATAL` -- and
`_NARRATIVE_PDF_ROW_RE` anchors on a bare leading digit, so the row matches
nothing and stages no candidate. Verified directly: the parenthesised line yields
`regex=False, candidate=None`, while the second-level `249-259 Parte entera`
parses fine as `(249, 11)`. The parent also declares NO count word -- "los
siguientes subcampos", not "se subdivide en cinco" -- so the count-gated
conjunction that recovered Modelo 184's hole cannot fire here either.

**Left alone this does not refuse, which is the dangerous part.** `@249+65`
carries `Numerico`, so it renders as ONE 65-digit numeric field, and because the
parent has no `components` the coverage gate's required position IS that 65-byte
span -- so a tree writing one number across five territory buckets passes
coverage. That is precisely the failure this audit's first finding names: a tree
that looks complete and is wrong about what the record is. Modelo 193 must not be
published until this is resolved.

**The fabrication hazard is real and was measured before proposing anything.**
Scanning every extracted design for parenthesised ranges finds **36 lines across
three modelos**, and they are NOT one population: 193's twenty and 296's ten are
genuine position subcampos, but Modelo 200's six are `(1923 - 2012) (T) -
Deduccion pendiente/generada [03454]` -- YEAR ranges in a deduction table.
Accepting a parenthesised range as a position would manufacture a field at offset
1923 of length 90, the invented-position class this parser's own comments call
the worst failure available.

**The discriminator that separates them already exists in this codebase:
containment.** A genuine subcampo range falls wholly inside its parent's declared
span -- `(249-261)` sits inside `249-313` -- while `(1923-2012)` sits inside
nothing, and 1923 exceeds every record extent in the corpus. So the shape of the
fix is: stage a parenthesised range as a CANDIDATE only, never as a read row, and
leave admission to the existing guarded machinery, which already refuses anything
that does not land in a real hole. The remaining piece is that admission into a
desglose parent's span currently requires a declared COUNT, and these parents
declare only that subcampos follow -- so the conjunction would need a second
admissible form: parent declares a subdivision, candidates tile its span EXACTLY,
no count required. For 193 that is five 13-byte candidates tiling 249-313 to the
byte.

That is a bounded change with a known blast radius and two ready regressions
(Modelo 200's year ranges must stay unadmitted; 193's and 296's must nest), but
it is parser work in the highest-risk area of this tree and wants its own change
rather than being folded into an authoring push.

**ATTEMPTED AND REVERTED, and the negative result is the useful part.** The fix
sketched above was implemented and measured. It failed on BOTH axes, so it is
recorded here rather than left as a plausible-looking recommendation the next
attempt would pay for again.

What was built: `(249-261)`-style parenthesised ranges staged as CANDIDATES only
(never read rows), plus a second admissible form in the desglose gap fill -- a
parent that declares a subdivision WITHOUT naming a count, where candidates tile
its span exactly.

**It did not fix Modelo 193.** `@249+65` still parses with `kids=0`. The reason
is specific and kills the approach: the solver walks the parent's span needing a
candidate at each successive offset, and only the FIRST subcampo -- `(249-261)
HACIENDA ESTATAL` -- is printed in that form. The remaining four foral subcampos
are not written as parenthesised ranges anywhere the extractor can see, so the
walk dead-ends at 262 and admits nothing. Staging the parenthesised form is
necessary but nowhere near sufficient; the design simply does not print the other
four in any shape currently readable.

**And it was far too broad.** Corpus-wide admissions went from **3 to 636** --
Modelos 604, 720 and others gained hundreds of newly-admitted sub-fields, because
"se subdivide" is a common phrase and dropping the count requirement left exact
tiling as the only guard. Registry validation stayed at 70 and every modelo with
a published layout stayed clean, so nothing REGRESSED -- but "nothing regressed"
is not evidence that 636 unreviewed changes to how designs are read are right,
and that is far more parse surface than one modelo's fix should move.

So the count requirement is doing real work and should stay: it is what keeps the
rule at one site. Reverted to 3 admitted fields, 70 failures, 102 tests green.

**What this means for 193 and 296.** They are NOT blocked on a rule that needs
relaxing. They are blocked on the design's own printing: four of the five foral
subcampos are unreadable in the current extraction, and no admission rule can
recover a row the extractor never sees. The next attempt should start at
acquisition -- whether a different extraction of these PDFs surfaces those rows
at all -- and not at the gap-fill rules, which is where this attempt spent its
effort. Until then, neither modelo may publish: `@249+65` carries a numeric
naturaleza and no components, so it would render as ONE field spanning five
administrations and coverage could not object.

### modelo-216-closed-and-what-a-nine-family-modelo-actually-costs | six modelos clean, 88 to 69

**Modelo 216 (IRNR retenciones) validates clean**, taking the campaign to six
modelos and registry failures from 88 to **69**. It went from NINE blocked
families to zero in one pass, which contradicts this audit's own earlier sizing
-- "136, 145, 216 and 721 each show ONE failure but block on seven to ten
families apiece" was read as "each is a whole modelo's work". For 216 it was not,
and the reason generalises: most of those families were resolvable from evidence
already in the tree.

**Authored (5):** `filing_schedules` (quarterly; the monthly grandes-empresas
regime the AEAT instructions describe is deliberately NOT declared, because this
revision's period_selector admits no monthly period), `verification_predicates`,
`applicability`, `extraction_profiles`, `live_cross_references`, plus the
extractor and portal application links those last two require.

**Dispositioned (4):** `parameters` (six formulas, all pure aggregation -- the
IRNR rate is applied by the retenedor at payment time and arrives already
withheld), `dependency_classifications` (296 is the resumen that depends on 216,
not the reverse), `relations` (nothing folds in; the prior-autoliquidacion
reference is a formula over its own casillas), and `bindings`.

**The bindings disposition is the one worth reading.** It was nearly deferred as
"a modelling question I should not answer", which was the right instinct and the
wrong conclusion -- the answer was checkable. `retenciones_aggregation` scopes by
`RetencionScheme`, and every member of that enum is an IRPF scheme:
`rendimientos_trabajo`, `rendimientos_trabajo_administrador`,
`actividades_economicas`, `actividades_profesionales`, `premios`,
`arrendamiento_urbano`, `intereses`, `dividendos`, `otros_capital_mobiliario`.
None is IRNR. So binding 216 to any available scheme would aggregate RESIDENT
IRPF withholding into a non-resident return, and the `dividendos` member is the
easiest way to make that error: modelo 216 splits dividendos from resto exactly
as the IRPF capital schemes do, but that member serves resident recipients
(modelo 123). The family is empty because the aggregation store models no IRNR
scheme -- and the disposition says so, rather than implying the values are
unbindable in principle. **Adding an IRNR scheme is a core-taxonomy change and
remains open work this disposition does not perform.**

**The extraction profile is grounded and honestly caveated.** Targets match by
PRINTED BOX NUMBER rather than label, and that is forced rather than preferred:
the bundled AEAT instructions label casillas 05 and 06 identically ("Numero de
rentas", under two different headings), and the same repetition runs through
08/09, 11/12, 14/15 and 17/18 -- modelo 100's own profile records that the parser
rejects an ambiguous label match. It is declared `review_required` and
`provisional_pending_specimen = true`, because no filed or synthetic 216
justificante is bundled to round-trip against; the patterns rest on
AEAT-published text alone, and a specimen is what would earn strict confidence.

**Revised guidance for 136, 145 and 721.** Size them by asking, per family,
whether the evidence is already in the tree -- sibling modelos with the same
legal shape, a bundled instructions page, an enum whose members settle the
question -- before assuming each needs research. 216's nine families needed one
bundled HTML page and four sibling fragments. Modelo 145 is the likeliest to
differ: it is a communication to the PAGADOR rather than a filing to AEAT, so its
`applicability` and `verification_expectations` need thought rather than
transfer.

### modelos-136-and-721-are-acquisition-not-authoring | corrects the sizing this audit gave one entry earlier

The entry above revised 136, 145 and 721 upward in tractability -- "size them by
asking, per family, whether the evidence is already in the tree". Measured, that
is wrong for 136 and 721, and the reason is worth recording because it is
invisible from the family list.

Both block on **`export_layouts`**, and neither can have one authored from what is
bundled.

**Modelo 136** (gravamen especial sobre premios de loterias, DA 33 LIRPF, Orden
HAP/70/2013) has **no design corpus at all** -- no `disenos_registro/modelo_136`
directory, no `aeat-dr-136-*` source, and no layout source of any kind among its
seven `source_refs`. And that absence is EVIDENCE rather than a gap in this
repository: the bundled design-corpus manifest was harvested on 2026-08-15 from
all ten of AEAT's own Diseños de Registro index pages, including
`modelos-100-199.html`, and it enumerates 58 modelos. Modelo 130, 131, 145, 151,
156 and 165 are all present from that same page; 136 is not. AEAT does not
publish a diseño de registro for it.

**Modelo 721** (monedas virtuales en el extranjero, art. 42 quater RGAT) is the
more interesting case, because it DOES cite layout authority --
`boe-modelo-721-2023-layout` and `boe-modelo-721-2024-layout`, both bundled and
sha-pinned. Both are `kind = "form_spec"`, the BOE orden's own anexo rather than
an AEAT diseño, which is why the earlier export-exemption work recorded that
"`form_spec` does not count". Running the shipped parser over them directly shows
why that classification is right and not merely conservative:

- The 2023 BASE anexo (`boe-a-2023-17429-modelo-721-layout.pdf`) yields
  `record-design PDF did not contain parseable field rows` -- no field rows at
  all.
- The 2024 anexo (`boe-a-2024-27528-modelo-721-layout-amendment.pdf`) DOES parse,
  and is refused for the right reason: `first field starts at position 58;
  expected 1`. It is an AMENDMENT that prints only the changed positions, so
  accepting it would author a layout silently missing positions 1-57.

So 721 has bundled layout authority that is, between the two documents, neither
complete nor machine-readable. Reclassifying either source to `record_design`
would not help; the parser's two refusals are correct statements about the
documents.

**Consequence for sizing.** These two belong with 193 and 296 in the
ACQUISITION bucket, not the family-authoring bucket:

- 193, 296 -- design published and bundled, but part of it (the foral
  apportionment subcampos) is unreadable by the current extraction.
- 136 -- no diseño published by AEAT at all.
- 721 -- layout published only as a BOE anexo, unparseable in the base document
  and partial in the amendment.

None is unblocked by more registry authoring, and the remaining families on each
cannot clear the modelo while `export_layouts` stands. Modelo 145 is NOT in this
bucket -- it has both a bundled diseño and an authored fixed-width layout
already, so the earlier "evidence may be in the tree" reading still holds for it,
with the caveat that it is a communication to the PAGADOR rather than a filing to
AEAT and its applicability and verification families need thought rather than
transfer from a sibling.

### modelo-349-closed-and-a-fill-omissibility-gap-it-exposed | seven modelos clean, 88 to 63

**Modelo 349 (declaracion recapitulativa de operaciones intracomunitarias)
validates clean**, taking the campaign to seven modelos and registry failures to
**63**. It is the first COVERAGE repair closed, and the shape of the work is
different from the family authoring that closed 720, 115, 111 and 216.

**The coverage gap was an under-declaration hiding as a filler.** The layout
already declared fields at `@179+17` and `@196+40` in both tipo-2 records -- named
`...-sustituto-nif-filler` and `...-sustituto-apellidos-filler`, `kind =
"filler"`. The design names them `NIF EMPRESARIO O PROFESIONAL DESTINATARIO
FINAL` and `APELLIDOS Y NOMBRE O RAZON SOCIAL DEL SUJETO`, and each field's own
content cell completes the name and states the condition: `... PASIVO SUSTITUTO
(Solo se cumplimentara en caso de clave ...)`. They carry a real taxpayer
identity whenever that clave applies, so modelling them as fillers wrote an empty
NIF over a position AEAT expects filled. Two casillas were authored
(`sustituto.nif`, `sustituto.apellidos-razon-social`, `required = false` because
the CONDITION is optional, not the datum) and the four fields rewired from
`filler` to `casilla`. This is exactly the case `_covers` documents -- "a FILLER
never covers a required position" -- working as intended.

**A genuine gate gap was found underneath it.** The same refusal listed
`@236+265` in the rectificaciones record, whose naturaleza is `Blancos` and whose
span runs to the record's declared 500 -- trailing fill. It was NOT omissible,
because `_omissible_reason` reads fill only from the DESCRIPTION and this row's
description cell had caught the page footnote `* Todos los importes seran
positivos.` instead of the fill word. The gate was therefore demanding real
taxpayer data for 265 bytes the design fills with blanks -- a requirement no
correct layout can satisfy, which is the incentive inversion that module exists
to remove.

Fixed by reading fill from the NATURALEZA column as a separate signal
(`_declared_fill_naturaleza`), deliberately NOT by widening `_DECLARED_FILL`:
that pattern is anchored on purpose, because the same words appear inside real
data positions (`"X o blanco"`, `'"0" - blanco, "1" - Si'`) and excusing those
would pass hundreds of slots in silence. A naturaleza of `Blancos` states no
choice -- it is the design typing the field, the same column that says `Numerico`
everywhere else. `OBLIGATORIO` still wins outright.

**Blast radius measured before landing: exactly SIX positions.** Of 152
Blancos-typed fields in the bundled corpus, 146 were already omissible through
their description; the six this admits are every one a genuine fill run whose
description says it differently -- Modelo 194's `CEROS.` twice, Modelo 296's
`BLANCO MODELO 296`, Modelo 604's English `BLANK` twice, and Modelo 349's
footnote-displaced row. Registry failures moved 69 to 66 on that change alone
(Modelo 390's 2025 revision also cleared its coverage refusal).

**Then five families, on the patterns already established:** a
`verification_expectation` (zero-formula recapitulative, `tolerance = 0.00`,
`extraction_unreliable`), a `verification_predicate` pairing
`decl.numero-operadores` with `decl.importe-operaciones` -- both BOUND, so
non-tautological, and the cross-border angle is what makes it matter: a zero
total against a non-zero operator count desynchronises the Spanish side of the
VIES reconciliation AEAT runs against the counterparties' own declarations -- and
dispositions for `formulas`, `parameters` and `dependency_classifications`.
Modelo 349's formulas disposition has its own ground worth noting: its four
declarante totals are not formula-computed but `input_kind = "bound"`, so the
aggregation they represent has a home and it is the binding layer, not this
family.

**Remaining coverage gaps, now the smallest category by effort:** 200 (23 of
52), 232 (182 of 222), 390 (424 of 478 and 424 of 482), 714 (203 of 1163 and 203
of 1174), 180 and 190. Modelo 349 suggests reading each one's missing positions
for a filler standing where a conditional datum belongs before assuming the
layout simply lacks fields.

### the-declared-count-desglose-rule-generalised-and-its-second-attempt-kept | 88 to 56

Registry failures are at **56**. Two changes since the Modelo 349 entry, and the
second is the one that needed the most care because a NEARLY IDENTICAL change was
reverted earlier in this campaign.

**Single-position corrections authored for Modelo 190.** Its perceptor record
declares `81-107 ... Este campo se subdivide en tres` (81 signo, 82-94 percepcion
integra, 95-107 retenciones) and `108-147 ... se subdivide en cuatro` (108 signo,
plus three 13-byte amounts). Both leading SIGNO bytes are printed as a bare
single position with no naturaleza -- `81 SIGNO DE LA PERCEPCION INTEGRA: Se
cumplimentara ... se consignara una <<N>>` -- which the parser refuses outright,
because that shape is otherwise indistinguishable from a numbered prose sentence.
`RecordDesignSinglePositionCorrection` exists for exactly this, so the two rows
were declared in a `.record-design-correction.json` sidecar beside each of
Modelo 190's two design PDFs, quoting AEAT's own text as the reason. This is the
sanctioned route: a declaration for one exact `(sheet, position)`, still subject
to the gap-fill containment test, rather than loosening what the parser accepts.

**The desglose gap fill now admits a parent with NO already-read children.** It
previously required at least one, which skipped precisely the designs where the
whole desglose went unread -- Modelo 190's two groups have zero read sub-rows.
The declared COUNT still carries the proof: candidates must tile the parent end
to end AND number exactly what it declares.

**Why this is not the change that was reverted.** The earlier attempt dropped the
COUNT requirement (admitting any parent that merely said "se subdivide"), took
corpus admissions from 3 to 636, and did not fix its target. This one keeps the
count and drops only the already-read-child precondition. Measured: corpus
admissions 3 to **515** across 21 modelos, registry failures **63 to 56**, and a
full before/after diff shows **no genuine regression** -- the only two "added"
lines are Modelo 190's own coverage line re-worded as its denominator grew (52 to
62 required positions, which is correct: nesting moves required positions from a
parent span onto its sub-fields) and one unrelated peer edit on Modelo 721.

**Verified by construction plus spot-check, not individually.** Every admission
is inside a parent whose own text declares a count and whose candidates tile it
exactly. Modelo 180 was checked against AEAT's text end to end: `59-107 PERSONA
CON QUIEN RELACIONARSE ... Este campo se subdivide en dos`, admitting `@59+9
TELEFONO` and `@68+40 APELLIDOS Y NOMBRE`, 9 + 40 = 49 = the full span, count 2.
Modelos 184 and 190 were verified the same way. **515 admissions were not
reviewed one by one**, and that is the honest limit of this evidence: the
argument is that a declared count AND exact tiling agreeing simultaneously is
hard to satisfy by coincidence, supported by three worked cases and a
net-negative failure delta.

**Modelo 190 is not closed.** It is at 28 of 62 positions with 34 still
unwritten, and they are genuinely absent fields rather than parse artefacts:
`@27+9 NIF DEL REPRESENTANTE LEGAL`, `@76+2 CODIGO PROVINCIA`, `@148+4 EJERCICIO
DEVENGO`, `@152+1 CEUTA O MELILLA`, `@153+4 ANO DE NACIMIENTO`, `@157+1 SITUACION
FAMILIAR`, `@158+9 NIF DEL CONYUGE`, `@167` discapacidad, `@168` contrato,
`@169` titular unidad de convivencia, `@170` movilidad geografica, `@171+13`
reducciones, `@184+13` gastos deducibles, `@197+13` pensiones compensatorias and
more. That is roughly 20 casillas to author with grounding plus their export
fields -- the same shape as Modelo 184's declarante block, and the next concrete
piece of work on this modelo.

### modelo-100-is-acquisition-blocked-too-and-the-0224-near-miss | the cheapest-looking item is not authorable

Modelo 100's 2020 revision shows ONE blocked family, `extraction_profiles`, and
its sibling revision 2021 already carries a rich 21-target profile. That makes it
look like the cheapest remaining item in the campaign. It is not authorable, and
the reason is worth recording alongside a near-miss it produced.

**The ids were checked, not assumed, and one of them moved.** Resolving each of
the 2021 profile's 21 targets through `semantic_role` against the 2020 revision's
OWN casilla set -- the discipline `no-silent-under-declaration` and the Modelo 100
predicates already require -- shows 20 resolving to the identical id. The
twenty-first does not: casilla **`0224` exists in BOTH revisions with DIFFERENT
roles**, `irpf_ed_rdto_neto` in 2020 against `irpf_ed_rdto_neto_previo_reduccion`
in 2021. AEAT split that concept between the two years. Copying the target list
verbatim -- which is what "the sibling revision already has one" invites -- would
have pointed the label pattern `Rendimiento\s+neto\s+\[` at a box the authority
redefined, extracting a value into a real casilla that means something else.
Nothing would have refused it.

**And the patterns themselves cannot be grounded for 2020.** The 2021 profile
records its own provenance honestly: "All label_patterns were authored against
the 2021-0A.pdf, 2022-0A.pdf and 2023-0A.pdf renders." The bundled justificante
fixtures for Modelo 100 are 2021, 2022, 2023, 2024 and 2025 -- **there is no 2020
render**. The 2020 revision's own layout source, `boe-modelo-100-2020-form`,
resolves to `corpus/normatives/html/orden-hac-248-2021.html`, which is the
approving orden rather than the printed form: probing it for four of the
profile's own labels finds only `Base liquidable general`, and not `Cuota integra
estatal`, `Cuota diferencial` or `Resultado de la declaracion`.

So authoring this profile would mean transplanting patterns validated on
2021-2023 documents and asserting they hold for 2020 -- grounding by analogy
across filing years, which this campaign's rules name explicitly as a defect
("mapping one year's casilla id to another's to copy grounding"). The `0224`
finding is the concrete proof that the analogy is unsafe here: if a casilla can
change meaning between adjacent years, a printed label can too, and neither
change announces itself.

**Modelo 100 therefore joins the acquisition bucket** with 136, 193, 296 and 721.
What unblocks it is a 2020 artefact -- a rendered 2020 justificante fixture, or a
2020 form document carrying the printed box labels -- not registry authoring. It
is worth stating plainly because the single-family failure line makes it look
like the opposite.

### modelo-180-2023-closed-and-an-ungrounded-deadline-window-found | 88 to 54

Registry failures are at **54**. Modelo 180's `2023-y-siguientes` revision now
validates clean; its `2019-2022` sibling is down to ONE blocked family, and that
one is a grounding question rather than authoring.

**Three families authored across both revisions.** `filing_schedules` (annual,
one period `0A` -- the schedule agrees with the revision's own period_selector
and states no dates, because the calendar lives on `deadline_windows`, a separate
family and a separate evidence question). `parameters`, dispositioned: both
formulas are `op = "copy"` over a relation (`decl.base-total` copies
`modelo-180-rel-115-base-anual`, `decl.retenciones-total` copies its retenciones
twin), and a copy applies nothing -- the rate was consumed by the quarterly
modelo 115, whose casilla 03 is `percent(02,
irpf.urban_rental_withholding_rate)`, which is where this registry holds it. And
a `verification_predicate` pairing `decl.total-perceptores` (bound, from the
perceptor store) with `decl.base-total` (copied from the 115 relation): the two
come from genuinely different places, so their disagreement is real, and
exposing it is what an annual resumen is FOR -- AEAT reconciles 180 against the
four 115 filings, so a resumen naming arrendadores while folding in no base means
either the quarterly chain or the perceptor records are incomplete.

**One authoring mistake, caught by the gate and worth recording.** The schedules
were first written with `profile_conditions` on
`field = "enrollment.pays_withheld_income"`. That is an APPLICABILITY payer fact
(`_applicability_payer_facts.PAYS_WITHHELD_INCOME`), not a filing-schedule
predicate, and the two vocabularies are separate: the user-profile schema
declares the schedule selectors, and it does not declare that one. The refusal
was correct and the fix was to drop the conditions entirely, which is also the
truthful shape -- modelo 180 has one annual schedule applying to every retenedor
obliged to file it, and the quarterly/monthly split that modelos 111 and 115
condition on is a property of the AUTOLIQUIDACION cadence with no counterpart in
an annual resumen.

**The remaining family is an EXISTING grounding gap, not new work.** Revision
`2019-2022` needs `deadline_windows`, and modelo 180's January filing plazo is
not established anywhere in the bundled corpus:

- `orden-hap-1732-2014` (the 2019-2022 revision's own orden) contains the word
  "enero" **zero times** in 86,999 characters of extracted text.
- The AEAT procedure page has one "enero", and it is a reference to Orden
  HAC/171/2004 approving modelo 184.
- The `2023-y-siguientes` windows that DO exist cite `orden-hfp-1284-2023:art-7`,
  and reading that article shows it amends modelo 180's RECORD DESIGN --
  "Posiciones Naturaleza Descripcion de los campos 76-77 Numerico CODIGO
  PROVINCIA ..." -- rather than establishing any plazo.
- The plazo's real home is the Orden de 20 de noviembre de 2000 that art. 7
  amends, and the bundled excerpt of it is 898 characters of `apartado primero`
  with no "enero" either.

So the existing 2023 windows assert `opens_on 2025-01-01 / closes_on 2025-01-31`
on a citation that does not carry those dates. That is a pre-existing defect this
work did not introduce and did not fix, and it is the reason 2019-2022's windows
were NOT authored: replicating an ungrounded date across four more filing years
would have cleared a failure line by making the same unbacked assertion four more
times. Grounding it needs the full text of the Orden de 20 de noviembre de 2000
(or whichever provision fixes the plazo), which is an acquisition step.

### modelo-131-and-the-plazo-provision-that-was-missing-from-the-catalogue | 88 to 49

Registry failures are at **49**. Modelo 131's `2024` and `2025` revisions now
validate clean, and the work turned up a legal-catalogue gap affecting Modelo 130
too.

**RIRPF art. 111 was not in the catalogue, and it is the provision that
ESTABLISHES the pago fraccionado plazo.** Modelo 130's existing deadline windows
cite `rd-439-2007:art-110`, but reading that article shows it is titled "Importe
del fraccionamiento" and fixes the AMOUNT (20 per cent for estimacion directa,
the 4/3/2 per cent scale for objetiva). The dates live one article further on,
and article 111 "Declaracion e ingreso" states them exactly: "Los tres primeros
trimestres, entre el dia 1 y el 20 de los meses de abril, julio y octubre" and
"Cuarto trimestre, entre el dia 1 y el 30 del mes de enero".

It was missing because the separately bundled per-article files run 100, 108,
109, **110**, 113, 115, 116 -- they skip 111 -- so the obvious citation was the
nearest available one. The full consolidated `rd-439-2007.html` IS bundled and
carries article 111 verbatim, so a legal entry was authored against it with both
plazo sentences as `required_text`, which the registry's own evidence gate then
validates against the corpus text. Stamped `agent_reviewed` /
`agent-prepared-pending-operator`, per the catalogue's existing honest-provenance
convention. **Modelo 130's windows still cite article 110 and should be
re-pointed**; that was not changed here.

**Then three families across three revisions.** `filing_schedules` for
2019-2023, 2024 and 2025 (quarterly, mirroring this modelo's own 2026 revision).
`deadline_windows` for 2024 and 2025, with their dates MIRRORED from modelo 130's
reviewed windows for the same filing years rather than recomputed: both modelos
are pagos fraccionados del IRPF filing on the one art. 111 plazo, so the
working-day rolling is identical, and 130's dates already encode it (2024 Q1
closes on the 22nd because the 20th was a Saturday). `payment_cutoff_on` was
deliberately OMITTED -- the domiciliacion cutoff is a separate AEAT operational
date with no grounded source here, and the field is optional. Plus the `deadline`
application link both revisions then required.

**And `casilla_continuidad_evolutions` for 2024, authored from measurement.**
Sixteen `continuidad_id`s exist in both 2019-2023 and 2024; for every one the
`legal_refs` tuples are identical AND the Spanish labels are byte-identical in
the locale catalogue, so all sixteen are `evolution_kind = "unchanged"` -- a
measured result rather than a default. The nine module-unit concepts 2024
introduces (`irpf-pf-modulos-*`) get no row, because a concept with no prior
revision has no transition to declare, and none was retired.

**What remains on 131 is the same grounding wall as Modelo 180.** Revision
`2019-2023` needs windows for filing years 2019 through 2023, and modelo 130
declares windows only for 2024, 2025 and 2026 -- there is nothing to mirror.
Computing them means applying working-day rolling to five years of quarterly
deadlines, which needs a national holiday calendar this repository does not
bundle; weekend-only rolling would silently produce a wrong date wherever the
20th fell on a holiday. Left unauthored deliberately.

**Operational note for anyone reading failure counts.** The shared tree was under
heavy concurrent write during this stretch and produced two spurious readings --
157 and 670 unique failures -- before settling at the real value. The loader says
so explicitly when it happens ("registry directory changed during cache
fingerprinting; retry after concurrent registry writes settle"). Re-read before
believing a jump.

### modelo-369-closed-across-all-three-oss-schemes | 88 to 46

Registry failures are at **46**. Modelo 369's `esquema-union`,
`esquema-exterior` and `esquema-importacion` revisions all validate clean.

**Two extraction profiles authored by mirroring this modelo's own union
revision.** That profile targets only `decl.ejercicio` and `decl.periodo`, with
labels `Ejercicio:` and `Per[ií]odo:`. Those two are the declaration HEADER AEAT
prints identically across all three OSS/IOSS schemes -- the scheme is selected on
the form rather than by printing a different header -- so the labels transfer
where a scheme-specific figure would not, and nothing else was targeted. Declared
`review_required` and `provisional_pending_specimen`, unlike the union profile
which is `corpus_round_trip_verified`: the bundled justificantes carry one 369
render (`2024-1T`) and there is no exterior or importacion specimen to
round-trip against.

**Three dispositions per revision.** `parameters`: the single formula sums the
per-member-state cuota casillas, and a sum applies nothing -- the VAT rate is the
CONSUMING member state's own, applied when each country cuota is determined, and
it arrives here already applied, because this declaration exists to route amounts
owed to other member states through the Spanish one-stop shop rather than to
compute them. `dependency_classifications`: the cuotas are bound from the
declarant's own OSS sales records, and the reconciliation runs OUTWARD to the
consuming member states -- the operations reported here are EXCLUDED from the
ordinary modelo 303 liquidacion rather than derived from it.

**The `verification_predicates` disposition is the one with a real argument
behind it, and it is the mirror image of the Modelo 115 and 111 predicates.**
Those two were authorable because each had a pair that could independently
disagree -- a bound perceptor count against a bound base, a bound importe against
a bound retencion. Modelo 369 has no such pair: measured on the revision, every
input casilla is a per-member-state cuota (`input_kind = bound`) and the only
computed casilla is their arithmetic sum, so any implication between a component
and the total holds by the addition itself and would assert nothing beyond the
engine adding correctly. That is exactly the tautology this campaign refused when
choosing Modelo 115's antecedent, applied in the opposite direction: there,
rejecting the tautological pair left a real one; here, rejecting it leaves none,
and the honest conclusion is that the family has nothing to say rather than that
a predicate is owed. The under-declaration risk is real but lives where the
cuotas are determined -- in the OSS sales records the bindings read -- not in a
relation between two casillas of this revision.

### modelo-145-eight-of-nine-families-and-the-form-that-never-reaches-aeat | 88 to 46

Modelo 145 went from NINE blocked families to one. The one that remains is
acquisition-blocked, so it is recorded here rather than left looking like
authoring.

**The governing fact, and it grounds most of the rest.** RD 439/2007 art. 88.1,
read from the bundled article text: "Los contribuyentes deberan comunicar al
pagador la situacion personal y familiar ... quedando obligado asimismo el
pagador a conservar la comunicacion debidamente firmada." **Modelo 145 is never
filed with AEAT.** The perceptor hands it to whoever pays them and the payer
keeps it. That single fact settles two families outright:

- `verification_expectations` -- an expectation reconciles a FILED return against
  the engine, and there is no filed document to reconcile against. This is a
  DIFFERENT ground from the zero-formula informativas that DO carry expectations
  (modelos 182, 184, 232, 347, 720): those are filed with AEAT and their figures
  can be checked against a justificante. The distinction matters, because the
  earlier reasoning in this campaign was "zero formulas does not excuse an
  expectation" -- and it still does not; what excuses it here is that nothing is
  filed.
- `live_cross_references` -- no AEAT surface to read back, because nothing of
  this form ever reaches one.

**Five more dispositions on measured facts:** `parameters` and
`verification_predicates` (zero formulas, no computed casilla, no base or cuota,
and `cuota_bearing = false` on its own applicability -- the retention rate these
circumstances feed is computed on the PAGADOR's side under arts. 80 to 87 and
never appears on this form); `bindings` (all 56 casillas are `input_kind =
manual`, and only a BOUND casilla requires a binding -- these are the perceptor's
own civil status, disability, dependants and mortgage circumstances, known to
that person, not aggregated from a ledger); `dependency_classifications` (145 is
the INPUT to a withholding calculation, not a summary of one -- the dependency
runs downstream to modelos 111 and 190); and `constructs` (no totals to group).

**An authoring correction worth recording.** `applicability` was first written
with `required_payer_fact = "receives_withheld_income"`, which does not exist.
Every member of `PayerFact` is a fact about someone who PAYS or trades --
`pays_withheld_income`, `pays_rent_with_retencion`, `trades_intracommunity` --
and modelo 145 is submitted by the PERCEPTOR, the person who RECEIVES the
rendimientos. The field is optional, so it is now unset with a comment saying
why, rather than fitted to the nearest payer-side member, which would have
asserted the wrong side of the relationship in a place nothing downstream would
re-check.

**What remains is acquisition.** `extraction_profiles` needs label patterns
grounded in a document carrying modelo 145's printed box labels, and neither
bundled instructions file has them: `modelo-145-procedure.html` and
`modelo-145-obligaciones-retenedor.html` are 2,170 and 2,138 characters of
navigation and metadata, and probing them for `Situacion familiar`,
`Discapacidad`, `Hijos y otros descendientes` and `Movilidad` finds none. Modelo
145 therefore joins 100, 136, 193, 296 and 721 in the acquisition bucket -- six
modelos now whose remaining blocker is a document this repository does not hold.

### deadline-windows-are-readable-from-the-bundled-calendars | 88 to 40, and a standing disposition worth revisiting

Registry failures are at **40**. Modelo 123's `2019-2023` revision validates
clean and its `2024-y-siguientes` sibling is down to one family.

**The important finding is about deadline windows generally.** Modelo 202's
existing disposition says the family is "deliberately empty rather than guessed"
because the close date "sits under a 'Hasta el N' heading that this pass could
not read back from the PDF reliably". **That is no longer true, and it was worth
testing rather than inheriting.** `pdfplumber` reads the bundled Calendario del
Contribuyente cleanly: tracking the last `Hasta el N de MONTH` heading and
matching model lists yields, for 2023, `Hasta el 20 de abril / julio / octubre --
Primer / Segundo / Tercer trimestre 2023: 111, 115, 117, 123, ...` and, from the
2024 calendar, `Hasta el 22 de enero -- Cuarto trimestre 2023`. The whole
quarterly grid extracts, including the weekend rolling that makes January close
on the 22nd rather than the 20th.

So **the blocker on deadline windows is corpus coverage, not readability**:
calendars are bundled for 2023, 2024, 2025 and 2026 only. That reframes three
revisions this campaign left blocked:

- Modelo 123 `2019-2023` -- CLOSED here, with its four windows for filing year
  2023 read from the bundled calendars. Filing years 2019 to 2022 are left
  undeclared and the fragment says so: a window per governed year is not
  required (modelo 115's open-ended revision declares 2026 alone), so the family
  is populated with what is grounded rather than padded with guesses.
- Modelo 131 `2019-2023` and Modelo 180 `2019-2022` -- still blocked, but now for
  a smaller reason than recorded earlier. 131's 2023 windows are extractable the
  same way; 180's annual window for filing year 2022 closes in January 2023 and
  is in the bundled 2023 calendar. **Modelo 202's own disposition should be
  revisited on the same ground.**

**Modelo 123's other families**, on established patterns: quarterly
`filing_schedules` for both revisions, `parameters` (pure aggregation over
already-withheld amounts), `dependency_classifications` (193 is the resumen that
depends on 123), `relations` (nothing folds in), the `deadline` application link,
and a `verification_predicate` per revision pairing the rentas/perceptor count
with the base -- count-to-base deliberately, not base-to-retencion, which is the
pair modelo 115's predicate records as tautological where the retencion is
computed from the base.

The `bindings` disposition is narrower than the others and says so: the
`retenciones_aggregation` enum DOES carry capital members (`intereses`,
`dividendos`, `otros_capital_mobiliario`), so unlike modelo 216 -- where no IRNR
scheme exists at all -- binding modelo 123 is possible in principle. The
disposition records that every input casilla is currently `manual` and that
changing how this modelo sources its figures is a modelling decision, not
something a binding fragment asserts on its own.

**What remains on 123 is the concept mapping.** `casilla_continuidad_evolutions`
on the 2024 revision needs `continuidad_id`s added across a genuine restructure:
8 casillas to 14, with AEAT splitting each total into dividendos and resto AND
changing the count basis from PERCEPTORES to RENTAS. Modelo 216's bundled
instructions document that reform ("Como novedad, para rentas devengadas desde
2024, hay que desglosar ... el correspondiente a dividendos ... y el
correspondiente a otras rentas"), but 123's own bundled instruction is a
4,705-character procedure page that does not, and using another modelo's document
to ground this one's concept identity is the same grounding-by-analogy this
campaign refused for Modelo 100's cross-year target list. Declaring `unchanged`
for a concept whose basis changed is the specific wrong outcome. Left for 123's
own 2024 orden or an operator ruling.

### modelos-131-and-180-fully-closed-on-the-calendar-finding | 88 to 38

Registry failures are at **38**. Modelos **131** (all four revisions) and **180**
(both revisions) now validate clean, closed directly by the deadline-window
finding in the entry above -- the windows the earlier passes recorded as
ungroundable are readable from the bundled Calendario del Contribuyente.

**Modelo 131 `2019-2023`**: four quarterly windows for filing year 2023, read as
"Hasta el 20 de abril / julio / octubre -- Estimacion objetiva: 131" from the
bundled 2023 calendar and "Hasta el 30 de enero -- Estimacion objetiva: 131" from
the 2024 one. The Q4 close on the 30th rather than the 20th independently matches
RIRPF art. 111's own split ("Cuarto trimestre, entre el dia 1 y el 30 del mes de
enero"), which is a useful cross-check: the calendar and the statute agree.

**Modelo 180 `2019-2022`**: one annual window for filing year 2022, read as
"Hasta el 31 de enero -- Resumen anual 2022: 180, 188, 190, 193, 193-S, 194, 196,
270" from the bundled 2023 calendar. This is the modelo whose plazo the earlier
entry established was NOT grounded anywhere -- `orden-hap-1732-2014` contains
"enero" zero times and `orden-hfp-1284-2023:art-7` amends the record design
rather than any plazo. The calendar is where it actually lives, and it gives the
31st, not the 30th that the pagos fraccionados carry: **the two modelos have
different January closes and the calendar is what distinguishes them.** Deriving
180's window from 131's rule would have been wrong by a day.

Earlier filing years are left undeclared in both, with the fragments saying why:
calendars are bundled from 2023 onward only, and a window per governed year is
not required -- modelo 115's open-ended revision declares 2026 alone.

**Still open on this thread**: modelo 180's EXISTING `2023-y-siguientes` windows
cite `orden-hfp-1284-2023:art-7` for dates that article does not carry, and they
should be re-pointed at the calendar the same way. Modelo 130's windows cite
`rd-439-2007:art-110` (the IMPORTE) rather than art. 111 (the plazo), which this
campaign added to the catalogue. Modelo 202's `deadline_windows` dispositions
rest on the readability claim this work disproved. None of the three was changed
here -- they are existing content, and re-pointing another modelo's citations is
a separate, deliberate change.

### modelo-190-families-and-two-casilla-ids-that-are-near-homographs | 88 to 37

Registry failures are at **37**. Modelo 190's `parameters` and
`verification_predicates` are resolved, leaving it blocked on coverage alone.

`parameters` is dispositioned on the now-familiar ground: both formulas are
`op = "add"` over the per-perceptor figures, an addition applies nothing, and the
retencion rate was set at payment time under RD 439/2007 arts. 80 to 86 and
consumed by the quarterly modelo 111 -- this annual resumen receives amounts
already withheld.

**The predicate is worth reading for the naming trap it walked into.** Modelo 190
carries two declarante casillas whose ids are near-homographs and whose meanings
are opposite:

| casilla_id | positions | semantic_role | input_kind |
|---|---|---|---|
| `decl.total-percepciones` | 136-144 | `total_percepciones_count` | bound |
| `decl.percepciones-total` | 145-160 | `total_percepciones_amount` | computed |

One is a COUNT and the other is MONEY. The predicate was first authored against
`decl.total-perceptores`, which exists in neither form -- a third spelling,
invented from the concept rather than read from the revision -- and the reference
check refused it. That refusal is the only thing between an invented id and a
fragment that looks right; had the wrong-but-real id been chosen instead, the
predicate would have loaded and compared a money total against a money total,
asserting the engine's own addition and firing on nothing. **The fragment now
opens by naming both ids, their positions and their semantic_roles**, because a
later reader has the same trap waiting.

The pairing itself is count-to-amount, and deliberately not amount-to-retenciones:
withholding on rendimientos del trabajo is scaled to the payer's projected annual
rate and is lawfully ZERO below the thresholds, which is the objection modelo
100's predicates record and the reason modelo 111's own predicate keys on its
actividades economicas block instead.

**Modelo 185 was examined and left alone, deliberately.** Its `2003-2025`
revision declares `deadline_windows` and `revision.toml` and NOTHING else -- zero
casillas, which the registry calls "unsupported placeholder definitions" -- and
the only bundled design for this modelo is `01-185-ejercicio-2026-y-siguientes`,
which governs a period this revision does not cover. Authoring 2003-2025's
casillas from a 2026 design would be grounding by analogy across periods, the
same defect refused for Modelo 100's cross-year target list. The revision also
raises a prior question this campaign should not answer: whether a
zero-casilla 2003-2025 revision should exist at all beside the `2025-y-siguientes`
one, or whether its windows belong to that sibling.

### modelo-303-revision-renamed-to-the-years-it-covers | 88 to 36

Registry failures are at **36**. Modelo 303's revision-id refusal is resolved by
doing what the gate asked rather than by widening the window.

The revision was named `2009-y-siguientes` while its own
`period_selector.year_to` said 2022, and the gate is explicit that the
disagreement is not cosmetic: "a reader meets the name first". The span genuinely
ended -- modelo 303 declares separate `2023`, `2024-hasta-08-y-2t`,
`2024-desde-09-y-3t`, `2025` and `2026-y-siguientes` revisions, so 2009-2022 is
what this one covers, and one of its own consuming tests says so in prose ("The
2009-y-siguientes revision covers ejercicios 2009-2022"). Renamed to **`2009-2022`**.
The gate's warning was heeded: the window was NOT reopened to silence the
refusal, which "asserts coverage over years nobody holds evidence for".

**The sweep is the part worth recording, because the name reaches further than
the directory.** 18 registry fragments (the revision directory, its section
headers, and ids that embed the revision name such as
`modelo-303-2009-y-siguientes-reconcile-when-present`), plus **60 Python files**
pinning the id, plus one code CONSTANT that the ordinary greps would not have
flagged as important:
`_m303_orden_constants._M303_2022_REVISION_ID = "2009-y-siguientes"`, which
guards the 2022 annual Orden's exact BOE/revision coordinate. That guard is what
caught the incomplete rename -- it refused with "annual Orden 2022 projection
must retain its exact BOE/revision coordinate" the moment the registry moved and
the constant did not. It behaved exactly as intended, and it is the reason this
rename is a sweep rather than a directory move.

Renaming was checked for safety first: modelo 303 had **zero files touched in the
preceding 45 minutes** while peers were active in 131, 180, 190, 296 and 714, so
a 79-file rename could land without colliding. In a shared tree that check is
part of the change, not a courtesy.

**Modelo 303 is not closed.** Its remaining two refusals are the
variable-envelope pair every modelo in that group carries -- `export_layouts`
plus the families behind it -- and that contract is still the campaign's highest-
leverage unbuilt item.

**Modelo 190's families are also resolved** in the same stretch (see the entry
above), leaving it on coverage alone.

### the-variable-envelope-contract-is-BUILT-and-half-applied | correcting this audit's most-repeated claim

This audit has said since its first finding that the variable-envelope
composition contract is "one shared piece of infrastructure gating eight
modelos" and "by far the highest-leverage item in the campaign", and every
subsequent entry -- including several written during this session -- repeated it
as though nothing had been built. **Measured, that is wrong and has been wrong
for some time.**

`compile_filing_envelope_definition` exists in `dev/registry/_variable_envelope.py`,
generalised off the Modelo 303 original, and `VariableEnvelopeSemantic` is an
authorable map section. **Four of the eight modelos are fully done** -- each with
an authored semantic map, an authored envelope semantic, and a PUBLISHED
generated export tree:

| modelo | map fragments | envelope semantics | published export trees |
|---|---|---|---|
| 151 | 2 epochs | 2 | 2 |
| 202 | 3 epochs | 3 | 3 |
| 322 | 1 epoch | 1 | 1 |
| 353 | 2 epochs | 2 | 2 |

None of those four appears in the failure set any longer. The contract is not
unbuilt infrastructure; it is proven machinery with four worked applications.

**And Modelo 303 is nearly done too, which the failure line hides.** Its five
later revisions -- `2023`, `2024-hasta-08-y-2t`, `2024-desde-09-y-3t`, `2025`
and `2026-y-siguientes` -- EACH carry a map epoch, an envelope semantic, a render
profile and a published `export/` tree. Only the `2009-2022` revision renamed
above lacks one, and there is no `2022` map epoch to match its `aeat-dr-303-2022`
design. So 303's remaining refusal is not "the contract does not exist" but "one
of six revisions has not had the contract applied to it yet", following a pattern
already executed five times inside the same modelo.

**What the four remaining modelos actually need**, so the next attempt sizes them
from evidence rather than from the stale framing:

- **303 `2009-2022`** -- map, envelope semantic and render profile for the
  `aeat-dr-303-2022` design. 118 casillas already exist with declared numbers, so
  the map is largely DERIVABLE the way Modelo 184's was (108 of 128 anchors
  resolved automatically from casilla numbers there). Scale reference: the 2023
  map is 6,184 lines across 7 fragments.
- **200** -- no map and no envelope semantic, but **128 render-profile fragments
  already authored**. The profile work is done and the map is the gap, which is
  the reverse of the usual order and worth knowing before starting.
- **308** and **309** -- nothing authored. Envelope `M30800` / `M30900` (13
  prefix fields each) plus one fixed record of 55 and 68 fields respectively over
  1,500 positions. Both currently declare only 2 and 5 casillas, so most of the
  work is casilla authoring rather than mapping; a large share of their fixed
  records is identity and header material that maps to producer keys rather than
  casillas, as in Modelos 347 and 184.

The standing recommendation "build the variable-envelope composition contract"
should be retired and replaced with "apply the existing contract to 303's
`2009-2022`, then 200, 308 and 309".

**Modelo 303's `2009-2022` blocker is neither the envelope contract nor the map:
it is 96 MISSING CASILLAS.** Measured before authoring anything, which is the
only reason this was caught rather than discovered halfway through a 6,000-line
map.

A planning pass over the `aeat-dr-303-2022` design resolves its 314 anchors from
two deliberately separate sources -- casilla anchors from the 2022 design's OWN
bracketed box number, structural anchors (literal, filler, header, draft)
transferred from the 2023 map by exact `(record_identity, description)` match.
The split is the point: Modelo 303 restructured in 2023, so carrying a CASILLA
mapping across epochs is the Modelo 100 `0224` hazard -- a box present in both
years meaning different things -- while the file envelope, identity block and
trailing blanks carry no box number and no taxpayer figure and their text is
stable. Result:

```
anchors             314
resolved by box      65
resolved by 2023    123
box with no casilla  99
unresolved           27
```

The design declares **156 boxes** and the revision models **118 casillas**, of
which **96 declared boxes have no casilla at all** -- and they are not marginal:
boxes 1 to 9 are the regimen general IVA devengado base/tipo/cuota rows, 78 to 99
the regularizaciones and compensaciones, 500 to 504 the prorratas page. **83 of
the 96 DO exist on the 2023 revision**, so the concepts are modelled elsewhere in
the same modelo, but transplanting them is precisely the renumbering hazard this
split was built to avoid.

So the ordering for this revision is: author ~96 IVA casillas with legal
grounding FIRST, then the map, envelope semantic and render profile. That is core
IVA content -- devengado tiers, recargo de equivalencia, prorrata -- on a revision
governing fourteen filing years, and `aeat-calculation-grounding` calls out
exactly this territory ("an IVA total cuota devengada aggregation MUST sum the
recargo de equivalencia cuota tiers alongside the standard, reducido and
super-reducido repercutido tiers"). It is a tax-modelling job, not a mapping one,
and it should be sized and reviewed as such.

The 27 genuinely unresolved anchors are a separate, much smaller list --
preconcursal declaration flags, the RS agricultural sub-fields stating their own
"1 entero y 5 decimales" widths, the SWIFT/IBAN/bank-address devolucion block,
and the DP30304 informacion-adicional run -- all of which are ordinary
classification work once the casillas exist.

### modelo-232-writes-taxpayer-names-into-AEAT-reserved-bytes | high | a filing-correctness defect in a PUBLISHED tree

Not fixed here, and flagged rather than half-fixed because the correction spans
another author's modelling across two revisions and a published export tree.

Modelo 232's coverage refusal is not only about unwritten positions. It also
reports **reserved-byte intrusions**: `m232-2016.dr23201.f021` writes into
`@220..239` and `f031` into `@341..360`, and the design labels both
`3.Informacion operaciones con personas o entidades vinculadas 1 - Reservado AEAT
(Nombre)`. The filer supplies the NIF; AEAT derives the name. Those bytes are the
Administracion's.

The registry models them as data anyway. The semantic map carries
`kind = "casilla"` with `casilla_id = "vinculada-1-reservado-nombre"` -- the word
*reservado* is inside the casilla id -- and this is not two stray entries:
**32 distinct `reservado` casilla ids** exist, each with its own binding fragment
(`0004-modelo-232-2016.page-01.220-239.vinculada-1-reservado-nombre.toml` and
siblings), across the `2016-2017` and `2018-y-siguientes` revisions, and the
PUBLISHED `export/` tree emits them.

This is the Modelo 576 hazard in its live form. That case was a blob field
spanning a reserved sub-field; here each reserved slot is individually modelled,
bound and emitted, so a generated filing carries taxpayer names in bytes AEAT
reserves for itself -- behind a valid digest. `_reserved_write_failures` is
reporting it correctly and has been all along; what is missing is the fix.

**The shape of the correction**, for whoever takes it:

1. The map entries become `kind = "filler"` -- the gate names this remedy
   explicitly ("emit those bytes as a filler instead"), and a filler there is
   CORRECT rather than a workaround: the record is contiguous, so the bytes must
   still be emitted, as blanks.
2. The 32 casillas then address no export field. A slot reserved for the
   Administracion holds no taxpayer datum, so the honest end state is that they
   are not casillas at all -- but deleting 32 casillas plus their bindings is a
   modelling decision belonging to whoever authored them, not a drive-by.
3. The tree must be REPUBLISHED afterwards; correcting the map alone leaves the
   shipped `export/` fragments writing the same bytes.

Modelo 232's other refusal is separate and structural: design record `DR23200` is
an auxiliary envelope header ("a source-proved 328-byte composition outside the
fixed-record totals") that the layout does not emit and that needs its own
emission contract. `compile_auxiliary_envelope_record` already exists in
`dev/registry/_auxiliary_envelope_record.py` and is imported by the export tree
renderer, so this is contract APPLICATION rather than contract building -- the
same correction this audit needed for the variable-envelope claim.

### modelo-232-families-closed-and-two-dispositions-the-gate-refused | 88 to 34

Registry failures are at **34**. Modelo 232's family blockers are resolved on
both revisions, leaving each with the coverage refusal alone -- which is the
reserved-byte defect recorded above, not authoring.

**Authored**: `applicability` for both revisions (the Impuesto sobre Sociedades
contribuyente with operaciones vinculadas above the RIS art. 13.4 thresholds, or
with operations and situations relating to paraisos fiscales),
`dependency_classifications`, `verification_predicates` and `projection_endpoints`
dispositions, and two `casilla_continuidad_evolutions` rows.

**The continuity rows are measured, not defaulted.** Modelo 232 declares exactly
two `continuidad_id`s; both revisions carry both; and for each, the casilla id,
the AEAT number and the legal_refs tuple are identical across the pair
(`decl.cnae` at `2.devengo.cnae`, `decl.ejercicio` at `2.devengo.ejercicio`).
Nothing added, nothing retired, so both are `unchanged`.

**Two dispositions were written and then REMOVED, both because the gate refused
them, and both refusals were right.**

1. A duplicate `projection_endpoints` disposition on `2018-y-siguientes` -- that
   revision already carried one. TOML caught it as a table redefinition.
2. A `parameters` disposition on `2018-y-siguientes`, refused with "declares
   family 'parameters' not applicable but also declares 1 of them; drop the
   disposition or drop the content". **That revision genuinely HAS a parameter**,
   so the disposition was false. The reasoning that produced it was sound for
   modelo 232 as a whole -- informative, zero formulas, no rate applied -- and
   still wrong for this revision, because a family-level argument about a
   modelo's nature does not survive contact with a revision that populated the
   family anyway.

That second one is the lesson worth carrying: several dispositions in this
campaign were written from a modelo-level argument ("this modelo computes
nothing, so parameters cannot apply") and applied across revisions in one pass.
The argument can be true of the modelo and false of a revision. **Check the
revision's own content before dispositioning its family**, which is what the
contradiction gate exists to enforce and what it caught here.

### modelo-390-closed-across-four-revisions | 88 to 30

Registry failures are at **30**. Modelo 390's `2022`, `2023`, `2024` and `2025`
revisions all validate clean. Its coverage refusals had already cleared (partly
from the naturaleza fill-omissibility fix recorded above, partly from peer work),
leaving family authoring only.

**`applicability` and `parameters` for all four.** The parameters disposition was
verified on EACH revision rather than argued from the modelo -- the lesson the
Modelo 232 contradiction taught one entry earlier. All four declare zero
parameters, and their four formulas aggregate already-computed period figures
into the annual summary: the IVA rates that produced those figures were applied
on the periodic modelo 303 autoliquidaciones the year is made of, and the resumen
anual restates their outcome.

**The continuity evolutions are the interesting part, because the change they
record is a real regulatory event.** Measuring the three transitions gives:

| transition | shared | legal_refs differ | labels differ | added | retired |
|---|---|---|---|---|---|
| 2022 to 2023 | 340 | 0 | 0 | 0 | 0 |
| 2023 to 2024 | 340 | 9 | 0 | 48 | 0 |
| 2024 to 2025 | 388 | 9 | 0 | 0 | 0 |

The nine are the same nine both times, and they are exactly the reduced-rate
tiers: `iva-base-imponible-repercutida-tipo-2`, `-tipo-5`, `-tipo-7-5`,
`iva-cuota-repercutida-tipo-2`, `-tipo-5`, `-tipo-7-5`, and the recargo de
equivalencia tiers `-tipo-0-26`, `-tipo-0-62`, `-tipo-1`. Each GAINS
`real-decreto-ley-4-2024:art-1` in 2024 and DROPS it again in 2025 -- the
temporary IVA reduction on basic foodstuffs, extended by RDL 4/2024 and then
lapsed. The registry already encoded that event correctly in the casillas' own
legal_refs; the evolutions now make the trajectory explicit.

**Row count follows the registry's existing convention, which was checked rather
than guessed.** Modelo 100 authors 46 rows against 455 continuidad_ids on its
2021 revision, 84 against 538 on 2022 -- roughly a tenth, dominated by
`label_evolved`, with one or two deliberate `unchanged` records. So evolutions
are authored for what CHANGED, not per concept, and generating 1,068 rows for
390's three transitions would have been noise rather than completeness. The 2023
transition, measured as fully unchanged, carries nine `unchanged` rows for the
same nine tiers, so their history starts from a stated fact instead of silence.

### modelo-714-reduced-to-its-two-real-blockers-and-a-predicate-that-cannot-exist | the state at 30

Modelo 714's coverage refusals -- the ones this audit opened with as the worked
case for why the coverage gate exists at all ("five revisions declaring 127
fields against a design carrying 1,200+ positions") -- have **cleared**. All five
revisions were family-blocked only, and three of those families are now authored:
`applicability`, `live_cross_references` (plus the portal application link they
require), and a `verification_predicates` disposition.

**That disposition is the one worth reading, because it is the first in this
campaign where NO predicate can exist rather than none being needed.** Modelo 714
has a base and a cuota, so the usual grounds -- informative, computes nothing --
do not apply. Every candidate pair fails for one of two opposite reasons:

- **base imponible to base liquidable, or patrimonio to cuota**: false-fires.
  Casilla 27 is the base imponible less the MINIMO EXENTO of Ley 19/1991 art. 28,
  so a taxpayer with substantial declared patrimonio, a zero base liquidable and
  zero cuota is the ordinary lawful case. This is the same shape that sent modelo
  111's antecedent away from its threshold-scaled trabajo block, and modelo 100's
  predicates record the identical objection.
- **base liquidable to cuota integra**: tautological. Casilla 29 is COMPUTED from
  27 by the art. 30 scale, so the implication holds by the arithmetic -- the
  pairing refused on modelo 115.

Every pair is therefore either unlawfully strict or vacuous. Modelo 369's
disposition reached the same conclusion from the opposite direction (only cuotas
and their sum, so nothing can disagree); this one reaches it with a full
calculation present, because a statutory threshold sits between the two figures
an implication would relate.

**What remains on 714 is two blockers, both outside authoring.**
`extraction_profiles` needs label patterns and the only bundled instruction is
`modelo-714-procedure.html` at **783 characters** of metadata -- "Casilla" does
not appear in it -- with no justificante fixture either, so it joins 100, 136,
145, 193, 296 and 721 in the acquisition bucket. And
`casilla_continuidad_evolutions` on 2022 through 2025 cannot be populated at all:
714 declares **zero `continuidad_id`s**, and an evolution row requires one, so
the prior question is whether this modelo should carry continuity keys -- the
same modelling decision left open on modelo 123.

**Tree state at 30 failures**, by what actually blocks them rather than by
modelo: acquisition (100, 136, 145, 185, 193, 296, 714, 721), variable-envelope
APPLICATION to a revision (200, 303, 308, 309, 360), a published-tree correctness
defect (232), casilla authoring (190), and continuity-key modelling (123, 714).
Only the last two categories are registry authoring in the sense this campaign
has been doing all session.

## DONE: MODELO 184 IS PUBLISHED AND FULLY IMPLEMENTED

**Zero validation failures**, `filing` grade, 87 casillas, 128-field generated
layout across three records (declarante 24, entidad 75, socio 29). With Modelo
347 that makes **two** modelos over the line; registry-wide failures fell from 88
at the start of this campaign to 73.

The parse hole was closed with the conjunction rule this finding said was needed,
and it fires on **exactly one site in the entire bundled corpus**. Three
independent facts must agree: the parent declares a subdivision COUNT, its read
sub-fields do not tile it, and staged candidates fill the remainder such that the
run then tiles end-to-end AND numbers exactly the declared count. Modelo 184's
`@147+9` ("se subdivide en cuatro", three read, `151-155 PORCENTAJE...` missing)
is the only place all three hold. Modelo 038's eleven chart artefacts declare no
count and fail at the first clause; Modelos 165 and 280 declare TWO, already read
two and hold a one-byte gap, so admitting there would make three where AEAT says
two and the count clause correctly refuses -- leaving their genuine defect
visible instead of papered over.

The search had to be a SEARCH, not a walk: AEAT nests these, staging both
`151-155 PORCENTAJE` and the `151-153 ENTERO` inside it at the same offset.
Keying one candidate per offset silently took whichever was read last and
produced five sub-fields where the design says four.

**Four further gaps surfaced only by driving publication, each a real hole rather
than a chore.** None was predictable from the finding above.

1. **The IR flattened desglose away.** `_record_design_ir` never read
   `components`, so once the parser began nesting, a desglose parent reached the
   renderer as ONE field spanning its children -- the Modelo 576 blob, which
   covers every sub-position by byte extent so coverage cannot object, while
   writing the group as a single value. Before the fold 184 refused outright,
   which was safe; after it, it would have rendered silently wrong. `_wire_positions`
   now descends to leaves, which is the resolution `_required_positions` already
   documents.
2. **No anchor could name an ordinal-less row.** Both `SemanticMapAnchor` and
   `RenderProfileAnchor` required `ordinal`, deliberately, because "every
   currently-authored anchor names a real field with a real printed ordinal" --
   true until the gap fill produced one that has none. Inventing an ordinal
   would fabricate a printed LABEL, which that field's own contract forbids, so
   both gained an explicit `ordinal_absent` declaration. Omitting both keys still
   refuses; only an author stating the absence reaches `None`.
3. **The render profile could not see an absent naturaleza.** Eligibility
   required a numeric type, so a row whose type cell AEAT printed EMPTY -- the
   strongest case for a reviewed wire fact there is -- was invisible to the
   profile's exhaustive-coverage check and then crashed the renderer on an
   unsupported type. The gap surfaced as a late refusal instead of the reviewable
   rule it should have demanded.
4. **The provenance normaliser caught its own schema drift**, refused, and said
   "review and version the normaliser". It was right: `_SEMANTIC_MAP_ANCHOR_KEYS`
   gained the key and `_LOADER_SEMANTIC_SCHEMA_VERSION` went 5 to 6, because two
   anchors differing only in whether the design printed an ordinal are different
   anchors and the digest must say so.

**Two registry defects were corrected in 184's own casillas, both grounded in
AEAT's text rather than inferred.**

- `tipo2.renta-atribuible-importe` declared `178-190` where both bundled design
  epochs print `177-190`, a 14-position field. One byte short at the start, which
  would have left position 177 unwritten.
- `tipo2.miembro-nif` at `9-17` was **removed**, with its manifest and
  expectation enrollments. No such field exists at those positions in any record
  of either epoch: both print `9-17 NIF DEL DECLARANTE` everywhere, and record
  2's own `18-26` is "N.I.F. ENTIDAD -- Consignar lo contenido en el campo 'N.I.F.
  del Declarante', posiciones 9-17 del registro de tipo 1", a copy of the
  declarante rather than a member. The member's NIF is record 3's `18-26` and was
  already correct as `tipo3.miembro-nif`. Left standing it bound a casilla named
  for the member to the bytes carrying the DECLARANTE's NIF, and it was silently
  absorbing record 1's declarante-NIF anchor during map derivation.

The map was derived from each casilla's OWN declared position range rather than
matched on description text, so it agrees with the registry by construction: 108
of 128 anchors resolved automatically and the remaining 20 were classified by
hand against the design's prose. **Both modelos carry `review_status =
"agent_reviewed"` with `reviewed_by = "agent-prepared-pending-operator"`. An
operator countersignature is still owed on both.**

### declare-the-missing-design-epochs | DONE, unblocked two modelos

Six sources across 193 and 347 now declare `record_design_epoch`, read from each
source's `applies_from` window: 193 at 2024 and 2025; 347 at 2008, 2010, 2011 and
2025. Both modelos moved from refusing the loader to generatable, with no change
to the registry failure set.

### complete-the-modelo-232-generated-tree | Now a coverage gap, not a crash

232's generated tree writes 157 of 222 required positions. The loader crash first
reported here no longer reproduces.

### close-modelo-296-with-a-gap-filling-second-pass | DONE for the hole; two unidentified bodies remain

Landed in the shipped extractor. A row carrying a position RANGE and a
description but no naturaleza is now staged, and admitted only into a span no
read row claims. The containment test is what makes it safe: a prose line
restating its own field's range is always claimed by that field, so it can never
be admitted, while a genuine hole can absorb exactly one candidate.

Measured across all 216 bundled designs: **one field admitted, in one sheet, in
one design** -- Modelo 296's `413-432 CÓDIGO LEI DEL PERCEPTOR` -- with zero
extraction errors. Modelo 296's perceptor record went from entirely skipped for a
hole to read with 41 fields, so the design now yields three record bodies rather
than two.

Four tests cover it, including the mutation proof: remove the disjointness test
and the prose case grows a duplicate field, which is the failure the guard
exists to prevent. A lone position with no range is still refused, since a
numbered paragraph is indistinguishable from a one-byte field.

**Modelo 360 is now COMPLETE, from a one-character cause.** Its second body was
headed `Pág. 2 DISEÑO DE REGISTRO 25/03/2021`, and the page-record pattern
required whitespace straight after the stem (`^P[áa]g\s+`), so the period form
never matched. AEAT abbreviates the word both ways. Allowing the optional period
takes 360 from one unnamed sheet plus a skipped body to two named sheets
(`Pág. 1` with 160 fields, `Pág. 2` with 102) and `is_complete = True`.
Corpus-wide the change took designs reporting skips from 31 to 29, with zero
extraction errors.

**Modelo 296 is now COMPLETE too.** Its two unidentified bodies were the design's
anexos, headed in a form no pattern covered:

```
ANEXO «VALORES NEGOCIABLES. RELACIÓN DE PAGO A CONTRIBUYENTES
(Tipo de Hoja «A»)
```

with a second at `RELACIÓN DE CERTIFICADOS DE PAGO` / `(Tipo de Hoja «B»)`. Added
as a fourth heading shape beside the three word orders and the bare tag form,
staging a name for geometry to confirm exactly as the type-last shape does, so a
false match stays inert.

The REQUIRED opening quotation mark is what separates a titled annex record from
a prose reference to a numbered annex ("... que figuran en el anexo II de la
Orden EHA/3496/2011"), and a mutation test pins it: drop the quote from the
pattern and such a citation renames the next record body.

Modelo 296 now reads **five record bodies with zero skips** -- declarante, two
perceptor records and both anexos (26 and 24 fields) -- against two sheets and
three skips before. Corpus-wide the anexo pattern names exactly two sheets, both
in 296, and designs reporting skips fell 31 -> 28 across the three parser fixes.

Its 2023 design also had no `record_design_epoch`; declared, as for 193 and 347.

### stop-the-scaffolder-reproducing-the-retired-convention | Cheapest convergence step

`dev/registry/newmodelo` creates `export_layouts/`. Decide the single convention
and make the scaffolder emit it.
