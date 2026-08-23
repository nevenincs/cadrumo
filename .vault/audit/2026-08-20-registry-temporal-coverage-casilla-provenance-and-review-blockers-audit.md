---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-20'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:d6e25b0c04380242473d7e9f998c4ecf338d593f7bdfa2ca63bb43f0ff5da3f9'
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

### the-continuity-ratchet-fired-on-exactly-the-ids-the-split-duplicated | medium | which branch applies, decided by measurement

``test_ungrounded_continuity_backlog_matches_its_committed_baseline`` reds after the
m184 and m347 splits, and it offers two branches without saying which:

> *"Either a chain lost its ``continuidad_id`` stamp (a regression -- restore the stamp),
> or a NEW revision landed carrying repeated casilla ids (legitimate -- those ids are
> un-reviewed, so raise the baseline)"*

Measured, the answer is unambiguous. Counting casilla ids present in BOTH halves of each
split:

| modelo | ids shared across the split halves | ratchet delta |
|---|---|---|
| m184 (2015-2024 / 2025-y-siguientes) | **86** | **+86** |
| m347 (2008-2024 / 2025-y-siguientes) | **39** | **+39** |

Exact, one-to-one. The ratchet fired on precisely the ids the split duplicated and on
nothing else, so the second branch applies: this is a legitimate consequence of new
revisions landing, not a lost stamp.

**Why splitting produces this by construction.** A split copies a revision's casilla set
into both halves. Every id then appears twice across the modelo with no
``continuidad_id`` linking the two occurrences, which is exactly the shape the ratchet
counts. Any split of a revision with N casillas will raise this backlog by N.

**Not raised, and the reason is a real choice.** The gate prints a ready-to-paste
replacement baseline, and taking it would record 125 further ids as un-reviewed backlog.
The stronger alternative is stamping ``continuidad_id`` on those chains, which ASSERTS
and reviews the continuity across the split rather than deferring it. Both are legitimate;
only the split's author knows whether they intend to establish continuity or accept the
backlog, and raising the baseline forecloses the better option silently.

What this contributes is the disambiguation the gate could not make: the counts match the
duplication exactly, so nobody needs to hunt for a lost stamp that is not missing.

This is the third distinct piece of split fallout recorded -- after the layout-coverage
gate not clearing, and the fragment names that had to be renamed. Together they describe
what a revision split drags behind it: stale fragment names (fixable mechanically, and
done), committed baselines that shift by exactly the duplicated-casilla count, bindings
and export records that move relative to their revision, and a layout gate that the split
does not satisfy at all.

### the-m347-binding-failure-is-the-test-not-the-data | medium | and a false content-loss finding was caught mid-diagnosis

The last undiagnosed split-fallout failure,
``test_committed_modelo_347_declares_counterpart_source_summary_bindings``, reports a
binding's ``legal_refs`` missing ``orden-hac-1431-2025:art-1``.

**The data is correct; the test is mis-targeted.**

| m347 half | cites ``orden-hac-1431-2025`` | correct |
|---|---|---|
| 2008-2024 | no | **yes** -- a span ending in 2024 must not cite an orden applying from 2025 |
| 2025-y-siguientes | yes | **yes** -- that is the half the orden governs |

The split placed the reference exactly where it belongs. The test's
``_modelo_347_revision()`` helper returns ``revisions["2008-2024"]`` -- the FIRST half --
and then asserts that half cites the 2025 orden. The helper was repointed at a concrete
revision id when the split landed, and this particular assertion travelled with it
without being re-read against what the new span means.

That is the same shape as the fragment names and the ratchet: **a split moves data
correctly and leaves an artefact pointing at the old shape.** Here the artefact is a test
expectation rather than a filename or a baseline.

**A false finding was caught mid-diagnosis and is worth recording.** An initial grep
returned zero hits for the orden in BOTH halves' binding files, which read as the split
having dropped a legal reference outright -- a content-loss finding about to be written
down. Counting occurrences across the whole modelo before and after the split gave 118
before and **119** after: nothing was lost, and one was added. The zero-for-both reading
was a bad grep, not a bad split. Re-measuring at the modelo level rather than trusting
the first negative is what caught it.

Not fixed here. The remedy is a test change on a helper the split's author repointed one
commit ago, and there are two defensible shapes -- retarget that one assertion at
``2025-y-siguientes``, or split the test to assert the pre-2025 and post-2025 refs
separately. Which they want is a statement about what the test is for.

With this the split-fallout map is complete: stale fragment names (fixed), a ratchet
baseline shifted by exactly the duplicated-casilla count (diagnosed, branch identified),
a layout gate the split cannot satisfy (recorded), and a test expectation that followed a
revision id but not its semantics.

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

## 2026-08-22 — the three standing blockers, worked to ground

The blockers were treated as in-scope rather than reported. All three moved; two of the
three "known" descriptions of them turned out to be wrong.

### A transitional provision would have made five fabricated deadlines look correct

Modelo 604's 2021-2023 era carried no deadline windows, and its own prose defended the
absence: "No window is fabricated for a past year." The premise was wrong on both halves.
This registry already carries historical windows on closed spans — m232/2016-2017 declares
windows for exactly its own two years, m184/2015-2024 and m347/2008-2024 likewise — so the
absence was an omission, and the plazo is a fixed monthly rule the orden states verbatim,
so nothing needed inventing.

What *did* need care is that the general rule does not govern the whole span. Orden
HAC/510/2021 was published **27 May 2021**, after the tax's first four liquidation periods
had already closed, and its **disposición transitoria única** folds enero–abril 2021 into
the mayo-2021 plazo. Periods 2021-01 through 2021-05 therefore share ONE window, 10–20 June
2021. Generating twelve ordinary 2021 windows — the obvious move — would have fabricated
five deadlines AEAT never set, and every one would have looked plausible.

The transitional provision was **not in the bundled corpus at all**. The bundled art. 3 was
also an abridgement carrying a verbatim provenance claim: it dropped the first paragraph
(periodo de liquidación = mes natural, Ley 5/2020 art. 8.3), the RD 366/2021 preamble, and
the words «según corresponda». Both were corrected against two BOE surfaces that agree.

**Generalise:** when a modelo's approving orden post-dates periods it governs, look for the
transitional clause before deriving any window from the general rule. The gap between a
tax's entry into force and its modelo's approval is where fabricated deadlines hide.

### A ratchet that forbade its own remedy

Enrolling three new legal references pushed the unverified-anchor ratchet from 89 to 92 and
was refused. The cause is structural: a hand-authored excerpt **cannot** produce an anchored
unit. The segmenter splits on `<h[1-6] class="articulo">` and reads the anchor from a
preceding `[Bloque N: #x]` marker, so an excerpt written as `<div id="a3"><h2>` — the shape
several bundled excerpts use — extracts as one anchorless unit against which *any* anchor
resolves, including a wrong one. Every new hand-authored citation therefore joined the
unverified population by construction, and the ratchet forbade the enrollment.

Re-shaping the excerpts to real BOE markup made the new entries verified on arrival and
pulled two pre-existing ones along, so the ceiling **tightened 89 → 87** instead of being
raised. The docstring already recorded a prior hand doing exactly this on Orden
EHA/1274/2007 — reading it first would have saved the rediscovery.

### A tally that detected nothing

`test_modelo_490_604_763_registry` pinned a total window count per modelo, its docstring
claiming "the orden fixes how many filing windows the tax has". It does not: an orden fixes
the **cadence**. 490 and 763 read 8 because two years of quarters happened to be enumerated;
604 read 12 for one year of months. Authoring a legitimate new era reddened a test that had
detected nothing about the new windows. Replaced with per-year cadence completeness, proven
to red on both a dropped and a doubled window — which a total cannot tell apart from a
legitimately added year.

### Two blocker descriptions were wrong

- **m763 needed the amending ordenes, and the split.** HAP/2373/2014 disposición final
  primera substitutes its anexo I "con efectos para los periodos de liquidación que se
  inicien a partir del 1 de enero de 2015"; HAC/1363/2018 artículo único substitutes it
  again "para las autoliquidaciones correspondientes al cuarto trimestre del año 2018 y
  siguientes". Both are now bundled and cited; the NO-LEGAL-EVIDENCE verdict is cleared.
- **m220's blocker was one acquisition, and it landed.** Orden HAC/529/2026 approves the
  2025 IS models; its art 6.3 is the modelo-220-specific plazo (LIS art 75.2) and is
  stronger grounding than the 2024 era's, whose only bundled provision naming 220 is art 3's
  *domiciliación bancaria* heading. The span is now split at 2024/2025 and no longer reports
  a spanned re-layout.

**Article 1 of HAC/529/2026 is deliberately NOT bundled.** No fetch returned its enumerated
list without elision, and bundling an abridged provision as verbatim is the exact defect
corrected in orden-hac-510-2021 the same day. Recorded in the excerpt's own provenance note.

### Still open

- m604 declares **no windows for filing year 2024** at all, though 2024-y-siguientes claims
  `valid_from 2024-01-01` and enumerates only 2025. A real hole, reported not closed.
- m763 still spans its 2012/2015 re-layout; the citation cleared the legal-evidence half,
  the split remains.
- HAC/529/2026 art. 1 and the m763 2018-4T orden remain to be bundled.
- Peers captured this work by bare commit **twice in one session**. The `reviewed_by` scope
  statement is what survived both times; commit messages did not.

### Correction: the stale m763 note was right, and this audit was wrong about it

An earlier entry above claimed the campaign note describing m763 as needing "BOE-A-2014-13180
+ BOE-A-2018-17602 bundled + three-way split at 2015 and Q4 2018" was "wrong on both counts".
It was not. **Both document ids are correct**, and **both boundaries are real** — the design
registrations bracket them exactly (`aeat-dr-763-2015` runs 2015-01-01 to 2018-09-30,
`enrolled-modelo-763-layout` from 2018-10-01) and each now has its orden bundled.

What misled me was the span gate, which reports a single boundary, "2012/2015". That is the
*same* 2015 boundary expressed as a design-epoch pair, not a competing account, and the gate's
silence on the 2018 one is a limit of what it can see — not evidence the boundary is absent.
Reading one instrument's verdict as the whole truth is the error; the design registrations were
sitting in the catalogue saying otherwise the entire time.

**The partition is larger than "three-way", too.** The 2018 boundary falls MID-YEAR, and
`PeriodSelector` is year-granular — `years`, `year_from`, `year_to` and one `periods` list, with
no per-year period bound. A mid-year era is therefore expressed by giving the boundary year its
own explicit `years = [YYYY]` revisions with disjoint period lists, with the open tail starting
at the next clean year. Modelo 490 already does this at its 2022 1T|2T boundary and documents
the reason in its own prose. So m763 wants **five** revisions: 2011-2014, 2015-2017, 2018-1T-3T,
2018-4T, 2019-y-siguientes.

**Why it was not executed here.** Each closed era additionally needs its own trimestral windows
derived from orden-eha-1881-2011 art 4 ("la presentación será trimestral y se efectuará durante
el mes siguiente a la finalización de cada trimestre natural"), because an applicability-grade
revision that cannot say when it is due does not meet its own grade — the lesson m604's
2021-2023 era already taught. This revision's eight windows cover 2025 and 2026 only, so four
of the five eras would land with none, and splitting without them would convert one honest
pending revision into five unstampable ones. The acquisition is done and durable; the partition
is the next step, specified above rather than half-started.

## 2026-08-22 (later) — m763's blocker is a first-application date, not a split

The partition was not the obstacle. Registering modelo 763's earliest bundled design
surfaced a disagreement that blocks it upstream.

**AEAT's index title for the artefact reads "ejercicios 2T-3T 2012, 2013 y 2014" — first
covered period 2T 2012. The revision claims `valid_from 2011-01-01`.** Five quarters are
claimed that AEAT's own design does not cover, and nothing bundled resolves it:

- The founding orden EHA/1881/2011 is *de 5 de julio de 2011*, in force the day after
  publication, and carries **no disposición transitoria and no first-application clause**
  (re-checked against BOE on 2026-08-22). Its 1T 2011 plazo would have run in April 2011,
  before the orden existed; its 2T plazo ran in July 2011, straddling entry into force.
- **Ley 13/2011, which created the tax, is in neither the corpus nor the legal catalogue.**

**Why this blocks the split rather than accompanying it.** Every one of this registry's 99
revisions carries at least one deadline window — measured across the whole tree, no
exceptions. There is no precedent for an era that cannot say when it is due, so each new era
needs its own trimestral windows, and the earliest era's cannot be authored without knowing
which trimestre was first. Deriving them from the art. 4 cadence alone would fabricate up to
five deadlines for periods the modelo may never have covered — the same trap orden
HAC/510/2021's disposición transitoria set for modelo 604, caught there only by reading the
orden before generating.

**Ley 13/2011 art. 48 could not be retrieved — text fetch is exhausted, do not repeat it.**
FOUR BOE surfaces were tried across two sittings: `buscar/act.php`, the ELI consolidated URL
(`/eli/es/l/2011/05/27/13/con`), `buscar/doc.php`, and `diario_boe/xml.php`. All four truncate
in or before Título V (arts. 21–24); the XML surface returns the table of contents listing
"Artículo 48. Impuesto sobre actividades de juego" but cuts off in the preámbulo. The
open-data block endpoint `/datosabiertos/api/legislacion-consolidada/id/BOE-A-2011-9280/texto/bloque/a48`
returns HTTP 400. Título VII (Régimen fiscal) sits at the end of a document too large for a
text-fetching tool to reach. Whoever resumes this needs a browser tool, the per-block API with
a correct block id, or the BOE PDF — not another `WebFetch` against a consolidated URL.

**A related fact that is measurable and already decisive on its own:** AEAT publishes NO
diseño de registro covering 2011 or 1T 2012 for this modelo. The three bundled designs, with
their manifest-recorded index titles, begin at 2T/3T 2012. That does not by itself rule on the
first devengo, but it means the registry's `valid_from = 2011-01-01` is unsupported by every
artefact AEAT ships for the form.

**Recorded rather than resolved, deliberately.** `applies_from = 2012-04-01` on the new
`aeat-dr-763-2012` source records what the artefact evidences; it is NOT a ruling on when the
modelo first applied, and the revision's own prose says so. Dating an era of a filing-grade
authority off a filename is not the standard, however plausible the date.

Side effect worth keeping: the registration gate's unregistered-design population went
**49 → 48**. The remaining 48 span modelos 036, 100, 111, 115, 123 and others — a real
inventory backlog, not m763-specific.

## 2026-08-22 — filing-capability triage: two predictors that beat "smallest first"

Opening the export-layout campaign on the smallest revision was the wrong instinct, and
measuring caught it before a byte offset was written. Two independent filters decide whether
a layout can be authored honestly, and neither is size.

### Filter 1 — does the design's field table TILE?

`extract_record_design` reports a field list; a fixed-width layout is only authorable if that
list tiles the record once, with no gap and no overlap. Measured across all worklist designs:

| modelo | fields | overlaps |
|---|---|---|
| **038** | 58 | **31 — CORRUPT** |
| 182 / 187 / 188 / 194 | 38–46 | 0 |
| 840 | 381 | 0 |
| 763 | 201 | 0 |
| 036 | 1047 | 0 |
| 220 (2024 / 2025) | 16079 / 16720 | 0 |

Modelo 038's PDF extracts with reversed text (`AIRATNEMELPMOC .CED` for "DEC.
COMPLEMENTARIA", `ODOIREP` for "PERIODO"), merged column descriptions, and 31 overlapping
fields. **Every offset in it would be a guess.** It is the only corrupt one — this is not a
PDF-versus-xlsx problem, and four other PDFs tile perfectly.

**The read-quality gate cannot see this.** `test_no_bundled_design_is_unreadable_or_only_partly_read`
reports 9 designs as PARTIAL ("sheets skipped"); modelo 038 is not among them, because its
sheets *are* read — they just come out garbled. The gate detects absence, not corruption. A
tiling check is the missing instrument.

### Filter 2 — do the design's years cover the revision's CLAIMED years?

`test_every_claimed_filing_year_is_covered_by_its_declared_layout_design` fires only on
revisions that ALREADY declare a layout. So a revision with no layout looks clean, and
authoring one moves it onto that gate's failing list. Measured claimed-vs-covered:

- **Fully covered, authorable now:** 840 (24/24y), 036 (2/2y), 220/2024 (1/1y), and 038
  (25/25y, but blocked by Filter 1).
- **Would trip the claimed-year gate:** 182 (**17 of 20 years uncovered**), 188 (4y), 194
  (4y), 187 (3y), 763 (1y — 2011, the same first-application question already open),
  220/2025-y-siguientes (2026).
- **No registered design at all:** 185, 136, 721.

This is the "gates overlap, so satisfying one can violate another" hazard, and the tell named
in the rules is oscillation. Authoring modelo 182's layout from a 2024-only design would take
the filing worklist 13 → 12 and push the claimed-year gate 15 → 16. That is a trade, not
progress. The third shape is an era split so each layout matches its own design — but the
early era then remains unfileable, so **the worklist cannot be driven to zero by authoring
layouts alone.** Most of these revisions are open-ended spans whose designs cover only recent
years; the residue needs older designs acquired from AEAT.

### Corrected order

**840 first** — fully design-covered, tiles clean, 381 fields, 2 casillas — then 036, then
220/2024. Not 038 (corrupt), and not the small informative returns (year gaps).

### Correction, same day: "reasoned absence" is NOT a third filter — it is the failure mode

Opening the first authoring iteration on modelo 840, its revision header reads "administered
municipally and is not a return this application emits", and its stamp says the missing layout
"is what the applicability rung asserts". Modelo 036 has the same shape, with a *production*
docstring in `_authority.py` stating it "is filed on AEAT's sede and produces no fichero here".
The obvious inference — that these are deliberate end-states rather than backlog, and should be
filtered out of the queue — is wrong, and the worklist gate says so in its own docstring:

> every modelo that could not emit a filing artifact carried a decision record declaring its
> layout withdrawn, each individually grounded and defensible, and nothing ever summed them.
> The tree stayed green while the application quietly could not file IVA, sociedades or
> retenciones. Converting "we cannot file this" into a declared, gate-satisfying state is
> precisely what let that go unnoticed for the whole of the project's history.

It then forbids, without exception, narrowing to a subset, adding an allowlist, or excusing
"informative" modelos, and states: "The one legitimate way to change this test's result is to
build an export layout." The gate is operator-sanctioned to fail permanently.

So a per-modelo justification for having no layout is not evidence the entry is illegitimate —
it is the artefact the gate exists to stop treating as sufficient. **Filters 1 and 2 (tiling,
year coverage) remain valid: they say a layout cannot be authored HONESTLY today. A reasoned
absence says only that someone previously decided not to, which is not the same thing and
must not be used to shorten the queue.**

**A contradiction found while checking this.** Modelo 840's revision prose says it "is not a
return this application emits", yet the revision DECLARES an export application link
(`surface = "export"`, `consumer = "cadrumo.application.filing.export_draft"`). One of the two
is wrong. Structured intent is declared for export; the prose denies it. Recorded, not
resolved — resolving it by authoring a layout would settle a product question by side effect.

**Export-surface declaration across the 13** (a structured signal the worklist gate does not
consult): 038, 220/2024, 220/2025-y-siguientes, 763 and 840 declare an `export` link; 036, 136,
182, 185, 187, 188, 194 and 721 do not. That asymmetry is worth an operator ruling — but note
the gate deliberately ignores it, for the reason quoted above.

### How an export layout is actually produced — two sanctioned paths, measured

Before hand-authoring 381 fields for modelo 840 it was worth asking who owns this job. Both
shapes ship, and the split is not arbitrary:

- **Generated** (`revisions/<rev>/export/`): 26 revisions across modelos 151, 184, 185, 200,
  202, 210, 222, 232, 296, 303 … Produced by `dev/registry/pipeline` —
  `render_complete_export_tree` → `validate_generated_export_tree` →
  `publish_validated_generated_export_tree` (journalled, exclusive-locked, with rollback) —
  driven by a **render profile** under `dev/registry/render_profiles/modelo_<id>/<era>/`.
  16 modelos have one. The tell in the data: m296's `producer_key`s are machine slugs
  truncated at a fixed width (`m296.dec.numero_identificativo_de_la_declaracio_2`).
- **Hand-authored** (`revisions/<rev>/export_layouts/`): **60 revisions across 35 modelos** —
  100, 111, 115, 117, 181, 190, 322, 341, 390, 604, 720 … This is the MAJORITY, and it is
  legitimate. Modelo 604's 2021-2023 layout is the quality bar for provenance prose; modelo
  181's `0003-record-declarado.toml` is the closest structural template for a
  declarante/declarado informative return.

**Rule of thumb established:** if the modelo has a render profile, drive the generator; if it
does not, hand-author against `export_layouts/`. Modelo 840 has no render profile, so
hand-authoring is correct for it. (Modelo 185 DOES have one — for era 2026 — and its
2025-y-siguientes revision already carries a generated `export/` tree; the worklist entry is
the older 2003-2025 era, which has no registered design at all.)

**Thin layouts are normal, and not thin in substance.** A 3-casilla revision was assumed to
imply a hollow file; measured, m296's layout is 13 literal + **112 header** + 5 casilla + 6
filler. The bulk of a fixed-width record is taxpayer profile data carried as `header` fields,
not casilla values. So a revision with 2 casillas can still emit a substantive file — modelo
840's page 1 is largely an identity and domicilio block that maps to headers, with its two
declared casillas landing at @270+4 (Ejercicio [14]) and @274+1 (Declaración de: [15]).

**Where this iteration stopped, and why.** Modelo 840's design tiles cleanly (381 fields, 3
records: Pág. 1 1132 bytes, Pág. 2 1165, Anexo 1067), covers 24 of 24 claimed years, and
declares an export application link — it is authorable. It was NOT authored, because the
`producer_key` namespace it needs for the domicilio block is unvalidated here: the shipped
examples use either global keys (`taxpayer.tax_id`, `contact_person.phone`) or generator-minted
modelo-scoped slugs, and hand-minting ~90 address-field keys at the end of a long working
session, against a schema whose accepted set has not been checked, is the condition under which
an offset gets invented. The next iteration should first establish what `producer_key` values
the schema accepts, then transcribe Pág. 1 position-by-position.

## 2026-08-22 — the filing worklist is a BINDINGS backlog, not a layout backlog

Chasing the `producer_key` question to the bottom overturned the campaign's premise. The
13 entries are not blocked on transcribing byte offsets. They are blocked on the data
model that feeds a layout.

### Three things measured, in order

**1. `producer_key` is a CLOSED enum, and it is modelo-scoped.** `core.FilingProducerKey`
carries per-modelo families — m200 135 keys, m296 112, m360 70, m222 23 — plus small generic
scopes (`taxpayer` 6, `selected_account` 6, `presenter` 1, `filing` 1,
`entidad_desarrolladora` 2). **There is no `m840` scope.** A key is not enough on its own
either: `filing_producer_values()` maps each enum member to a value from a typed
`FilingProducerSnapshot`, so a new modelo-scoped family needs enum members AND a lexicals
producer AND profile data behind it. That is a feature, not a transcription.

**2. But modelo-scoped keys are NOT required.** 22 shipped layouts use generic keys only —
modelo 604 uses 2 headers, 347 uses 3, 714 uses 3. So a layout can bind literals, two or
three generic headers, its casillas, and fillers. The producer namespace is not the blocker.

**3. The actual mechanism: 60 of 86 shipped layouts DERIVE their fields from bindings.**
Modelo 720's layout declares just 2 inline fields because it sets `binding_record = "type_1"`
and lets the derivation supply the rest; the inline fields are only the BLANCOS tail the
derivation misses. The worklist gate's own docstring says this outright — "layouts are
derived from bindings first, so a revision declaring none inline but deriving one counts as
capable".

### What that means for the 13

| revision | casillas | bindings |
|---|---|---|
| 036/2025-02-03 | 31 | 1 |
| 182/2007 | 7 | 5 |
| 188 / 194 | 5 | 0 |
| 187 | 4 | 0 |
| 038, 220/2024, 763, 840 | 2 | 0 |

Modelo 840 has 2 casillas and 0 bindings against a 381-field design. Any layout authored from
that binds two positions and must declare the other ~379 as filler — which asserts AEAT reads
blanks where it reads the sujeto pasivo's domicilio, the elementos tributarios and the
relación de locales. That is a structurally thin file behind a valid digest, which
`modelo-export-mirrors-official-structure` names as the defect the completeness gate exists to
stop. Omitting them instead truncates the record: emitted length is
`max(offset + length - 1)`, as modelo 720's own comment records.

**So the honest ceiling is not "3 of 13 authorable". It is ZERO authorable as a layout today.**
Every one of the 13 needs its casilla and binding set authored first; the layout is the last
step, and for 60 of 86 shipped cases it is largely derived rather than written.

Filters 1 and 2 from the earlier entry remain correct and still apply — they just were not the
binding constraint. Ordering the queue by design size was measuring the wrong axis entirely:
the right axis is how much of the casilla/binding model already exists.

### Consequence for the loop

The campaign goal as written ("author the missing fixed-width export layouts") cannot be
executed on any of the 13. The prerequisite work is casilla and binding authoring from the
bundled designs — which is exactly the "NEEDS CASILLA AUTHORING AT SCALE" category the previous
campaign had already identified and set aside. That category was never a separate backlog from
this one; it IS this one.

### Correction: it is the CASILLA set, not bindings — and modelo 181 proves it

The entry above states "60 of 86 shipped layouts DERIVE their fields from bindings". That is
wrong as a causal claim. 60 of 86 is the count of revisions that have bindings AND a layout —
correlation. **26 of 86 shipped layouts have no bindings at all**, and modelo 181 is the
decisive counter-example:

- modelo 181/2009-y-siguientes: **42 casillas, 0 bindings**, 2 records, and its layout is
  5 literal + 2 draft + 2 header + **40 casilla** + 1 filler.

So a fixed-width layout is driven by the **casilla set**. Binding-derived records (modelo 720's
`binding_record = "type_1"`) are a second, additive mechanism for repeating rows, not the
general one. The worklist gate's docstring line "layouts are derived from bindings first"
describes the resolution ORDER inside the filing boundary, not a requirement that bindings
exist.

**The conclusion from the previous entry survives, with a corrected reason.** Modelo 840 still
cannot get a substantive layout — but because it declares 2 casillas against a 381-field
design, not because it lacks bindings. The prerequisite is authoring the casilla set from the
bundled design, which is what modelo 181 already did (42 casillas for a 2-record informative
return).

**This makes the queue tractable again, on a corrected axis.** The right ordering is by how
many casillas remain to author, i.e. design fields not yet covered by a declared casilla:

| revision | casillas | design fields | records |
|---|---|---|---|
| 188/2019 | 5 | 40 | 2 |
| 194/2019 | 5 | 41 | 2 |
| 182/2007 | 7 | 38 | 2 |
| 187/2019 | 4 | 46 | 2 |
| 840/2003 | 2 | 381 | 3 |
| 036/2025 | 31 | 1047 | 13 |
| 220/2024 | 2 | 16079 | 137 |

The four informative returns are ~35 casillas each — the same scale modelo 181 already carries
— and their designs tile clean. They remain subject to Filter 2 (year coverage), which is a
separate and still-real blocker for a LAYOUT, but authoring their casilla sets is useful work
that is not blocked by it.

## 2026-08-22 — authoring modelo 840's casilla set: three things the design does not tell you

Coverage 0 -> 48 of 108 across three iterations (Apartado I [1]-[13], II [16], III [17]-[32],
V [68]-[83]). Three hazards were only findable by measuring, not by reading the design.

**1. AEAT numbers by the PRINTED FORM, not by byte order.** [11] Provincia @213 precedes [10]
Municipio @215; [31] @485, [29] @487, [30] @522; [72] @1018, [70] @1020, [71] @1055, [73]
@1061. Nine of forty-eight fields are out of order. Sorting a design's fields by box number to
pair them with offsets silently mis-assigns them, and nothing downstream would catch it —
every offset would still tile.

**2. "Reservado" is not the discriminator; the bracket number is.** Boxes [16], [21], [30],
[32], [71], [73] and [76] are marked Reservado — the administration fills them — but AEAT
still numbers them and `build_diseno_coverage_report` derives all seven. They are declared
with `required = false`. The UNNUMBERED reserved run at @250+6 carries no box number, is not
derived, and is correctly not a casilla. Reading the label would have got this backwards; the
question was settled by enumerating the derived set.

**3. A singleton `semantic_role` that normalises onto another role is refused.** The
registry validates for typo-twins and refused `local_indirecto_pto` and `local_indirecto_piso`
until each declared `semantic_role_cardinality = "intentional_singleton"` with a reason. That
declaration is the normal case, not an escape hatch — 1561 casillas carry it.

**An honest limit recorded in the data:** box [79] is "Pto." and the diseño never expands it,
three boxes from [82] "Pta." (Puerta). In AEAT address blocks Pto. is ordinarily Portal, but
"ordinarily" is not the standard for a filing-grade label in four languages, so the label keeps
AEAT's own abbreviation and says why. Expanding it needs an official source.

### Apartado IV is blocked, and the reason is a false green rather than effort

The derived set holds **108 distinct numbers**, but five of Apartado IV's numbers label
MULTIPLE physical positions: [53], [54] and [55] each head a triplet (Agrupación / Grupo /
Epígrafe 1º, 2º, 3º), [62] is a date split into día/mes/año components, and [63] labels both
Causa de la baja and Causa de la variación. They collapse to ONE derived casilla each.
Declaring one casilla per number would make the coverage report read fully covered while
**eleven real positions stay unmodelled** — worse than the gap it replaces, because it is
invisible. Apartado IV needs a distinguishing convention (modelo 604 used slugs for its eight
signo casillas; modelo 181 used byte spans) chosen deliberately, not mid-transcription.

## 2026-08-22 — a second defect of the same shape in the stamp writer

Modelo 840 became unstampable while its neighbours stamped cleanly. The CLI reported
`invalid TOML: expected newline, found a period at line 30` — naming a line that, read from
disk, was blank.

The manifest was never broken. The **writer** broke it and then correctly refused its own
output. Its table-end scan took the next line beginning with `[` as a new TOML table — but
this revision's `reviewed_by` cites AEAT box numbers, and the wrap put `[13]. VERIFIED -- ...`
at the start of a physical line, cutting the revision table thirty lines early. The rebuild
emitted the remaining prose and the trailing `family_dispositions` outside any table;
post-write validation caught it and restored the bytes, which is exactly why the file on disk
always looked healthy and every direct loader call succeeded.

Fixed by skipping each governance assignment's full span before looking for a table header —
the same span walk `_without_governance_assignments` already performs. Both must agree, or the
body slice and the removal disagree about where the table ends. Bite-proved both ways.

**This is the second defect of this shape in this writer.** The first dropped only the KEY
line of a multi-line value and orphaned its prose; this one reads that same prose as
structure. The general rule: **a governance value's physical lines are opaque text, and no
line-oriented scan may interpret them.**

**Diagnostic lesson worth more than the fix.** The error's line number MOVED between attempts
— 30, then 63, then 6 — while the file did not change. A line number that moves against a
static file is the tell that the reported text is not the text on disk. Several probes were
spent on cache-poisoning and peer-mutation theories before that registered. Related: a
`reviewed_by` change on an already-reviewed revision REQUIRES `--reviewed-at`, because an
omitted date would carry the previous reviewer's date onto the new claim.

## 2026-08-22 — Pag. 2 of modelo 840: two findings that generalise past this modelo

Coverage 48 -> 72 of 108. Two things learned here apply to every casilla set authored
from a diseño, not just this one.

### The design carries its own type, and it disagrees with the label

`RecordDesignField` exposes `type_code` — `An` (alfanumerico) or `Num` — alongside
`offset`, `length`, `description`, `validation`, `content` and `components`. **Use it.**
Box [84] is named "Cuota consignada directamente en las tarifas" and every instinct says
`money`; the design types it `An`, because it is a *Reservado* box the administration
fills as text. Across Pag. 2 the split is exact: every Reservado box is `An`, every
taxpayer-supplied figure is `Num`. The `Num` ones here carry no `ent + dec` hint in their
description — unlike the repeating rows, which say `7ent + 2dec` explicitly — so they are
integer counts and surfaces rather than money.

Reading the label instead of the type code would have mis-typed nine of the twenty-four.

### Most fields on a detail record are a REPEATING GROUP, not casillas

Pag. 2 has 110 fields but only **26 distinct box numbers**; the Anexo has 165 fields and
**4**. The bulk of both is one block restated: Apartado VI's `A) 1.`, `A) 2.`, `A) 3.` …
each carry the same four fields (`2Cod+30Descrip`, `Numero 7ent+2dec`, `Importe unitario`,
`Cuota`), and **AEAT prints no box number on any of them**. The Anexo repeats an address
block the same way.

These are repeating detail rows — the shape modelo 720 models with `binding_record` /
`repeat = "binding_rows"` — not flat casillas. Minting a byte-span number per repetition
would model a repeating structure as fixed positions and invent a distinct concept for
every occurrence. **So a record's field count is a bad estimate of its casilla count**, and
the ratio of fields to distinct numbers is the tell: 110:26 and 165:4 mean "repeating",
106:82 means "flat".

This also revises the campaign's own arithmetic. The remaining 36 uncovered derived
casillas are NOT 36 units of transcription: they are Apartado IV of Pag. 1 (blocked on the
collapsed-number convention), boxes [86] and [109] (same blocker), and an Anexo that is
almost entirely a repeating block.

### The typo-twin validator caught a real readability trap

Authoring the C and D blocks as `elem_trib_local_*` and `elem_trib_locales_*` produced
`elem_trib_local_cuota_elemento` beside `elem_trib_locales_cuota_elemento` — one letter
apart, two different concepts — and the registry refused both. Declaring them
`intentional_singleton` would have satisfied the gate and left the trap in place. They were
renamed instead to the distinction AEAT actually draws: **municipal** (C, cuota municipal)
versus **provincial-nacional** (D, cuota provincial o nacional). The check was right; the
names were wrong.

## 2026-08-22 — the collapsed-number convention, settled

Three iterations deferred this. It gated Apartado IV of modelo 840 and boxes [86] and
[109] of its Pag. 2, and it is now decided and proven on the smaller case.

### The problem, stated precisely

`build_diseno_coverage_report` keys a derived casilla on `(segmento, number)`, so several
design fields printing the same `[NN]` collapse to ONE derived casilla. Declaring a single
casilla per number satisfies the coverage report while the other physical positions stay
unmodelled — **covered on paper, absent in fact**. Across modelo 840 that is sixteen
positions behind seven numbers.

### The convention, taken from modelo 604 rather than invented

Modelo 604 carries eight "signo" casillas that qualify another box. Each one puts a
DESCRIPTIVE SLUG in `number` — `liq-03-signo-base-rectificaciones` — instead of repeating
the box number it refers to, because `(segmento, number)` is uniqueness-enforced.

Generalised: **where N positions share one printed number, ONE casilla carries AEAT's
number and each remaining position becomes its own casilla with a slug number.** The
derived box is covered exactly once and no position is dropped.

**A slug-numbered casilla does not count toward diseño coverage, and that is correct.**
Coverage measures how many of AEAT's printed boxes are modelled, not how many casillas
exist. Proven on the Pag. 2 case: five new casillas moved coverage by exactly two
(72 -> 74 of 108), which is the honest arithmetic — five positions modelled, two boxes
covered.

### Not every collapse is the same shape, and the treatment differs

- **Two unrelated concepts sharing a number** — [86] is the Apartado VI "B) Suma" of
  maquinas recreativas at @672 AND the Apartado VII "Cuota maquinas recreativas" at @1044.
  Two casillas; the number stays where the box is defined.
- **Composite components of one value** — [109]'s Dia, Mes and Ano are three fields of a
  single date. That is the "composite components" class of legitimate non-casilla design
  row: ONE `date` casilla, not three integers. So [109]'s five positions become three
  casillas (Lugar, fecha, calidad), which is the honest count.
- **A repeated independent fact** — [53], [54] and [55] each head a triplet (Agrupacion /
  Grupo / Epigrafe 1o, 2o, 3o), and each of the three is a separate "S"-or-blank flag the
  filer sets independently. Three casillas each, one numbered and two slugged. NOT a
  composite: collapsing them to one casilla would lose two independent facts.

Deciding by shape rather than applying one rule everywhere is the whole content of this
convention. The first case would be wrong as a composite; the second would be wrong as
three casillas.

### What it unblocks

Apartado IV of Pag. 1 ([33]-[67], including the [53]/[54]/[55] triplets, the [62] date and
the [63] dual cause) is now authorable. The Anexo remains a separate matter: 165 fields
carrying 4 distinct numbers, almost entirely one repeating relacion-de-locales block, which
is a `binding_record` shape rather than a casilla set.

## 2026-08-22 — modelo 840 reaches 108 of 108, and one false claim on the way

The derived casilla set is complete: 121 casillas covering all 108 AEAT box numbers the
bundled aeat-dr-840 diseño prints, from 0 of 108 at the campaign start.

| unit | casillas | coverage |
|---|---|---|
| Apartado I [1]-[13] + regrounding [14][15] | 15 | 15 |
| Apartado II [16], Apartado III [17]-[32] | 17 | 32 |
| Apartado V [68]-[83] | 16 | 48 |
| Pag. 2 [84]-[108] | 24 | 72 |
| collapsed [86] and [109] | 5 | 74 |
| Apartado IV [33]-[67] | 44 | **108** |

**121 casillas against 108 boxes is the convention working, not an inconsistency.** A
slug-numbered casilla models a physical position without claiming an AEAT box, so the
casilla count tracks positions and coverage tracks boxes.

### Three refusals that mattered more than the transcription

**Box [56] does not exist and none was invented.** The printed sequence runs [55], then two
UNNUMBERED flags at @698 and @699 (campamento turístico, recepción de loterías), then [57].
The gap sits exactly where a [56] would fall — which is why minting one would have been easy,
plausible, and wrong. Both flags carry slugs.

**Box [79] and box [48] are "Pto." and their labels keep that abbreviation.** The diseño
never expands it, and each sits a few boxes from a "Pta." (Puerta). In AEAT address blocks
Pto. is ordinarily Portal — but "ordinarily" is not the standard for a filing-grade label
rendered in four languages. Expanding it needs an official source.

**`type_code` decides `data_type`, with one refinement.** Every Reservado box is `An` and
every taxpayer figure is `Num`. But a `Num` field whose value is a fixed-width CODE stays
`text`, because a leading zero is significant and an integer round-trip drops it — the
código postal, código de municipio, número, teléfono and the 13-digit N. Ref. Following
`type_code` blindly would have mis-typed five; following the label would have mis-typed nine.

### A tautological self-check, and the correction

One commit claimed 176 locale strings were applied when only 6 of 44 labels carried a value.
Two errors compounded:

1. The locale sets ran in the background and the GENERATOR's output ("wrote 176 set
   commands") was read as confirmation the SETS had run. The generator only writes the script.
2. **The verification could not have failed.** It checked whether each locale KEY appeared in
   the shard — but `scaffold` creates keys as empty drafts, so that check passes identically
   whether 176 values were set or zero were.

`test_every_casilla_label_resolves_in_the_mandatory_spanish_source` caught it and named all 38.
**The right check is the one the gate makes: count non-null `label:` values**, which is now
44 of 44 in each of es/en/ca/hu. A verification that cannot distinguish success from failure
is worse than none, because it is reported as evidence.

### What remains on this modelo, and it is not casillas

The Anexo is 165 fields carrying only 4 distinct box numbers — almost entirely one
relación-de-locales block restated with no number on any repetition. Same for most of Pag. 2,
where 24 of 110 fields are casillas. Those repetitions are the `binding_record` /
`repeat = "binding_rows"` shape modelo 720 uses. **The next question for modelo 840 is a
binding set, then a layout — not more casillas.**

## 2026-08-22 — modelo 187 took the year-mismatch trade, observed not reverted

A peer authored an export layout for modelo 187/2019-y-siguientes during this session.
It is recorded here because it is the exact trade this campaign measured and warned
against two iterations earlier, and because a third gate broke as a side effect that is
easy to misattribute.

**What happened.** `aeat-dr-187-2022` applies from 2022 onward; the revision claims
2019 onward. Authoring a layout from it moved:

- `test_filing_capability_worklist` 13 -> 12 (m187 can now emit)
- `test_layout_design_applies_to_claimed_years` gained m187, which now reports
  "claims ejercicio(s) 2019-2021 (3 year(s))" uncovered
- `test_detail_row_field_declaration_coverage::test_the_probe_answers_for_a_modelo_whose_snapshot_refuses`
  now FAILS with "DID NOT RAISE RegistryValidationError"

**The third one is the trap for whoever triages next.** That test is an ANTI-VACUITY
guard: it pins modelos 182 and 187 as genuinely refusing so the probe cannot pass by
having stopped being exercised. Giving m187 a layout made its snapshot succeed, so the
guard broke. It reads like an unrelated regression and is not — it is a direct
consequence, and m182 still refuses correctly.

**Not reverted, deliberately.** The peer is actively working this modelo and the rules
say coordinate rather than barge. Three outcomes are defensible and the choice is
theirs: acquire the 2019-2021 design and keep the layout; split the revision at 2022 so
the layout matches its own design era (the earlier era then stays unfileable, so the
worklist entry returns); or withdraw the layout. Whichever is chosen, the anti-vacuity
guard needs a refusing modelo that is still refusing.

**The general shape, restated.** Satisfying the filing worklist by authoring a layout
from a design that does not cover the revision's claimed years is a TRADE, not progress:
one gate goes green, another goes red, and the byte offsets are wrong for the uncovered
years. Modelo 181 already carries this defect. The tell named in the rules is
oscillation between two gates, and it applies here.

## 2026-08-22 — modelo 036: re-grounding, and two defects the diseño itself carries

Coverage 29 -> 59 of 288 across two units (PÁGINA 1 completed, PÁGINA 3 authored).

### The re-grounding: two sources, and they do not support the same things

The causa-110..150 fragment claimed its numbers AND labels were "transcribed verbatim
from the AEAT Instrucciones Modelo 036, Anexo 3, PÁGINA 1" and cited a bundled file.
That file is a **5.4 KB navigation shell with no casilla table**, and across all six
bundled modelo 036 instruction files the numbers 101, 103, 141, 151 and 152 appear in
none. The file's own title names Anexo 3, so **the capture dropped the table** rather
than the source lacking one — the same class as the m038 corrupt design and the m604
abridged excerpt.

Re-grounded by SPLITTING the claim rather than swapping the citation:

- **Numbers and sections → the diseño, and they check out.** The best part: the TIPO
  axis the fragment maps onto `section` is carried by the diseño itself — every
  description opens `"Alta."`, `"Modificación."` or `"Baja."`. The alta/modificación/baja
  mapping was grounded all along, just attributed to the wrong source.
- **Labels are NOT re-derived from the diseño, deliberately.** They are richer and in
  places better. The diseño carries AEAT's own typo at [130] (`"Solicitud de ata/baja"`),
  renders [142] and [143] unaccented and lowercase, and abbreviates throughout.
  Re-grounding labels on it would have DEGRADED them.

The labels diverge in ways a rendering of the diseño could not produce — [124] and [142]
carry "y baja", [129] says "alta/baja" where the diseño says "inscripción/baja", [145]
carries a page reference the diseño does not print. That divergence is itself the
evidence they came from instruction prose.

**One label corrected on that evidence:** [137] read "otros Impuestos", dropping the
"y registros" the diseño states. A narrowing of what the box covers; fixed in all four
catalogues. The other four divergences are recorded, not changed — each is plausible and
none is contradicted by the diseño. Adjudicating them needs the real Anexo 3 table.

### Two defects the diseño carries, both recorded not corrected

**A bracket with TWO numbers in it, invisible to the extractor.** PÁGINA 3's
causa-de-la-representación fields at @480+1 and @956+1 are labelled `[330 332]` and
`[380 382]`. The derived-casilla regex matches a SINGLE number inside a bracket, so
**none of 330, 332, 380 or 382 is in the derived set** — confirmed by enumerating it,
not inferred. Declaring one as `number` would claim a box the coverage report cannot
see, so both take slugs. If that regex is ever widened, these two are the first places
to re-check.

**A block mislabel.** The field at @480 is described `"3.2.- Causa de la representación"`
but sits inside block 3.1 — 3.2 does not open until @487, and its own neighbours at
@481/@483/@485 read `"3.1.-"`. The offsets are unambiguous, so the file follows the
offsets. Same judgement m840's non-monotonic numbering forced: **trust the position, not
the prose.**

### The convention keeps transferring

Boxes [141], [152], [303], [313], [353] and [363] are each ONE `date` casilla over three
component fields — the m840 convention now applied six times across two modelos without
adjustment. m036's construct is deliberately left alone: it is a censo-foundation
construct listing only profile-bound facts, and all the transcribed form boxes sit
outside it. Copying m840's construct shape here would have been wrong.

## 2026-08-22 — the coverage DENOMINATOR undercounts, and it is not a modelo 036 quirk

Every coverage figure this campaign has reported takes `build_diseno_coverage_report`'s
derived set as the number of boxes a diseño prints. For modelo 036 that is **288**. The
diseño actually prints **348**.

Sixty numbers are invisible to the derived-casilla regex, which matches `[NNN]`:

| shape | count | example |
|---|---|---|
| malformed bracket — closing only, no opening | 58 | `921]`, `922]`, `923]` |
| multi-number bracket | 4 | `[330 332]`, `[300,301,302]` |

**So "N of 288" is measured against a floor, not the true box set** — including the stamps
already written on this revision. The direction of the error flatters progress.

### The two shapes look identical in a dump and need opposite treatment

This is the part worth carrying, because getting it backwards is easy.

**A malformed bracket holds ONE number for ONE field.** PÁGINA 9 prints a well-formed
`[920]` on each sucesor block's N.I.F. and then `921]`, `922]`, `923]` on the three fields
that follow. The run 920–943 is contiguous, four per block, in offset order, verified
across all six blocks. Those casillas carry AEAT's **real numbers** — reading them is not
minting them. The regex sees 6 numbers where AEAT prints 24.

**A multi-number bracket is a SELECTOR, not a field's number.** PÁGINA 3's causa flags are
one byte each and carry `[300,301,302]`, `[311,312]`, `[330 332]`. The printed form has
three separate tick boxes (300 Alta / 301 Baja / 302 Modificación) and the fichero
collapses them into a single code byte that selects among them. **No single number
describes that field**, so it takes a slug. Assigning it "300" would claim a box the field
is not.

The tell is the field width against the count of numbers: one byte carrying three numbers
is a selector; a 125-byte name field carrying one number is a box with a broken bracket.

### What this does not change

Coverage arithmetic stays honest as authored: the 18 PÁGINA 9 casillas holding 921–943
moved coverage by **zero**, because the derived set cannot see those numbers. Casilla
counts track positions, coverage tracks regex-visible boxes, and the gap between them is
now explained by two distinct causes rather than one.

### Scoped, not left as a worry: it is modelo 036's design only

The obvious next question is whether every design this loop has measured against carries
the same undercount. Measured, and it does not:

| design | regex-visible | real | undercount |
|---|---|---|---|
| `aeat-dr-036-2025` | 288 | **348** | **60** |
| `aeat-dr-840` | 108 | 108 | 0 |
| `aeat-dr-220-2024` | 7604 | 7604 | 0 |

So modelo 840's "108 of 108" IS the true box set, and the stamps claiming it stand. The
defect belongs to the modelo 036 diseno, which is also the modelo whose instructions
capture dropped its table -- two independent transcription problems in one corpus entry.

The scan is cheap and worth re-running on any newly registered design: match a closing
bracket with no opening one, and a bracket holding two numbers separated by whitespace or
a comma, beside the normal well-formed form, then diff the sets.

## 2026-08-22 (later) — the denominator is 659, not 288 and not 348, and I was wrong twice

This entry supersedes the "348" figure recorded above. Measuring properly, the modelo 036
diseño prints **659 distinct box numbers**. The derived set sees **288** — 44% of them.

| class | count | why the regex misses it |
|---|---|---|
| plain `[NNN]` | 288 | visible; this is the derived set |
| **lettered `[A4]`, `[B94]`** | **223** | the pattern matches digits only |
| only inside a LIST bracket | 129 | `[300,301,302]`, `[B1,B2]` |
| only via a MALFORMED bracket | 19 | `921]` — closing bracket, no opening |
| **TRUE distinct boxes** | **659** | |

### Two things I asserted that were wrong

**"348" was itself an undercount.** The first correction scanned for malformed and
multi-number brackets but not for LETTERED boxes, which are the largest class by far. A
scan that finds one invisibility class is not evidence there is only one.

**"Pág. 0, 2A and 2C carry no box numbers at all, being repeating or structural records"
— stated in a stamp — is wrong for two of the three.** Measured per record:

| record | fields | plain digits | real boxes |
|---|---|---|---|
| Pág. 0 | 15 | 0 | **0** — genuinely the envelope, the claim holds here |
| Pág. 2A | 118 | 0 | **83** |
| Pág. 2C | 85 | 0 | **57** |

Pág. 2A is the *persona física* identity and domicilio record — `[A4]` N.I.F./N.I.E.,
`[A5]` Apellido 1, `[A11]` Tipo de vía. It is not structural and never was. The reason it
looked structural is exactly the reason it is uncovered: **its boxes are lettered, so the
derived set reports zero for it, and zero derived reads as "no boxes" if you do not
check the descriptions.**

### The lesson, which is about the instrument and not this modelo

Three times now a measurement has been taken from a derived count without asking what
the deriving code can see. The tiling check, the coverage report and this box census all
answer a narrower question than the one being asked of them. **A derived zero is not
evidence of absence; it is evidence the deriver found nothing it recognises.**

Scope, re-measured with the full pattern: `aeat-dr-840` and `aeat-dr-220-2024` still show
**zero** undercount — they use plain numbering throughout — so modelo 840's "108 of 108"
remains the true box set and its stamps stand. The defect is the modelo 036 diseño's
alone, and it now has three independent transcription problems: lettered boxes the regex
cannot read, malformed brackets, and an instructions capture that dropped its table.

### What this does to the campaign's figures

m036 coverage reads "65 of 288". Against the true set it is **65 of 659 — under 10%**.
Nothing authored is wrong; the casillas and their numbers are all read from the design.
What was wrong is every denominator I have reported for this modelo, and the direction of
the error consistently flattered progress.

## 2026-08-22 (later still) — Pagina 2A authored, and the denominator moved a fourth time

### What landed

Modelo 036 Pag. 2A is authored: **104 casillas covering all 86 box numbers it
prints**, plus 18 slugs for fields carrying no printed number. Every offset, length
and number was cross-checked back against the design row it came from — 86 design
numbers, 86 authored, zero missing, zero invented, zero length mismatches. The record
tiles 1..2000 exactly once. All 199 modelo 036 labels resolve to non-null values
across es/en/ca/hu, verified by counting **values**, not keys.

This is the record a previous stamp declared to have no boxes at all.

### The denominator has now been reported four times, and every figure was a floor

| reported | by what pattern | wrong because |
|---|---|---|
| 288 | `\[\d+\]` | misses lettered, list and malformed brackets |
| 348 | + malformed, + multi-number | **misses lettered boxes**, the largest class |
| 659 | + lettered | misses the parenthesised form `(a28)` |
| **667** | + parenthesised | current best; still only a floor |

**This is the same instrument error four times, committed inside the very tool built
to detect the instrument error.** Each pass widened the pattern, found more, and each
time the new figure was reported as though it were the true set. It was not. It was
the largest number that pattern could see.

The honest form of the claim is not "modelo 036 prints 667 boxes". It is: **a pattern
admitting five bracket forms finds 667 distinct box numbers, and nothing establishes
that a sixth form does not exist.** Any coverage denominator derived by pattern-match
over prose carries that caveat and should state it.

Current coverage, on that basis: **169 of 667 (25%)** — 83 plain-digit boxes and 86
lettered. 498 remain.

### A latent corpus hazard, found by accident, and a mistake made chasing it

Mid-iteration the registry suite went from 8 failures to **742 failed / 203 errors**.
Root cause was not any registry edit: `source 'boe-modelo-194-form-layout' byte count
mismatch`. The corpus file `corpus/normatives/html/orden-1999-11-18.html` was 104069
bytes on disk against a declared and committed 103935 — a delta of exactly 134 bytes,
being 134 CRLF pairs.

**`git status` reported the file as unmodified throughout.** `.gitattributes` sets
`* text=auto eol=lf`, so git normalises CRLF away on commit: the corrupted working
file and the clean blob are indistinguishable to git, while the validator — which
reads the bytes on disk and hashes them — sees a broken content-addressed artefact.
The corruption is invisible to the tool everyone checks and fatal to the tool nobody
checks until the suite reds.

The mechanism is a Python text-mode write on Windows translating `\n` to `\r\n`.
Any script that authors a corpus file with `open(...,'w')` or `write_text` **without
`newline=""`** silently corrupts it.

`.gitattributes` already protects `corpus/aeat_official/**` with `-text`, and its own
comment states the reason exactly: "a rewritten byte is not a cosmetic difference — it
invalidates the artefact and whatever conclusion was drawn from it." **The sibling
tree `corpus/normatives/` carries the same content-addressed evidence and has no such
protection.** Extending `-text` to it would not stop a bad script writing CRLF, but it
would make the damage VISIBLE in `git status` instead of silently normalised. Not
applied here: it changes checkout semantics for 1406 committed files and deserves its
own reviewed change rather than a drive-by inside a loop iteration.

**The mistake, recorded because it was mine and it was destructive.** Chasing this, a
blanket "replace CRLF with LF across `corpus/normatives/`" was run. It rewrote two
PDFs — `boe-a-2023-17429-modelo-721-layout.pdf` and its 2024 amendment — shrinking
them by 4 and 8 bytes, because **`\r\n` inside a PDF is binary content, not a line
ending.** Both were restored byte-exact from git and verified by size and hash; no
damage persists. The lesson generalises past PDFs: a whitespace or line-ending
normalisation must be scoped by FORMAT, never by directory, and content-addressed
evidence is the last place to run a blanket rewrite.

## 2026-08-22 — Pagina 2C authored, and two modelos have crossed into AUTHORABLE

### What landed

Modelo 036 Pag. 2C: **73 casillas covering all 57 box numbers it prints**, plus 16
slugs. The revision is now **272 casillas, 226 of 667 real boxes (34%)**, up from
169. Zero missing, zero invented, zero length mismatches; the record tiles 1..1400
exactly once. 292 locale strings applied; all 272 label keys verified non-null by
counting values across es/en/ca/hu. Suite: **zero regressions** against the previous
run's FAILED list, and the two reviewability failures from the prior iteration are
now green.

This completes the retraction begun with Pag. 2A. The claim "Pag. 0, 2A and 2C carry
no box numbers at all" was true of Pag. 0 alone: 2A prints 86, 2C prints 57, all of
them lettered and therefore invisible to a digits-only regex.

### The loop's prerequisite is now MET for two modelos — the next unit is different

The v7 brief's premise is that the filing worklist is a casilla backlog, and that a
revision with 2 casillas against a 381-field design cannot carry a real layout. That
was correct, and it is now discharged for two entries. The worklist gate reports:

| revision | worklist status |
|---|---|
| 840 / 2003-y-siguientes | **AUTHORABLE on era** — cites `aeat-dr-840`, **121 casillas** — needs its semantic map and layout |
| 036 / 2025-02-03-y-siguientes | **AUTHORABLE on era** — cites `aeat-dr-036-2025`, **272 casillas** — needs its semantic map and layout |
| 220 / 2024 | AUTHORABLE on era — 2 casillas — casilla set still the blocker |
| 390 / 2021 | AUTHORABLE on era — 10 casillas |

**So "author the casilla set" is no longer the right next unit for 840 or 036.** What
they need is the semantic map and the export layout. The gate names its own
precondition for that work: *the design's extraction must be checked for PARTIAL
OVERLAP first* (`test_cited_design_field_bounds_are_self_consistent`) — a gap-only
tiling check is insufficient, because partial overlap leaves no holes.

Modelo 840 is the smaller and better-shaped first target: 121 casillas over 108 boxes
across 3 records, against modelo 036's 272 casillas over 13 records of which 8 remain
wholly unauthored.

Note this does NOT reopen the v6 instruction. v6 failed because it asked for layouts
on revisions holding 2 casillas. The precondition it lacked is exactly what these two
iterations built.

### Remaining modelo 036 work, exactly quantified

441 of 667 boxes unmodelled: Pag. 5 (107), Pag. 2B (98), Pag. 4 (88), Pag. 6 (52),
Pag. 7 (42), Pag. 10 (24), Pag. 8 (16), and 14 still open on Pag. 3. Pag. 0 is the
envelope and has none.

### Two transcription judgements recorded rather than buried

**C68 and C69 name the wrong entity in AEAT's own text.** Both descriptions open
"Persona Fisica." while sitting inside the establecimiento permanente record and
numbered in its C series. Read as a copy-paste artefact in the published spreadsheet;
the labels describe the record the fields actually belong to. This is a *judgement*
about AEAT's text rather than a transcription of it, so it is flagged in the fragment
and in the stamp instead of being silently normalised.

**Slug numbers collide across records.** Pag. 2C's unnumbered fields carry the same
names as Pag. 2A's (`codigo-via-ine`, `aeat-alta`), and `(segmento, number)`
uniqueness is enforced revision-wide. The collision was surfaced by the loader
refusing the first attempt, not anticipated — worth remembering when authoring any
second record of a modelo whose records repeat a block structure.

## 2026-08-22 — modelo 220 opened: the first position mapping, and the design is fully overlap-clean

### What landed

Record **T22001000** of modelo 220 revision 2024: **77 casillas**, taking the revision
from 2 to 79. It is the grupo fiscal declarante record — identificación of the
representante or dominante, periodo impositivo, the dominante, fourteen CNAE
activities, twelve tipo-de-grupo flags, the INCN tranche, three legal representatives
and the incidencias contact.

This is the **first casilla-to-position mapping ever authored for this modelo**. The
revision's own fragment previously recorded that none existed, so a number was not
invented; that prose was corrected in the same commit rather than left describing a
state that no longer holds.

### The whole design is overlap-clean — measured once, useful for every future iteration

The filing-capability worklist names its own precondition for authoring against this
design: the extraction must be checked for **partial overlap**, not merely for gaps,
because partial overlap leaves no holes and a gap-only check passes straight over it.

Measured across **all 137 records / 16 079 fields of `aeat-dr-220-2024`: zero partial
overlaps, zero gaps.** The precondition is satisfied for the entire design, not just
the record authored here. That removes a per-record risk from every remaining
iteration on this modelo — though each record's own tiling is still worth asserting
before its offsets are used, since the check is cheap.

### A stronger completeness discipline than previous iterations

Earlier records were verified by confirming that every authored row matched its design
row. That catches fabrication but not omission. This record adds the complement:
**every one of the design's 91 fields is either authored or explicitly excluded with a
stated reason**, and the set difference is asserted empty. Nothing is unaccounted for.

The fourteen exclusions, each named in the fragment: the six-field modelo/página
identifier envelope; the two página-complementaria mechanics fields (borderline —
recorded as such rather than silently dropped); the administration-reserved tipo de
declaración; `@106` ejercicio (the same fact as the existing `decl.ejercicio`, which a
layout will bind to that position — a second casilla would double-declare one value);
the filing-program "inoperatividad de la ayuda al cálculo" flag; and the reservado,
sello electrónico and fin-de-registro runs.

**This is worth adopting as the standard check.** "Every authored row is real" and
"every real field is accounted for" are different claims, and only the second one
bounds the undercount.

### Generated runs are proven against the design, not trusted to arithmetic

Two runs in this record are regular enough to generate: the fourteen CNAE
epigrafe/descripción pairs step 65 positions from 258, and the three representante
legal blocks step 65 from 1196. Both were confirmed to land exactly where the next
declared block begins (1168 and 1391 respectively) — but each generated offset was
still cross-checked individually against its own design row. A stride that lands
correctly at both ends can still be wrong in the middle.

### Scale, stated honestly

7604 distinct AEAT box numbers in the design; **12 modelled** (the bracket-numbered
caracteres flags), 7592 remaining. This record is roughly **one half of one percent**
of the box set, and 136 of 137 records are untouched. Modelo 220 is a long haul at one
record per iteration; the value of this iteration is that the modelo is now open and
its conventions are settled, not that the backlog moved materially.

### Suite

14 failures, unchanged in count. One new entry —
`test_loader_cache_isolation::test_bundled_root_disk_cache_is_shared_across_processes`
— **is a parallel-run flake, not a regression**: all 11 tests in that module pass
single-process (`-n0`). The m390 fragment-naming failure was fixed by a peer in the
same window.

## 2026-08-22 — Pagina 2B authored: the three identity records are complete, and AEAT collides with itself

### What landed

Modelo 036 Pag. 2B: **119 casillas covering 96 of the 98 box numbers it prints**, plus
23 slugs. Revision now **391 casillas, 322 of 667 real boxes (48%)**, up from 226.

This completes the modelo's **three identity records**: Pag. 2A persona física, Pag. 2B
persona jurídica o entidad, Pag. 2C establecimiento permanente of a non-resident entity.

Pag. 2B is also the only one of the three the derived set can partly see: its
personalidad jurídica block carries plain-digit boxes (65, 68, 69, 70, 71, 73, 75, 77,
78, 79) alongside the lettered B series. 2A and 2C are wholly lettered and moved the
derived report by zero.

### AEAT prints [B72], [B74] and [B76] TWICE EACH in one record

Confirmed against the raw cell text, not inferred from a parse. The two homes:

| home | evidence |
|---|---|
| domicilio social block | **B71…B85 is a complete, coherent run** — B71 tipo de vía, B72 nombre de la vía, B73 tipo núm., B74 núm casa, B75 calif., B76 bloque … B85 código de provincia |
| personalidad jurídica, `@1734` `@1737` `@1740` | neighbours are **plain digits** — 70, 71, 73, 75, 77 — so the three B-prefixed entries interrupt an otherwise unbroken plain sequence |

The domicilio social fields keep the numbers; the personalidad jurídica fields take
slugs, per the modelo 604 precedent that a field naming *another* box's number keeps a
slug. Revision-wide `(segmento, number)` uniqueness made duplication unavailable anyway.

**What was deliberately not done.** The plain run strongly suggests AEAT meant [72],
[74], [76]. That reading is an **inference, not a transcription**, so those numbers were
not adopted — the registry does not assert a box number AEAT did not print. The
distinction is the whole discipline: a plausible reconstruction of what a source *meant*
is not evidence of what it *says*.

### An error I made, and the step that caught it

`@11+1` prints `[B1,B2]` — one selecting code byte behind two printed tick boxes
(residente/constituida en España, or no residente/constituida en el extranjero). My
extraction's fallback pattern matched the trailing `B2]` and I adopted **B2** as the
casilla number.

That is exactly the mistake this modelo's own Pag. 3 fragment warns about, and a rule I
had written down before breaking it: **where one byte carries a bracket LISTING several
numbers, no single number describes the field, so it takes a slug.** The tell is field
width against number count.

It now takes a slug, and B1 and B2 are both unmodelled *as numbers* — correct rather
than a gap, since neither names the field alone. The fragment says so explicitly so a
later reader does not "fix" it back.

**The step that caught it is worth keeping: re-measure coverage per record AFTER
authoring, rather than trusting the authoring pass.** The authoring pass and the
verification pass used the same extraction, so they agreed with each other and were both
wrong; the per-record coverage scan used a wider pattern and disagreed. Two passes that
share a parser cannot check each other.

### Remaining modelo 036 work

345 of 667 boxes: Pag. 5 (107), Pag. 4 (88), Pag. 6 (52), Pag. 7 (42), Pag. 10 (24),
Pag. 8 (16), 14 still open on Pag. 3, plus B1/B2 correctly unmodelled. Pag. 0 is the
envelope.

### Incidental

Casilla ids cap at **64 characters**, and this record's section names overflow it
(`domicilio_residencia_extranjero` is 31 on its own). Its ids use a short token per
section while the section path keeps its full name; 2A and 2C did not need this, so the
three identity records are internally consistent but not identical in id shape.

Suite: **13 failures, zero new.** The `test_loader_cache_isolation` entry from the
previous run is gone, confirming it was a parallel flake. A collection ERROR in
`test_binding_coverage_breadth` was a peer's in-flight rename
(`_ENROLLED_SOURCE_KINDS` → `ENROLLED_SOURCE_KINDS`), already fixed uncommitted in their
working tree and passing; left for them.

## 2026-08-22 — Pagina 5 (IVA) authored, a sixth bracket form found, and coverage split three ways

### What landed

Modelo 036 Pag. 5: **68 casillas over its 115 fields** — 54 carrying an AEAT number,
14 slugs. Revision now **459 casillas**. It is the IVA record: obligaciones, inicio de
actividad, regímenes, registros, prorrata y sectores diferenciados, ingreso del IVA a
la importación, llevanza de libros, facturación por terceros.

Zero mismatches, zero invented, zero missed; all 115 fields authored, a collapsed date
component, or explicitly excluded. Tiles 1..380 exactly once, no gap, no partial
overlap. Suite: **13 failures, zero new, zero gone, no collection errors.**

### The sixth bracket form — the previous stamp's caveat came true

The last stamp said 667 was "what a pattern admitting five bracket forms finds, and
nothing establishes a sixth does not exist." One exists.

`@273+1` prints its numbers as a **parenthesised list** — `(532,737)` — where every
other multi-number field on this modelo uses a square-bracketed one. None of the five
patterns could see it. **Denominator: 667 → 669.**

| # | denominator | what the correction added |
|---|---|---|
| 1 | 288 | `[NNN]` only |
| 2 | 348 | malformed + multi-number brackets |
| 3 | 659 | lettered boxes (the largest class) |
| 4 | 667 | parenthesised single `(a28)` |
| 5 | **669** | **parenthesised LIST `(532,737)`** |

Every correction came from widening the pattern, never from reading the design
differently. Two numbers is trivial in magnitude; the pattern is not. **The caveat
stands unchanged for a seventh form.**

### Coverage now needs THREE numbers, not one

A single "remaining" figure conflates an unmodelled field with a modelled one, and
overstates the gap by 57:

| state | count | meaning |
|---|---|---|
| directly modelled | **376** | each number on its own casilla |
| behind a slug casilla | **57** | Pag. 5: 55, Pag. 2B: 2 — **the FIELD is modelled**; the number is not individually addressable because AEAT prints several on one byte |
| no casilla at all | **236** | Pag. 4 (88), Pag. 6 (52), Pag. 7 (42), Pag. 10 (24), Pag. 8 (16), Pag. 3 (14) |

Reporting "293 remaining" would be true arithmetic and a false picture. **This split is
worth carrying to any modelo whose design collapses several printed tick boxes onto one
selecting byte.**

### List brackets: Pag. 5 has more than any other record

19 fields carry a bracket listing several numbers, 53 numbers between them. The
regímenes de agricultura, simplificado and criterio de caja each print **five numbers on
one byte** — alta, baja, renuncia, revocación, inclusión — collapsed into a single
selecting code byte. No single number describes such a field, so each takes a slug.

Those numbers are deliberately not modelled individually, and the fragment says so
explicitly, so a later reader does not split one byte into five casillas. **The tell is
field width against number count** — one byte cannot hold five independent values.

### Remaining modelo 036 work

236 boxes with no casilla: Pag. 4 (88), Pag. 6 (52), Pag. 7 (42), Pag. 10 (24), Pag. 8
(16), Pag. 3 (14). Authored: Pag. 1, 2A, 2B, 2C, 5, 9 and most of 3. Pag. 0 is the
envelope.

## 2026-08-22 — Pagina 4 authored, and the box count moves in BOTH directions for the first time

### What landed

Modelo 036 Pag. 4: **92 casillas over its 130 fields** — 91 numbered, 1 slug. Revision
now **551 casillas**. Pag. 4 is actividades y locales: the declared activity, its
I.A.E. classification, activity outside a fixed local, two locales directly affected
and two indirectly.

Zero mismatches, zero invented, zero missed; all 130 fields authored, collapsed, or
explicitly excluded. Tiles 1..900 exactly once, no gap, no partial overlap. Suite:
**13 failures, zero new, zero gone.**

### The measurement is noisy in BOTH directions — this is new

Five previous corrections to this modelo's denominator all **added** numbers a narrower
pattern had missed, and could be read as monotone progress toward a true value. This
record breaks that reading:

| direction | finding | effect |
|---|---|---|
| **added** | a **seventh number form**: `NNNbis` — `[412bis]`, `[433bis]`, `[454bis]`, `[4774bis]`. Every pattern so far allowed at most ONE trailing letter | **+4** |
| **removed** | a **false positive**, the first found: the four "Superficie **(m2)**" fields print the UNIT in parentheses, and `(m2)` matches a bracketed-number pattern exactly as a real box would. `m2` was counted as a box in **every** denominator reported for this modelo | **−1** |

**669 − 1 + 4 = 672.**

The sharper lesson: widening a pattern does not only reveal undercounting, **it also
admits noise**. A token that merely *looks* like a box number is not one. Any
pattern-derived count over prose carries error in both directions, and the honest form
of the claim remains "a pattern admitting N forms, less known unit strings, finds X".

Full history: 288 → 348 → 659 → 667 → 669 → **672**.

### `[4774bis]` is AEAT's typo, transcribed as printed

The other three indicators each pair with their own block's referencia catastral —
412bis/[412], 433bis/[433], 454bis/[454] — and the second indirect block's is **[477]**,
so the pattern points at `477bis`. That is an **inference, not a transcription**, and is
not adopted, exactly as the `[B72]`/`[B74]`/`[B76]` collision on Pag. 2B was left as
printed. Third time this distinction has decided an authoring choice on this modelo.

### One number over two adjacent fields

`[402]` is printed on **both** `@71+1` (sección del I.A.E.) and `@72+4` (grupo o
epígrafe) — contiguous fields that together form the single classification the box
names. One casilla of five positions, same convention as the date triples.

### Coverage, three ways

| state | count |
|---|---|
| directly modelled | **467** |
| behind a slug casilla (field modelled, number not individually addressable) | **57** — Pag. 5: 55, Pag. 2B: 2 |
| no casilla at all | **148** — Pag. 6 (52), Pag. 7 (42), Pag. 10 (24), Pag. 8 (16), Pag. 3 (14) |

Authored: Pag. 1, 2A, 2B, 2C, 4, 5, 9 and most of 3. Pag. 0 is the envelope.

### Note on capture

This iteration's fragments were absorbed by a peer's bare commit before my own pathspec
commit ran — the accepted scenario, and the reason every real claim lives in the
fragment header and the `reviewed_by` stamp rather than in a commit message. Nothing
was lost; the commit message simply never existed.

## 2026-08-22 — Pagina 6 authored, a second false-positive class, and one number over a whole block

### What landed

Modelo 036 Pag. 6: **47 casillas over its 88 fields** — 25 numbered, 22 slugs. Revision
now **598 casillas**. It carries the IRPF obligations and rendimiento method, the
Impuesto sobre Sociedades obligations and exenciones, the IRNR establecimiento
permanente modalidad, and the Ley 49/2002 special-regime election.

Zero mismatches, zero invented, zero missed; all 88 fields authored, collapsed, or
explicitly excluded. Tiles 1..400 exactly once, no gap, no partial overlap. Suite:
**13 failures, zero new, zero gone.**

### A second false-positive class, larger than the first

Pag. 4 established that a token which merely *looks* like a box number is not one —
`(m2)` in "Superficie (m2)" was counted as a box called `m2`. This record carries a
bigger instance of the same error:

**Twenty-four fields** open `IRPF. (1) Si determinaba el rendimiento neto…` or
`(2) Si determinaba…`, where `(1)` and `(2)` are **footnote markers** keyed to notes
printed below the form. Both matched a parenthesised-number pattern and were counted as
boxes `1` and `2` in every denominator reported for this modelo.

**Corrected: 670** (seven-form set, less the three noise tokens `m2`, `1`, `2`).

Seven denominators now: 288 → 348 → 659 → 667 → 669 → 672 → **670**. **The two most
recent moved in opposite directions**, and that is the substantive point rather than any
single figure: a pattern applied to prose mis-measures in *both* directions. No count
derived this way is the design's true box total — it is what a stated pattern, less
stated noise, finds.

### One number over a whole repeating block — a shape not previously met

AEAT prints `[613]` over **all twelve fields** of the estimación objetiva activity block
and `[614]` over all twelve of the modalidad simplificada block. Each block is four
activity rows of sección I.A.E. / grupo o epígrafe / tipo de actividad.

No single field owns either number, so all sixteen casillas take slugs, and 613/614 join
the numbers covered by a modelled *field* without being individually addressable — the
same state as a list bracket.

Both rejected alternatives are worth stating, because both are plausible:

- splitting one number across four rows would **assert four boxes AEAT does not print**;
- collapsing four rows into one casilla would **lose four distinct declared activities**.

Within each row, sección + grupo o epígrafe become one casilla and tipo de actividad
another — the same split Pag. 4's design declares explicitly for `[402]` and `[403]`.

### `[640]` is a two-component date, not a truncated triple

The design declares only `@129+2` día and `@131+2` mes for *fecha de cierre del
ejercicio económico*, with **no año component** — an annual closing date being a day and
a month. The casilla spans four positions, not eight. Recorded explicitly so a later
reader does not "restore" a year field that was never there.

### Coverage, three ways

| state | count |
|---|---|
| directly modelled | **492** |
| behind a slug casilla | **82** — Pag. 5: 55, Pag. 6: 25, Pag. 2B: 2 |
| no casilla at all | **96** — Pag. 7 (42), Pag. 10 (24), Pag. 8 (16), Pag. 3 (14) |

Authored: Pag. 1, 2A, 2B, 2C, 4, 5, 6, 9 and most of 3. Pag. 0 is the envelope.
Three records remain plus the Pag. 3 remainder.

## 2026-08-23 — Pagina 7 authored, and an eighth number form

### What landed

Modelo 036 Pag. 7: **42 casillas over its 84 fields** — 38 numbered, 4 slugs. Revision
now **640 casillas**. It carries retenciones e ingresos a cuenta across eight income
kinds, impuestos especiales, adquisiciones intracomunitarias, impuestos
medioambientales, servicios digitales, the two telecomunicaciones regimes, and the
registro de extractores de depósitos fiscales.

Zero mismatches, zero invented, zero missed; all 84 fields authored, collapsed, or
explicitly excluded. Tiles 1..400 exactly once, no gap, no partial overlap. Suite:
**13 failures, zero new, zero gone.**

### An eighth number form: the dotted suffix

The extractores block prints `[716.a]`, `[717.a]`, `[716.b]`, `[717.b]` — a number, a
full stop, then a letter. Every pattern used on this modelo allowed a trailing letter
attached **directly** (`A4`, `412bis`) but never one behind a separator, so all four
were invisible. Their bare stems `716` and `717` appear nowhere else in the design
either, so these are not mis-parsed variants of numbers already counted. **+4 → 674.**

The pair is semantically clear despite the new form: `716` is the alta/baja flag and
`717` its fecha, with `.a` for alcohol y bebidas derivadas and `.b` for hidrocarburos.
The suffix distinguishes two product scopes of the **same** registro — which is why AEAT
numbered them as variants rather than as separate boxes. That reading comes from the two
field descriptions, which differ only in product scope; it is not inferred from the
numbering shape.

### Eight denominators, and what the sequence now shows

288 → 348 → 659 → 667 → 669 → 672 → 670 → **674**.

The point is no longer that the count keeps moving. It is that **the last three
corrections each found a different KIND of error** — a missing form, then a false
positive, then another missing form. The error is not converging on a residual of one
type that could be bounded and closed out; each pass finds a new category. A count
derived by pattern-matching prose is a measurement carrying error in both directions,
and should always be stated as "what a stated pattern, less stated noise, finds".

### Coverage, three ways

| state | count |
|---|---|
| directly modelled | **530** |
| behind a slug casilla | **90** — Pag. 5: 55, Pag. 6: 25, Pag. 7: 8, Pag. 2B: 2 |
| no casilla at all | **54** — Pag. 10 (24), Pag. 8 (16), Pag. 3 (14) |

Authored: Pag. 1, 2A, 2B, 2C, 4, 5, 6, 7, 9 and most of 3. Pag. 0 is the envelope.
**Two records remain plus the Pag. 3 remainder.**

## 2026-08-23 — Paginas 8 and 10 authored: every record of modelo 036 now has a casilla set

### The milestone, stated carefully

Modelo 036 revision `2025-02-03-y-siguientes` now carries **706 casillas across all
thirteen records**. Coverage:

| state | count |
|---|---|
| directly modelled | **541** |
| behind a slug casilla (field modelled, number not individually addressable) | **133** |
| **no casilla at all** | **0** |

Zero is the milestone, and it means exactly one thing: **no field of any record is
undeclared**. It does *not* mean every number is individually addressable, and it does
*not* mean the modelo can be filed. A complete casilla set is the **prerequisite** for a
layout, which is what this loop exists to build — not a substitute for one.

Suite: **13 failures, zero new, zero gone.**

### Two repeating records, modelled differently — the number set decides, not the shape

This is the reusable finding.

| record | blocks | numbers | modelled as |
|---|---|---|---|
| Pag. 8 socios | 4 × 13 fields, stride 357 | **identical across blocks** — every block's N.I.F. is `[800]`, every fecha `[805]` | **ONE row**, 10 casillas |
| Pag. 10 titulares | 6 × 13 fields, stride 284 | **distinct per block** — 1000-1003, 1004-1007 … 1020-1023 | **six blocks**, 54 casillas |
| Pag. 9 sucesores | 6 blocks | distinct — 920-943 | six blocks (earlier iteration) |

Verified rather than assumed: Pag. 8's four per-block number sets were compared directly
and found identical.

The reasoning: a casilla is **offset-free** — it carries a number, never a position — so
when four blocks share one number set, those numbers describe a *row*, and one row is
the complete description of what the taxpayer declares. The four physical blocks are a
**layout** concern, for the repeat mechanism, exactly as modelo 720's `binding_record`
handles its repeating rows.

**Both rejected alternatives are recorded in the fragment, because both are tempting:**

- authoring four blocks needs three sets of **invented** slug numbers, asserting twelve
  boxes AEAT does not print;
- giving 12a the real numbers while 12b–d take slugs **privileges one block** over three
  identical ones, which the design does not do.

**A warning is written into the fragment for whoever authors the layout:** mapping
Pag. 8's ten casillas once, at offsets 11–167, leaves blocks 12b, 12c and 12d unfilled.
The repeat is required — stride 357, count 4.

### The completeness complement earned its keep

Reading Pag. 10 block-by-block accounted for 88 of its 90 fields. Asserting the
complement — every field either authored or explicitly excluded — surfaced **two
record-level fields sitting after the six blocks**: "declaración de no variación de
datos" (`@1715+1`) and "entidad sin obligación de identificar al titular real"
(`@1716+1`). Both are filer-supplied and carry no printed number.

A block-shaped reading would have dropped both silently, and nothing else in the process
would have caught them. This is the second time the complement has found something the
primary reading missed.

### The denominator remains a measurement

674: what a pattern admitting **eight** bracket forms finds, less the three known noise
tokens (`m2`, `1`, `2`). Across the campaign: 288 → 348 → 659 → 667 → 669 → 672 → 670 →
674. The last three corrections each found a *different kind* of error, so the error is
not converging on a residual of one type. **A ninth form may exist.**

### What modelo 036 still needs

A semantic map and an export layout. The filing-capability worklist has reported it
AUTHORABLE since the casilla count passed 272; the casilla work is now finished, and the
remaining 133 non-addressable numbers are a property of AEAT's numbering, not a gap.

## 2026-08-23 — modelo 220 T22002000, and the repeating-record rule now holds across two modelos

### What landed

Modelo 220 record **T22002000** (entidades del grupo en régimen de consolidación
fiscal): **16 casillas** — the entidad dominante block and **one** entidad dependiente
row. Revision 79 → **95 casillas**. Second of the design's 137 records.

Suite: **14 failures, one new, and it is not mine** —
`test_inss_maternidad_paternidad_art7h::test_help_exposes_prestacion_inss_exenta` is a
CLI help assertion that passes in isolation (`-n0`, 5 passed); this iteration touched
only registry TOML and locale catalogues.

### The rule, now stated at full strength: THE NUMBER SET DECIDES, NOT THE REPETITION

Four repeating records have now been authored across two modelos, and the decision has
gone both ways on a consistent principle:

| record | blocks | AEAT numbers across blocks | authored as |
|---|---|---|---|
| m036 Pag. 9 sucesores | 6 | **distinct** (920–943) | six blocks |
| m036 Pag. 10 titulares | 6 | **distinct** (1000–1023) | six blocks |
| m036 Pag. 8 socios | 4 | **identical** ([800] on every block's NIF) | one row |
| m220 T22002000 | 20 | **none at all** | one row |

Where AEAT numbers the rows apart, author them apart; where it does not, author the row.

T22002000 is the sharpest case because it prints **no box numbers anywhere** — all 197
fields are unnumbered, and the twenty blocks are distinguished only by an ordinal
appended to each description (`NIF. 1`, `NIF. 2`). The byte-span number those casillas
carry is **our** convention (modelo 181's), not AEAT's.

That is exactly why one row is right: minting twenty sets of byte-span numbers would
assert 180 distinct declared boxes where the design declares one repeating row of nine
fields — and would put our own invention on the same footing as AEAT's numbering
everywhere else in the registry. A casilla is offset-free, so one row is the complete
description of what a member entity declares; the repetition is a layout concern for the
repeat mechanism (`binding_record`).

**The block count is arithmetic, not an estimate:** nine-field blocks start at @128 with
stride 122 and end exactly at @2568 where the reservado begins — (2568−128)/122 = 20.

**Warning written into the fragment:** a layout mapping these nine casillas once, at
@128–@249, leaves nineteen blocks unfilled. Repeat required — stride 122, count 20.

### Completeness accounting extended to cover repeats

The complement check now has three buckets rather than two. All 197 fields are:
**16 authored + 171 covered by the nineteen repeat blocks + 10 explicitly excluded**,
difference empty. Counting repeat-covered fields as accounted-for is what lets a
one-row declaration still prove it left nothing behind.

### Scale, stated so the casilla count is not misread

135 of 137 records unauthored; **7592 of 7604 AEAT box numbers unmodelled**. The twelve
modelled numbers are all on T22001000. **This record adds none, because it prints none.**
Progress on modelo 220 must not be read from the casilla count — 95 casillas describe
two records out of 137.

## 2026-08-23 — modelo 220 T22012000: 180 numbered casillas, and a decomposition that had to be checked

### What landed

Modelo 220 record **T22012000** — deducciones por doble imposición (interna RDLEG
4/2004, interna DT 23ª LIS, internacional RDLEG 4/2004, internacional LIS, plus the tipo
de gravamen): **180 casillas, every one carrying a real AEAT box number.** Revision 95 →
**275 casillas**. Third of 137 records.

First record on this modelo where *every* casilla is numbered — T22001000 numbered 12 of
77, T22002000 numbered none because it prints none. This one is a numbered grid: 179
money cells of 17 positions plus the tipo de gravamen, a distinct number on each, so
there is nothing to collapse and no slug anywhere.

Suite: **13 failures, zero new**, and the previous iteration's CLI-help entry is gone —
confirming it was the flake it looked like.

### The finding: a derived id needs a uniqueness check, or it silently merges cells

The 180 descriptions were decomposed into four closed axes — **family** (5 values),
**group** (6), **scope** (22), **column** (6) — and the decomposition was verified two
ways *before any id was minted*:

1. every one of the 180 resolves into known vocabulary, **nothing unresolved**;
2. the resulting four-part keys are **unique across all 180, no collision**.

**Check 2 earned its keep immediately.** A first attempt used only three axes and
produced **seven colliding keys covering nineteen numbers** — ids that would have merged
distinct cells and silently mis-declared them. The missing axis was the group qualifier
AEAT prints before a colon: `DI interna ejerc. anteriores:`, `DI jurídica … art. 31 LIS`,
`DI económica … art. 32 LIS`, `Total 2024`.

Nothing downstream would have caught it. The registry enforces unique `number`, and the
numbers were fine — it was the *ids* that collided, and an id collision inside one
generator run just means the later row overwrites the earlier in a dict, or trips an
assert only if you wrote one. **Whenever a casilla id is derived rather than transcribed,
assert the derived keys are unique before minting them.**

A third, independent confirmation came free: the 180 Spanish labels are composed from the
same four axes and are **all distinct, zero duplicates**. Two casillas describing the same
thing would have surfaced there.

### AEAT misspells its own section heading four ways

`RDLEG 4/2004`, `RDLEG4/2004`, `RDL 4/2004`, `RDLRG 4/2004` — plus two truncated column
labels (`licado en esta liquidación`). All are **matched deliberately** so the
decomposition reflects what the design says; the casilla *labels* use the corrected form,
because a label is read by an operator while the match is read against AEAT. Third
distinct class of source-text noise found on these designs, after the unit strings (`m2`)
and the footnote markers (`(1)`, `(2)`).

### Stated so a complete record is not mistaken for a modelled calculation

These 180 casillas **declare** the deduction grid; none of them **computes** it. No
formula, construct or binding is attached, so nothing reconciles a carried-forward
deduction against the amount applied, and nothing checks that pendiente-futuro equals
pendiente minus aplicado. 134 of 137 records remain unauthored and **7412 of 7604 AEAT
numbers remain unmodelled** — 275 casillas describe three records.

## 2026-08-23 — modelo 220 is MULTI-SEGMENT: three conventions I invented that already existed

### What landed

Modelo 220 record **T22012B00** authored and **T22012000 re-authored**: 344 casillas
across the two deduction-grid records, every one carrying a real AEAT box number.
Revision 275 → **439 casillas**, four of 137 records. Suite back to **13 failures, zero
net regressions**.

### AEAT reuses box numbers across records — the modelo is multi-segment

Number `00285` is a **different declared cell** in T22012000 than in T22012B00, and the
two records share many such numbers. The loader refuses bare casilla ids for such a
modelo. Every casilla in both records now declares `segmento` and takes the
`<SEGMENTO>:<number>` id shape — **the convention modelo 200 already established.**

### The finding: three conventions reached for by guess, all of which already existed

| what I invented | what already existed | how it surfaced |
|---|---|---|
| four-axis derived ids | `segmento` + `<SEGMENTO>:<number>`, from modelo 200 | loader refused the result |
| — | — | |
| `-` joining a segment-qualified filename | `+` | `test_casilla_fragment_naming` named the expected stem |

The derived scheme was not careless. It survived three checks — nothing unresolved, no
duplicate key within a record, and no duplicate key **across** records — and every one of
those checks caught a real defect:

- a missing **group** axis collided nineteen numbers;
- a missing **"Total períodos anteriores"** scope collided four more **and silently
  mislabelled five casillas already committed** under the previous stamp (corrected here).

And it was still the wrong thing to build. **Two lessons, both paid for with two full
authoring passes over 180 casillas:**

1. **A derived id that passes every check you thought of is still worse than a
   transcribed one.** `segmento` + `number` are both AEAT's own; nothing can drift.
2. **Re-implementing a convention the registry already has is a defect in itself**,
   however carefully the re-implementation is verified. The architecture rules say this
   about code; it applies just as directly to data conventions.

The cheap move I skipped: before minting an id scheme, look at how the *other*
multi-record modelo in the same tax does it. Modelo 200 is the nearest analogue by
meaning and was one grep away.

### The decomposition survives where it is genuinely needed

The four axes still drive the **labels**, which must say what a cell means in four
languages and are composed from checked vocabularies rather than free text. The two grids
share **113 cell meanings** with no wording to tell them apart, so each label carries
AEAT's own record identifier — opaque but truthful, and 113 identical labels would leave
an operator unable to tell which cell they were filling. Duplicate Spanish labels: **0**.

### The denominator for modelo 220 was undercounted

Counting **distinct** box numbers gives 7604. That undercounts the declarable cells,
because a number reused across records is several cells. Counting **(record, number)
slots** gives **11605**. Modelled: **356 slots**; 11249 remain across 133 records.

Every m220 figure reported in earlier entries used the distinct-number denominator and
was therefore too small.

### Deliberate divergence, recorded so it is not read as an oversight

T22001000 and T22002000 do **not** carry `segmento`: their fields are largely or wholly
unnumbered, so the convention has nothing to key on and no collision has arisen.

## 2026-08-23 — the four modelo 220 deduction grids, and a number reused WITHIN one record

### What landed

Records **T22012B10** and **T22012B20** authored, completing the design's four
deducción-por-doble-imposición grids: **715 casillas** across T22012000, T22012B00,
T22012B10 and T22012B20. Revision 439 → **810 casillas**, six of 137 records.

Suite: **11 failures** — zero new, and two m390 entries cleared by a peer.

### AEAT reuses a box number WITHIN one record — and it is semantic, not an error

`segmento` disambiguates numbers reused *across* records. It cannot help when the same
number appears **twice in one record**, which 33 numbers do.

The reading: every one is a **"Tipo gravamen período generación"** cell, and the tipo de
gravamen of a generation year is a property of the **period**, not of the deduction
family — so AEAT prints the same value in both the interna and the internacional grid.
One number is one declared value, so each becomes **one casilla** covering both offsets.

**The reading is asserted, not assumed.** The generator refuses unless every reused
number is a tipo-gravamen cell of identical width. If AEAT ever reuses a number for two
genuinely different values, that assertion fires rather than silently merging them.

Those cells are **rates, not amounts** — 42 casillas now type `ratio`. The rate column is
*interleaved between* money columns rather than sitting at the edge of the grid, which is
why it was easy to miss; typing a percentage as money would misdeclare it.

### The collision check has now caught four distinct defects

Its record across this modelo:

| pass | what it caught |
|---|---|
| 1 | missing **group** axis — 19 numbers merged |
| 2 | missing **"Total períodos anteriores"** scope — 4 merged, **5 already-committed casillas mislabelled** |
| 3 | id scheme needed a **record** segment — 113 keys shared across two records |
| 4 | **an ordering bug I introduced** — see below |

**The ordering bug is the instructive one.** Adding a lowercase `"deduccion pendiente"`
fragment made it shadow `"2024: deduccion pendiente"`, because the latter *contains* the
former. Every 2024 cell would have been read as a prior-period one. **Matching by
substring makes superstring-first ordering part of the contract**, and nothing but the
collision check would have surfaced it — the decomposition still resolved 100% of fields,
it just resolved them wrongly.

### New vocabulary, all read from the design

An **art. 71 family** for individual deductions carried into the group; a **"DI interna"
sub-family that AEAT nests under its own "internacional LIS" banner** — both kept,
because reclassifying the family to *interna* would override AEAT's own heading with an
inference; the tipo-gravamen rate column; and four spelling variants, including a fully
uppercase DT 23 heading and a phrase AEAT splits with a stray dot (`periodos. futuros`).

### Scale

**10878 of 11605 (record, number) slots remain unmodelled** across 131 of 137 records;
727 modelled. 810 casillas describe six records — the casilla count is not progress.

And still: these casillas **declare** the grids; none **computes** one. Nothing
reconciles a carried-forward deduction against the amount applied, and nothing applies
the tipo de gravamen to anything.

## 2026-08-23 — two records held back, and a target assessed and rejected

### What landed

Records **T22012A01** and **T22012A11** authored — family 12 now at six of its eight
records, 831 casillas. Revision 810 → **926 casillas**, eight of 137 records.

Suite: **8 failures, zero new** — back to the campaign's stated baseline; peers cleared
three more.

### Two records that load cleanly and are still unfit to ship

T22012A00 and T22012A10 now resolve **completely** — zero unresolved fields — but their
four-axis keys still **collide**: twelve pairs in A00, one in A10.

Since ids became transcribed (`SEGMENTO:number`), a key collision no longer threatens the
ids at all. It threatens the **labels**, which are composed from those axes. Shipping
those records would hand an operator **two identical labels inside one record** with no
way to tell which cell they were filling.

They are held back until a further distinguishing axis is found. **A record that loads
cleanly and passes every gate can still be unfit to ship** — the gates check structural
validity, not whether a human can use the result.

### This iteration was mostly vocabulary discovery

Worth stating plainly rather than presenting the outcome as though it were direct. **Five
rounds** of extension were needed to reach zero-unresolved across family 12, each
surfacing further variants of AEAT's *own* headings:

- `INTERNACIONALRDLEG` — space dropped
- `Deducciones por doble imposicion internacional RDLEG` — title-case beside the uppercase form
- `Ded. pendiente`, `Ded. Pendiente` — beside `Deduccion pendiente`
- `periodos. futuros` — phrase split by a stray dot
- a heading naming **no law at all**

### Two headings got their own family keys rather than an assumed home

`DEDUCCIONES POR DOBLE IMPOSICION INTERNA .` names **no law** and is ambiguous between the
RDLEG and DT 23 families — picking either would be an inference the design does not
support. `Deducciones doble imposicion internacional 2024` names the **year** where its
sibling names the law. Both are recorded as what they say and nothing more.

The no-law matcher is tested **last**, because every other interna heading contains it as
a prefix — the same ordering constraint that caused a real defect last iteration.

### Family 14 assessed and rejected — recorded so it is not re-derived

33 records, **3959 numbered fields**, and a concept axis running to **hundreds** of
distinct incentive types, each needing a correct label in four languages. Not a
one-iteration unit, and guessing would produce user-facing labels that could not be stood
behind.

**The tractable next targets, measured by vocabulary footprint:**

| family | records | numbered | distinct headings |
|---|---|---|---|
| **T22004** | 8 | 315 | **8** |
| **T22016** | 2 | 140 | **3** |
| T22005 | 9 | 702 | 14 |
| T22013 | 18 | 1644 | 12 |
| T22007 | 36 | 3139 | 80 |
| T22014 | 33 | 3959 | 22 (but ~hundreds of concepts) |

Heading count is the cheap proxy for how much label vocabulary a family needs.

### Scale

**10762 of 11605 slots remain** across 129 records; 843 modelled. 926 casillas describe
eight records.

## 2026-08-23 — modelo 220 family 16, and the same truncation mistake made twice

### What landed

Family 16 authored, both records — **140 casillas** across T22016000 and T22016001, the
*reparto entre Administraciones forales*. Revision 926 → **1066 casillas**, ten of 137
records. Suite: **8 failures, zero new**.

The family is a perfectly regular grid of **28 concepts × 5 territories**, verified rather
than assumed: every concept occurs exactly five times, and 28 × 5 = 140 equals the
numbered-field count exactly.

### The finding: never build a matcher from truncated output — and I did it twice

**First time.** I hand-wrote concept matchers from a survey that had truncated
descriptions at 104 characters, so fragments like `Abono de de` and `Complementa`
collapsed genuinely distinct concepts and produced **24 key collisions**. Fixed by
*deriving* the concept as the remainder — what is left once heading, territory and row
index are removed — which cannot mis-match because nothing is guessed at.

**Second time, same iteration.** The derived concept was then **slugged to 34 characters**
for use as a key, collapsing 28 concepts into 22 — six pairs would have shipped with
identical labels, exactly the defect that made me hold two records back last iteration.
Caught before shipping; keyed by full text instead.

**Truncation is fine for reading and never for keying.** The same error twice in one
iteration is why it is written down rather than merely fixed.

### Measuring beat the obvious reading

Two of the 140 rows name no territory. They sit fifth in a run of five. The obvious
reading was *Territorio común* — and measuring the other runs showed **15 end in "Total
territorios forales" against only 2 in "Territorio común"**. So the obvious reading was
wrong, and the majority pattern is itself only positional evidence. The territory is
recorded as **unnamed**, with the label saying so.

### AEAT's own text, again

Both Basque and Spanish territory names in one design — Araba/Álava, Gipuzkoa/Guipúzcoa,
Bizkaia/Vizcaya — and a word broken across a space (`insufi ciencia`). Both spellings
matched; labels use the Basque form and the corrected word.

### A tree-wide failure count is not evidence about your own change

An intermediate suite run this iteration reported **183 failures**. The cause was a peer's
**untracked, half-authored modelo 210 revision directory** whose casillas referenced
export fields that did not yet exist — which fails registry validation globally and
therefore fails almost everything. It settled within the iteration; the re-run gave 8
failures, zero new.

Worth remembering alongside the CRLF incident: in a shared worktree, a sudden tree-wide
red is more often another hand mid-authoring than a regression in the change under review.
**Check what the failure actually says before attributing it.**

### Scale

**10622 of 11605 slots remain** across 127 records; 983 modelled. 1066 casillas describe
ten records. T22012A00 and T22012A10 are still held back for colliding label keys.

## 2026-08-23 — modelo 220 family 08, and a correction to my own targeting proxy

### What landed

Family 08 authored, both records — **76 casillas** across T22008A00 and T22008B00, the
*consolidación de resultados contables y de bases imponibles*. Revision 1066 → **1142
casillas**, twelve of 137 records.

### The proxy I recommended last iteration was wrong

The previous entry named **T22004** as a tractable next target because it has only **8
distinct headings**. Measured properly, T22004 has 315 numbered fields over **212 distinct
concepts**. Heading count measures *families*; it says nothing about label vocabulary, and
the two are unrelated.

**Concept count is the right proxy**, because it is exactly what has to be translated into
four languages. Re-measured:

| family | records | numbers | headings | **concepts** |
|---|---|---|---|---|
| T22008 | 2 | 76 | 11 | **47** |
| T22009 | 2 | 99 | 12 | **68** |
| T22004 | 8 | 315 | **8** | **212** |
| T22012 (rest) | 2 | 279 | 8 | 225 |
| T22003 | 10 | 394 | 41 | 322 |
| T22005 | 9 | 702 | 14 | 507 |
| T22013 | 18 | 1644 | 12 | 836 |
| T22014 | 33 | 3959 | 22 | 1025 |
| T22007 | 36 | 3139 | 80 | 1223 |

T22004 has the *fewest* headings and the third-*most* concepts. **T22009 (68) is the next
tractable target.**

### Two records, two shapes — and neither was assumed

**T22008B00 is a grid**: eight concept groups × seven settlement columns, plus two
standalone lines. The arithmetic closes exactly — the SALDO group carries four columns
rather than seven, so 4 + 7×7 + 2 = 55, the numbered-field count.

**T22008A00 is not a grid**: its twenty-one lettered lines A–G2 are each a distinct
concept with no repeating axis, so each label comes from the design's own line. Forcing a
decomposition would have invented an axis the design lacks — and the arithmetic would not
have closed, which is how you can tell the difference.

**Column matching is order-dependent, and the table now says so.** `Cuenta de Pérdidas y
Ganancias` is a *prefix* of `…Aumentos (A)`, so the variants must be tested first. Same
shape as the family-12 defect where a lowercase fragment shadowed its own superstring.

### AEAT prints arithmetic that this registry does not implement

Line C reads `Diferencia por consolidación de resultados (= A - B)`, line F `(= D - E)`,
and line E carries a formula over other casillas. Those relations are in the labels
exactly as AEAT prints them, and **nothing here computes or checks them**. A label that
states an equation is not an implementation of it.

### Suite: two new failures, neither mine

Both are modelo 210 `2026-y-siguientes` — a peer's in-flight revision whose labels are not
yet in the Spanish catalogue. Confirmed by reading the output: 34 modelo 210 entries, zero
modelo 220. **Second consecutive iteration where that peer's half-authored m210 work moved
the count** — worth recognising the pattern rather than re-diagnosing it each time.

### Scale

**10546 of 11605 slots remain** across 125 records; 1059 modelled. T22012A00 and T22012A10
still held back for colliding label keys.

## 2026-08-23 — T22009000, and making the same mistake a third time

### What landed

Record **T22009000** — the *liquidación del grupo*: 63 casillas running from cuota íntegra
through bonificaciones, deducciones por doble imposición and otras deducciones to cuota
líquida, cuota diferencial and líquido a ingresar. Revision 1142 → **1205 casillas**,
thirteen of 137 records.

Suite: 10 failures. The one new entry is the known `test_loader_cache_isolation`
parallel flake (11 pass single-process); a peer's m210 continuidad failure cleared.

### I made the truncation mistake a third time — and the note did not stop me

Last iteration's entry says, having made it twice in one pass: *never build a matcher
from truncated output.* This iteration I built the label table's **keys** by transcribing
them from a 150-character-truncated listing. **Six were subtly wrong** — `Cap III Tit VII`
became `Cap III Tit VI`, `art 30 RDLEG 4/2004` became `art 30 LIS RDLeg 4/2004`, and so
on.

**What caught it was not the written lesson but an assertion in the code.** The label
table refuses to fall back to Spanish and reports every unmapped tail, so six casillas
could not be labelled and the generator stopped. The fix was to **dump the exact strings
from the data** rather than retype them from a display.

**The durable finding: writing a lesson down did not prevent me repeating it three
iterations running. Only a mechanical check did. Put the check in the code, not in the
notes.**

### And the correction introduced a quieter defect that no gate caught

Renaming those six table keys left **three translations attached to their old law
references** — one key read `arts 31 y 32 LIS` while its English still said
`art. 100.11 LIS`. Found by reading the diff, not by any gate, and realigned.

**A key rename moves the key, not the value under it**, and a translation table has no way
to notice its value no longer matches its key. Worth a check of its own if this pattern
recurs: assert that a translation mentioning an article number mentions the *same* one as
its key.

### T22009001 not shipped, deliberately

Casillas **02796 and 02797 have byte-identical descriptions**, both ending "Estado.", at
adjacent offsets. The pair above them is the same concept split Estado / D. Forales, so
AEAT repeated the wrong suffix — but which one is the foral column is not something the
design states. Guessing would put a jurisdiction on a filed box on a neighbour's shape.
The record is fully extracted, tiles clean, and decomposes with a single collision at
exactly that pair; it waits for a resolution.

### Stated in the stamp, because a complete record is not a working one

This record is a **settlement chain** — cuota íntegra less bonificaciones gives cuota
líquida, less retenciones gives cuota diferencial, and so on. **Not one of those relations
is modelled.** Every step is declared as a box and none is computed.

### Scale

**10483 of 11605 slots remain** across 124 records; 1122 modelled. T22012A00, T22012A10
and now T22009001 are held back.

## 2026-08-23 — the two per-entity detail records, and closing the truncation class

### What landed

Records **T22010000** and **T22011000** — the per-entity detail sheets. T22010000 lists
transparencia fiscal internacional (art. 100.10 LIS) and doble imposicion interna
intersocietaria entity by entity; T22011000 lists the eight bonificaciones. **22
casillas**, revision 1205 → **1227**, fifteen of 137 records.

Suite: **10 failures, zero caused by me.** One entry left (the loader-cache parallel
flake), one arrived — `test_record_design_coordinate_stutter_recovery`, which belongs to a
peer's uncommitted `_record_design.py` edits.

### The number set decided the casilla set, not the shape

Both records repeat a detail block carrying **no box number**, differing only by a printed
row index: 44 blocks of 3 fields, 24 blocks of 9. One row is declared per record and a
layout repeat writes the rest — modelo 720's `binding_record` mechanism. Declaring every
block would have minted 132 and 216 casillas for 3 and 9 declared values.

**The stride is proven, not assumed.** The run starts at @16 in both; 16 + 43×44 and
16 + 145×24 land exactly on @1908 and @3496, where the first total begins. Every block was
compared field-for-field against the first with its index removed: **one distinct shape
each**. The arithmetic closing is the tell that the decomposition is right — the same
signal that separated T22008B00's grid from T22008A00's flat list.

### The truncation class is closed, not watched for

Three stamps running recorded the same defect: a table keyed on **transcribed prose**
carried a silently mistyped key — once from a truncated survey, once from a truncated slug,
once from a truncated listing. Each time only an assertion in the code caught it, never the
written lesson.

**This iteration the translation table is keyed by casilla id**, which is generated rather
than retyped, and it asserts bidirectionally that its id set equals the authored id set.
The defect can no longer be introduced, rather than being caught after the fact.

That is the shape of the general fix: **when a lesson says "be careful typing X", the
answer is to stop typing X**, not to be careful. Watching for a defect three times running
was the signal that the input itself was wrong.

### AEAT's detail row and its total disagree, in both records

`D.I. Interna **inter**societaria al 5/10%` in the detail, `D.I. Interna societaria` in the
total. `Cap. III **Tít.** VII LIS` accented in the detail, `Tit.` unaccented in the total.
Both transcribed as printed and both surfaced by **comparing the two column lists in code**
— neither would have survived reading by eye.

### The coverage denominator moved under the campaign

The previous stamp recorded **11605** numbered slots with 1122 modelled. Today the same
measurement over the same workbook reports **11570** with **1117** — because a peer changed
the record-design extractor between the two runs. **Zero authored slots are orphaned**;
every one is still evidenced. Nothing was lost.

But the lesson is durable: **a coverage figure is only true against the extractor of the day
it was measured**, and a stamp stating one should say so. Two consecutive stamps reporting
different totals for an unchanged workbook otherwise reads as an error in one of them.

The same recount corrected an older conflation: 137 is the **sheet** count, but only **133**
records carry numbers at all.

### Scale

**10453 of 11570 slots remain** across 118 numbered records; 1117 modelled. T22009001,
T22012A00 and T22012A10 stay held back.

## 2026-08-23 — T220DID00, and two things the design says that the design contradicts

### What landed

Record **T220DID00** — the *documento de ingreso o devolución*, the payment slip of the
consolidated declaration: devengo, identificación, three liquidación figures, the
devolución block with its account details, the ingreso block, the abono/compensación of
activos por impuesto diferido (art. 130 LIS), and the cuota cero mark. **31 casillas**,
revision 1227 → **1258**, sixteen of 137 records.

Suite: **9 failures, zero caused by me** — one cleared (a peer fixed their
`_record_design` test), nothing new.

### AEAT's apartado numbering disagrees with itself

The design numbers the apartados (1)–(7) inside the field descriptions. The bank country
code at @419 is printed as **"Devolución (5)"** — but the devolución block is (4) and (5)
is Ingreso. **Routing on the digit would have filed a devolución field under ingreso.**

Deriving the apartado from its **name** is immune to that, and the generator now asserts
name↔number consistency in *both* directions and prints every disagreement. It also
**refuses to run if the disagreement ever disappears**, so a corrected workbook cannot
leave a stale claim standing in the fragment.

### The bracket is not always last

Box 00562 prints as `Cuota íntegra del grupo [00562]. {DID_liq_CI}` — the design's own
variable name comes *after* the bracket. An end-anchored search **silently minted a
byte-span number for a box AEAT numbers.**

Found by **reading the generated output against the design**, not by an assertion. An
assertion now refuses any description carrying an unread bracket.

That is three iterations running where the defect surfaced only because output was read
back, and the fix has the same shape every time: **turn the reading into a check.** The
list so far — key text retyped from truncation, a table key renamed without its value, an
end-anchored match on a non-terminal token — are different bugs with one cause: a step
that was verified by eye once instead of by code every time.

### Four boxes carry a letter, not a number

`[D]` importe a devolver, `[I]` importe a ingresar, `[A]` abono, `[C]` compensación. Each
was counted across **all 137 sheets** and appears **exactly once**, in this record only —
the shape of a per-record box identifier, not a column marker. Taken as AEAT's own number,
as modelo 604's alphabetic casillas already are, and recorded as a judgement.

### One AEAT box, several casillas — a limitation of the convention

Box **00562 is now declared twice** in this revision (`T22009000:00562` and
`T220DID00:00562`), and the design prints it in **seven** records. The `(segmento, number)`
convention — modelo 200's, adopted here — gives each record its own casilla.

**A layout must bind these to the same value rather than collect them twice, and nothing
enforces that today.** Worth a gate before any m220 layout is authored: every casilla
sharing a `number` across segmentos must resolve to one value.

### Two fields read identically until the apartado is added

Both `Código IBAN - Bloque`, one under devolución and one under ingreso. The within-record
duplicate-label assertion caught it; the apartado is now part of the label, not decoration.

### Scale

**10447 of 11570 slots remain** across 117 numbered records; 1123 modelled, zero orphaned.
T22009001, T22012A00 and T22012A10 stay held back.

## 2026-08-23 — the T22015 deducción records, and what deriving a heading found

### What landed

Records **T22015A00** and **T22015B00** — the two deducción detail records: deducciones
por reinversión, and the deducción por inversión de beneficios. **21 casillas**, revision
1258 → **1279**, eighteen of 137 records.

Suite: **identical FAILED list, zero regressions.**

Same repeating shape as T22010000/T22011000, but the row index is a **parenthesised
ordinal** rather than a trailing digit, and it sits in a different place in each record.
33 blocks each; 16 + 89×33 and 16 + 81×33 land exactly on the first total.

### Deriving the heading found a legal-citation split nobody typed

The record heading is **derived as the common prefix of its own group**, not retyped. That
is what surfaced the finding:

**T22015B00 prints a different legal citation on its details and on its totals.** Every one
of its 231 detail lines says `DEDUCCIÓN POR INVERSIÓN DE BENEFICIOS (DT 24.5 LIS y Art. 37
TRLIS)`; every one of its three totals says `(Art. 37 LIS)`. Transitional provision plus
the repealed TRLIS article on one side, the current LIS article on the other — for the same
deducción.

**T22015A00 has no common total heading at all**, because AEAT prefixes only its *first*
total with `Resultado de la autoliquidación.`.

Neither would have been noticed had the heading been read off one line and applied to the
rest — which is exactly what the previous iterations did in other forms. Totals therefore
keep their printed text whole; only detail labels have a heading stripped.

### A blanket punctuation rule corrupted a legal reference

Regularising the space after a period — added so `reinversión (2).Deducción` and
`reinversión (4). Deducción` would compare equal — rewrote **`DT 24.5 LIS` as
`DT 24. 5 LIS`**.

Now scoped to a period that separates *words*, so it cannot reach inside a number AEAT
printed. And the block-shape comparison moved onto letters and digits only, so punctuation
spacing cannot make one printed shape look like two.

**The general form: a normalisation written to make two strings compare equal will happily
change a third string that was already correct.** Scope it to the exact thing that differed.

### AEAT repeats a phrase inside one description

Block 1 of T22015A00 reads `...por transmisión del activo por transmisión del activo`; the
other 32 blocks print the tail once. Collapsed in the label, kept doubled in the comment —
the same call as T220DID00's `Estado. Estado`.

Worth noting **how** it was found: the block-shape check *refused to see one shape*. The
collapse was a response to a failing assertion, not a precaution taken in advance. Three
iterations ago that class of thing was found by eye; it is now found by the code.

### Scale

**10441 of 11570 slots remain** across 115 numbered records; 1129 modelled, zero orphaned.
The cross-record hazard is unchanged: box 00562 is declared twice and nothing yet makes two
casillas sharing a number resolve to one value.

## 2026-08-23 — the four T22007 correction records, and the same bug twice

### What landed

Records **T22007D00, E00, F00 and H00** — the four sibling per-operation detail records
under *otras correcciones a la suma de bases imponibles*: elimination of non-exempt
internal dividends; incorporation of previously-eliminated impairments of group equity
holdings; those same impairments still pending; and everything not covered by the
preceding sections. **20 casillas**, revision 1279 → **1299**, twenty-two of 137 records.

Suite: **identical FAILED list, zero regressions.**

### One family, four records, two notations for the same thing

**T22007D00 and T22007H00 print a parenthesised row ordinal; T22007E00 and T22007F00 print
a trailing digit.** Same family, same purpose, same 50-block shape — two notations.

The generator therefore **tries both forms on every record and requires exactly one to
explain every line**. An ambiguous or unexplained record refuses rather than being read
under whichever form its neighbour used. The ordinals are then asserted to be exactly 1..50
with each appearing once per block field — which is what rules out a description that merely
ends in a number.

The general point: **sibling records are not evidence about each other.** Four sheets that
are byte-for-byte the same shape still disagreed on notation.

### The same normalisation bug, one iteration later

Last iteration the period-spacing rule rewrote the legal reference `DT 24.5 LIS` as
`DT 24. 5 LIS`. This iteration the *same rule* rewrote **`N.I.F.` as `N. I. F.`** on eight
labels.

It now requires two letters before the period, so it cannot enter an abbreviation. The
previous iteration's records were re-generated under the sharper rule and came out
**byte-identical**, so nothing already shipped carried the defect.

Recurrence within one iteration of the first sighting says the earlier fix was **scoped to
the instance, not to the cause**. The cause is: *a normalisation written to make two strings
compare equal will reach strings that were already correct.* The durable form is not a
better regex each time — it is to run the normalisation only where a difference was actually
observed, or to normalise for comparison only and never for output. Worth doing properly if
a third instance appears.

### AEAT's own text, again

`Deteriorio` for *Deterioro* on every detail line of T22007E00, and the `fi` ligature broken
in `grupo fi scal` in its total — the third family carrying that ligature defect. Corrected
in the labels, kept as printed in the comments, and every correction applied is listed on the
fragment's own face.

### The record subject had to be derived, not assumed

**T22007E00 and T22007F00 share two detail lines word for word.** Only the record's subject
tells them apart, and that subject is derived from the total's own text rather than retyped.

### Scale

**10437 of 11570 slots remain** across 111 numbered records; 1133 modelled, zero orphaned.

## 2026-08-23 — T22007M00, the gastos financieros limitation, and fixing the cause

### What landed

Record **T22007M00** — the *limitación en la deducibilidad de gastos financieros* of the
grupo fiscal: the art. 16.5 / 67 b) / 83 LIS limit for debt taken on to acquire
participaciones, then the general 30% del beneficio operativo limit of art. 16.1 and 16.2.
Lettered a)–r) with j1)–j6) and a closing total. **27 casillas**, revision 1299 → **1326**,
twenty-three of 137 records. A **flat** record: no repeating block, and every one of its 27
boxes carries AEAT's own number, so nothing is minted.

Suite: **identical FAILED list, zero regressions.**

### The normalisation bug, fixed at the cause this time

Two stamps running recorded the same defect — a punctuation rule written to make two
strings compare equal reaching a third that was already correct (`DT 24.5 LIS` →
`DT 24. 5 LIS`, then `N.I.F.` → `N. I. F.`). Last entry named the cause but deferred the
fix.

**The cause is normalising for OUTPUT what only needed normalising for COMPARISON.** This
record needs no comparison at all, so its label is the design's own text with only the box
number and the heading removed, and no spacing rule runs over it. That is the shape any
future generator should take: normalise inside the comparison key, never on the way to a
label.

### AEAT emits the real ligature codepoint — inconsistently, inside one record

Not the broken `fi ` spacing seen on families 07, 09 and 16 but **U+FB01 itself**, in 21 of
these 27 descriptions — and mixed with plain `financieros` on the other lines of the *same
record*.

Consequence worth keeping: **a search for `financieros` over the raw design misses 21 of
these lines.** Any survey of this workbook that greps for a Spanish word is undercounting by
an unknown amount unless it folds the ligature first.

### AEAT's arithmetic annotations are not well-formed

The descriptions carry the record's own algebra in square brackets that are *not* box
numbers: `(= [c1+f])`, `(<= [b], [a=c1+c2], >= 0)`, `(= 30%* [j1-j2-j3-j4+j5-j6]`. The
letters name other lines of the record.

But line d) closes a parenthesis with a square bracket — `([b>=c1+d+e], >= 0]` — and line
j) never closes its parenthesis at all. **Any future attempt to compile these into formulas
must treat them as prose needing human adjudication, not as a parseable grammar.** They are
kept verbatim in all four catalogues rather than translated away, since they are the
record's cross-reference notation.

### Two numbers fall outside the record's own run

Twenty-five boxes are `03196`–`03220` consecutively; **j6) is `02219` and m) is `02220`**,
from a different block. Recorded because a reader scanning for a contiguous range would
conclude two boxes were missing.

### Scale

**10410 of 11570 slots remain** across 110 numbered records; 1160 modelled, zero orphaned.

## 2026-08-23 — T22005A00, and repairing the ligature from AEAT's own evidence

### What landed

Record **T22005A00** — the *estado de ingresos y gastos consolidados reconocidos*: the
resultado consolidado, the eight items recognised directly in consolidated equity with
their total, the seven transfers to the consolidated P&L with their total, and the
consolidated total split between the sociedad dominante and the socios externos.
**21 casillas**, revision 1326 → **1347**, twenty-four of 137 records. Flat record, every
box carrying AEAT's own number.

Suite: **identical FAILED list, zero regressions.**

### One record, three spellings of one word

The previous entry recorded that AEAT emits U+FB01 and that a grep for a Spanish word over
this workbook silently misses those lines. Measured across the whole design: **U+FB01 307
times, U+FB02 twice, and 29 of them followed by a space** that splits the word.

This record carries **all three forms of the same word**: `instrumentos ﬁ nancieros` at @33,
`instrumentos ﬁnancieros` at @50, and plain `Activos financieros` in that *same line* at
@50. Expanding the codepoint alone leaves `fi nancieros` in an operator label.

**The repair is grounded in the workbook's own vocabulary.** A split is rejoined only when
the joined token already appears as a whole word elsewhere in the design — `financieros`
attested 615 times, `flujos` 7 — and an **unattested split refuses the run** rather than
being joined on a hunch. That is evidence from AEAT's text, not a rule about where Spanish
words break.

This is the shape the three earlier normalisation defects should have taken from the start:
**derive the correction from data already present, and refuse when the data does not support
it.**

### Uniqueness is a property of the pair, not the line

Seven line labels appear **twice** in this record — `Efecto impositivo`, `Por coberturas de
flujos de efectivo`, `Subvenciones, donaciones y legados recibidos` and four more — once
under INGRESOS Y GASTOS and again under TRANSFERENCIAS. That is AEAT's structure.

The within-record duplicate assertion originally fired on the bare line, and **taking that
at face value would have forced a false distinction into the labels**. The right invariant
is `(section, label)`, plus uniqueness of the *composed* label in all four catalogues —
which is where an operator actually reads it. A check that fires is not automatically
right; what it asserts has to be the thing that matters.

### Two numbers are absent from consecutive runs

`00336`–`00345` skips **00343**; `00346`–`00354` skips **00352**. They are not in the sheet
at all. Recorded so a reader checking for a contiguous range does not conclude two boxes
were dropped in transcription.

### Scale

**10389 of 11570 slots remain** across 109 numbered records; 1181 modelled, zero orphaned.

## 2026-08-23 — T22005A01, and the derivation that was right most of the time

### What landed

Record **T22005A01** — the *estado de ingresos y gastos reconocidos consolidado*, the
entidades de crédito variant (IFRS shape: otro resultado global split into items that will
and will not be reclassified). **43 casillas**, revision 1347 → **1390**, twenty-five of 137
records. Every box carries AEAT's own number.

Suite: **identical FAILED list, zero regressions.**

### I nearly invented a hierarchy into a filing-grade record

**Nineteen of the 43 boxes share their printed text with a sibling** — six read `Transferido
a resultados`, six `Otras reclasificaciones`, five `Ganancias o (-) pérdidas de valor
contabilizadas en el patrimonio neto`, two `Activos no corrientes…`. On the printed modelo
they sit indented under different parents.

**The diseño de registro carries no indentation at all** — no level column, no `validation`,
no `components`, only flat description text. The generator now *asserts* that emptiness, so
a future workbook that does carry structure cannot be read blind under this fragment's
claim.

The obvious derivation — parent = nearest preceding non-repeated line — **looks right and is
wrong in four places**, each verified against the design:

- `00276` would take `00275` as parent; it is a *sibling* of it under `00274`.
- `00287`/`00288` would hang off `00286`, which is itself a child of `00285`.
- `00292` would be read as parent of `00293`; both are siblings under `00289`.
- `00298`–`00301` would all hang off `00656`; `00298` is itself parent of the other three.

**A derivation that is right most of the time is a worse outcome than no derivation**,
because the wrong attributions are invisible — they look exactly like the right ones. It was
discarded on that evidence.

### An assumption every previous stamp carried was wrong

Every earlier iteration reported "duplicate Spanish labels across the revision: **0**" as
though it were an invariant. Measured elsewhere: **modelo 200 carries 96 shared label texts
(one used 20 times) and modelo 100 carries 198.**

The zero was a *property of the records happened to be authored so far*, never a
requirement — and treating it as a requirement here would have forced a false distinction
into 19 filing-grade labels. The revision now reports 4 duplicated texts covering 19
casillas: exactly what the design duplicates.

**The right invariant is not "no duplicates" but "the duplicated set equals the design's."**
That version still bites — and did: a Hungarian translation collapsed `00277` and `00306`,
which AEAT separates **by a definite article alone** (`de inversiones` vs `de las
inversiones`). Without the assertion the two would have become indistinguishable in one
catalogue only.

### Also

AEAT misspells `valorados` as **`calorados`** on `00647`. Corrected by name in the label,
never by a general rule, kept as printed in the comment.

### Scale

**10346 of 11570 slots remain** across 108 numbered records; 1224 modelled, zero orphaned.
The nesting of this record is **not modelled at all**; if a layout or UI ever needs the tree
it must come from a source that carries it.

## 2026-08-23 — T22005A02, and a vocabulary that attested its own damage

### What landed

Record **T22005A02** — the second *estado de ingresos y gastos reconocidos consolidado*:
otros ingresos y gastos reconocidos broken down by concept with the valuation, transfer and
reclassification lines of each. **37 casillas**, revision 1390 → **1427**, twenty-six of 137
records.

Suite: **identical FAILED list, zero regressions.**

### The same family, two treatments, and the reason is in the data

**This record prints its own hierarchy** — every child line carries its parent's name inline
(`Cobertura de los flujos de efectivo. Ganancias y pérdidas por valoración`), so all 37
labels are distinct on AEAT's own text.

Its sibling T22005A01 was authored **flat** last iteration for exactly the opposite reason:
nineteen boxes share their printed text, the design carries no indentation, and a positional
derivation was tried and refused. Read together, the pair is the point: **one family
produced a nested record and a flat one, and the difference is evidenced in each design
rather than chosen.**

### An attestation vocabulary drawn from the corpus being repaired attests the damage

Last iteration's ligature repair rejoins a split only when the joined token is attested
elsewhere in the design. Here AEAT breaks `reclasificaciones` as `reclasifi caciones` **in
several sheets** — so a naive word count records `reclasifi` as a word eleven times over,
the left-side guard concluded it was already a word, and **the repair silently did nothing**.

Two counts are now kept: every token, and only those tokens seen in a position that *cannot*
be the left half of a split. The general form: **when you build evidence from a corpus you
are correcting, the corpus votes for its own errors** — count only the occurrences that
could not themselves be damaged.

The rejoin also had to stop anchoring on a token boundary. T22005A00's split was
`instrumentos ﬁ nancieros`, where the fragment *begins* at the ligature; this record's sits
**mid-word**. A boundary-anchored rule finds the first and silently misses the second.

### AEAT's separator is inconsistent three ways inside one group

A period and space in most lines, a **bare space** at @84 and @101, and **nothing at all** at
@67 — `…para la ventaGanancias y pérdidas por valoración`. A separator is inserted only where
the prefix is an **attested standalone line of the same record** (box 00384 prints it alone),
so the split point is evidence, not a judgement about where the phrase ends.

### The sector attribution is inferred, and now says so

AEAT prints the **same heading** on A01 and A02 and names no sector on either. The section
slugs say `credito` and `aseguradoras` because of each record's vocabulary — insurance
accounting plan on one, credit-institution on the other. That reading is *not stated by the
design*, so the fragment marks it as inferred and the operator-facing labels claim no sector.

### The cross-record hazard has surfaced in the labels

Box **00500** is declared in both records, and because AEAT gives both the same heading the
two casillas carry an **identical operator label**. That is correct — one declared value on
two alternative pages — and it is the clearest demonstration yet of the hazard every stamp
has recorded: a layout must bind such casillas to one value, and nothing enforces that.

The revision now carries 5 duplicated label texts over 21 casillas: 4 are AEAT's own repeats
inside A01, the fifth is this.

### Scale

**10309 of 11570 slots remain** across 107 numbered records; 1261 modelled, zero orphaned.

## 2026-08-23 — T22003A00, the consolidated balance-sheet activo

### What landed

Record **T22003A00** — the *balance consolidado, activo* in the general PGC shape: activo no
corriente through the long-term investments, activo corriente through the short-term ones,
closing on TOTAL ACTIVO. **37 casillas**, revision 1427 → **1464**, twenty-seven of 137
records.

Suite: **identical FAILED list, zero regressions.**

### The generator is generalised, not copied a third time

Heading derived as the common prefix; ligature repair grounded in a vocabulary counted twice
so the damage cannot attest itself; separator inserted only after an attested standalone
line; completeness complement and type coverage asserted. Three records have now gone
through it, and **the shared machinery is what makes their claims comparable** — each
fragment's header states the same checks because the same code ran them.

### Two boxes left flat, for the reason established last iteration

`00701` (derechos de emisión de gases de efecto invernadero) and `00761` (otros) carry **no
parent name**, though they sit between Existencias and Deudores comerciales and read on the
printed modelo as breakdowns of Existencias. The design doesn't say so, so nothing here says
so — the same refusal that kept T22005A01 flat, applied to two boxes instead of nineteen.

That's the pattern generalising properly: **the rule is not "this record is nested" or "this
one isn't" but "each line is nested only where its own text says so."**

### AEAT's separator, again — and why deriving beat ruling

`ACTIVO. Inmovilizado intangible` with a space, `ACTIVO.Activos por impuesto diferido`
without. Deriving the heading as a common prefix and stripping the remainder lands both on
the same heading, so **no rule about AEAT's punctuation was needed at all** — which is the
cleanest resolution yet of the class that produced `DT 24. 5 LIS` and `N. I. F.`.

### The ligature measurement holds on a third family

Seven of this record's 37 lines carry the real U+FB01 codepoint, unsplit, in `Inversiones
financieras` and `Periodificaciones`. Design-wide count now **309**. A plain-text search of
this workbook for a Spanish word still silently misses them.

### A trap for whoever continues this family

**The sheet suffix is not a reliable guide to which side of the balance a record covers.**
`T22003B02` opens `ACTIVO. Inmovilizado intangible` despite the B — it continues an ACTIVO
page rather than starting a PASIVO one. Read the descriptions, not the sheet names.

### Scale

**10272 of 11570 slots remain** across 106 numbered records; 1298 modelled, zero orphaned.
Nothing here sums a group into its head or checks activo against patrimonio neto plus
pasivo: the balance sheet does not balance.

## 2026-08-23 — iteration blocked: the registry does not load

**No record was authored and no stamp was written this iteration.** The registry fails
validation, so `bundled_authority()` cannot be loaded, locale keys cannot be derived, and a
suite run would measure someone else's churn rather than this work.

### What is broken, precisely

**189 failures, every one in `modelo 322 revision 2008-2022`:**

- 187 × a casilla referencing an export field that does not exist
  (`m322-2022.page-01.f019` and siblings)
- 1 × the revision declaring no export layout at all
- 1 × its `filing` grade claim blocked by that absence

Zero failures involve modelo 220 or any record authored in this campaign. The 32 m220
fragments — 1464 casillas — all parse standalone.

### It is a peer's era split, in flight right now

`6d416bbd33` renamed m322's `2008-2023` revision to `2023`, and a new `2008-2022` revision
is being built beside it: its casillas already carry `export_refs` into an `m322-2022`
layout whose directory does not exist yet. The peer's worktree also holds uncommitted edits
to the 2023 export records and untracked `dev/registry/mappings/modelo_322/2022/` and
`render_profiles/modelo_322/2022/`.

**The failure count moved between two consecutive load attempts — 203 then 189 — so files
are being written as this is measured.** That is the tell that separates a stable break from
an active one, and it is worth checking before diagnosing anything: a count that changes
under a re-run is not a defect to analyse, it is a worktree in motion.

### Why this is recorded rather than worked around

The honest options were to author T22003B00 from the design alone and hold it unloaded, or
to stop. Authoring without loading would skip every check this campaign relies on — locale
keys, label resolution, the completeness complement against a loaded revision — and would
put a fragment into a tree whose owner is mid-restructure. **The protocol's value is that it
is not optional when it is inconvenient.**

This is also the structure-change fallout the campaign brief warns about, observed live: an
era split leaves casillas pointing at a layout that does not exist until the layout lands,
and in this registry that state is not degraded, it is a hard load failure for every consumer
of the whole authority.

### Next iteration

Re-measure first. If m322 still fails, the block is not mine to clear without coordinating.
The next unit remains **T22003B00** (61 fields, 51 numbered boxes, the patrimonio neto and
pasivo side of the general-PGC balance sheet), which pairs with T22003A00 authored last
iteration.

## 2026-08-23 — T22003B00, and an assertion that was wrong about its own record

### The block cleared

The peer's m322 era split landed; the registry loads clean and the FAILED list is back to
the nine it stood at before. Nothing had to be done to clear it — which is the right outcome
for a block that was never mine.

### What landed

Record **T22003B00** — the *balance consolidado, patrimonio neto y pasivo*, completing the
pair with T22003A00. **51 casillas**, revision 1464 → **1515**, twenty-eight of 137 records.

### An empty common prefix is a valid answer

The generator derives a record's heading as the common prefix of its numbered lines, and
**asserted the result was non-empty**. T22003A00 prefixes every line with `ACTIVO`; this
record prefixes **nothing at all** — its lines begin directly with `PATRIMONIO NETO`,
`Fondos propios`, `Capital`.

The assertion would have failed here, and **the assertion was wrong, not the record**.
Forcing a heading would have put a word AEAT does not print onto 51 filing-grade labels.

That's a distinct failure mode from the ones logged so far: not a derivation that produced a
wrong answer, but **a guard that treated a legitimate answer as impossible**. A check
encodes an assumption; when it fires, the assumption is as likely to be the defect as the
data. Second time this campaign — the T22005A00 duplicate-label check fired on AEAT's own
structure.

### AEAT is inconsistent inside one group

Five boxes sit under `Reservas` on the printed modelo and carry **no prefix** — `00003`,
`00752`, `00753`, `00764` — while `00750` and `00702` *are* prefixed `Reservas.` in the same
run. All left flat: nested only where the line itself says so.

`00003` also sits far outside the record's `00185`–`00252` range. AEAT's numbering, not a
transcription slip, and recorded so nobody concludes otherwise.

### Parentheses that carry arithmetic

`(Acciones y participaciones de la sociedad dominante)` and `(Dividendo a cuenta)` are
parenthesised because they **subtract**. Kept verbatim in all four catalogues — stripping
them would silently drop the sign convention. **Nothing here acts on it**: it is punctuation
in a label, and a consumer treating those lines as additive will be wrong.

Also `Procisiones` for *Provisiones* on `00735` — corrected by name, reported on the
fragment.

### Both sides now exist, and still nothing checks them

`TOTAL ACTIVO` `00180` and `TOTAL PATRIMONIO NETO Y PASIVO` `00252` are both declared, and
**nothing checks that they are equal.** No formula sums a group into its head, sums heads
into a total, or relates the totals. Authoring both sides makes the check possible; it does
not make it exist — worth stating plainly, because a complete balance sheet is exactly the
kind of artefact a reader assumes must balance.

### Scale

**10221 of 11570 slots remain** across 105 numbered records; 1349 modelled, zero orphaned.

## 2026-08-23 — T22003A02, and the first fix that would have caught all three

### What landed

Record **T22003A02** — the *balance consolidado activo* in the aseguradoras shape: the
financial-asset portfolios by measurement category, préstamos y partidas a cobrar with its
long breakdown, the participación del reaseguro en las provisiones técnicas, and
inmovilizado material. **47 casillas**, revision 1515 → **1562**, twenty-nine of 137 records.

Suite: **identical FAILED list, zero regressions.**

### A correction must declare how many times it will fire

AEAT drops the initial letter at @186, printing `nversiones por cuenta de los tomadores`
where @271 prints the same phrase correctly. Correcting the bare fragment **also matched the
correct line four rows below** and produced `IInversiones`.

The substitution is now anchored to the preceding separator *and* **declares an expected
firing count**, asserted after every label is built.

That count assertion is the first form of this fix that **would have caught all three**
earlier instances of the same family — `DT 24.5 LIS` → `DT 24. 5 LIS`, `N.I.F.` →
`N. I. F.`, and this one. Each was a substitution reaching further than intended; each was
caught by a different downstream check or by eye. **"How many times should this fire?" is
answerable in advance and checkable afterwards**, which the scoping fixes never were.

### AEAT gets the separator wrong in both directions, on one record

**None** at @50 and @84 (`para negociar.Instrumentos de patrimonio`) and **two** at @696 and
@730 (`provisiones técnicas.. Provisión para prestaciones`). Both repaired only after an
attested standalone line of the same record; five repairs, each listed on the fragment face.

### Three-level nesting, and why it works here

`Préstamos y partidas a cobrar. Préstamos. Entidades asociadas` — AEAT prints every level
inline. The locale composition takes the **longest attested prefix** as the parent, which
resolves the depth without a rule about how deep the tree goes. T22005A01 stays the
counter-example: it prints no nesting, so it was authored flat.

### The refusal to infer a sector has a visible cost, and it is recorded

Because both activo records carry AEAT's identical `ACTIVO` heading, `T22003A00:00177` and
`T22003A02:00101` now **share an operator label** (`Efectivo y otros activos líquidos
equivalentes`). These are *different* boxes — unlike box `00500`, which is one box printed on
two pages.

They belong to alternative sector layouts a taxpayer never files together, and separating
them would mean asserting a sector AEAT does not print. **The cost of not inferring is a
collision; the cost of inferring is a false claim on a filing-grade label.** The collision is
recorded rather than hidden.

Revision now: 6 duplicated texts over 23 casillas — 4 AEAT repeats inside T22005A01, 1 box
declared twice, and this.

### Scale

**10174 of 11570 slots remain** across 104 numbered records; 1396 modelled, zero orphaned.
This record has no TOTAL: the aseguradoras activo continues onto sheets not yet authored.

## 2026-08-23 — T22003B02, and the identifier that was in the data all along

### What landed

Record **T22003B02**, closing the aseguradoras *balance consolidado activo* on `00162`
TOTAL ACTIVO. **20 casillas**, revision 1562 → **1582**, thirty of 137 records.

Suite: four new FAILED entries, **none mine** — see below.

### AEAT declares each record's identity in its envelope, and this campaign was discarding it

The design carries literal constants at `@6`, `@8`, `@9` — **página, letra, hoja**. Every
fragment since the first has excluded those eight envelope fields as "identifier envelope
mechanics".

Sibling sector pages share **every heading AEAT prints in the body**: three ACTIVO records
all head their lines `ACTIVO`, and two declare a box called `Total activo`. **Four operator
labels had collided across them**, including two *different* boxes both reading
`Balance consolidado. Activo. Total activo`.

The envelope is the only **non-inferential** way to tell such records apart — and it was
sitting in data already read and already thrown away.

Swept across five records (T22003A00, A02, B02, T22005A01, A02): **184 labels** now carry
`(pág. 3A hoja 00)`, `(pág. 3B hoja 02)`, `(pág. 5A hoja 01)` and so on. Revision duplicates
fall from **9 texts over 29 casillas to 4 over 19**, and every survivor is AEAT's own repeat
inside T22005A01, where the design prints no hierarchy to separate them.

**The previous entry framed the collision as the price of refusing to infer a sector. That
framing was incomplete** — there was a third option, in the data, and it took a *fourth*
collision before I went looking. A cost accepted twice should have prompted the search the
first time; "we chose the lesser evil" is a conclusion worth re-opening whenever the same
evil recurs.

### The suite measured a moving tree again

The FAILED list gained four entries. Re-running each individually: **three already passed**,
and the fourth failed on `registrar command is absent for 'modelo work calculate'` — a
peer's CLI command-spec sweep landing mid-run. None reads registry TOML or locale YAML.

Zero regressions from this work, and the diff-against-baseline discipline is exactly what
separated four external entries from a real one. Second time this campaign that a peer's
in-flight work has appeared in my results; both times individual re-runs settled it in under
a minute.

### Smaller notes

- **The sheet suffix says B and this is an ACTIVO page.** It continues A02. The suffix
  letters in this family do not track the side of the balance.
- `00150`, `00151`, `00152` carry no prefix naming `00149` though they break it down on the
  printed modelo — left flat, as ever.
- AEAT capitalises `Empresas` on `00150` and not on `00151`, inside one group of three
  parallel lines. Transcribed as printed: a rule regularising casing would be a rule about
  AEAT's typography, and this campaign has paid three times for those.

### Scale

**10154 of 11570 slots remain** across 103 numbered records; 1416 modelled, zero orphaned.
The aseguradoras activo now has a total, and nothing computes it.

## 2026-08-23 — T22003C02, the aseguradoras pasivo

### What landed

Record **T22003C02** — the *balance consolidado pasivo* in the aseguradoras shape: débitos y
partidas a pagar with its long breakdown, provisiones técnicas and no técnicas, pasivos
fiscales, resto de pasivos, closing on `00207` TOTAL PASIVO. **48 casillas**, revision
1582 → **1630**, thirty-one of 137 records.

### One suffix, two parents, one translation

`Provisión para primas no consumidas` sits **twice** in this record — once under
*provisiones técnicas* (`00183`) and once under *provisión de seguros de vida* (`00186`).
`Provisión para riesgos en curso` does the same (`00184`, `00187`).

They are different boxes; the composed labels separate them. But **translating each suffix
once is what keeps the two readings identical in all four catalogues where AEAT prints them
identically.** A per-box translation table would have let the pair drift — the same failure
the campaign already hit when a Hungarian string collapsed two lines AEAT separates by a
definite article.

That is the quiet argument for composition over per-box tables: it makes *sameness* as
enforceable as difference.

### The page identifier held

`(pág. 3C hoja 02)`, from the envelope constants. The revision's duplicated-label count is
**unchanged at 4 texts over 19 casillas** — all AEAT's own repeats inside T22005A01. This
record added none, which is the first evidence the mechanism generalises rather than just
patching the four collisions that prompted it.

### The suite measured a moving tree for the third iteration running

Three new FAILED entries — one legal-grounding scan over production Python, two
scenario-runner reachability checks. **All three pass on an individual re-run.** None reads
registry TOML or locale YAML.

The cost of establishing that is about a minute, and the diff-against-baseline is what makes
it cheap: without it the choice is between accepting a twelve-failure run and re-running
everything. Worth stating as settled practice rather than re-deriving it each time.

### Both totals now exist for this sector, and nothing relates them

`00162` TOTAL ACTIVO (page 3B) and `00207` TOTAL PASIVO (page 3C) are both declared. Nothing
sums a group into its head, nothing sums heads into either total, and nothing checks activo
against pasivo plus patrimonio neto — **for which T22003D02 is not authored at all**, so the
accounting identity could not be expressed here even if something were willing to.

### Scale

**10106 of 11570 slots remain** across 102 numbered records; 1464 modelled, zero orphaned.

## 2026-08-23 — T22003D02, closing the aseguradoras balance sheet

### What landed

Record **T22003D02** — the aseguradoras *patrimonio neto*, closing on `00232` TOTAL
PATRIMONIO NETO and `00233` TOTAL PASIVO Y PATRIMONIO NETO. **36 casillas**, revision
1630 → **1666**, thirty-two of 137 records.

**The aseguradoras balance sheet is now complete**: pages 3A and 3B the activo, 3C the
pasivo, 3D the patrimonio neto.

Suite: identical to the clean baseline, **zero regressions**.

### AEAT abbreviates a parent on one child and not its sibling

`00219` reads `Resultados de ejercicios anteriores atribuidos a la sociedad dominante.
Remanente`; `00220` reads `Resultados de ejercicios anteriores. (Resultados negativos …)` —
the same concept, written short.

**The short form is not a standalone box of this record**, so it stays *inside the leaf
label* rather than being promoted to a heading it never was. My first attempt at the
translation table did promote it — and the unmapped-parent assertion refused, which is how
the question got asked at all.

Expanding it to match the sibling would be a guess that two lines AEAT wrote differently
mean the same thing. Same refusal as T22005A01's flat authoring and the unparented `00701`
/ `00761`.

### The registry was red on the first load and green on the second

3569 failures, every one in modelo 200 revision 2024, while a peer's revision rename and
export-layout work was landing. The immediate re-run loaded clean.

**Fourth iteration in a row where re-running before diagnosing was the whole diagnosis.**
Two of those four would have cost an hour of investigation each if the first reading had
been taken as fact.

### The accounting identity is now expressible, and still not expressed

`00162` TOTAL ACTIVO and `00233` TOTAL PASIVO Y PATRIMONIO NETO are both declared, and
**nothing relates them**. Authoring all four pages made the check possible; it did not make
it exist.

That is worth restating each time it changes state, because "the balance sheet is complete"
is exactly the sentence a reader will shorten to "the balance sheet balances."

### Scale

**10070 of 11570 slots remain** across 101 numbered records; 1500 modelled, zero orphaned.
The general-PGC balance is complete; the crédito one — A01, A11, B01, C01 — is not.

## 2026-08-23 — the crédito activo, and a stamp made without a usable suite run

### What landed

Records **T22003A01** and **T22003A11** — the *balance consolidado activo* in the entidades
de crédito shape, closing on `00152` TOTAL ACTIVO. **66 casillas**, revision 1666 →
**1732**, thirty-four of 137 records.

### The suite could not be diffed, and the stamp says so first

The registry suite returned **604 failures and 96 errors** against a clean baseline of 9.
Cause: a peer's in-flight modelo 200 work leaves the whole authority failing validation —
**3596 validation failures, zero naming modelo 220**, stable across three consecutive load
attempts. Every test that loads the authority fails regardless of this work.

The FAILED-list diff is the gate this campaign leans on hardest, and it was unavailable. The
record-level checks *did* run, before the breakage and against a loaded authority.

**The stamp leads with that gap rather than burying it**, and states plainly that the
revision's suite state is unknown: *"it was green at the previous stamp and nothing here
touches production code, but that is an argument, not a measurement."* The next iteration
must re-run once m200 clears.

Choosing to stamp at all was the close call. Not stamping would have left the previous stamp
standing at 32 records / 1666 casillas — an out-of-date claim is its own small dishonesty,
and a disclosed gap beats a stale number.

### Thirty-three of fifty-four boxes share a label, and that is the honest cost

T22003A01 is a **portfolio × instrument matrix**: AEAT prints the portfolio head on its own
row and the instrument rows beneath it *without* the portfolio name. Five boxes read
`Valores representativos de deuda`, five `Préstamos y anticipos`, five the same Pro memoria
line.

A numbering-block rule was considered and refused as **partial**: the `00615`, `00623`,
`00631` runs are contiguous, but the `00102` and `00110` runs have gaps and their Pro memoria
lines carry out-of-run numbers `00750`/`00751`. **Right for three blocks and not two** is
precisely the case already refused on T22005A01.

Stated plainly on the fragment: an operator surface showing labels without numbers will
present five identical rows on this page. A real cost, recorded rather than traded for an
unverifiable tree.

### The duplicate assertion had to change to admit the record

The generator asserted **no duplicate labels**. That would have refused T22003A01 outright
and forced a distinction AEAT does not make. It now asserts **the duplicated set equals the
design's** — the form the T22005A01 *locale* generator already used, now also in the
fragment generator.

Third time this campaign a check has fired on AEAT's own structure rather than a defect.
The pattern is stable enough to name: **a check encodes an assumption about the data; when
it fires on a new record, ask which of the two is wrong before fixing either.**

### A record that spells its own heading two ways

T22003A11 prints both `ACTIVO (cont.).` and `ACTIVO (cont).`. A common-prefix derivation
stops mid-word at `ACTIVO (cont` and finds *no* heading, which would have left the prefix on
all twelve labels. The sheet now declares a heading **pattern**; every line is asserted to
match and the spellings found are reported.

### Scale

**10004 of 11570 slots remain** across 99 numbered records; 1566 modelled, zero orphaned —
measured by reading the committed TOML directly, because the authority would not load.

## 2026-08-23 — no record authored; the measurement pattern was wrong instead

### The gate is still down, so the iteration did something else

The authority still will not load — a peer's modelo 200 work leaves **5475 validation
failures, zero naming modelo 220**, stable across repeated attempts. The previous stamp
deferred a suite verification to "the next iteration"; **this is that iteration and it cannot
discharge it either.**

Rather than add a second record's worth of unverified surface, this iteration paid the part
of the debt that does not need the authority: a direct re-derivation of every authored
casilla from the design.

### The provenance claim holds — 1732 casillas, zero problems

Every casilla across 39 fragments and 32 sheets checked against `aeat-dr-220-2024` without
the authority: every segmento a real sheet; every numeric number **printed by AEAT**, none
minted; every byte span resolving to a field at exactly that offset and length; every letter
number a bracket AEAT prints; all 32 sheets tiling once with no gap and no partial overlap;
no repeated id or `(segmento, number)` pair.

### And the verifier found a defect in my own reporting

It flagged three casillas — `[2309]`, `[4520]` on T22012B00 and `[000507]` on T22012B20 — as
**minted numbers**. They are not. AEAT prints all three.

**AEAT's box numbers on modelo 220 are not all five digits**: the design carries **12
three-digit, 13 four-digit and 8 six-digit** brackets alongside 11610 five-digit ones. The
pattern `\[(\d{5})\]` was chosen once at the first m220 measurement and **inherited by every
figure since**, so 33 real filing boxes were never counted.

**The true denominator is 11603, not 11570.** Corrected: 1569 modelled, 10034 remaining.
Every "N of the 11570" in this revision's earlier stamps understates both sides.

Checked and clean: of the 33, three are authored and **thirty lie in records not yet
authored — zero fall inside a record already shipped.** The per-record completeness
complement was field-level and never had the flaw; only the coverage arithmetic did.

### What this says, beyond the number

A verifier written *specifically to be trustworthy* encoded the same wrong assumption as the
thing it was verifying, and reported correct data as defective. That is the **fourth** time
this campaign a check has fired on AEAT's own structure rather than a defect — and the first
inside a verification whose whole purpose was to be believed.

The general shape: **a measurement pattern adopted at first contact with a corpus silently
defines what counts as data for everything downstream, and nothing re-examines it unless
something forces the question.** Writing a second check does not help if it inherits the
first one's premise. What forced the question here was checking the corpus against the
*design* rather than against another derived figure.

### Scale

**10034 of 11603 slots remain**; 1569 modelled, zero orphaned, across 34 of 137 records.

**Obligation carried forward:** the next iteration that finds a loadable authority must run
the registry suite and diff the FAILED list *before* authoring anything further. Two stamps
now stand with the suite state recorded as unknown.
