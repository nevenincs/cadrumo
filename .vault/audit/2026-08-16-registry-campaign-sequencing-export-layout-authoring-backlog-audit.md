---
tags:
  - '#audit'
  - '#registry-campaign-sequencing'
date: '2026-08-16'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:aad20042284885da2f0112d8b2e0e96e0b0445fc3ebfcdef5641816bfabec032'
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
