---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-20'
modified: '2026-08-21'
body_schema: 'body-v1'
body_hash: 'sha256:c3636f524786743d85fe166f45df130f6079ffacddc8dc08f293414d8c7ffd58'
related:
  - "[[2026-08-15-registry-temporal-coverage-audit]]"
  - "[[2026-08-16-registry-temporal-coverage-designless-modelo-adjudication-audit]]"
---

## Scope

A review-stamping campaign over the pending-review population, driven by reading each
modelo's own approving orden and its printed annex rather than the conformance screen.
Census moved 76 / 1 / 21 to 79 / 1 / 18 (agent_reviewed / operator_reviewed /
pending). Everything below is measured against the bundled corpus or a fetched BOE
source; the negative results are recorded so the next attempt does not repeat them.

## Findings

### fabricated-casillas-on-four-informativas | high | Four modelos declared boxes their printed annex does not have, and formulas asserting identities the forms deny

Modelos 187, 188, 194 and 296 each declared casillas `03/04/05` with a
`modelo-NNN-total` formula shaped `add(args=[04])` -- an identity copy of one casilla
-- justified in test prose as "per the AEAT form's own printed total row". Reading the
annex images disproved that appeal for all four:

| modelo | annex | boxes actually printed | what the registry declared |
|---|---|---|---|
| 187 | Orden HAP/1608/2014 ANEXO I | 01-04, **no 05**; 03 is *enajenaciones* | 03 as "base", 05 invented |
| 188 | Orden 17-11-1999 ANEXO IV | 01-08; two rows split by sign of base | all three wrong |
| 194 | Orden 18-11-1999 ANEXO VIII | identical to 188 | all three wrong |
| 296 | Orden EHA/3290/2008 ANEXO II | 01-04; 04 is retenciones *ingresadas* | numbers shifted by one |

Modelo 296's was the most consequential: box 04 (design offset 175) is a filtered
subset of box 03 -- only perceptores whose CLAVE is 3 to 25, or CLAVE 1 or 2 with
PAGO = 1 -- so copying 03 into it asserted an identity the diseño explicitly denies,
and the fixed-width export wrote that asserted figure into the ingresadas field. Any
declarante with a CLAVE 1/2 perceptor lacking PAGO = 1 would have filed an overstated
figure.

All four are re-authored, the formulas deleted, the four allowlist entries in
`src/cadrumo/domain/calculations/registry/tests/test_formula_citation_discriminates.py`
cleared (the allowlist is now empty and the gate a pure ratchet), and the tests that
pinned the old shape rewritten. `boe-modelo-{187,188,194,296}-form-layout` were
re-pointed off the wrong ordenes onto freshly bundled correct ones, and each annex
transcribed to a guidance-tier `boe-modelo-NNN-form-text` extract.

**How the annex images were reached, since `act.php` hides them:** the consolidated
HTML drops annex images, which is why a `form_spec` source could carry zero
occurrences of "casilla". `diario_boe/txt.php?id=...` lists them and the `/datos/`
prefix serves them. Walking that HTML in document order maps each image to its ANEXO
heading, which is how the euros variant was distinguished from the pesetas one.

### generated-tree-epoch-outside-revision-span | high | Three generated export trees render from a design epoch that does not cover their revision's span

Every multi-design modelo's design sources are already epoch-windowed and
non-overlapping, so "which design governs which filing year" is answered at the source
level. What is not answered is which design a GENERATED export tree was rendered from.
Each `_GeneratedTree` row in `dev/registry/tests/test_generated_export_trees.py`
declares one `filing_year`, so check mode validates the tree at that year only:

- `_GeneratedTree("200", "2024-y-siguientes", "aeat-dr-200-2025", ...)` -- revision
  opens 2024; the 2024 design closed 2024-12-31, so a 2024 filing exports through the
  2025 layout.
- `_GeneratedTree("347", "2008-y-siguientes", "aeat-dr-347-2025", ...)` -- 17 years
  covered by the 2008/2010/2011 designs export through the 2025 layout.
- `_GeneratedTree("322", "2008-2025", "aeat-dr-322-2024-2025", ...)` -- years under
  `aeat-dr-322-2023` export through the 2024-2025 layout.
- `_GeneratedTree("210", "2025", "aeat-dr-210-2022", ...)` is the only consistent row;
  its revision sits inside the pinned window.

The machinery already knows epochs are year-bound -- `test_record_design_ir` asserts
"aeat-dr-200-2024 does not apply to filing year 2025" -- so the gap is that nothing
asks whether a tree is right for the REST of its revision's span. Not remediated here:
200, 322 and 347 are campaign-held trees.

### m188-m194-plazo-correct-but-unlocatable | medium | A filing deadline whose value is right and whose establishing provision is not any of five candidates

**RESOLVED by operator ruling; the finding is kept because the search results save the
next reader five dead ends.**

Modelos 188 and 194 declare a 1-31 January window. Five instruments were checked and
none establishes it:

1. Orden 17-11-1999 (m188): papel "los veinte primeros días naturales del mes de
   enero"; soporte "entre el 1 de enero y el 20 de febrero".
2. Orden 18-11-1999 (m194): the same two channels, same dates.
3. Orden HAC/2895/2002, the Internet-presentation orden the m188 corpus itself names:
   telemática "entre el 1 de enero y el 20 de febrero".
4. Orden HAC/1276/2019 (modifies the 18-11-1999 orden; the obvious candidate since the
   revision is named `2019-y-siguientes`): changes no plazo, only field definitions.
5. Orden HAP/2194/2013, the general informativa-presentation orden: full 639 KB
   consolidated text carries **zero** occurrences of "31 de enero".

BOE's own amendment analysis settles why: the "SE MODIFICA" list on each consolidated
page names only anexos (`el anexo V` for the m188 orden; `el anexo X` and `lo indicado`
for m194's). **No plazo article of either orden was ever amended.**

**THE RULING: ground it in AEAT-emitted information, and keep the ranges uniform within
a regime.** The authority for the window is the Calendario del Contribuyente, now
bundled as `aeat-calendario-contribuyente-2026-hasta-2-febrero` and cited on both
windows. The value is unchanged, because it was already correct.

The same pass settled the storage convention the whole tree now follows: **a window
stores the NOMINAL statutory range and `shift_deadline` produces the operational date**.
That is verified against AEAT's own calendar in both directions -- its "Hasta el 2 de
febrero" page lists 180, 182, 187, 188, 190, 193, 194, 196, 270, 296 and 345, and
nominal 2026-01-31 yields 2026-02-02 (`sabado`) for every one; its "Hasta el 31 de
enero" page lists only modelo 369, and that one yields 2026-01-31
(`modelo_exception`), because M369 is the sole member of `MODELOS_WITHOUT_SHIFT`. The
registry's exception list and AEAT's calendar agree without either being derived from
the other.

Modelo 345 was the last window still storing a pre-shifted date (`2026-02-02`, AEAT's
shifted date copied into the data) against its own Orden HFP/823/2022 art. 4 -- "entre
el 1 y el 31 de enero de cada año". Corrected. A sweep over every filing-year-2025
annual window closing in January or February 2026 now shows none storing a shifted
date.

### stub-population-is-not-one-class | medium | Six revisions treated as interchangeable 2-casilla stubs differ on the axis that decides reviewability

Measured with `build_diseno_coverage_report(..., multi_segment=False)`:

| revision | diseño derives | covered | verdict |
|---|---|---|---|
| 038/2002-y-siguientes | 0 | 0 | unmeasured (geometry-recovered source) |
| 185/2003-2025 | 0 | 0 | unmeasured |
| 185/2025-y-siguientes | 0 | 0 | unmeasured |
| 222/2025-y-siguientes | 63 | 0 | real gap |
| 840/2003-y-siguientes | 108 | 0 | real gap |
| 220/2024-y-siguientes | 7682 | 0 | real gap |

The three with a real gap declare two header casillas against a published,
machine-derivable form surface and are refused: an `agent_reviewed` stamp there would
wear the same checkbox as a fully covered revision. The distinction between "the form
numbers nothing" and "the source could not be read completely" is now reportable --
`DisenoCoverageReport.recovered_from_chart_geometry` plus `extracted_fields` /
`described_fields` -- because the pre-existing `extraction_found_no_casillas` docstring
told readers to "distinguish the two by whether the source yielded fields at all" and
the report carried no count with which to do it.

### review-status-drove-a-corpus-audit-to-abort | high | Reviewing an applicability-grade revision made the registry stop loading, and one of two sibling call sites already knew better

`audit_registry_model_law_coverage` and `audit_registry_construct_evidence` in
`src/cadrumo/domain/calculations/registry/_coverage.py` ask the same question of every
revision and disagreed on the answer. The first catches the filing-capability refusal
and records it, with a comment stating that review state and filing capability are
different conditions and that 83 revisions refuse there. The second made the identical
call unguarded, so stamping an `applicability`-grade revision `agent_reviewed` raised
`RegistryValidationError` and the registry stopped loading -- reproduced on modelo 038
("declares no export layout, so no filing artifact can be produced from it"). An
applicability-grade revision therefore could not be reviewed at all, which is why none
of the stamped revisions was ever one. Fixed by making the second site do what the
first one's comment already said, recording the reason on a new
`authority_fallback_reason` so "reviewed but cannot file" stays distinguishable from
"nobody reviewed it".

### m182-models-a-fraction-of-the-donor-row | high | Modelo 182 can represent 5 of 18 declarable donor fields, and the omissions move a taxpayer's deduction in both directions

Modelo 182 `2007-y-siguientes` had never been examined by this campaign. It is not a
stub: 7 casillas (2 declaration-header plus 5 tipo-2 donor-row), 5 `donativo_donor`
ledger bindings, 9 deadline windows. Its casillas model the tipo-2 RECORD, so field
coverage against the diseño is the applicable measure -- casilla-number coverage is
inapplicable here for the usual substantive reason (38 fields, all described, zero
numbered boxes).

Measured against `01-182-ejercicio-2025.pdf`, the tipo-2 registro carries 23 fields:
5 envelope/filler, 5 modelled, **13 data-bearing and unmodelled**:

| offset | field | why it matters |
|---|---|---|
| 98, 100 | `DEDUCCIÓN COM. AUTÓNOMA`, `% DE DEDUCCIÓN COM. AUTÓNOMA` | an autonomous-community donation deduction the donor is entitled to; unrepresentable means the donor's deduction is UNDER-stated |
| 106, 107 | `REVOCACIÓN`, `EJERCICIO EN QUE SE EFECTUÓ LA DONACIÓN REVOCADA` | a revoked donation must be reported; unrepresentable means an earlier deduction stands when it should not -- the OVER-deduction direction |
| 78 | `CLAVE` | the donation-type key that selects the applicable régimen |
| 97 | `DONATIVO … EN ESPECIE` | in-kind donations cannot be distinguished from cash |
| 111, 112 | `TIPO DE BIEN`, `IDENTIFICACIÓN DEL BIEN` | the in-kind asset itself |
| 133, 142 | patrimonio protegido titular NIF and name | contributions to a protected patrimony |
| 27, 76, 105 | representante legal NIF, código provincia, naturaleza del declarado | declarant-side identification |

This is the shape the `no-silent-under-declaration` rule asks to be probed in BOTH
directions: the CCAA deduction omission is the OVER-PAYMENT direction, which that rule
notes is the unwatched one, and the revocación omission is the under-declaration one.

**Not stamped.** A review would assert this revision was examined while it can
represent under a third of the record it models. Remediation is authoring the
remaining tipo-2 casillas and the bindings that feed them -- the five that exist map
exactly to the five `donativo_donor` bindings, so the registry currently models what
the ledger supplies rather than what the form declares, and closing the gap means
extending both.

**A trap noticed while measuring it, worth stating.** m182 reports
`construct_evidence_gaps=10` where every stamped revision reports 0. All ten are
`unvalidated`, whose reason is "has refs but no validated registry authority" -- the
fail-closed state of an UNREVIEWED revision. Stamping would flip all ten to
`inherited` without verifying anything. A gap count that a stamp erases is not evidence
for stamping, and is not evidence against it either; the substantive field coverage
above is what decides.

### m222-authoring-is-specified-not-blocked | medium | The smallest "needs casilla authoring at scale" blocker is fully derivable from its bundled diseño, and here is what it costs

Modelo 222 (pagos fraccionados, régimen de consolidación fiscal) declares 2
declaration-header casillas against a diseño deriving 63 -- the smallest member of the
authoring-at-scale group, and the one worth scoping first. It is NOT blocked on missing
information. Measured against `01-222-ejercicio-2025-y-siguientes.xlsx`:

- **63 box-tagged fields**, carrying the box number inline as `[NN]`, so the numbering
  needs no inference.
- **Data types are derivable from field length**: 57 fields of length 17 are money, 6 of
  length 5 are percentages (`ratio`).
- **Sections are derivable from the description prefix**: 3 boxes under
  `A) Liquidación` (modalidad art. 40.2 LIS) and 59 under `B) Liquidación`
  (art. 40.3 LIS), which further splits into `B.1) Caso general` and
  `B.2) Casos específicos`.
- **Legal grounding is the two LIS modalidad articles** the descriptions name
  themselves, art. 40.2 and art. 40.3.

**THE TRAP THIS SPEC EXISTS TO NAME. 63 tagged fields carry only 60 DISTINCT box
numbers.** Boxes 16, 22 and 32 each appear twice, both times inside the same sheet
(`DR22202`) at different offsets, carrying different data:

| box | offset | what it holds |
|---|---|---|
| 16 | 13 | B.1 caso general -- Base del pago fraccionado |
| 16 | 137 | B.1 caso general -- Resultado previo |
| 22 | 193 | B.2 casos específicos -- Importe |
| 22 | 429 | B.2 casos específicos -- Resultado previo |
| 32 | 519 | B.2 casos específicos -- Resultado |
| 32 | 553 | B.2 casos específicos -- Cantidad a ingresar |

Authoring these three as a bare `16`, `22`, `32` would collapse six distinct declared
figures into three, and the coverage report would still read 60 of 60 because it keys
on the number. They must take the box-then-offset id shape (`16-13`, `16-137`), which
is the same convention modelo 100 uses for its repeated boxes.

**Cost, stated so the decision is informed:** 63 casilla declarations plus 63 labels in
four locales -- 252 locale strings -- plus the semantic roles, which must not collide
(the singleton-role typo gate refuses near-twins, and this form has natural twins like
two "Resultado previo" boxes in different modalidades).

**This is a FEATURE, not a review fix.** Authoring the boxes makes modelo 222 filing-
capable, which is a product decision about whether Cadrumo supports the consolidated-
group pago fraccionado. It is deliberately not started here: a half-authored casilla
set is a silently narrower registry, and worse than the honest 2-casilla stub that
exists now.

### box-number-coverage-has-an-unmeasured-limit | medium | 21 of 56 diseños print one box number over several fields, and the obvious way to detect it is wrong

``build_diseno_coverage_report`` keys a derived casilla on ``(segmento, number)``. A
single-segment form has no ``segmento``, so two fields printing the same ``[NN]``
derive ONE casilla, and a registry declaring that number reads as covering both. The
second figure is unmodelled and no gap appears.

The docstring anticipates recurrence ACROSS sheets and justifies collapsing it. What it
does not discuss is recurrence WITHIN one sheet, which is the modelo 222 shape: boxes
16, 22 and 32 each print twice in ``DR22202`` at different offsets, over "Base del pago
fraccionado" versus "Resultado previo" and similar pairs.

**Measured across the bundled corpus** -- first diseño per modelo, box tag read from
each field's own description:

| modelo | repeated numbers | extra fields that collapse |
|---|---|---|
| 151 | 50 | 403 |
| 036 | 82 | 193 |
| 390 | 9 | 24 |
| 840 | 7 | 18 |
| 763 | 10 | 10 |
| 303 | 8 | 8 |
| 200 | 5 | 6 |
| 714 | 5 | 5 |

...and 13 more with 1-3 each, for **21 of 56 modelos scanned**. This is the common
case, not a curiosity, and it means a coverage figure counts NUMBERS while the form
carries more FIGURES than numbers.

**THE OBVIOUS DETECTOR IS WRONG, AND WAS BUILT AND REVERTED RATHER THAN SHIPPED.**
Adding a `box_tagged_fields` count and flagging `box_tagged_fields >
len(diseno_casillas)` looks like it separates the two. It does not. A field's
description cites OTHER boxes inside its own arithmetic -- modelo 353's label is
literally ``Resultado ([01] - [08]). [03]`` -- and ``_sheet_record_numbers`` scans
``description``, ``validation`` AND ``content``, so a referenced number enters the
derived set exactly like a declared one. Measured on modelo 222: **63 fields carry a
tag, but there are 82 tag occurrences, and 3 fields cite more than one distinct box.**
The field count and the number count are therefore not comparable in either direction,
and the flag reported `False` for modelo 222 -- the very form that motivated it.

**What a correct measure needs** is a way to tell a field's OWN box tag from a box it
merely references. The extraction does not mark that today; the tag is just text in a
description. Until it does, the honest statement is the one above: coverage counts
numbers, 21 modelos carry more figures than numbers, and the size of that gap is
unquantified.

### m604-declares-no-official-box-numbers | medium | 122 casillas, zero numeric ``number``, on a revision that declares a byte-extent fichero layout

m604 was authored between iterations (`32e91b24fb`, `67ebbc9fed`, `11ec8d3bcc`) and now
carries **79 casillas at 2024-y-siguientes and 43 at 2021-2023**, span-matched to
``03-604-ejercicio-2024.xlsx`` and ``04-604-ejercicios-2021-a-2023.xlsx``. It is no
longer a 2-casilla stub.

``build_diseno_coverage_report`` nevertheless reports **0 of 37 covered** on both. That
is not a content gap -- the liquidación boxes ARE modelled (15 casillas under
``liquidacion`` plus 30 under ``territorio`` at 2024). It is a **numbering** mismatch:
every one of the 122 casillas carries a slug in ``number``
(``liq-01-base-imponible``, ``terr-alava-cuota-total-atribuible``), and the report keys
on the printed box number.

**The corpus convention is the opposite**, measured across the reviewed set: numeric
``number`` = the printed AEAT box, slug = a field with no printed box.
m390/2025 364 numeric of 393; m303/2025 181 of 207; m200 3460 of 3462; m036 29 of 31.
**m604 is 0 of 122** -- the only member of the set with no official numbering at all.
The ``CasillaDefinition`` docstring is explicit that ``number`` is "reviewed AEAT
record-design metadata", and `modelo-export-mirrors-official-structure` gates the
casilla SET *and its numbering* against the official layout.

**Why it happened, and why the schema is not the culprit.** ``(segmento, number)`` is
hard-enforced unique (`_validate_revision_identity.py:180`), and m604 is single-segment,
so ``segmento`` is ``None`` and ``number`` alone must be unique. The 2024 diseño prints
boxes 03, 04 and 10 over TWO record fields each -- a signo byte and the value -- so a
literal ``number = "03"`` on both is refused. `7282a513e4` shows a peer hitting exactly
that refusal on ``decl-idioma`` and escaping via a slug; the escape then spread to all
122.

**A duplication hypothesis was tested and REFUTED, not shipped as a finding.** m303,
m390 and m200 declare no ``signo`` casilla across 4,000+ casillas, which looked like
m604 duplicating a concept the corpus models as the sign of a ``money`` value. It is
not: m604 declares a **byte-extent** fichero layout that maps every byte, signo bytes
included, to a backing casilla via ``export_refs``, whereas m303's export file is a
2.2 KB envelope descriptor (``prefix_extent``, ``record_identity``,
``closer_derivation``) with no per-byte map. The two are not comparable and m604's
signo casillas are structurally required.

**What the narrow fix would be** -- NOT applied, see below. A signo field has no printed
box of its own: the diseño reads "Signo BI [03]", the sign OF box 03. So the signo
casillas keep their slug while the twelve liquidación VALUE casillas take their printed
``01``..``12``, and uniqueness holds. If the 30 territorio casillas likewise carry the
printed boxes, the distinct total is ~37 -- exactly the count the report derives, which
is a checkable prediction rather than an assumption.

**Not applied: m604 is peer-owned and landed 2026-08-20.** No reasoning body was
recorded on `32e91b24fb` ("for the updated coverage/signed rules"), so there is no
stated rationale to weigh against the corpus convention, and rewriting 122 freshly
landed casillas on one reading would be barging. m604 stays **pending_review** in both
revisions: a revision whose numbering does not mirror the official layout cannot be
honestly stamped, and stamping it would flip it onto the filing-authority proof path.

### the-span-gate-is-not-what-separates-reviewed-from-pending | high | 60 of 80 stamped revisions carry the same failure the pending ones do, and no stamp says so

``test_every_modelo_revision_span_is_corpus_proven`` and
``test_no_revision_spans_a_design_relayout`` are the richest instruments in the registry
suite. They report, per revision, whether AEAT's published record designs actually
evidence the span the revision claims, and their messages are unusually directive --
*"do not treat the gap as anything other than a failure"*, *"do not split this revision
on today's evidence"*, *"do not attempt to satisfy this with design evidence alone"*.

**Measured this iteration: the two gates name 74 revisions. 60 are already
``agent_reviewed``. 14 are ``pending_review``.** Of the 15 pending revisions, 14 are
flagged -- but so are three quarters of the reviewed corpus.

The consequence is the finding. The span gate **cannot** be the bar that separates a
stamped revision from a pending one, because the stamped population fails it at
roughly the same rate. Treating it as a stamping blocker for any single revision would
apply a standard 60 of its already-stamped peers do not meet. Yet nothing in the census
records this: ``review_status=agent_reviewed`` and the 81/0/14 summary give no hint that
most reviewed revisions have no corpus proof of their own span.

**This session's own m194 stamp is an instance.** It enumerates real limits -- the
tipo-2 per-perceptor detail is not modelled, no export layout is declared,
full-diseño casilla-number coverage is inapplicable -- and every one is true. It simply
never states that the bundled design evidences no year inside the revision's span. The
stamp misrepresents nothing it asserts; it is narrower than the gate's bar without
saying so, and a later reader cannot tell the difference from the census.

**Precedent set rather than argued.** m182/2007-y-siguientes was stamped this iteration
with the span hole named in ``reviewed_by``, along with the deferred-binding limit and
the explicit note that ``independent_check_coverage`` 0.0000 is NO CLAIM rather than
zero. It is applicability grade, ``fixed_width_export`` stays false, and the scope does
not flip to filing. Census 80/0/15 -> 81/0/14, 95 rows, clean load.

**What this changes about "clear the pending set".** The remaining 14 are not a backlog
of unreviewed work sitting behind one shared obstacle. Fourteen of them share an
obstacle that 60 *reviewed* revisions also have. The honest target is not to drive
pending to zero but to make every stamp state which of the standing failures it does
not close -- otherwise the count moves and the corpus learns nothing.

**Corollary worth its own attention:** the gate's own module docstring records a
previous instrument failure in this exact shape -- a privately re-declared four-digit
box-number regex against Modelo 200's five-digit boxes, which switched the box-offset
and box-set signals off while reporting nothing wrong. Its note is the general lesson:
*"Agreement between two instruments sharing one blind spot is worth nothing, and unlike
a wrong answer it offers nothing to notice."*

## Recommendations

- ~~Operator ruling needed on the m188/m194 window.~~ **Ruled and implemented:** store
  the nominal statutory range, let `shift_deadline` produce the operational date, and
  ground a window whose orden does not state its plazo in AEAT's own Calendario del
  Contribuyente. See the plazo finding above.
- **A deadline window must never store a shifted date.** Storing AEAT's published
  operational date instead of the statutory one silently drops the shift REASON the
  operator is entitled to -- the calendar then shows a date that moved without saying
  it moved. Three modelos had done it (200, 220, 345); all are corrected.
- **Pin each generated tree to a design epoch that covers its revision span**, or split
  the revision per edition. The check gate cannot see the mismatch today.
- **Do not let the pending-review population be cleared by stamping to green tests.**
  30 of 113 registry-suite failures are one deliberate gate meeting the 18 pending
  revisions; modelo 840 fails for exactly that reason AND covers 0 of 108 derived
  casillas. Stamping it would green a test and record a false review in one act.
- **Run the registry test suite after re-authoring a revision, not the conformance
  report.** `dev.registry.conformance report` is a screen: it stayed green at 95
  revision rows through four commits while eight tests pinning the deleted formulas
  were red.
