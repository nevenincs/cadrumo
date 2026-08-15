---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-15'
modified: '2026-08-15'
body_schema: 'body-v1'
body_hash: 'sha256:804994a4cb07a6977af06cf9b9a3a95bec60f8f7f924e61b9950694efca13a90'
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
re-derivation. Both are recorded as findings rather than silently corrected,
because in each case the correction changes what is being asked for.

Scope boundary: this document ranks nothing and decides nothing. Several of
these are product decisions whose evidence does not select an option, and where
that is the case it is said plainly instead of being resolved by preference.

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
the review: no modelo revision in the bundled tree declares a non-default
`review_status`. The five string matches for `review_status` under the modelo
tree are all Modelo 303 *binding* fragments, a third subject again.

The consequence is that the revision axis is **not blocked on a decision at
all** — it is blocked on someone performing 102 per-revision reviews, which is
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

One difference is **not** cosmetic and is easy to miss under the naming noise.
The Modelo 303 role is `PERIOD`, which carries a quarterly or monthly token; the
neutral role is `ANNUAL_PERIOD`, which the Modelo 390 header fixes to the
constant `"0A"`. A generalisation that renames without widening that one role
would silently narrow every periodic modelo to an annual token. Whatever shape
is chosen, that role has to admit both.

The claim that de-scoping closes thirteen or more revisions, several to genuine
completeness, is **reported by a lane** and was not re-derived here. The
structural identity above is what this audit verified; the revision count is
what should be re-checked before it is used to size the work.

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

Group B has a concrete and already-observed cost. The export coverage gate's
design resolution takes **every** `record_design` source a layout cites and
concatenates their sheets; it performs no window filtering. A Modelo 156 layout
authored during this campaign cited two sources that named the same file with
the same hash, and the gate duly read the same two sheets twice and reported
"58 of 60" where the truth was "29 of 30". On Modelo 347 the same mechanism
would quadruple the denominator.

**Group C, acquired but unenrolled** — Modelo 490 and Modelo 763, per the
finding above. Their remedy is not a split; it is the source-enrolment gate.

Modelo 604 is the worked precedent for Group A and B alike, and it is already
approved: two revisions with bounded selectors, `2021-2023` and
`2024-y-siguientes`, against two designs whose `applies_from` and `applies_to`
tile them exactly. Nothing else in the census matches that shape.

A window-based design selector already exists and already works, but only for
one modelo: `src/cadrumo/domain/calculations/registry/_m303_orden_resolution.py`
at lines 100 to 113 filters candidate designs by
`applies_from <= filing_date <= applies_to` and refuses unless exactly one
survives. That is precisely the resolution Group B needs, generalised to no
modelo but 303.

The fourteen era-*overlap* instances in three shapes are **reported by a lane**
and were not re-derived here. They are named in the request as the same missing
invariant, and if that is right they belong in whatever ruling covers Group B,
since both are about a revision that cannot say which design governs which year.

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

### itemised-repetition-tier | medium | Modelo 714's itemised rows need a repeat mode neither shipped mode expresses

**Reported by a lane**, not re-derived here. Modelo 714 is recorded as needing
roughly 985 itemised asset detail fields whose page-packed repetition is
expressed by neither `binding_rows` nor `projection_rows`, the two modes
`ExportRecordDefinition.repeat` admits.

The open question recorded against it is whether those rows are in scope at all,
which decides whether "complete" for Modelo 714 means roughly 130 positions or
roughly 1,200 — and the same question is reported to generalise to the other
large modelos. That scoping question should be settled before any schema change
is designed, because the two answers imply different schemas.

## Recommendations

Each recommendation names the decision a follow-on ADR must make. None of them
records the decision.

**On source enrolment.** An ADR must decide who may assert
`SourceReference.review_status`, and whether that vocabulary gains an unreviewed
member as the revision-level vocabulary already has. Ruling this unblocks the
four acquired Modelo 490 and Modelo 763 designs immediately and unblocks every
future source acquisition. The revision-level review backlog should be tracked
separately and not folded into this ADR: it needs no decision, only 102 reviews,
and pairing them would make a work item look like a blocker.

**On the envelope vocabularies.** An ADR must decide whether the Modelo 303
envelope definition is re-expressed on the neutral role vocabulary, and must
rule on the one substantive difference between them — whether the period role
admits both an annual constant and a periodic token. The thirteen-role identity
and the 328-byte extent are settled; the revision count that would close should
be re-derived before it is used to justify the work.

**On temporal coverage.** An ADR must decide, separately for each group, how a
revision binds to a design: whether Group A splits revisions on the Modelo 604
precedent, whether Group B generalises the existing Modelo 303 window selector
or splits as well, and what a revision must do when no design covers part of its
declared span. Modelo 165 is the case to reason from, because its evidence is
positive rather than inferential. Until it is ruled, no layout should be
authored on a Group A revision: doing so writes a later era's bytes into an
earlier era's filings, silently.

Two implementation traps belong in whatever plan follows and should not be
rediscovered: the coverage gate concatenates the sheets of every design source a
layout cites, so a layout must cite exactly one; and reading only per-modelo
legal files undercounts registered designs, because several modelos register
theirs in shared catalogues.

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
schema change follows from that answer and cannot be designed ahead of it.
