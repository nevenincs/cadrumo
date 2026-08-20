---
tags:
  - '#audit'
  - '#registry-temporal-coverage'
date: '2026-08-20'
modified: '2026-08-20'
body_schema: 'body-v1'
body_hash: 'sha256:5a9f5b269d0714d726a373cb7e3f91d9d7f86c9f7f43848f470f942b23077fd1'
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
for m194's). **No plazo article of either orden was ever amended.** AEAT's Calendario
del Contribuyente nevertheless publishes "Hasta el 31 de enero" for modelos 180, 188,
190, 193, 193-S, 194, 196 and 270.

So the declared window is a CONSERVATIVE SUBSET of the legal telematic window -- it
closes 31 January where the cited orden allows until 20 February -- and matches AEAT's
published operational calendar. Deliberately unchanged: widening to 20 February would
be legally grounded but would tell an operator they have three weeks more than AEAT
publishes, and re-grounding onto the Calendario would ground a filing DEADLINE in a
guidance page. This needs an operator ruling, not an agent edit.

The contrast explains why modelo 187 could be stamped and its two siblings could not:
m187's approving orden is from 2014 and restates the window in modern form ("entre el
1 y el 31 de enero de cada año"), so its plazo is grounded. Identical casilla work,
different grounding outcome, visible only by reading each orden's plazo article.

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

## Recommendations

- **Operator ruling needed** on the m188/m194 window: keep 1-31 January and accept
  AEAT's Calendario as its authority, or widen to the cited orden's 20 February. Do not
  leave it citing a provision that states neither.
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
