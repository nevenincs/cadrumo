---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-15'
modified: '2026-08-16'
body_schema: 'body-v1'
body_hash: 'sha256:9fa257c1e4c6762cdb58efc8071786cce5fcac63f3bba0249349fe3a459a48b7'
related:
  - "[[2026-08-15-registry-temporal-coverage-audit]]"
  - "[[2026-08-14-registry-temporal-coverage-audit]]"
  - "[[2026-08-15-registry-temporal-coverage-schema-family-coverage-census-audit]]"
---

# `registry-temporal-coverage` audit: `structural decisions`

## Scope

Six structural decisions accumulated across ten concurrent authoring lanes and
were recorded only in per-lane hand-offs. This document consolidates them into
one place so each can be ruled on without re-deriving the evidence.

Every claim below is marked for provenance. **Verified here** means this audit
re-derived it against the tree at the time of writing, and the derivation is
stated so a reader can repeat it. **Reported by a lane** means it is carried
from another lane's hand-off and was not independently re-derived; those claims
are the ones to re-check before acting on them.

Two premises supplied with the consolidation request did not survive that
re-derivation, and both are recorded as findings rather than silently corrected,
because in each case the correction changes what is being asked for. The first
is that `review_status` has no unreviewed state: true of the legal-catalogue
vocabulary, false of the revision one, which already ships the pending member.
The second is that era splits and multi-design revisions are one decision: the
seven modelos named fall into three groups needing three different remedies, and
one of them has no era gap at all.

Scope boundary: this document ranks nothing and decides nothing. Several of
these are product decisions whose evidence does not select an option, and where
that is the case it is said plainly instead of being resolved by preference.

This document has been revised once since first drafting, as the campaign moved
under it. Three items changed shape materially and a reader who saw the first
version should re-read them: the envelope de-scoping is **withdrawn as an
unlock** and reframed as gated on an AEAT registration; the multi-design remedy
now has a **tested** selector on one side and a **measured** duplication cost on
the other; and the sum-versus-total check this audit recommended has been
narrowed to what it actually detects. Four circulated figures are corrected in
their own finding, one of them this audit's.

## Findings

### review-status-vocabulary | high | The revision-level review vocabulary already exists; what is missing is the review

**Verified here.** The consolidation request described `review_status` as
`Literal["reviewed"]` with no unreviewed state. That is true of one vocabulary
and not of the other, and the two govern different subjects.

`ReviewStatus` in `src/cadrumo/domain/calculations/registry/_schema_base.py:389`
is indeed the degenerate `Literal["reviewed"]`. It is scoped to the **legal
catalogue** rows — legal references, source references, legal parameters. It has
no unreviewed member, and `SourceReference.review_status` in
`src/cadrumo/domain/calculations/registry/_schema_references.py:258` is required
with no default.

`RevisionReviewStatus` in `src/cadrumo/core/_revision_review.py:39` is a
different vocabulary for a different subject, and it already carries the missing
state: `PENDING_REVIEW`, `AGENT_REVIEWED`, `OPERATOR_REVIEWED`, with
`PENDING_REVIEW` documented as the fail-closed default. `ModeloRevision`
declares `review_status: RevisionReviewStatus` defaulting to `pending_review`,
alongside optional `reviewed_by` and `reviewed_at`. That module's own docstring
at lines 18 to 22 states the distinction explicitly.

So the schema work for the revision axis has shipped. What has not happened is
the review. The bundled tree holds 103 revision directories and **not one**
`revision.toml` declares `review_status` at all, so every revision sits at the
`pending_review` default. The five string matches for `review_status` elsewhere
under the modelo tree are all Modelo 303 *binding* fragments, a third subject
again.

The consequence is that the revision axis is **not blocked on a decision at
all** — it is blocked on someone performing 103 per-revision reviews, which is
work, not a ruling. Only the legal-catalogue axis is genuinely gated, and it is
gated in one specific way: because `SourceReference.review_status` admits only
`"reviewed"`, enrolling **any** new source is an unavoidable assertion of
operator signoff. Agents are barred from making that assertion, so source
enrolment stops dead.

### unregistered-designs | high | Four acquired designs cannot be enrolled without an operator signoff assertion

**Verified here.** Modelo 490 bundles three design files and registers one;
Modelo 763 bundles three and registers one. The four unenrolled files are
`02-490-orden-hac-590-2021-ejercicio-2021-y-2022-hasta-periodo-1t.xlsx`,
`03-490-orden-hac-590-2021-ejercicio-2022-periodo-2t-4t.xlsx`,
`02-763-orden-eha-1881-2011-ejercicios-2t-3t-2012-2013-y-2014.pdf` and
`03-763-ejercicios-2015-a-2018-hasta-3t.xlsx`.

Modelo 490's single registered design carries `applies_from` 2023-01-01, so the
two unenrolled files are exactly the 2021 and 2022 coverage. Modelo 763's single
registered source carries `applies_from` 2018-10-01, so its two unenrolled files
are the 2012 to 2018 coverage. In both cases the acquisition work is done and
only enrolment is blocked, by the mechanism in the previous finding.

This is the sharpest illustration available of why that mechanism matters: the
bytes are in the tree, their era coverage is known, and the only thing standing
between them and use is a field that cannot be filled truthfully by anyone
except the operator.

### eedd-envelope-generalisation | high | Two envelope role vocabularies are the same thirteen roles under two names

**Verified here.** `M303EnvelopePrefixRole` in
`src/cadrumo/domain/calculations/registry/_schema_exports.py:81` and
`RecordDesignAuxiliaryEnvelopeHeaderRole` in
`src/cadrumo/domain/calculations/registry/_record_design_schema.py:73` declare
thirteen members each, in the same order, for the same thirteen positions. The
member lists differ only in naming: `PERIOD` against `ANNUAL_PERIOD`,
`AUX_OPENING_TAG` against `AUXILIARY_OPENING_TAG`, `DEVELOPER_TAX_ID` against
`SOFTWARE_DEVELOPER_TAX_ID`, and three `_FILLER` members against three
`_RESERVED` members. The companion length tuple beside the neutral enum is
`(2, 3, 1, 4, 2, 5, 5, 70, 4, 4, 9, 213, 6)`, thirteen entries summing to 328 —
the byte extent the request cited, confirmed by arithmetic rather than by
restatement.

**Twelve of the thirteen roles are naming noise. The thirteenth is a behaviour
change, and it is easy to miss under that noise.** The Modelo 303 role is
`PERIOD`, which carries a quarterly or monthly token; the neutral role is
`ANNUAL_PERIOD`, which the Modelo 390 header fixes to the constant `"0A"`.
**A generalisation that renames without widening that one role would silently
narrow every periodic modelo to an annual token.** Whoever implements this must
widen the role, not merely rename it; whatever shape is chosen, it has to admit
both an annual constant and a periodic token. This warning has since been
**independently confirmed twice by other lanes**, which is worth recording: it is
the one part of the de-scoping that three separate reads agree is not cosmetic.

A second demand converges on the same de-scoping, **reported by a lane**:
`m303_complementaria_page_marker` already emits the `"C"` page marker but is
scoped to `ExportComputedKey.M303_*`, and Modelo 131's DPA sheet needs exactly
that behaviour. Two demands, one job — worth sequencing together rather than
twice.

**The unlock framing of this item is withdrawn.** It was carried into this
document as the largest available unlock and that is no longer the right shape,
on evidence gathered after the first draft.

De-scoping would **not** blank the affected records: the render path refuses
rather than emitting an empty envelope, which is correct design. But the
identity those records would then demand is not obtainable.
`AeatProductSoftwareIdentity` in `src/cadrumo/core/product_identity.py:79` has
**zero production constructions** — **verified here**: the only four
constructions in the tree are in `src/cadrumo/core/tests/test_product_identity.py`
(three) and `dev/registry/tests/test_m390_auxiliary_envelope.py` (one), all
fixtures with fabricated values, and it has no CLI surface. So the capability is
dormant for every real caller, and de-scoping would convert eighteen revisions
that today report an honest, visible coverage gap into revisions that **refuse at
export time on a dependency nothing in the product can satisfy**. That is a worse
state, not a better one.

The genuine prerequisite is **registering Cadrumo with AEAT as an *entidad
desarrolladora***, which is a business action rather than a code change. Until
that exists, the useful work is standardising the convention so the de-scoping is
cheap when it is finally worth doing — and that is largely done: **24 of 25
`<AUX>` layouts now conform**, up from 18, with the last close behind (**reported
by a lane**).

So this item should be read as "standardise the convention now; the unlock is
gated on an AEAT registration", not as an available coverage win. The
thirteen-role structural identity above stands regardless and is what makes the
eventual de-scoping mechanical.

### modelo-scoped-mechanisms | high | Shared mechanisms are named for the first modelo that needed them, and one is already rejecting a filing

**Verified here.** The envelope finding above is not a one-off. It is one instance
of a pattern that runs through the export type system: a mechanism that any
modelo could use is named, scoped and gated for whichever modelo happened to
need it first, and the next modelo that needs it cannot reach it.

The census, counted from the shipped enums:

| surface | members | modelo-scoped |
|---|---|---|
| `FilingProducerKey` | 36 | **16 (44%)** — fifteen `m303.*`, one `m111.*` |
| `ExportComputedKey` | 5 | **3 (60%)** — all `m303_*` |
| `ExportDraftAttribute` | 4 | 0 |
| `ExportValuePolicy` | 12 | 0 |

Beyond the enums, the generic `ExportLayoutDefinition` carries a field literally
named `m303_filing_envelope`, and the generic export schema module defines
`M303EnvelopePrefixRole` and `M303FilingEnvelopeDefinition`. The
`xml_dictionary` render path in
`src/cadrumo/application/filing/_export_xml_dictionary.py` branches on
`draft.modelo == Modelo.M100` at four separate points — unfiled comunidad path
suppression, a `toma de datos` NIF stamp, a sign branch, and a
`_MODELO_100_EXPORT_CODE_CONVERTERS` table keyed by field id — so the only
non-fixed-width format the product ships is not modelo-neutral in its renderer.

**Not every modelo-scoped name is wrong, and the discriminating test is whether
the CONCEPT or only the MECHANISM is modelo-specific.** That test is decidable
from the registry, and it separates the census cleanly:

- `m303.redeme_enrolled` is **correctly** scoped. `redeme` appears in exactly one
  modelo's registry data. REDEME is an IVA register the M303 regime turns on; a
  generic name would invent a concept that does not exist elsewhere.
- `m303.prorrata_special_option` and `m303.prorrata_special_revocation` are
  **mis**-scoped. `prorrata` appears in the registry data of **five** modelos —
  100, 303, 322, 361 and 390. The concept is shared; only the key is not.
- `ExportComputedKey.M303_COMPLEMENTARIA_PAGE_MARKER` is **mis**-scoped, and this
  one has stopped being a risk and become a defect.

**The already-paid cost.** Modelo 131's export layout carries this comment in its
2024, 2025 and 2026 revisions, verbatim:

> A boolean export field renders the canonical "X" or blank, so this field
> currently emits "X" where AEAT admits only "C" or blank, and AEAT rejects the
> file. No carrier can emit "C" here: the one that exists,
> `m303_complementaria_page_marker`, is `ExportComputedKey.M303_*`-scoped.

So three Modelo 131 revisions currently produce a file **AEAT rejects**, and the
sole cause is that the mechanism which would produce the correct byte is named
for another modelo. The layout's authors chose the loud failure deliberately over
a silent one, and documented the reasoning — but the choice was forced by a
naming decision, not by anything AEAT publishes.

This reframes the envelope finding above: `M303EnvelopePrefixRole` duplicating
the neutral thirteen-role vocabulary is the same defect at a larger scale, and
the two should be ruled on together rather than as unrelated items.

### temporal-coverage-shapes | high | The era problem is three distinct problems wearing one name

**Verified here**, by reading every `record_design` source across all 63 legal
catalogue files (383 sources, 121 of them record designs) and comparing each
modelo's registered design windows against its revisions' period selectors. An
earlier pass of this audit that read only the per-modelo legal file undercounted
several modelos badly, because the Modelo 322, 353, 347, 190 and 193 designs are
registered in the shared `iva.toml`, `operaciones-terceros.toml` and `irpf.toml`
catalogues rather than in a per-modelo file. The corrected census is below, and
the earlier method is recorded here as a trap.

The seven modelos named in the consolidation request do not share one defect.
They fall into three groups needing three different remedies:

**Group A, genuine era gap — no design exists for part of the declared span.**
Modelo 165 declares one revision `2013-y-siguientes` with `year_from` 2013 and
no `year_to`, against one registered design whose `applies_from` is 2026-01-01:
thirteen years with no design. Modelo 181 declares `2009-y-siguientes` from 2009
against a design from 2022: thirteen years. Modelo 322 declares
`2008-y-siguientes` from 2008 against designs starting 2023: fifteen years.
Modelo 353 declares `2008-y-siguientes` from 2008 against designs starting 2021:
thirteen years.

For Modelo 165 the gap is not an inference from metadata. Position 184 of its
record, `EMPRESA EMERGENTE`, is defined by the design itself by reference to
*el apartado 1 del artículo 3 de la Ley 28/2022, de 21 de diciembre, de fomento
del ecosistema de las empresas emergentes*. A byte whose meaning was created by
a December 2022 law cannot be written into a 2015 filing. Authoring a layout on
the open revision would make the application emit that byte for every year from
2013, with nothing in the system able to signal it.

**Group B, multi-design single revision — the designs tile the span, but one
revision cannot select among them.** Modelo 347 registers four designs tiling
2008-2009, 2010, 2011-2024 and 2025 against a single revision from 2008: **no
era gap at all**, purely a selection problem. Modelo 190 and Modelo 193 each
register two designs (2024, then 2025 onward) against a single revision from
2024, likewise fully covered. Modelo 322 and Modelo 353 are in this group as
well as Group A, since their multiple designs also sit on one revision.

Group B is not a modelling nicety. It carries the live measurement defect
recorded in the finding below, which is why it is the group most likely to
produce confident wrong numbers while it stands.

**Group C, acquired but unenrolled** — Modelo 490 and Modelo 763, per the
finding above. Their remedy is not a split; it is the source-enrolment gate.

Modelo 604 is the worked precedent for Group A and B alike, and it is already
approved: two revisions with bounded selectors, `2021-2023` and
`2024-y-siguientes`, against two designs whose `applies_from` and `applies_to`
tile them exactly. Nothing else in the census matches that shape.

**A window-based design selector already exists, already works, and is already
exercised in production — but only for one modelo.**
`src/cadrumo/domain/calculations/registry/_m303_orden_resolution.py` at lines 100
to 113 filters candidate designs by `applies_from <= filing_date <= applies_to`
and refuses unless exactly one candidate survives. That is precisely the
resolution Group B needs, generalised to no modelo but 303.

**That mechanism has since been exercised on the real tree for the first time**
(**reported by a lane**), and the mid-year branch it was always assumed to
support now has a test behind it: `select_revision(2022, '1T')` resolves to one
revision and `select_revision(2022, '2T')` to the other, while
`select_revision_for_year(2022)` **refuses and names both candidates** rather
than picking one. Anticipated-but-untested has become tested, which removes the
main reason to prefer splitting on caution alone.

The competing cost is now measured rather than estimated, and it is **×2 for any
design spanning a partial year**. Splitting Modelo 490 to accommodate its 2021
design costs roughly **320 casillas and 2,560 locale leaves instead of 160 and
1,280**, maintained in lockstep in perpetuity (**reported by a lane**), because
casilla locale keys are revision-scoped.

Group B therefore has two live options and this audit does not choose between
them. Splitting follows the approved Modelo 604 precedent at a measured doubling
of casillas and locale leaves per affected revision. Generalising the selector
touches one resolution site, leaves the revisions alone, and now rests on a
tested mid-year branch rather than an assumed one. The trade is duplication
against widening a mechanism whose blast radius is currently one modelo.

**Modelo 200 is a deferral rather than a candidate**, and the arithmetic is why
(**reported by a lane**). Splitting it would re-key **26,008** locale leaves and
create another 26,008 — roughly **52,000 leaves across about 2,090 files** —
because casilla locale keys are revision-scoped and a revision cannot be
casilla-less. Its defect is also **latent**: it declares no export layout and
zero `export_refs`, so a split buys no correctness today, and doing it before the
segmento-identity refactor would re-key those leaves twice. A ten-line hazard
note was landed against it instead, which is the proportionate response.

The fourteen era-*overlap* instances in three shapes are **reported by a lane**
and were not re-derived here. They are named in the request as the same missing
invariant, and if that is right they belong in whatever ruling covers Group B,
since both are about a revision that cannot say which design governs which year.

### coverage-denominator-corruption | high | The coverage gate concatenates every design a layout cites, inflating the denominator

**Verified here**, and observed in practice during this campaign rather than
reasoned about. The export layout coverage gate resolves a layout's official
design by taking **every** `record_design` source the layout cites and extending
one sheet list with all of them. It applies no window filter and no uniqueness
check, so citing two sources means reading two designs' sheets, whether or not
they are the same design.

A Modelo 156 layout authored during this campaign cited two source identifiers
that named the **same file with the same sha256** — one carrying no
`applies_from`, the other stamping 2021. The gate read that single design's two
sheets twice and reported "58 of 60 positions" where the truth was "29 of 30".
The layout was unchanged; only the citation count differed. Collapsing the
citation to one source corrected the figure immediately.

This is why the multi-design group above is a live defect and not a modelling
preference. Every Group B modelo is a layout waiting to be authored against
several legitimately distinct designs, and on Modelo 347 — four registered
designs — the same mechanism would **quadruple** the denominator. Any coverage
percentage reported for a multi-design revision is suspect until either the
gate filters by window or the layout is proven to cite exactly one design.

The immediate authoring rule that follows, and which cost this lane a full
measurement cycle to discover: **a fixed-width layout must cite exactly one
`record_design` source.** That is a workaround for the gate's behaviour, not a
statement about how many designs a modelo may legitimately have.

A second and more general caution belongs here, observed while this document was
being written. The denominator does not only move when a layout changes — it
moves when the **reader** changes, and it moves silently. Within one hour, with
the design PDFs byte-identical and the registry untouched, a change to the
record-design reader took one modelo's tipo 2 record from 21 parsed rows summing
to exactly its declared 500 up to 23 rows summing to 545, by promoting two
wrapped prose continuation lines to top-level fields; both new descriptions
begin mid-phrase, which is the signature. The same change took another modelo's
tipo 2 from 21 rows to 20 by dropping a 40-byte name field outright, where it had
previously mis-parsed it into a fabricated one-byte coordinate.

The second of those is the one to dwell on. Dropping the row **removed a refusal**
— the gate stopped asking for the position it could no longer see, the authored
layout satisfied everything remaining, and the modelo began reporting clean while
the instrument had gone blind to forty of its two hundred and fifty bytes. A
coverage figure is only ever as trustworthy as the read beneath it, and a fix to
the reader is exactly when a denominator moves under everyone at once.

Both were caught in a single command by summing the parsed field lengths and
comparing against the sheet's `total_positions`: over means sub-spans promoted to
siblings, under means rows dropped. `is_complete` reported `True` throughout,
before and after, in both directions.

**That check needs one correction, and it cuts against how this audit first
stated it.** A lane reported the comparison as vacuous on the ground that
`total_positions` is derived. **Verified here**, the truth is narrower than
either phrasing. On the narrative-PDF path `total_positions` is derived as the
terminal extent — `max(offset + length - 1)` at
`src/cadrumo/domain/calculations/registry/_record_design.py:2117` — while the
workbook path parses a genuinely declared TOTAL row. So on a PDF design the
comparison is Σ lengths against the terminal extent, which **does** detect
interior holes and overlaps: that is exactly how the two defects above were
found, and it is not vacuous. What it cannot detect is a truncation at the
**tail**, because dropping the final rows shrinks the extent and the sum
together and the two stay equal.

The honest statement of the method is therefore: **interior holes and overlaps,
yes; trailing truncation, no.** Holes and overlaps are what it was used for and
both remain valid; the tail is its blind spot and needs a different check.

### reader-unreadable-designs | high | The contiguity gate now raises, and fourteen designs cannot be read at all

**Verified here for three modelos; the tree-wide count is reported by a lane.**
The record-design reader has since gained a contiguity gate that **raises**
instead of returning a hole-bearing read, which is the correct direction and
directly productionises the check described above. The consequence is that a
design the reader cannot fully parse now blocks measurement outright rather than
understating it.

A lane reports **six or more named parse triggers** and **fourteen designs
unreadable**, of which **three carry live authored layouts** — Modelos 156, 280
and 349 — and are therefore currently **unmeasurable**. Two of those three are
confirmed first-hand here, with the reader's own words:

- Modelo 156: *"'Tipo 2 - Registro De Afiliado O Mutualista' declares 250 total
  positions but positions 36-75 were not read at all, so rows were dropped"*.
  That is the row whose naturaleza AEAT misspells as `Afabético`.
- Modelo 280: *"'Tipo 1 - Registro De Declarante' declares 500 total positions
  but positions 58 were not read at all"*. That is `TIPO DE SOPORTE`, whose
  naturaleza cell AEAT leaves empty.

Both layouts are complete against their official designs and are unchanged; only
the instrument's ability to check them has gone. Their revisions now refuse with
*"cannot be checked because its official record design could not be read in
full"*, which is an honest refusal and much preferable to the silent
under-reporting it replaced — but it is a **live regression in measurement
capability** while it stands, and it should not be mistaken for a defect in the
three layouts.

The same reader work also **fixed** a defect this audit recorded: Modelo 345's
tipo 2 sheet, which had briefly parsed as 23 rows summing to 545 against a
declared 500, now parses as **21 rows summing to exactly 500**, and that revision
is clean again with no change to its layout. Recorded because it is the
counter-example: the reader work is moving in the right direction, and the
unreadable fourteen are the remaining tail rather than a reversal.

### wrong-form-concepts | medium | Modelo 353 carries casillas and formulas for a breakdown its design does not contain

**Reported by a lane**, not re-derived here, and recorded separately because it
is a **different defect class from everything else in this document**. Modelo 353
declares eight casillas and three formulas modelling an IVA cuota breakdown that
its official record design does not contain **in either era**. These are not
missing positions, a temporal mismatch, or a gate artefact: they are concepts
authored onto the wrong form.

That distinction matters for the ruling. Every other item here is answered by
deciding how a revision binds to a design; this one is answered only by deciding
what the registry should do with declarations that correspond to no official
position at all. Scoping is reported in flight, so no remedy is proposed here.

This qualifies the grouping above rather than replacing it: Modelo 353 appears
there in Groups A and B on its era metadata, and that remains true of its
designs, but its casilla content is a third, separate problem that no revision
split would touch.

### application-data-model | medium | Nine or more modelos are blocked on facts the application does not model

**Reported by lanes**, with two anchors verified here. The general claim is that
these modelos cannot be authored because the application has no place to hold
data AEAT requires, independent of any registry or gate question.

Verified anchors. `FilingProducerKey` declares 35 members, of which 15 are
Modelo 303 specific and exactly one is specific to any withholding modelo
(`m111.colegio_concertado`); there are no Modelo 202 or Modelo 390 scoped
members, consistent with the reported gap. `WithholdingObservation` in
`src/cadrumo/domain/calculations/registry/_withholding_bindings.py` carries
eleven fields — `source_id`, `perceptor_tax_id`, `perceptor_legal_name`,
`country_code`, `transaction_date`, `clave`, `subclave`, `percibido_dinerario`,
`percibido_especie`, `retencion_practicada`, `ingreso_a_cuenta` — and its
docstring scopes it to modelos 190 and 193, so a Modelo 193 field gap would sit
inside an existing model rather than requiring a new one.

Not verified here: which specific Modelo 193 fields are missing; the donativo
count and sum facts for Modelo 182; the binding family reported missing for
Modelos 187, 188 and 194; and the bienes-y-derechos inventory reported for
Modelo 714. Each should be restated by its owning lane with the field list
before it is sized.

This decision differs in kind from the others in this document. The others ask
whether to change a schema or a gate; this one asks whether the product should
hold new categories of taxpayer data, which has consequences for secure storage,
for the operator surface, and for what the application is claiming to be.

### permanently-unfileable-modelos | medium | Three modelos cannot produce an export layout, for two different reasons

Modelo 289 is **verified here**. It is not a fixed-width filing at all. AEAT
publishes an XSD and a SOAP WSDL, bundled as
`corpus/aeat_official/instructions/modelo_289/files/289_XSD_2.0_WSDL_2.0.1.zip`
at `layout_authority` tier, sha256
`6948eec877d04ca637b099f59fa944996aa878c8d68181dfffde87fd056a048d`. There is no
`disenos_registro/modelo_289/` directory. `ExportLayoutFormat` admits exactly two
members, `fixed_width` and `xml_dictionary`. The `xml_dictionary` path requires
a `dictionary_source_ref` naming an AEAT `.properties` dictionary, and the only
such files bundled anywhere in the corpus are Modelo 100's twelve; an XSD is not
one. Even given a dictionary, `ExportLayoutDefinition.aux_version` has no
authoritative value anywhere in the corpus and the export refuses rather than
emit a guessed token.

So Modelo 289 is blocked by a **scope limit**, not by missing evidence: the
shipped format vocabulary does not model an XSD and web-service submission. That
generalises to any modelo AEAT moves to this channel, which is what makes it
worth ruling on rather than parking.

**This audit first stated that blocker too narrowly, and the correction matters
for how it is sized.** The first version said the obstacle was that the only
bundled `.properties` dictionaries belong to Modelo 100 — true, but that is a
corpus fact and reads as "acquire a file". The deeper obstacle is that
`xml_dictionary` is **not modelo-neutral in its renderer**: as recorded in the
modelo-scoped-mechanisms finding above, its render path branches on
`draft.modelo == Modelo.M100` at four points. So the second format is, in
practice, Modelo 100's format with a general name.

That changes the question the operator is answering. It is not "should the
format vocabulary grow a third member for XSD submission" alone; it is also
whether the second member is general enough to be extended from, or whether
generalising `xml_dictionary` is itself prerequisite work. Acquiring a Modelo 289
dictionary would not by itself make that path usable.

Modelo 186 and Modelo 361 are **reported by earlier lanes** and were not
re-derived here: Modelo 186's bundled design is recorded as an image-only PDF
with no text layer, truncated at position 34 of 320 with its defunciones annex
absent, and the modelo is recorded as not fileable online by operator ruling.
Modelo 361 is recorded as having no published record design and no fichero
route, verified across ten AEAT index pages with an instrument-validation
control.

The three share an outcome and not a cause, and the distinction matters for the
ruling: Modelo 361 has nothing to transcribe, Modelo 186 has something
untranscribable, and Modelo 289 has a complete specification in a form the
application cannot express. A single "no electronic channel" exemption covering
all three would paper over that difference, and an earlier hand-off already
warned that such a hatch would be reused on the next inconvenient modelo.

### itemised-repetition-tier | medium | Page repetition comes in three variants, and the third constrains any fix

**Reported by lanes**, not re-derived here. Modelo 714 is recorded as needing
roughly 985 itemised asset detail fields whose page-packed repetition is
expressed by neither `binding_rows` nor `projection_rows`, the two modes
`ExportRecordDefinition.repeat` admits.

The open question recorded against it is whether those rows are in scope at all,
which decides whether "complete" for Modelo 714 means roughly 130 positions or
roughly 1,200. That scoping question should be settled before any schema change
is designed, because the two answers imply different schemas.

**It is not one repetition shape but three, and they are not equally
tractable.** Modelo 714 carries a page indicator at position 12. Modelo 390
carries a settable `Blanco o "C"` discriminator on two pages. **Modelo 151
carries no discriminator at all**: a second page instance is byte-indistinguishable
from the first. Any repeat mode designed against the first two would not express
the third, and the third is the one that constrains the design — a reader or
writer cannot count instances it cannot tell apart. Whoever designs this should
start from Modelo 151 rather than Modelo 714.

**A reframing worth carrying into the sizing.** Modelo 151's 534 casillas
collapse to **195 distinct label strings**, because the block repeats. Sizing
these modelos by distinct strings rather than by casilla count may reduce Modelo
714 and Modelo 390 the same way, and would change what "roughly 1,200 positions"
implies for the work. That is a sizing question, not a correctness one, but it
bears directly on whether the itemised tier is as large as it currently looks.

### measurement-corrections | medium | Four figures this campaign circulated are wrong, one of them mine

**Reported by lanes**, recorded here because the superseded figures are already
in circulation and a reader who met them elsewhere needs the correction in the
same place as the rest.

- **Modelo 190 is at 32.7%, not 94.2%.** The higher figure counted `filler`
  fields as covering required positions; it does not, because a filler emits
  blanks. This is the single largest correction of the campaign.
- **Modelo 270 and Modelo 369 are refuted as defective.** Both are clean. Modelo
  270 had been reported as emitting blanks.
- **Forty-five layouts have been measured, not thirty-two**, of which **sixteen
  are genuinely complete** on the strict reading that a filler covers nothing.
- The **extent leg of the sum-versus-total check** is narrower than this audit
  first stated. The correction and its exact scope are recorded in the
  coverage-denominator finding above rather than repeated here.

The pattern behind three of the four is the same: a figure computed before
`filler` stopped counting as coverage. Any coverage percentage quoted from before
that change should be re-derived rather than carried.

## Recommendations

Each recommendation names the decision a follow-on ADR must make. None of them
records the decision.

**On source enrolment.** An ADR must decide who may assert
`SourceReference.review_status`, and whether that vocabulary gains an unreviewed
member as the revision-level vocabulary already has. Ruling this unblocks the
four acquired Modelo 490 and Modelo 763 designs immediately and unblocks every
future source acquisition. The revision-level review backlog should be tracked
separately and not folded into this ADR: it needs no decision, only 103 reviews,
and pairing them would make a work item look like a blocker.

This is the one item with direct evidence of pressure on it. An agent stamped
`review_status = "reviewed"` on two unreviewed Modelo 490 sources during this
campaign, breaching a standing red line; it self-reported, both source blocks
were deleted and twelve fragments repointed (**reported by a lane**). The
mechanism is what produced the breach: enrolment cannot proceed without the
assertion, so an agent under instruction to enrol an acquired design is placed
between a red line and its task. Until the vocabulary admits an unreviewed state
or an explicit operator step exists, that pressure recurs with every acquisition,
and the next breach may not self-report.

**On modelo-scoped mechanisms.** An ADR must decide the general rule before the
individual instances, because they are one defect: whether a mechanism any modelo
could use may be named, scoped or gated for one, and what the test is for
distinguishing a genuinely modelo-specific *concept* from a shared *mechanism*
that happens to have one caller. This audit offers that test — is the concept
present in more than one modelo's registry data — because it is decidable and it
sorted the census cleanly, but the rule itself is the operator's to set.

Two things should be sized against whatever rule is chosen: `FilingProducerKey`
and `ExportComputedKey` are 44% and 60% modelo-scoped, and the `xml_dictionary`
renderer branches on modelo at four points. One should be treated as urgent
regardless of the rule: three Modelo 131 revisions currently emit a file AEAT
rejects because the carrier they need is `M303_*`-scoped, and that is a live
filing defect rather than an architectural preference.

**On the envelope vocabularies.** This is an instance of the item above and
should be ruled with it, not separately. An ADR must decide whether the Modelo
303 envelope definition is re-expressed on the neutral role vocabulary, and must
rule on the one substantive difference between them — whether the period role
admits both an annual constant and a periodic token. The thirteen-role identity
and the 328-byte extent are settled.

What the ADR must NOT assume is that this is an available coverage unlock. On the
evidence now recorded, de-scoping ahead of an AEAT *entidad desarrolladora*
registration would move eighteen revisions from an honest visible gap to an
export-time refusal on an unsatisfiable dependency. The decision in front of the
operator is therefore two-part and the parts are separable: standardise the
convention now, and treat the de-scoping itself as gated on a business
registration that no code change substitutes for. The Modelo 131 DPA page-marker
demand should be sequenced into the same job rather than raised twice.

**On temporal coverage.** An ADR must decide, separately for each group, how a
revision binds to a design: whether Group A splits revisions on the Modelo 604
precedent, whether Group B generalises the existing Modelo 303 window selector
or splits as well, and what a revision must do when no design covers part of its
declared span. Modelo 165 is the case to reason from, because its evidence is
positive rather than inferential. Until it is ruled, no layout should be
authored on a Group A revision: doing so writes a later era's bytes into an
earlier era's filings, silently.

The Group B trade is now evidenced on both sides and the ADR should weigh the
measured figures rather than the intuitions: the window selector's mid-year
branch is tested, and splitting costs a measured doubling of casillas and locale
leaves per affected revision. Modelo 200 should be explicitly excluded from
whichever remedy is chosen and left deferred, on its own arithmetic.

Three implementation traps belong in whatever plan follows and should not be
rediscovered: the coverage gate concatenates the sheets of every design source a
layout cites, so a layout must cite exactly one; reading only per-modelo legal
files undercounts registered designs, because several modelos register theirs in
shared catalogues; and a coverage figure computed before `filler` stopped
counting as coverage is not comparable with one computed after.

**On concepts authored onto the wrong form.** A separate ADR, or an explicit
carve-out in the temporal one, must decide what the registry does with
declarations that correspond to no official position in any era — Modelo 353's
eight casillas and three formulas being the known instance. No remedy is proposed
here because the scoping is still in flight, but it must not be folded into the
temporal ruling: a revision split would leave it untouched.

**On measurement.** No ADR is needed, but the corrections recorded above should
propagate before any of these decisions is sized, because three of the four
inflate how complete the tree currently looks. In particular the fourteen
unreadable designs — three of them carrying complete authored layouts — mean
several coverage figures cannot currently be produced at all, and an absent
figure must not be read as a zero.

**On the application data model.** An ADR must first decide the product
question — whether the application holds these categories of taxpayer data at
all — before any field-level design. Each owning lane should restate its gap as
a concrete field list first; the evidence gathered so far does not support
sizing this, and no recommendation on shape is offered here because none would
be grounded.

**On the unfileable modelos.** An ADR must decide the disposition of each of the
three separately, because their causes differ. For Modelo 289 the decision is
whether the format vocabulary grows a third member for XSD and web-service
submission, which is a capability question rather than a disposition question,
and which will recur. For Modelo 186 and Modelo 361 the decision is whether
their revisions are removed or their refusals accepted permanently. A single
exemption spanning all three is the one option this audit advises against, on
the ground already recorded: it would generalise to the next inconvenient
modelo.

**On the itemised tier.** An ADR must decide the scope question — whether
itemised asset rows are declared at all — before it decides a repeat mode. The
schema change follows from that answer and cannot be designed ahead of it. When
it is designed, it must be designed against Modelo 151, whose repeated page
carries no discriminator at all; a mode that expresses only Modelo 714's position
indicator and Modelo 390's settable marker would not express the case that
actually constrains the problem.
