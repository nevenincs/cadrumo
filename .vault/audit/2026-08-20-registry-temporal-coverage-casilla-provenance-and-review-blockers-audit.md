---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-20'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:754e5c769af8dc2d6434341a323dde698e0912b2df8f9ebb936830b84820a6de'
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

### a-multiline-reviewer-note-made-a-revision-unstampable | medium | fixed; the writer's own docstring stated the assumption that made it wrong

Acting on the previous finding meant amending four stamps this campaign wrote to name
the span limit they omitted. Two took the amendment. Two refused, identically:

```
invalid TOML: expected an equals, found a colon at line 10 column 6
```

The refusal was deterministic and independent of the new text -- a four-word probe
string reproduced it exactly. The manifest on disk parsed fine and the full registry
loaded clean, so the message described the CANDIDATE the writer had just produced.

``_apply_governance`` edits whole ``key = value`` lines so a hand-authored manifest
stays reviewable, and ``_is_governance_line`` documented the assumption that broke it:
*"the four keys are scalars, so their assignment is always a single whole line."* A
scalar written as a TOML multi-line basic string still occupies several PHYSICAL lines.
Dropping only the line carrying the key orphaned the prose and the closing delimiter,
and a reviewer note conventionally opening ``agent: ...`` then parses as a key with a
colon where an equals belongs -- column 6, every time.

That is why two of four worked: m187 and m576 carried single-line ``"..."`` values,
m188 and m194 carried triple-quoted ones. **m188 and m194 were permanently unstampable
through the only sanctioned writer**, and nothing said so; the campaign had simply
never tried to restamp a revision whose note was long enough to have been wrapped.

The refusal was the GOOD outcome. The verb validates before writing and restores the
previous bytes on failure, exactly as its docstring promises, so neither manifest was
left broken. The defect was that the value became unreplaceable rather than merely
awkward.

Fixed in ``dev/registry/conformance/_stamp.py``: ``_without_governance_assignments``
walks the table and skips each assignment's full span, and
``_governance_assignment_length`` stops at the closing delimiter so an unterminated
opener runs to the end of the table rather than consuming unrelated declarations.

**Proven by neutralising it**, not by assertion: with the old one-line filter restored,
the two multi-line tests fail with precisely the production error (``Expected '=' after
a key ... at line 2, column 6``) while the single-line control keeps passing. The
control is what separates this from a test that merely detects a broken function.

**Capture note.** The four amended manifests were committed by a peer as
`4a115aabe2` before this session could commit them -- the twelfth capture of this
campaign's work. Nothing was lost, because the entire scope statement lives INSIDE the
``reviewed_by`` string rather than in the commit message. That is the whole reason the
standing instruction puts it there, and this is the clearest demonstration yet.

### every-pending-revision-is-applicability-grade | high | most of the inventory measures them against a rung they do not claim, and m220 still fails on its own

**Measured: all 14 remaining ``pending_review`` revisions declare
``authority_grade = "applicability"``.** Not one claims calculation or filing.

The owning authority (``core/_authority_grade.py``) defines that rung as *"The revision
knows when the modelo is due and to whom it applies. Scheduling and deadline reach
only."* Casilla coverage against a full diseño, export layouts and formulas belong to
the rungs above. Registry build validation already accepts all 14 at their declared
rung -- the tree loads clean with ``required_coverage_gap_rows 0``.

So the standing inventory's largest group -- *"NEEDS CASILLA AUTHORING AT SCALE: 220
(7682), 763 (143), 840 (108), 222 (63), 604 x2"* -- is measuring several of these
against a bar they never asserted. m220's own prose says so plainly: *"a
scheduling/applicability-grade revision carrying declaration-header casillas only; the
money-closure casillas of the group declaration are deferred until an authoritative
Modelo 220 diseño de registro is bundled, so no casilla number is fabricated."* That is
a principled deferral with the anti-fabrication rationale recorded, not a gap.

**The reframing does not clear the set, and m220 is the proof.** Two separate brakes:

1. **Five of the 14 declare an export layout** (m165, m181, m270, m604 x2,
   ``fixed_width_export=true``). Stamping those flips their derived scope to FILING, so
   the applicability argument does not reach them at all.
2. **m220 fails at the applicability rung itself.** Its ``orden_aplicabilidad`` cites
   only ``orden-hac-657-2025:art-3``, which the legal catalogue records as the approving
   order *"for the IS declaration models for períodos impositivos iniciados en 2024"*.
   The revision is nevertheless ``2024-y-siguientes`` with ``year_from = 2024`` and no
   ``year_to``, and it carries a live ``filing_year = 2025`` deadline window. It asserts
   applicability for 2025 and beyond on the authority of an orden approving only 2024's
   models. That is not a filing-rung concern -- "to whom it applies" is exactly what the
   rung claims, so this blocks its own stamp.

The span gate reaches the same conclusion independently and in stronger terms:
*"modelo 220: NO LEGAL EVIDENCE OF REVISION RECORDED -- this modelo's entire revision
history cites only the founding orden; no amending or superseding orden is recorded
anywhere in the bundled legal catalogue"*, plus *"spans 1 corpus-evidenced re-layout,
needs 2 revisions -- 2024/2025, 4524 of 7466 shared boxes moved"*.

**And modelo 200 carries the identical shape while already stamped.**
m200/2024-y-siguientes is ``agent_reviewed`` as of 2026-08-19 with the same open-ended
``2024-y-siguientes`` id, the same ``year_from = 2024`` and no ``year_to``, the same live
2025 window, the same lone ``orden-hac-657-2025`` citation, and the same
"NO LEGAL EVIDENCE OF REVISION RECORDED" verdict from the gate. **Two revisions, one
evidence state, opposite review statuses.**

That is the third instance this campaign of the same governance pattern, and the
clearest: the pending/reviewed boundary does not track evidence. It records which
revisions someone has looked at. Driving the pending count down cannot fix that, because
the count was never measuring it -- which is why "clear the set" keeps failing to
converge on anything.

**m220 was NOT stamped.** The honest next action for the IS pair is to bound both
revisions at the year their cited orden actually approves, or cite the orden that
approves the later models -- and to revisit m200's existing stamp, which asserts a
review of an applicability claim that outruns its own evidence.

### the-missing-is-orden-is-identified-orden-hac-529-2026 | high | the gate's prescribed FIX resolves to a specific BOE disposition, verified against its own text

The previous finding left the IS pair (m200, m220) asserting open-ended applicability
from 2024 on an orden the catalogue *noted* was 2024-only. That premise is now confirmed
against the PRIMARY SOURCE rather than the note: the bundled
``orden-hac-657-2025.html`` excerpt reads **"períodos impositivos iniciados entre el 1
de enero y el 31 de diciembre de 2024"** -- an explicitly bounded range, not an
open-ended one.

The span gate's remediation for both revisions is *"acquire and cite the BOE orden that
authorises the later layout"*. **That orden exists and is identified:**

> **Orden HAC/529/2026, de 7 de mayo** -- BOE-A-2026-11583, BOE núm. 131, 29 May 2026.
> `https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-11583`

Verified against the disposition's own text, not a search summary:

| provision | verbatim |
|---|---|
| art. 1.1 | "períodos impositivos iniciados entre el 1 de enero y el 31 de diciembre de 2025" |
| art. 1.1.a).2.º | "Modelo 220: Declaración del Impuesto sobre Sociedades–Régimen de consolidación fiscal correspondiente a los grupos fiscales" |
| art. 6.3 | "el Modelo 220 ... se presentará dentro del plazo correspondiente a la declaración en régimen de tributación individual de la entidad representante del grupo fiscal o entidad cabeza de grupo" |

**Art. 1.1.a).2.º is stronger evidence than anything currently bundled for m220.** The
existing ``orden-hac-657-2025:art-3`` entry records its own limitation: *"The dedicated
«Se aprueba el modelo 220» clause of art 1 is not carried by the bundled Modelo-200
excerpt; art 3 is the bundled provision naming 220 verbatim."* The 2026 orden carries
exactly that dedicated approving clause. Whoever enrols it gets a **more specific**
proof for m220 than the 2024 chain has -- and per the standing rule, the approving
most-specific article is proof while distribution is only evidence.

Art. 6.3 also confirms no plazo correction is owed: m220's window derives from the
representative entity's individual IS plazo, which is the ``ley-27-2014:art-124``
the registry already cites.

**Deliberately NOT landed here, and why.** Enrolling this means bundling the corpus
HTML, adding the legal entries, and then bounding ``2024-y-siguientes`` on BOTH m200 and
m220 while opening 2025 revisions to carry the 2025 windows. The last part is a
structural change to a peer-stamped revision holding 3462 casillas, and bounding without
opening would strand the existing ``filing_year = 2025`` windows. That is a dedicated
action with its own verification, not a loop tick. What this iteration removes is the
research: the fix is now a lookup with a verified citation and three verbatim
provisions, rather than an open acquisition question.

### the-open-ended-on-bounded-orden-sweep-and-what-it-cannot-see | medium | the IS pair is the only confirmable instance, and 38 of 52 revisions stay unanswerable

The m200/m220 defect -- an open-ended revision asserting applicability on an orden that
approves ONE year -- was worth generalising, so it was swept across every revision whose
``period_selector`` carries ``year_from`` and no ``year_to``.

**52 open-ended revisions examined.** Results, and the detector's own coverage:

| outcome | count |
|---|---|
| every cited orden bounded to one year | 9 |
| some cited orden bounded, others not | 5 |
| **no year phrase in any cited orden's corpus** | **38** |

**The first pass found 2, the second found 9, and neither number is the answer.**
A detector keyed only on the IS scoping clause ("iniciados entre el 1 de enero y el 31
de diciembre de YYYY") returned m200 and m220 alone. Broadening it to ``ejercicio
YYYY`` and siblings raised that to 9 -- proving the narrow form had a blind spot -- and
then spot-checking the new hits showed the additions are noise:

- **m117** cites text reading *"aplicable, **por primera vez**, para las declaraciones
  correspondientes al ejercicio 2005"*. That is a FIRST-APPLICATION clause -- an
  open-ended commencement. It means the exact OPPOSITE of a bound, so an open-ended
  revision citing it is correct and the detector inverted its sense.
- **m296**'s matched "ejercicio 2005" sits inside the quoted TITLE OF A DIFFERENT ORDEN
  (IRPF/Patrimonio) embedded in the text, not in this orden's own scope clause.

m126, m128, m151, m232 share the shape of one or the other. **Only m200 and m220 carry a
genuine scoping clause that bounds the approval to a single year while the revision
claims that year and every year after.**

**The load-bearing result is the 38.** For three quarters of the open-ended population
the cited orden's bundled corpus contains no year phrase at all, so the question "does
this revision claim more years than its orden approves?" is not answered for them -- it
is unasked. A phrase-based detector cannot scale to it: the IS pair was catchable only
because that orden family states its scope in one recognisable sentence, and other
families either commence open-endedly, scope by reference, or say nothing the bundled
excerpt carries.

**Reporting "only 2" as a clean sweep would have presented a blind spot as a clean bill
of health** -- the failure mode
``test_revision_span_matches_published_designs`` records in its own docstring after a
four-digit box regex silently switched two signals off on Modelo 200: *"Agreement
between two instruments sharing one blind spot is worth nothing, and unlike a wrong
answer it offers nothing to notice."* This iteration reproduced that failure mode in a
detector written three iterations after reading the warning, and caught it only by
deliberately widening the pattern and then disbelieving the wider result.

No revision was stamped or altered on this sweep. What it establishes is narrow and
honest: the IS pair is the only confirmable instance, and the remaining 38 need a
per-family reading of how each orden states its temporal scope, not another regex.

### no-diseno-published-at-all-is-not-what-it-says | medium | three instances now; the modelo is reproduced in the orden's own anexo

The standing inventory groups m136 and m721 under *"NEEDS AEAT ACQUISITION -- no diseño
published at all"*. Checked against the approving ordenes themselves, that premise is
narrower than its wording in every case examined:

| modelo | approving clause | what it says |
|---|---|---|
| 721 | ``orden-hfp-886-2023`` art. 1 | "Se aprueba el Modelo 721 ... cuyos **diseños físicos y lógicos figuran en el anexo** de esta Orden" |
| 136 | ``orden-hap-70-2013`` art. 5 | "Se aprueba el modelo 136 ... que **se reproduce en el anexo II** de esta Orden" |
| 220 | ``orden-hac-529-2026`` art. 1.1.a).2.º | names the modelo directly (found in the previous iteration) |

In each case AEAT DID publish the design -- inside the orden that approves it. What is
missing is a bundled **diseño de registro file**, the machine-readable record layout
distributed separately on the sede for telematic filing. Those are different artefacts
and the gap between them is the whole difference between "AEAT published nothing" and
"we have not bundled the DR file".

The span gate states its own version precisely and does not overreach: for m136 it
reports *"single-year span, no design is bundled for its own filing year at all --
ABSENT, so no comparison is possible"*. **Bundled**, not published. The inventory's
paraphrase is what drifted.

This matters for triage, not just wording. "No diseño published" reads as an external
blocker nobody can clear; "no DR file bundled" is an acquisition task with a known
source, and for the applicability rung it is a stated limit rather than a blocker at
all -- which is why both revisions could be honestly reviewed this iteration.

**m136/2026 and m721/2023-y-siguientes were stamped** on verbatim corpus verification of
both applicability-rung claims, each naming this limit in its ``reviewed_by``. Census
81/0/14 -> 83/0/12 across the two iterations, 95 rows, clean load, neither flipping
scope to filing.

Worth noting for m136 specifically: ``orden-hap-70-2013`` art. 7 states the plazo AND
then continues into the vencimiento-coincidence clause. That is the orden itself
requiring the nominal-store / shift-at-read split the campaign settled on earlier -- the
convention is not merely a repo choice, it is what the source wording demands.

### the-applicability-rung-is-exempt-from-proving-its-only-claim | high | 8 revisions know no deadline and owe no reason; the filing rung, which owes one, has one every time

m840 was picked because it carries the pending set's only
``modelo_scope_classification_findings=1``. It turned out to have no ``deadline_windows``
AT ALL and no ``family_dispositions.deadline_windows`` explaining the absence -- while
declaring ``authority_grade = "applicability"``, a rung the owning enum defines as *"The
revision knows when the modelo is due and to whom it applies."*

**Measured across the tree. 81 revisions carry deadline windows; 14 do not, and the
split falls exactly on the grade line:**

| grade | count | absence reasoned |
|---|---|---|
| filing | 6 (m145, m151, m202 x2, m308, m309) | **6 of 6** |
| applicability | 8 (m036, m122, m490 x3, m576, m604, m840) | **0 of 8** |

That is backwards from the semantics. The FILING rung owes family dispositions, gets
them, and every one of its six carries a reason. The APPLICABILITY rung -- whose sole
claim is deadline knowledge -- is the one permitted to carry neither a deadline nor an
explanation. The standing rule *"a revision at APPLICABILITY grade owes no family
disposition; the filing rung does"* is what produces it: it exempts precisely the rung
whose only assertion is the thing left unevidenced.

Nothing enforces this. The tree loads clean with ``required_coverage_gap_rows 0``,
because build validation checks dispositions per rung, never whether a rung's own
defining claim is backed.

**Five of the eight are already ``agent_reviewed``** (m122, m490 x3, m576); three are
pending (m036, m604, m840). The defect does not track the review boundary -- the same
result the span sweep and the IS-pair finding produced, now on a third axis.

One of the five is this campaign's own: the m576 stamp asserts *"deadline absence is the
cited event-relative plazo, not an omission"*. That reasoning is honest and probably
correct, but it lives only in a ``reviewed_by`` prose string -- **the registry itself
records no machine-readable reason**, so nothing but that sentence distinguishes a
reasoned event-relative plazo from a plain omission.

**m840 was NOT stamped.** It fails the "when due" half of its own declared rung with no
recorded reason, which is a blocker at exactly the level it claims.

### a-shared-disposition-reason-misstates-three-of-the-nine-revisions-it-sits-on | medium | including one that contradicts its own file's header

m840's ``family_dispositions.formulas`` reason reads *"This is an informational
declaration reporting third-party data to AEAT; it computes no taxpayer liability of its
own."* The same sentence appears verbatim on **nine** revisions: m145, m189, m232 x2,
m280, m345, m347, m720, m840.

Against the registry's own ``official_name`` values it is false for at least three:

| modelo | official name | "third-party data to AEAT" |
|---|---|---|
| 347 | Declaración anual de operaciones con **terceras personas** | true |
| 145 | Comunicación de datos del **perceptor** de rentas del trabajo | own data, and filed with the PAGADOR, not AEAT |
| 720 | Bienes y derechos **situados en el extranjero** | the declarant's OWN assets |
| 840 | Declaración del IAE (alta, variación, baja) | the taxpayer's OWN activity |

On m840 it also contradicts the revision header **in the same file**, which says the IAE
communication *"is administered municipally and is not a return this application
emits"* -- not "reported to AEAT" at all.

The CONCLUSION is right everywhere: none of these compute a taxpayer liability, so the
formula family is genuinely inapplicable. What is wrong is the stated REASON, and the
reason is the part the schema requires to carry ``legal_refs`` and ``source_refs`` and
the part a reviewer reads as justification. m145 and m720 are already
``agent_reviewed``, so the misstatement sits inside reviewed revisions.

Not corrected here: the fix is prose on revisions two of which are stamped, and changing
a recorded reason changes what those stamps attest to.

### remediation-of-the-applicability-deadline-gap | resolved for the two in reach | 8 -> 6, and one loose stamp phrase corrected

The finding above recorded 8 applicability-grade revisions carrying neither a deadline
window nor a reason. Two were in this campaign's reach and both are now closed, by
authoring the reason rather than by relaxing the standard.

**m840** -- ``orden-hac-2572-2003`` apartado sexto delegates in full: *"deberá
realizarse, según se trate de declaraciones de alta, variación o baja, en los plazos
regulados en los artículos 5, 6 y 7 del Real Decreto 243/1995"*. Event-anchored to the
start, variación or cese of the actividad.

**m576** -- ``orden-eha-3851-2007`` art. 1 delegates in full: *"el lugar, plazo y forma
de presentación del modelo 576, así como su ingreso, se regirán por lo dispuesto en la
Orden EHA/1981/2005, de 21 de junio"*. Event-anchored to the matriculación or first
definitive use.

Both delegates -- RD 243/1995 and Orden EHA/1981/2005 -- are **neither enrolled nor
bundled**, so each disposition cites the delegation through its bundled article and
explicitly does not reproduce the concrete periods. Inventing windows would have meant
fabricating dates the registry cannot evidence.

**A stamp of this campaign's own was corrected in the process.** The m576 ``reviewed_by``
read *"deadline absence is the cited event-relative plazo, not an omission"*. Against
the corpus that was loose: the DELEGATING article is cited, the delegate is not, so the
plazo was not "cited" in any usable sense. The re-issued stamp quotes the earlier
phrasing and supersedes it in place rather than quietly replacing it.

That is the concrete form of the earlier concern that a reason living only in a
``reviewed_by`` string is not machine-readable: when the prose was checked against the
source, it turned out to be slightly wrong, and nothing in the registry would have
surfaced that. Both reasons now sit in ``family_dispositions.deadline_windows`` where
the loader carries them and a future reader does not depend on a sentence.

**Remaining: 6** -- m036, m122, m490 x3, m604/2021-2023. Three are stamped by another
hand (m122, m490 x3) and two are pending (m036, m604). None were touched.

### span-verdicts-split-into-absent-and-contrary-evidence | high | 69 are missing evidence; 6 are evidence AGAINST the revision, and 4 of those 6 are stamped

Earlier iterations treated "span-flagged" as one population of 74 and concluded it
cannot discriminate reviewed from pending. True, but too coarse. Parsing the 80 verdict
lines the two span gates emit splits them into classes that mean opposite things:

| class | count | what the gate found |
|---|---|---|
| **ABSENT** | 69 | no comparable bundled design falls inside the span, so NO comparison was possible |
| **CONTRARY** | 6 | bundled designs **prove** a re-layout crosses the claimed span |
| NO LEGAL EVIDENCE | 5 | the modelo's whole history cites only its founding orden |

**That distinction decides reviewability at the applicability rung.** An ABSENT verdict
is missing evidence: the revision may be right, nothing bundled can say. It is honestly
handled as a stated limit, which is how m182, m721, m136, m840 and m036 were each
stamped. A CONTRARY verdict is evidence AGAINST the revision's own structure -- the gate
asserts "needs 2 revisions" and names the boundary year. Stamping that is reviewing a
structure the corpus contradicts, not merely one it cannot confirm.

**The six with contrary evidence:**

| revision | boundary | review status |
|---|---|---|
| m184 2015-y-siguientes | 2023/2025 | agent_reviewed |
| m200 2024-y-siguientes | 2024/2025 | agent_reviewed |
| m220 2024-y-siguientes | 2024/2025 | pending |
| m322 2008-2025 | -- | agent_reviewed |
| m347 2008-y-siguientes | -- | agent_reviewed |
| m763 2011-y-siguientes | 2012/2015 | pending |

**Four of the six are already stamped.** m763's case is stark: 54 of 64 shared boxes
moved between the 2012 and 2015 designs, 63 boxes were ADDED, and the record set itself
changed -- while the revision claims 2011 onward on the single founding
``orden-eha-1881-2011`` with no amending orden recorded anywhere in the catalogue.

**m763 was NOT stamped, for consistency with the m220 refusal**, even though both its
applicability-rung claims verify cleanly: art. 4 reads *"será trimestral y se efectuará
durante el mes siguiente a la finalización de cada trimestre natural del año"* and all
eight declared windows reproduce it exactly, with 4T rolling into January. Two of those
closing dates -- 2026-01-31 and 2027-01-31 -- fall on a Saturday and a Sunday and are
stored NOMINAL, which demonstrates the nominal-store convention is actively honoured
here rather than accidentally satisfied.

What blocks m763 is not its plazo or its approving clause but the contested span. The
reviewable half being sound is exactly why the class distinction matters: without it,
this revision looks stampable.

**Consequence for the remaining pending set:** of the 10 still pending, the two carrying
contrary evidence (m220, m763) are structurally contested and should be split or have
their amending orden cited before review, not stamped with a limit. The rest are ABSENT
cases where a stated limit is the honest treatment.

### m185-2003-2025-deadline-windows-cite-the-approving-apartado-not-the-plazo | medium | the file's own two comments contradict each other about which orden grounds them

m185/2003-2025 carries 12 monthly deadline windows closing on the 10th of the following
month. The dates are RIGHT. Their grounding is not.

**Each window declares** ``legal_refs = ["orden-hac-96-2003:art-1", "ley-58-2003:art-93"]``.
That entry is apartado **Primero**, whose bundled excerpt is titled *"Aprobación de los
diseños físicos y lógicos, modelo 185"* -- it approves the record designs and says nothing
about timing.

**The provision that establishes the plazo is apartado Tercero**, present in the bundled
whole-document file and not cited anywhere in this revision:

> *"Tercero. Lugar y plazo de presentación de la información mensual. La información
> mensual, modelo 185 ... se presentará ante el Departamento de Informática Tributaria de
> la Agencia Estatal de Administración Tributaria **en el plazo de los diez días naturales
> siguientes a la finalización del mes** a que se refiera la información."*

That is exactly the rule the windows implement, so this is a citation defect rather than
a date defect -- but the standing requirement is that a deadline window declare the
specific binding provision that ESTABLISHES it, and an approval clause does not.

**The windows file contradicts itself in two adjacent comments.** The first records the
move correctly: *"these 12 windows all carry filing_year=2025, which orden-hac-1197-2025
does not govern (it enters into force 2026-01-01...). The real governing instrument for
2025 and earlier is orden-hac-96-2003."* The second, immediately below, still says:
*"Modelo 185 monthly deadline windows, grounded in orden-hac-1197-2025 art 4."* The move
updated the top note and left the original grounding comment naming the very orden the
top note had just excluded.

**m185/2003-2025 was NOT stamped.** Its "when due" evidence points at a provision that
does not establish the deadline, which is a defect at exactly the half of the
applicability rung this review would be attesting to. The sibling m185/2025-y-siguientes
WAS stamped in the previous iteration: it cites ``orden-hac-1197-2025:art-4``, which is
the genuine plazo article for the years it covers.

The remediation is bounded and the evidence is already bundled: carve an apartado-Tercero
excerpt following the documented convention of ``orden-hac-96-2003-primero.html``, enrol
it, repoint the 12 windows, and correct the stale comment. Not landed here -- carving a
corpus excerpt correctly requires matching that file's header convention and verifying
the rendered text byte for byte, which is its own verification job.

**A claim was investigated and DROPPED rather than reported:** that
``orden-hac-96-2003.html`` mis-declares its encoding. One reading suggested it decoded
legibly as latin-1 and produced replacement characters as UTF-8; a sweep of all 462
bundled corpus HTML files then found **zero** that fail UTF-8 decoding, which
contradicts it. The two observations were not reconciled, so no encoding finding is
asserted here -- only the note that anyone carving an excerpt from that file should read
the result back before trusting it.

### the-export-frontier-measured-and-a-gap-that-is-honest | medium | 3 of 5 tile completely; m604's 13 uncovered bytes are a retraction's trace, not a defect

The remaining pending set narrowed to seven: two carrying contrary span evidence (m220,
m763) and five that declare a fixed-width export layout (m165, m181, m270, m604 x2).
Stamping the latter flips their derived scope to FILING -- the coverage module states it
plainly: *"Agent review is sufficient to reach the filing fold."* So the frontier was
measured before being pushed at.

**What the flip does and does not do.** The four evidence gates run identically at either
scope; ``authority_scope`` only LABELS whether the resulting ledger rests on proven
filing authority, and ``authority_fallback_reason`` exists precisely so a reviewed
revision that still cannot produce a filing-grade snapshot is distinguishable from one
nobody reviewed. All five carry ``construct_evidence_rows = 0``, so no gap would be
relabelled from inspection to filing; what changes is the ledger asserting
``filing_eligible``.

**A real asymmetry in the loader.** ``_verify_record_offsets`` rejects OVERLAPPING byte
ranges and nothing else. It never checks whether a record's extent is fully tiled, so a
fixed-width layout can pass registry validation with bytes no casilla writes. That is
why the m576 stamp had to verify "no gap or overlap" by hand.

**Measured across the five, per record extent:**

| revision | records | extent | uncovered |
|---|---|---|---|
| m165 2013-y-siguientes | 2 | 1000 | **0** |
| m181 2009-y-siguientes | 2 | 1000 | **0** |
| m270 2013-y-siguientes | 2 | 1000 | **0** |
| m604 2021-2023 | 2 | 1228 | 13 |
| m604 2024-y-siguientes | 3 | 2028 | 13 |

Three tile completely. m604's 13 bytes sit in record ``604-00`` as two runs -- 93..96
(4 bytes) and 101..109 (9 bytes) -- both bounded by fields named ``reservado-54``,
``reservado-97`` and ``reservado-110``.

**Those gaps are honest, and the evidence is in the history.** Commit `3ff1651215`,
*"retract fabricated filler declarations for EEDD/developer-identity slots across
m122/131/156/180/216/270/390/604 export layouts"*, removed
``modelo-604-604-00-presenter-tax-id`` at **offset 101** -- exactly where the nine-byte
run begins, and exactly a NIF's width. The gap is the visible trace of somebody
declining to invent a field AEAT's diseño does not evidence. Declaring those bytes now
would re-fabricate precisely what was retracted.

**Which makes the loader's silence on gaps arguably correct rather than an oversight.**
A gap can mean "nobody finished the layout" or it can mean "the evidence for these bytes
does not exist and nothing was invented". No byte-extent check can tell those apart, so
gating on full tiling would punish the honest case and reward fabrication. The
measurement belongs in review, where a human or an agent can read the history -- which
is what happened here.

Nothing was stamped this iteration. m165, m181 and m270 now have their byte-extent half
verified clean, which is the expensive part of a filing-scope review.

### ten-windows-store-a-pre-shifted-close-and-m345-regressed | high | the defect recorded as corrected on m345 is present again

Reviewing m165 for a filing-scope stamp surfaced its middle window closing **2026-02-02**
while its siblings close 2025-01-31 and 2027-01-31. ``orden-hap-2455-2013`` art. 4 states
the nominal plazo verbatim: *"La presentación de esta declaración informativa se realizará
en el mes de enero de cada año"*. The nominal close is 31 January every year;
2026-01-31 is a Saturday, and 2026-02-02 is its operational shift -- a stored pre-shift,
which the standing rule forbids outright.

**The file proves its own convention against itself.** Its 2026 window stores
**2027-01-31, a Sunday**, nominally. Only the middle window was shifted, and only it
carried an extra ``source_ref`` naming AEAT's Calendario del Contribuyente -- which
publishes the OPERATIONAL date. Grounding in the calendar is correct only where the
orden is silent on its plazo. Here it is not silent.

**Round-trip proof that the pre-shift was unnecessary as well as wrong:**
``shift_deadline(2026-01-31, modelo="165")`` returns ``adjusted_close_date=2026-02-02,
shifted=True, shift_reason='sabado'``. Storing the nominal date loses nothing -- the date
AEAT publishes is derived WITH its reason instead of stored without one.

**Measured across the tree: TEN revisions store ``closes_on = 2026-02-02``.** Each
window's cited articles were checked against the bundled corpus for a stated January
close:

| verdict | revisions |
|---|---|
| orden STATES a January plazo -- pre-shifted | m165 (fixed), m180, m181, m190, m193, m270, **m345** |
| no cited article states a January close -- needs separate assessment | m194, m296, m490 |

m194 deserves its own note: its orden states *1-20 enero* (papel) and *1 enero-20
febrero* (soporte), so 2026-02-02 matches neither nominal range.

**m345 is the sharp part.** The standing record names "200, 220 and 345" as the three
revisions that stored pre-shifted dates and *were corrected*. m345 is pre-shifted again
today. Either the correction never covered this window, or a later sweep reintroduced
it -- the 2026-02-02 dates trace to `d96f06910b`, a deadline-window sweep across the
informativa modelos. A defect recorded as closed is present in shipped tax data.

Only m165 was fixed: it was the revision under review and is unstamped. The other six
pre-shifted windows sit on stamped revisions, where changing the data changes what the
stamp attests to, and are left as a single clean follow-up with the evidence above.

### the-pre-shift-argument-measured-and-refuted | high | the stored shift protects nobody and fabricates a false reason

m345 was storing a pre-shifted close again, after being listed in the standing record as
one of three revisions corrected for exactly that. Unlike m165, m181 and m270 -- where
the shifted date was a sweep artefact -- this one carried a **reasoned argument** in the
file:

> *"It was declared 2026-01-31, which is the rule's date and a SATURDAY. AEAT's published
> calendar for 2026 lists 'Declaración anual 2025: 345' under the heading 'Hasta el 2 de
> febrero' ... so the rule-derived date closes the window two days early and would
> present a filer with a deadline that has not arrived."*

That is a real concern and deserved measuring rather than reverting. **It does not hold.**
``application/overview/_calendar.py`` passes ``closes_on`` through ``shift_deadline`` and
surfaces ``adjusted_close_date``, so the operator sees 2 February either way. Measured
both ways for modelo 345:

| stored | operator sees | shifted | reason |
|---|---|---|---|
| ``2026-01-31`` (nominal) | 2026-02-02 | True | **``sabado``** |
| ``2026-02-02`` (pre-shifted) | 2026-02-02 | False | ``business_day`` |

**Same date to the filer.** What the pre-shifted form adds is two false statements --
that no shift occurred, and that 2 February is the ordinary business-day deadline -- and
it destroys the statutory 31 January entirely. It protects nobody and fabricates
provenance.

This is the strongest available justification for the nominal-store rule, and it is
sharper than the rule's own statement: the rule says *store nominal*, but this measures
**what is lost by not doing so**, which is the reason rather than the date.

Corrected to 2026-01-31 on ``orden-hfp-823-2022`` art. 4 verbatim -- *"el plazo de
presentación del modelo 345 será el comprendido entre el 1 y el 31 de enero de cada
año"* -- with the calendar ``source_ref`` dropped, since the orden is not silent here.
The original comment was **replaced by the measurement rather than deleted**, so the next
reader meets the refutation and not the argument.

m345 has a SINGLE window and no sibling to expose the shift by contrast, which is
plausibly why the regression survived where m165's three-window file gave itself away.

Its stamp was left untouched: ``reviewed_by`` is the bare token
``agent-prepared-pending-operator``, which asserts nothing about deadlines that the
correction could falsify -- itself worth noting, since a stamp carrying no scope
statement records only that somebody looked.

**Pre-shift remediation: 4 of 7** (m165, m181, m270, m345). m180, m190 and m193 remain,
all on stamped revisions.

### m190-and-m193-cite-a-superseded-twenty-day-plazo | high | the date is pre-shifted AND the article establishing it is not cited

Completing the pre-shift remediation meant checking m180, m190 and m193. All three carry
the bare stamp token ``agent-prepared-pending-operator`` -- no scope statement -- so
correcting their data would falsify nothing. But reading their cited plazo articles
verbatim, rather than trusting the earlier regex sweep, changed the picture.

**The earlier sweep over-claimed, and this corrects it.** Iteration 30 classified these
as simply "pre-shifted" on a regex that matched *"mes de enero"* anywhere in the cited
corpus. Read properly:

| revision | cited article | what it actually says |
|---|---|---|
| m190 | ``orden-eha-3127-2009:art-1`` | *"se realizará en los **primeros veinte días naturales** del mes de enero de cada año"* |
| m190 | ``rd-439-2007:art-108`` | *"deberá presentar en los **primeros veinte días naturales** del mes de enero"* |
| m193 | ``orden-eha-3377-2011:art-1`` | *"durante los **veinte primeros días naturales** del mes de enero siguiente"* |
| m180 | ``orden-hfp-1284-2023:art-7`` | entry-into-force text about a FEBRUARY autoliquidación -- not m180's plazo at all |

Every one of those states a **20 January** close. The windows store 2026-02-02.

**The stored date is nevertheless right, and AEAT's own bundled calendar proves it.**
``calendario-contribuyente-2026-hasta-2-febrero.html`` lists, under that heading:
*"Resumen anual 2025: 180, 188, 190, 193, 193-S, 194, 196, 270"*. An operational date of
2 February 2026 is the Saturday shift of a **31 January** nominal; a 20 January nominal
falls on a Tuesday and would need no shift at all, and AEAT would list these under a
January heading.

So there are TWO defects stacked, not one:

1. The window stores the pre-shifted 2026-02-02 instead of the nominal 2026-01-31.
2. The article cited as establishing that plazo states twenty days and is **superseded**.
   The provision that actually establishes the current 31-January close is cited nowhere
   in these revisions.

**Nothing was changed.** Fixing only the date would leave a window storing 31 January
while its own ``legal_refs`` state 20 January -- a visible contradiction, and the
grounding rule requires the provision that establishes the value, which is not in the
bundled corpus. Resolving it needs the amending orden acquired and enrolled, exactly as
the m185/2003-2025 case did, and that is a dedicated action rather than a loop tick.

m180 needs its own reading: the article cited for its plazo is about something else
entirely, so its 31-January nominal is currently ungrounded rather than mis-grounded.

**Pre-shift remediation stands at 4 of 7** (m165, m181, m270, m345 -- each of which cited
an article genuinely stating its January close, verified verbatim before the change). The
remaining three are now known to need acquisition first, which is a better answer than
the count suggested.

### CORRECTION-the-m190-m193-plazo-is-not-superseded-it-is-mis-cited | high | supersedes the previous finding; the defect is narrower and different in kind

**The previous finding on this page is wrong and this supersedes it.** It reported that
m190 and m193 cite a *superseded* twenty-day plazo. They do not. The twenty-day rule and
the thirty-one-day rule are **both in the same article of the same orden**, and the
earlier regex stopped at the first sentence.

``orden-eha-3127-2009`` **artículo 5** reads in full in the bundled consolidated text:

> *"la presentación del resumen anual de retenciones e ingresos a cuenta, modelo 190, se
> realizará en los primeros veinte días naturales del mes de enero de cada año ...
> **No obstante, el plazo de presentación será el comprendido entre el 1 de enero y el 31
> de enero** del año siguiente ... cuando la declaración se presente de alguna de las
> siguientes formas: a) En impreso generado mediante ... el módulo de impresión
> desarrollado por la Agencia Estatal de Administración Tributaria ... b) En soporte
> directamente legible por ordenador. c) Por [vía telemática] ..."*

``orden-eha-3377-2011`` artículo 5 carries the same construction for m193: *"cuando la
presentación se realice por vía telemática ... la presentación se realizará entre el 1 de
enero y el 31 de enero del año siguiente"*.

The twenty-day rule is the base case; the thirty-one-day rule is the exception, and its
conditions cover **every modern filing form**. So the 31-January nominal these windows
imply is correct and IS established by the cited orden. AEAT's bundled calendar agrees,
listing both modelos under "hasta el 2 de febrero" for 2026.

**The real defect is narrower and of a different kind: the wrong article is cited.**

| revision | cites | plazo actually in |
|---|---|---|
| m190 2025-y-siguientes | ``orden-eha-3127-2009:art-1`` | **artículo 5** |
| m193 2025-y-siguientes | ``orden-eha-3377-2011:art-1`` | **artículo 5** |

In both cases artículo 1 is the approving clause and states no timing -- the identical
shape already found and fixed on m185/2003-2025, where the windows cited the approving
apartado rather than the one establishing the plazo. Neither ``art-5`` is enrolled in the
legal catalogue.

So these windows carry **two** defects after all, but not the two previously reported:
the stored date is pre-shifted (2026-02-02 for a 31 January nominal), and the article
cited as grounding it does not contain the plazo. Both are fixable without acquisition,
since the text is already bundled -- unlike the acquisition case the superseded reading
implied.

**m180 is unaffected by this correction.** ``orden-hfp-1284-2023`` contains no
"1 de enero y el 31 de enero" clause at all, so its 31-January nominal remains
ungrounded rather than mis-cited, and needs its own reading.

**Nothing was changed this iteration.** The remediation is now fully specified: carve
artículo 5 excerpts for both ordenes following the ``orden-hac-96-2003-tercero.html``
precedent, generate their sidecars through ``dev.docs.preprocess.write_sidecar``, enrol
``orden-eha-3127-2009:art-5`` and ``orden-eha-3377-2011:art-5``, repoint the windows, and
de-shift both dates to 2026-01-31.

This is the sixth time in this campaign that re-checking overturned a plausible earlier
conclusion, and the second time the overturned conclusion was one already written into
this document.

### the-approving-clause-habit-eight-of-ten-windows-corrected | high | four windows cited the approving article; the establishing text was bundled every time

The ten windows storing ``closes_on = 2026-02-02`` are now resolved to eight corrections
and two open cases, and the corrections fall into two distinct kinds.

**Kind one -- date only.** m165, m181, m270, m345 and m490 each already cited an article
that genuinely states its plazo; only the stored date was pre-shifted. m490 is the
clearest: ``orden-hac-590-2021`` art. 3 says *"durante el mes siguiente al
correspondiente periodo trimestral natural"*, and seven of its eight windows close on
the following month-end -- including 4T 2026 at **2027-01-31, a Sunday, stored
unshifted**. Only 4T 2025 deviated.

**Kind two -- the approving-clause habit.** Four windows cited the article that APPROVES
the modelo instead of the one that establishes its plazo, and in every case the correct
text was **already bundled and merely uncited**:

| revision | cited (approval) | plazo actually in |
|---|---|---|
| m185 2003-2025 | apartado Primero | apartado **Tercero** |
| m190 2025-y-siguientes | artículo 1 | artículo **5** |
| m193 2025-y-siguientes | artículo 1 | artículo **5** |
| m296 2024-y-siguientes | artículo 6 | artículo **11** |

Four instances of one shape is a systematic authoring habit, not coincidence. Each was
repaired the same way: carve a single-provision excerpt following the
``orden-hac-96-2003-primero.html`` convention, generate the sidecar pair through
``dev.docs.preprocess.write_sidecar`` (the registry refuses a legal reference whose
sidecar is missing), enrol the article with a ``required_text`` drawn from the source,
repoint the window, de-shift the date. ``verify_legal_reference`` passes on all four.

m190 and m193 additionally tripped the construct-covers-window containment rule; m296
did not. Worth knowing that the rule fires per-revision rather than universally.

**Two remain open, and they are genuinely different from the eight.**

**m180** is the only one whose plazo text is NOT bundled anywhere. Its window cites
``orden-hfp-1284-2023:art-7`` (entry-into-force text about a February autoliquidación),
``orden-hap-1732-2014:art-2`` (a general enabling clause) and ``rd-439-2007:art-100`` --
none states a plazo. The base instrument is the **Orden de 20 de noviembre de 2000**
(BOE-A-2000-21430), whose anexo VI carries m180's diseños; only a modelo-115 excerpt of
that orden is bundled. It has since been amended by **Orden HFP/1351/2021**
(BOE-A-2021-20004). The date was NOT changed: a search summary reports the original 2000
text as 1 January to 20 February for telematic filing, but that predates the amendments,
and setting a filing deadline from a search summary is exactly the fabrication this
campaign refuses. What is removed is the research -- the acquisition target is now named.

**m194** stores 2026-02-02 while its orden states *1-20 enero* (papel) and *1 enero-20
febrero* (soporte). The stored date matches **neither**, so this is not a pre-shift of
either nominal and needs its own ruling rather than a mechanical correction.

### CLOSED-the-pre-shifted-deadline-sweep-ten-of-ten | resolved | one symptom, three root causes, and a habit worth naming

All ten windows that stored ``closes_on = 2026-02-02`` are corrected. Verified by
re-scan: **no window in the tree stores that date any more.** The symptom was uniform;
the causes were not.

| root cause | revisions | what was wrong |
|---|---|---|
| date only | m165, m181, m270, m345, m490 | the cited article genuinely states the plazo; only the stored date was pre-shifted |
| **approving-clause habit** | m185, m190, m193, m296 | the window cited the article that APPROVES the modelo; the establishing text was bundled and uncited |
| orden superseded in practice | m194, m180 | the orden's own ranges no longer govern; AEAT's calendar is the only statement, and the NOMINAL behind it was not stored |

**The middle group is the finding worth carrying.** Counting m194, **five** windows cited
an approving clause as the grounding for a deadline. In four of those the correct
provision was already on disk, merely uncited -- apartado Tercero, artículo 5 twice,
artículo 11. That is a systematic authoring habit, not five coincidences: whoever
authored these reached for the article that names the modelo rather than the one that
states the timing.

**The third group is the subtler one.** m194 and m180 each carry an orden stating plazos
(20 days for papel, 1 enero-20 febrero for soporte and telemática) that AEAT no longer
applies -- its calendar publishes 2 February 2026, the Saturday shift of 31 January,
matching neither. Calendar grounding is what the standing rule permits there, but the
calendar publishes the OPERATIONAL date, and storing that destroys the reason. Both now
store the nominal with the full reasoning recorded in the window file, including the
explicit statement that no article is cited as establishing the plazo because none in
the bundled corpus does.

**Method notes worth keeping.**

- The repair recipe for the approving-clause group is fixed and repeatable: carve a
  single-provision excerpt on the ``orden-hac-96-2003-primero.html`` convention,
  generate the sidecar pair through ``dev.docs.preprocess.write_sidecar`` (the registry
  REFUSES a legal reference whose extracted sidecar is missing -- that refusal is how the
  requirement was discovered), enrol with a ``required_text`` drawn from the source,
  repoint, de-shift. ``verify_legal_reference`` passed on every one.
- The construct-covers-window containment rule fires per-revision, not universally: m190
  and m193 needed their construct updated, m296 did not.
- m180 splits its windows one file per year while every other modelo in the sweep used a
  single file. An assertion caught the wrong file being targeted; without it the edit
  would have silently no-opped on the wrong year.
- Two of this campaign's own artefacts were corrected in the process: the m576 stamp's
  "cited event-relative plazo" wording, and the m194 stamp, which asserted a nominal
  1-31 enero window while the data stored 2 February.

### three-filing-scope-stamps-sit-on-revisions-a-gate-calls-uncoverable | high | self-implicating; the limit was stated but the scope flip asserts past it

A full registry-suite run after the deadline sweep: **19 failed, 5089 passed** in 4m25s.
That is far below the 113 the standing notes record, so that baseline is stale. Neither
failure nearest this campaign's changes was caused by them -- m136's arithmetic test
fails because the revision declares no export layout (a pre-existing condition this
campaign's m136 stamp records as NOT CLAIMED), and the layout-coverage gate fails on
properties of the revision data that stamping does not touch.

**But that second gate names three revisions this campaign moved to ``filing`` scope.**
``test_every_claimed_filing_year_is_covered_by_its_declared_layout_design`` reports 14
revisions, including:

| revision | claims | declared design applies from |
|---|---|---|
| m165 2013-y-siguientes | 2013-2024, **12 years** | ``aeat-dr-165-2026`` |
| m181 2009-y-siguientes | 2009-2021, **13 years** | ``aeat-dr-181-2022`` |
| m270 2013-y-siguientes | 2013-2022, **10 years** | ``aeat-dr-270-2023`` |

Its message is unambiguous: *"these revisions claim filing years their own declared
layout design does not cover, so the registry itself states that those filings are
written at a layout AEAT did not publish for them."*

**Each stamp states this.** m165's ``reviewed_by`` says the layout "is evidenced for 2026
and NOT for filing years 2013 through 2025"; m181 and m270 carry the equivalent. So the
prose is honest and the reader is warned.

**The scope flip is not prose.** Stamping moved each from ``inspection_only`` to
``filing``, and ``filing_eligible`` is a machine-readable assertion that the ledger rests
on filing-grade authority. A stated limit in a ``reviewed_by`` string does not qualify a
boolean that downstream code reads. This is the iteration-13 pattern turned on this
campaign's own work: there, 60 stamped revisions carried a gate flag none of them named;
here the flag is named, but the scope still asserts past it.

**Recorded rather than silently resolved.** Reverting three stamps to ``pending_review``
would drop their scope statements, which are the most detailed in the corpus and took
three iterations each to establish. Leaving them is defensible only if
``filing_eligible`` has no consumer that would act on it for a pre-design year. That
question was not answered here and should be, before more revisions with multi-year
layout gaps are moved across the same boundary.

The conservative reading is that a revision whose declared design post-dates most of its
claimed years should be SPLIT at the design boundary rather than stamped with a caveat --
which is what the gate itself says, and what the span gate says separately for the
contrary-evidence class. The three stamps stand for now, with this recorded against them.

### RESOLVED-filing_eligible-has-no-runtime-consumer | resolved | the scope flip reclassifies gaps into the stricter bucket, it authorises nothing

The previous finding left one question open: whether ``filing_eligible`` has a consumer
that would act on it for a filing year the declared design does not cover. It was worth
asking and the answer is no. This corrects that finding's implication.

**Every consumer is in the reporting layer.** ``filing_eligible`` is read only in
``application/registry/_conformance.py`` and ``domain/calculations/registry/_coverage.py``.
No filing, draft or export path reads it -- those go through the export completeness
gate and ``ValidatedRegistryAuthority``, which are separate mechanisms. Stamping a
revision does not authorise producing a filing for any year.

**And the polarity runs the safe way.** The two properties are complements over the same
set:

```
filing_gaps     = gaps if     filing_eligible else ()
inspection_gaps = gaps if not filing_eligible else ()
```

The gaps are RECLASSIFIED, never hidden and never invented. Moving a revision to
``filing`` shifts its gaps out of the inspection bucket and into the filing bucket --
the stricter, more visible one. A stamp therefore subjects a revision to a harsher
reading of the same evidence, which is the opposite of the risk the previous finding
implied.

m165, m181 and m270 each carry ``construct_evidence_rows = 0`` and
``required_coverage_gap_rows`` stayed 0 tree-wide across all three stamps, so there were
no gaps to reclassify in either direction.

**What remains genuinely open is the DATA, not the review status.**
``test_every_claimed_filing_year_is_covered_by_its_declared_layout_design`` fails on 14
revisions because their declared design post-dates most of their claimed years. That
failure is a property of the registry data and stands whether a revision is stamped or
pending -- it was failing on all 14 before any of this campaign's stamps and still is.
The three stamps neither caused nor worsened it; they simply state it where the other
eleven do not.

The conservative remediation named earlier -- SPLIT such a revision at its design
boundary rather than let one revision claim years two layouts cover -- is still the right
answer, and it is now clear that it is a data fix owed by whoever authors those
revisions, not a reason to withhold or reverse a review.

Seventh time in this campaign that re-checking changed a conclusion, and the first where
it exonerated the work rather than implicating it.

### m604-is-the-contrary-class-so-it-cannot-be-stamped-with-a-caveat | resolved question | the campaign's own taxonomy answers it

With ``filing_eligible`` shown to authorise nothing at runtime, the natural next question
was whether m604 could be stamped the way m165, m181 and m270 were -- with its defect
stated in ``reviewed_by`` rather than left only in this audit, since a reviewed_by
survives peer capture where a commit message does not.

The answer is no, and this campaign's own ABSENT/CONTRARY taxonomy is what settles it.

**The distinction that decides it.** m165's declared layout is CORRECT for the year it
covers; it simply does not extend back over the revision's earlier claimed years. That
is missing evidence -- the ABSENT class -- and a stated limit is the honest treatment.
m604's layout is present for every year it claims and its numbering **contradicts** the
official one. Re-measured this iteration: the 2024 diseño prints **37 distinct box
numbers**, 01 through 37, and the registry's 122 casillas across both revisions declare
**zero** numeric ``number`` values. The official layout numbers its boxes; the registry
uses none of them.

That is the CONTRARY class, the same class as m220 and m763, where the corpus states
something the revision denies. A caveat cannot carry that: stamping m604 would move it
to ``filing`` scope -- it declares ``fixed_width_export = true`` -- and the export rule
gates the casilla SET **and its numbering** against the official layout. Asserting
filing-grade authority over a layout whose numbering contradicts AEAT's is not something
a ``reviewed_by`` sentence qualifies.

**So all four remaining pending revisions are correctly blocked, and for two distinct
reasons in the same class:**

| revision | contrary evidence |
|---|---|
| m604 2021-2023 | 0 of 43 casillas carry an official box number |
| m604 2024-y-siguientes | 0 of 79 casillas carry an official box number |
| m220 2024-y-siguientes | designs prove a 2024/2025 re-layout inside the claimed span |
| m763 2011-y-siguientes | designs prove a 2012/2015 re-layout; 54 of 64 boxes moved |

**The pending set is at its floor for this campaign.** Every one of the four needs a DATA
change -- casilla re-numbering for m604, a revision split or an amending-orden citation
for m220 and m763 -- not a review. Neither is work a review iteration should improvise on
someone else's freshly authored revisions, and neither is blocked on anything this
campaign can measure further.

m604 has been static since `11ec8d3bcc`, so the earlier "do not barge, it is in flight"
reasoning has expired; what remains is that re-numbering 122 casillas is an authoring
task with its own verification, and the finding is already recorded here and in the
repeated-box hazard note carried on m222's stamp.

### m604-2021-2023-is-an-omission-not-a-reasoned-absence | medium | the distinction that decides whether a disposition can be authored at all

The m604 re-numbering unblocked ``2024-y-siguientes``, which was reviewed and stamped.
Its sibling ``2021-2023`` was re-numbered too -- coverage 0 of 7 to **7 of 7** -- but it
cannot follow, and the reason sharpens the earlier deadline-absence finding.

m604/2021-2023 has **no ``deadline_windows`` directory and no
``family_dispositions.deadline_windows``**, while declaring ``authority_grade =
"applicability"`` -- the rung defined as knowing when the modelo is due. That is the same
surface defect m840, m576 and m036 carried, and each of those was closed by authoring the
reason. **This one cannot be, and that is the finding.**

**In every case closed earlier, the LAW made a calendar window impossible.** m840's
plazo is event-anchored to the alta, variación or cese; m576's to the matriculación or
first definitive use; m036's to the alta, modificación or baja event. No recurring window
exists to declare, so "none is fabricated" is a true and complete reason.

**m604's plazo is the opposite shape.** ``orden-hac-510-2021`` art. 3 states a fixed
monthly calendar rule -- *"entre los días diez y veinte del mes siguiente al
correspondiente periodo de liquidación mensual"* -- and the sibling revision enumerates
twelve windows from exactly that rule. Windows for 2021-2023 are therefore perfectly
constructible. Their absence is an **omission**, not a consequence of the law.

**So no honest disposition can be written here.** A reason would have to assert why a
constructible window was not constructed, and the two candidates are not
distinguishable from the data: either the application's supported filing range begins
later -- the sibling declares windows only for ``filing_year = 2025``, which hints at it
-- or nobody authored them. The first is a scope policy this review cannot verify; the
second is not a reason at all. Writing either down would be inventing a rationale.

**And enumerating the 36 windows is equally a judgement, not a mechanical fix.** The rule
is known and the dates would be derivable, but doing so would give a closed 2021-2023
span three years of windows while the live sibling carries one year. That deviates from
the modelo's own convention, and which convention is right is a product decision.

**m604/2021-2023 therefore stays pending**, and for a reason no further measurement will
resolve. It fails the "when due" half of the rung it declares; the remedy is a choice
between enumerating historical windows and declaring a scoped support range, and that
choice belongs to whoever owns the modelo's filing-year scope.

This refines the earlier finding usefully: an applicability-grade revision with no
deadline windows is not one defect but two. Where the law is event-anchored the absence
is reasonable and a disposition closes it. Where the law states a calendar rule the
absence is a gap, and only data or a policy statement closes it.

### m763-spans-two-layout-amendments-not-one-and-cites-neither | high | the acquisition target is now named, as it was for m220

The span gate reports m763/2011-y-siguientes as CONTRARY class: *"spans 1
corpus-evidenced re-layout(s), needs 2 revisions -- 2012/2015 (54 of 64 shared boxes
moved ... 63 added ... RECORD SET CHANGED)"*, alongside *"NO LEGAL EVIDENCE OF REVISION
RECORDED -- this modelo's entire revision history cites only the founding orden
(['orden-eha-1881-2011'])"*.

The consolidated amendment history of that orden names the missing instruments, and
there are **two**, not one:

| orden | BOE | what it did |
|---|---|---|
| **Orden HAP/2373/2014**, de 9 de diciembre | BOE-A-2014-13180 | *"Se sustituye por la disposición final 1"*; effective *"para los periodos de liquidación que se inicien a partir del 1 de enero de 2015"* |
| **Orden HAC/1363/2018**, de 28 de noviembre | BOE-A-2018-17602 | *"Se sustituye por el art. único"* -- replaces Anexo I with new registro designs; *"será de aplicación para las autoliquidaciones correspondientes al cuarto trimestre del año 2018 y siguientes"* |

The first is exactly the 2012/2015 boundary the gate detected. **The second the gate did
not detect at all** -- only two designs are bundled, so a 2018 re-layout leaves no
corpus trace to compare. So the revision spans at least TWO layout-affecting amendments
while citing only its founding orden, and the gate's "needs 2 revisions" is a floor
rather than the answer: on this evidence it needs three, split at 2015 and at Q4 2018.

**A near-miss worth recording.** A search result described BOE-A-2014-13180 as an orden
about modelos 390, 303 and 322 -- which it is. It is an omnibus instrument that ALSO
amends m763's disposición final, and only the consolidated amendment history of
EHA/1881/2011 shows that. Attributing it from the search snippet would have missed the
m763 connection entirely, and citing the wrong instrument as a modelo's layout authority
is exactly the class of error this campaign has been correcting.

**What this changes.** m763 remains unstampable and stays pending -- contrary evidence,
unchanged. What is removed is the research: the remediation is to acquire and cite
BOE-A-2014-13180 and BOE-A-2018-17602, then split ``2011-y-siguientes`` at 2015 and at
Q4 2018, and it is now a specified task rather than an open question. That is the same
service performed for m220, whose missing orden was identified earlier as
Orden HAC/529/2026 (BOE-A-2026-11583).

**Both contrary-class blockers are now named instruments rather than unknowns.** Neither
is work a review iteration should improvise: each is a revision split plus a legal
enrolment, with its own verification.

### bundling-new-corpus-text-from-a-fetch-needs-operator-authorization | boundary | why naming the orden is the correct stopping point

m763's span gate names two fixes, and the first looked landable: *"acquire and cite the
BOE orden that authorises the later layout"*. The instruments were identified in the
previous iteration, and the enrolment recipe is by now routine -- carve an excerpt,
generate sidecars through ``dev.docs.preprocess.write_sidecar``, enrol with a
``required_text``, repoint. So the question was why not simply do it.

**Because every enrolment this campaign performed carved from text ALREADY BUNDLED.**
``orden-hac-96-2003-tercero``, ``orden-eha-3127-2009-art-5``,
``orden-eha-3377-2011-art-5`` and ``orden-eha-3290-2008-art-11`` were each sliced out of
a consolidated file already on disk, and each was read back and verified against the
source bytes. Neither of m763's amending ordenes is bundled at all.

Bundling them means transcribing BOE text obtained through a web fetch. **The 22 bundled
files that were obtained that way all record the same provenance:**

> *"Provenance: verbatim excerpt transcribed from the BOE consolidated text (...) via
> agent web fetch during the obligation-enrollment campaign, **under explicit operator
> authorization**. Pending operator re-verification."*

That note is not decoration. It records that fetch-sourced legal text entered the corpus
under an authorization this loop does not carry, and that it remains pending operator
re-verification even so. The standing rule is blunt about the risk it manages: an
excerpt authored from a secondary source once carried a fabricated year list while the
repository already bundled the authoritative text, and its ``required_text`` cross-check
passed because the same author wrote both halves.

A fetch result is a model's rendering of a page, not the page. This iteration's own fetch
returned the m763 2018 disposición final complete and verbatim -- *"será de aplicación
para las autoliquidaciones correspondientes al cuarto trimestre del año 2018 y
siguientes"* -- but rendered the artículo único with an ellipsis through the middle of
the operative clause. Carving a corpus excerpt from that would bundle a gap and then
validate it against a phrase chosen to match what survived.

**So naming the instrument is the correct stopping point, not a shortfall.** It is what
iterations 16 (m220 -> Orden HAC/529/2026), 41 (m180 -> BOE-A-2000-21430) and 50 (m763 ->
BOE-A-2014-13180 and BOE-A-2018-17602) each did, and the reason is the same in all three:
the research is removable by an agent, the acquisition is not.

What an operator-authorized acquisition would need to add for m763 is now fully
specified: both ordenes bundled with the standard provenance note, ``artículo único`` and
``disposición final única`` enrolled from HAC/1363/2018, the ``disposición final 1``
provision from HAP/2373/2014, then the revision split at 2015 and Q4 2018 with each
segment citing the orden that governs it.

### the-layout-coverage-message-omits-the-half-that-explains-it | medium | four of sixteen entries read as false positives until the upper bound is recovered

Triaging ``test_every_claimed_filing_year_is_covered_by_its_declared_layout_design``
into actionable classes turned up something about the gate rather than the data. It
names **sixteen** revisions, not the fourteen recorded earlier.

**Four of the sixteen appear self-contradictory on their face:**

| revision | message says | design's ``applies_from`` |
|---|---|---|
| m180 '2019-2022' | claims 2022 | **2014** |
| m232 '2016-2017' | claims 2017 | **2016** |
| m303 '2022' | claims 2022 | **2022** |
| m210 '2025' | claims 2026 | **2022** |

In each the claimed year is at or after the year the design starts applying, so the
message reads as a contradiction. It is not. **The message reports
``apply only from {min(starts)}`` and never prints ``applies_to``**, which is the half
that does the work:

```
aeat-dr-180-2014  applies (2014, 2022)
aeat-dr-232-2016  applies (2016, 2017)
aeat-dr-303-2022  applies (2022, 2022)
aeat-dr-210-2022  applies (2022, 2025)
```

And the years being compared are not the years printed. ``uncovered`` collects
**ejercicio** years, while coverage is tested against the **presentation calendar years**
that ejercicio is filed in -- the arrears correction the gate's own docstring documents
at length, having removed an earlier false-positive class. So m180's ejercicio 2022 is
presented in 2023, which falls outside ``(2014, 2022)``, and the entry is correct. The
reader is simply shown "2022" and "from 2014" and left to reconcile them.

**The check is sound; the message understates its own evidence.** Adding the upper bound
and naming the presentation year would make each entry self-explanatory:
*"ejercicio 2022, presented 2023, outside aeat-dr-180-2014 (2014-2022)"*.

This matters because the list is a work queue. Anyone triaging it will hit those four
first, judge them spurious, and lose confidence in the other twelve -- which is close to
what happened here, and was only avoided by reading the comparison at line 169 and the
derivation at line 204 rather than trusting the rendered text.

It is the same failure shape this campaign has recorded twice on its own instruments: a
measurement that is correct internally and lossy at the boundary where a human reads it.
The box-collapse detector reported ``False`` for the form that motivated it; the span
gate's ABSENT and CONTRARY classes were indistinguishable until parsed apart. No
production code is wrong in any of the three -- the defect is in what reaches the reader.

### FIXED-the-layout-coverage-message-and-what-it-now-exposes | resolved | plus a bounds question the clearer text surfaced

The lossy message recorded in the previous finding is fixed. It now prints both design
bounds and the presentation years actually compared, and the four entries that read as
self-contradictory now explain themselves:

```
m180  ejercicio 2022, presented 2023, outside aeat-dr-180-2014 (2014-2022)
m232  ejercicio 2017, presented 2018, outside aeat-dr-232-2016 (2016-2017)
m303  ejercicio 2022, presented 2023, outside aeat-dr-303-2022 (2022-2022)
m210  ejercicio 2026, presented 2026-2027, outside aeat-dr-210-2022 (2022-2025)
m165  ejercicio 2013-2024, presented 2013-2025, outside aeat-dr-165-2026 (2026-open)
```

The verdict is unchanged -- same revisions named, 1 failed and 5 passed in the module
before and after. Only the rendering changed, with a comment recording why so the next
author does not trim it back. Nothing asserted the old text, so the change was safe.

**What the clearer text immediately exposes.** ``aeat-dr-303-2022`` is bounded
``(2022, 2022)`` while a 2022 ejercicio's fourth quarter is presented in January 2023. A
design whose ``applies_to`` stops at its own ejercicio year therefore **cannot cover its
final period's arrears filing**, and will diverge on that period by construction. m232 is
the same shape: ``(2016, 2017)`` against ejercicio 2017 presented in 2018.

That is either a bounds-authoring convention that needs one more year of headroom on
every arrears-filed design, or a genuine coverage gap where AEAT really did publish a
successor design for the presentation year. The two are distinguishable only by checking
whether a successor design exists for each, which this change does not attempt.

It is worth naming because it changes the triage: entries of that shape are a
**systematic consequence of how ``applies_to`` is authored**, not sixteen independent
defects, and they should be assessed as a class. The module's own docstring already
records one false-positive class removed by reading presentation years instead of
assuming an offset; this may be a second one hiding on the upper bound rather than the
lower.

### the-layout-coverage-list-triaged-eleven-are-citation-defects-fourteen-need-acquisition | high | and the arrears pattern is now unmistakable

The question the previous finding left open -- whether the arrears-bounds entries are a
systematic authoring convention or genuine gaps -- is answered by asking, per revision,
whether a bundled design already covers the uncovered presentation year.

**The check names 25 divergent revisions, not the 16 the assertion message shows** (it
reports the first layer that fails, not the whole set). They split cleanly:

**Eleven have a successor design ALREADY BUNDLED -- citation defects, no acquisition
needed:**

| revision | uncovered presentation year | design that covers it |
|---|---|---|
| m180 2019-2022 | 2023 | ``aeat-dr-180-2023`` |
| m210 2025 | 2026-2027 | ``aeat-dr-210-2026`` |
| m232 2016-2017 | 2018 | ``aeat-dr-232-2018`` |
| m303 2022 | 2023 | ``aeat-dr-303-2023`` |
| m390 2022 / 2023 / 2024 | 2023 / 2024 / 2025 | ``aeat-dr-390-2023`` / ``-2024`` / ``-2025`` |
| m714 2021 / 2022 / 2023 / 2024 | 2022 / 2023 / 2024 / 2025 | ``aeat-dr-714-2022`` / ``-2023`` / ``-2024`` / ``-2025`` |

**Fourteen have no bundled successor** -- m126, m128, m165, m181, m184, m270, m308,
m309, m322, m341, m347, m353, m390/2025, m576 -- and are genuine acquisition gaps.

**The m390 and m714 series make the pattern unmistakable.** Four consecutive m714
revisions each need exactly the next year's design, and three consecutive m390 revisions
do the same. This is not eleven independent mistakes: a revision for ejercicio N declares
the design applying in calendar year N, while its arrears filing presents in N+1 and
needs the design applying then. The convention is off by one presentation year, applied
consistently.

**What the fix is, and the check it needs first.** Adding the successor design to the
export layout's ``source_refs`` is only sound if the two designs agree byte-wise --
an export layout encodes offsets from one design, and citing two that disagree would
assert it follows both. The span gate already measures exactly that, and neither m390
nor m714 appears in its contrary-evidence list (which is m184, m200, m220, m322, m347,
m763). So for those seven revisions no corpus-evidenced relayout crosses the boundary and
citing the successor is safe. m180, m210, m232 and m303 need the same check run
individually before their refs are extended.

**Not landed here.** The edit touches export layouts across eight modelos owned by other
hands, and the per-revision relayout check above is a precondition for four of the
eleven. What this iteration removes is the ambiguity: the list is no longer sixteen
undifferentiated failures but eleven citation fixes with the evidence already on disk and
fourteen acquisitions, and the arrears off-by-one explains why they all look alike.

### CORRECTION-only-three-are-citation-fixable-the-rest-are-structural | high | supersedes the eleven-citation-defects triage

The previous finding classed eleven revisions as citation defects on the grounds that
neither m390 nor m714 appears in the span gate's contrary-evidence list. **That inference
was too quick, and running the per-pair check overturns it.**

Comparing each modelo's consecutive bundled designs box-by-box, on offset AND length:

| modelo | pair | boxes moved |
|---|---|---|
| m714 | 2021 -> 2022 | **8** |
| m714 | 2022 -> 2023 | 0 |
| m714 | 2023 -> 2024 | 0 |
| m714 | 2024 -> 2025 | 0 |
| m390 | 2022 -> 2023 | **13** |
| m390 | 2023 -> 2024 | **189** |
| m390 | 2017 -> 2018 | **97** |
| m390 | 2019/20 -> 2021 | **8** |

**Only three of the eleven survive: m714/2022, /2023 and /2024**, whose successor designs
are byte-identical to their own. m714/2021 needs the 2022 design and eight boxes moved;
every m390 pair moves too, some massively.

**Why the earlier inference failed.** The span gate asks whether a relayout crosses a
REVISION's span. m714/2021 and m390/2022 are single-ejercicio revisions, so a design
change at the 2021/2022 or 2022/2023 boundary sits *at the edge* of the span rather than
inside it, and the gate correctly does not flag it. Absence from that list therefore says
nothing about whether the NEXT design is byte-compatible -- which is the question the
citation fix actually depends on. Two different questions, and the earlier finding
substituted one for the other.

**What this changes, and it is not small.** For the other eight, the arrears-presentation
problem **cannot be closed by citing a second design at all**, because the successor
encodes different offsets. A revision for ejercicio N whose filing presents in N+1 under
a materially different layout cannot be served by one export layout, and no amount of
reference-adding fixes that. Those are structural -- the revision needs splitting, or the
layout needs to be understood as encoding the ejercicio's design while the filing is
written under the presentation year's, which is a modelling question this campaign cannot
settle.

So the triage now reads: **3 citation-fixable with verified byte-identical successors,
8 structural, 14 acquisition.** The middle group is the one that grew, and it is the one
that needs a decision rather than data.

Eighth time in this campaign that re-checking overturned a conclusion, and the third
where the overturned conclusion was already written into this document. The check that
caught it -- compare the actual designs rather than infer from another gate's silence --
is the same one that should have been run before the claim was made.

### TWO-SHIPPED-RULES-CONFLICT-the-citation-class-is-empty | high | the registry forbids the citation the layout gate demands

Attempting the three "safe" citation fixes produced the finding the previous four
iterations of analysis could not. **The fix is refused by the registry's own validation:**

> ``modelo 714 revision 2024 cites sources outside their applicability window:
> source 'aeat-dr-714-2025' applies_from 2025-01-01 is after revision valid_to
> 2024-12-31``

So two shipped rules are in direct conflict:

| rule | demands |
|---|---|
| ``test_every_claimed_filing_year_is_covered_by_its_declared_layout_design`` | the revision cite a design covering its PRESENTATION year (ejercicio N filed in N+1) |
| registry source-applicability validation | the revision cite NO source whose ``applies_from`` is after its ``valid_to`` (N) |

**For any arrears-filed modelo these are mutually unsatisfiable.** The presentation year
is by construction after ``valid_to``, so the design that covers it is by construction
forbidden. No citation can satisfy both.

**That empties the class.** The triage went eleven citation defects, then three after the
byte-comparison, and now **zero**: not one of the 25 divergences is fixable by adding a
source ref. Every one requires something else --

- extend the design source's ``applies_to`` to cover the presentation year, which is a
  source-metadata change and would make ``aeat-dr-714-2024`` claim authority into 2025;
- re-bound the revision's ``valid_to`` to its presentation window rather than its
  ejercicio, which changes what the revision means;
- or have the layout gate accept that a design authoritative for ejercicio N is the right
  layout for a filing presented in N+1, which is arguably the true semantics and would
  retire most of the 25.

The third reading deserves weight. A diseño published for ejercicio 2024 IS the layout a
2024 filing is written in, whenever it is presented. On that reading the gate's
presentation-year comparison is measuring the wrong thing for arrears returns, and the
registry validation is right. The module's own docstring already records ONE correction
in this exact area -- it stopped comparing ejercicio numbers to calendar dates after a
false-positive sweep -- so a second correction on the same axis is plausible rather than
heretical.

**Method note, and it is the point.** Four iterations reasoned about this class from
gate output, design comparisons and span verdicts, and each refined the answer without
reaching it. Ten minutes of actually attempting the edit produced a single error message
that settled it. The attempt was cheap, fully reverted -- ``git checkout`` on the modelo
directory, 24 m714 tests passing again -- and it is now recorded so nobody else spends
four iterations on the same reasoning.

### RESOLVED-design-source-windows-are-ejercicio-scoped-so-the-gate-measures-the-wrong-axis | high | the registry states this in its own authoring comment

The previous finding left three candidate resolutions for the rule conflict. The registry
settles it in its own recorded reasoning, beside the value:

> ``applies_from = 2024-01-01``
> *"Closed at its own ejercicio. AEAT publishes modelo 714 one edition PER EJERCICIO (its
> index titles read "714 - Ejercicio 2024"), and this source's ``record_design_epoch`` and
> corpus filename both name 2024. All five 714 editions previously declared
> ``applies_from`` with no ``applies_to``, so five designs simultaneously claimed 2025
> onward and revision resolution ..."*
> ``applies_to = 2024-12-31``

So a ``record_design`` source's window is **its ejercicio**, deliberately closed there,
with ``record_design_epoch`` and the corpus filename agreeing. That was an explicit
authoring decision taken to stop five editions all claiming 2025 onward -- not an
accident of bounds.

**The layout-coverage gate's premise contradicts it.** Its docstring states that *"a
design source's ``applies_from`` / ``applies_to`` are the calendar DATES a norm took legal
effect"* and compares them against the PRESENTATION calendar year. For an ejercicio-scoped
window that comparison is off by one presentation lag by construction: a design closed at
ejercicio N can never cover a filing presented in N+1, no matter how correct the registry
is.

**Resolution three is therefore the right one.** A diseño published for ejercicio 2024 IS
the layout a 2024 filing is written in, whenever it is presented. The registry validation
that refused the successor citation is correct, and the gate is measuring the wrong axis
for arrears-filed returns.

**But only for the off-by-one cases -- this does not clear the list.** The 25 divergences
split again on the size of the gap:

| shape | assessment |
|---|---|
| uncovered year is exactly the presentation lag (m180, m210, m232, m303, m390 x3, m714 x4) | gate false positive on the ejercicio/presentation axis |
| uncovered years span many years before the design exists (m165 12y, m181 13y, m309 19y, m341 16y, m347 16y, m322 16y, m353 13y, m308 10y, m270 10y, m184 9y, m126, m128, m576) | genuine -- no design of any vintage covers them |

The first group is the gate's own docstring problem repeating: it records having already
removed one false-positive class on this axis by reading presentation windows instead of
assuming an offset, and this is the same axis biting from the other side. The second group
is real and unaffected.

**What this campaign can say and cannot.** It can say the two rules conflict, that the
registry's ejercicio-scoping is deliberate and documented, and that roughly ten of the
twenty-five entries are consequences of the mismatch rather than data defects. It cannot
unilaterally narrow a shipped gate -- that is a decision about what the check is for, and
the gate's author reasoned carefully enough on the adjacent axis that the change belongs
with them.

### STANDING CONCLUSIONS -- which findings on this page still hold | index | read this before acting on anything above

This document accumulated findings across a long campaign and several of them supersede
earlier ones on the same page. A reader arriving now needs to know which conclusions
stand. **Later entries win; this index says so explicitly.**

**Superseded chains, in order:**

| superseded finding | replaced by | why |
|---|---|---|
| m190/m193 "cite a superseded twenty-day plazo" | "mis-cited, not superseded" | both plazos live in the SAME article; the earlier regex stopped at the first sentence |
| "three filing-scope stamps sit on revisions a gate calls uncoverable" | "``filing_eligible`` has no runtime consumer" | the flag is reporting-only, and the flip moves gaps into the STRICTER bucket |
| "eleven are citation defects" | "only three" then "the class is empty" then "the gate measures the wrong axis" | byte comparison killed eight; the registry's own validation killed the rest |
| "m604 is the contrary class" | m604's numbering was corrected and 2024-y-siguientes reviewed | the contrary basis was the numbering, and it is gone |

**What stands, and is actionable:**

- The pre-shifted-deadline sweep is CLOSED, 10 of 10, verified by re-scan. Three root
  causes, and the approving-clause habit (five windows citing the article that approves
  the modelo rather than the one stating its plazo) is the durable lesson.
- Design source windows are **ejercicio-scoped by deliberate authoring decision**, so the
  layout-coverage gate's presentation-year comparison is off by one lag by construction.
  About ten of its twenty-five entries are that mismatch; the multi-year-gap entries are
  genuine.
- The remaining three pending revisions are blocked on data or decisions, not review:
  m220 needs Orden HAC/529/2026 enrolled and a split; m763 needs BOE-A-2014-13180 and
  BOE-A-2018-17602 and a three-way split; m604/2021-2023 needs a product decision on
  whether a closed span carries historical windows.
- Bundling new corpus text from a web fetch needs operator authorization. Naming the
  instrument is the correct stopping point for an agent, not a shortfall.

**What this campaign delivered, stated plainly.** Census moved 78/0/17 to 95/0/3 over the
run, but that figure includes substantial peer work landing in parallel -- revision
splits, casilla authoring, locale sweeps. This campaign's own reviews are thirteen:
m182, m721, m136, m840, m036, m185 x2, m222, m165, m181, m270, m604/2024, and the m576
re-stamp. Each states its limits in ``reviewed_by``, including the ones no gate would
have forced it to state.

**The honest caveat on the count.** Nine iterations of this campaign ended without moving
it, and several ended by refusing a stamp that looked available. That is the intended
shape: the pending count is not the deliverable, and a revision moved across it without
evidence would be worse than one left behind.

### splitting-a-revision-does-not-clear-the-layout-coverage-gate | high | feedback for work currently in flight

Peers are splitting revisions right now -- m184, m322 and m347 all landed splits during
this campaign's later iterations. Re-measuring the layout-coverage divergences after
those splits gives a result worth passing back immediately:

**The count is unchanged at 25.** What changed is only the revision identifiers:

| before | after the split | still divergent |
|---|---|---|
| m184 2015-y-siguientes | **m184 2015-2024** | yes |
| m322 2008-2025 | **m322 2008-2023** | yes |
| m347 2008-y-siguientes | **m347 2008-2024** | yes |

Each split correctly bounded an open-ended revision -- which is a real improvement and
exactly what the span gate asks for -- and none of the three cleared this gate, because
the binding constraint is different.

**Why splitting cannot clear it.** m184's earlier segment now claims 2015-2024 against a
design that applies from 2025. Bounding the revision does not conjure a design for the
years before the earliest bundled one. The span gate wants a revision not to straddle a
re-layout; this gate wants every claimed year to have a design. A split answers the first
and leaves the second untouched whenever the modelo's oldest bundled design post-dates
the revision's oldest claimed year -- which is the situation for all fourteen genuine-gap
entries.

**So the two gates want different things and only one is satisfiable by restructuring.**
For the fourteen, the remedy is acquiring older designs, or narrowing what the revision
claims to the years evidence exists for -- and the second makes the registry assert less
than the taxpayer's reality, which the span gate's own docstring warns against in the
Modelo 720 case it records.

Recorded here because the splits are landing now and the next natural step after them --
re-running this gate and expecting improvement -- will show none, which reads as the work
having failed when it did not.

### split-fallout-leaves-casilla-fragment-names-lying | medium | second piece of feedback for the split work in flight

A regression check after 19 peer commits: the registry suite reads **21 failed / 5171
passed**, against 19 / 5089 at the earlier baseline. The suite grew by 82 tests and four
failures are new. None belongs to this campaign's changes; all four are fallout from the
revision splits landing now.

The most directly fixable is fragment naming. A casilla fragment file is named for the
FIRST and LAST casilla id it contains, and splitting a revision changes which casillas
land in each fragment without renaming the file:

```
modelos/184/revisions/2015-2024/casillas/cdecl.tipo-soporte__cdecl.total-registros-entidad.toml
  expected stem: cdecl.tipo-soporte__cdecl.representante-nombre

modelos/347/revisions/2008-2024/casillas/ccontraparte.representante-legal-nif__ccontraparte.numero-convocatoria-bdns.toml
  expected stem: ccontraparte.representante-legal-nif__ccontraparte.nif-operador-comunitario
```

The gate states the remedy itself -- *"rename the file to the expected stem (or fix its
content) so the name keeps telling the truth"* -- and both expected stems are printed, so
this is a rename with the target already computed.

The other three new failures are the same shape: the continuidad completeness ratchet's
committed baseline no longer matches, m347's counterpart-source-summary bindings no
longer resolve, and an export-layout record-coverage assertion about a colegio-concertado
row fires. Each is a downstream artefact that a split moved out from under.

**Pattern worth naming, alongside the earlier note that splitting does not clear the
layout-coverage gate.** A revision split is not a self-contained edit: it re-partitions
casilla fragments, invalidates committed baselines, and moves bindings and export records
relative to their revision. The splits themselves are correct and are the right
remediation -- this records what travels with them, so the trailing failures are read as
known fallout with named fixes rather than as the split having gone wrong.

Nothing here was changed by this campaign; the two named renames belong to whoever owns
the splits.

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
