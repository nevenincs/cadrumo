---
tags:
  - '#audit'
  - '#declaracion-real-render-verification'
date: '2026-07-27'
modified: '2026-07-27'
related:
  - "[[2026-07-26-declaracion-real-render-verification-plan]]"
  - "[[2026-07-26-declaracion-real-render-verification-adr]]"
---

# `declaracion-real-render-verification` audit: `attacking the R12 language partition, plus scoping the decl.ejercicio fix`

## Scope

Two tasks. First, attack render-verifier's language-immunity partition (all
124 immune targets are exactly `bbox_anchored` plus `numeric_casilla`, all
154 exposed targets are `named_label`, nothing else correlates) by a
different method than the profile-by-profile sweep that produced it, and by
checking for the specific failure modes named in the dispatch brief. Second,
scope the `decl.ejercicio` `value_kind` fix Step `P04.S24` names: what
consumes the extracted value, whether the "plain integers" protocol wording
is live, and whether the fix is contained or a typed-boundary change.

Report-only throughout: no registry data, production code, or test file is
modified. The semantic code index remained truncated throughout and was not
used as evidence. Method is stated beside every claim; measured versus
inferred is stated per conclusion.

## Findings

### the-282-target-census-reproduces-exactly-under-a-genuinely-different-method | high | raw tomllib fragment parse against the loaded-authority sweep P03.S10 used

P03.S10 measured by loading each revision through the registry authority.
Re-derived the same census by parsing every `extraction_profiles/*.toml`
fragment directly with `tomllib`, filtering `surface == "declaracion_pdf"`,
with no authority object model involved at all: 282 targets, 158
`named_label`, 102 `bbox_anchored`, 22 `numeric_casilla`. Exact match, by a
method that does not share any code path with the one that produced the
original figures.

### no-named-label-pattern-is-secretly-immune-checked-three-ways | high | the partition is exact, not exact-given-current-data

Attacked the specific failure mode named in the dispatch brief: a
`named_label` pattern that matches on digits or a box number alone would sit
in the exposed bucket while actually being immune. Checked all 158
`named_label` patterns three ways. First, whether any carries no alphabetic
run of three or more characters at all (the classifier's own immunity
rule) -- zero do; every one genuinely has prose content the rule would flag.
Second, whether any pattern's entire alphabetic content is acronym-shaped
(all-uppercase, the signature of a language-invariant code like `IVA` or
`NIF` rather than translated prose) -- zero do; every pattern includes at
least one lowercase word. Third, whether any pattern's required alphabetic
content consists entirely of English-Spanish cognates (`total`, `base`,
`declaración`, and similar words spelled identically or near-identically in
both languages) -- zero do. Manually read the twenty patterns with the
least total alphabetic content, the ones most likely to be thin enough to
hide a false exposure classification, and none of them is a cognate or an
acronym: `Ejercicio`, `Suma`, `Resultado`, `Periodo` and similar are all
Spanish-specific vocabulary with no reason to expect the same string on an
English, Catalan, or Galician render.

**The partition is measured as exact, not merely assumed exact from the
current 29-profile snapshot.**

### bbox-anchored-immunity-has-one-real-cross-language-data-point-not-zero | high | measured directly on the only bilingual pair the repository holds

Attacked the second named concern: `bbox_anchored` anchors on the printed
box number, but the surrounding layout positions it, and a render in
another language might reflow that layout. The repository holds exactly
one genuine cross-language pair to check this against -- Modelo 390's
Spanish facsimile (`manual_annexes/390/2024-0A.pdf`) and its English real
render (`justificantes/390/2021-0A.pdf`) -- and both share a `bbox_anchored`
target on box 49 (`iva.anual.soportado.interiores`).

Extracted the raw word positions from both PDFs directly with the real
production `_extract_pages_words` and located the word `"49"` in each: `x0
= 412.81` on the Spanish facsimile, `x0 = 411.89` on the English real
render -- a difference under one point, and both comfortably inside the
profile's own `anchor_x_min = 407.0` / `anchor_x_max = 425.0` window. The
box-number column did not reflow when the surrounding label prose was
translated to English.

This is real, not inferred: one specific target, on one specific modelo,
empirically confirmed stable across a genuine language change. It is not
proof that all 102 `bbox_anchored` targets across every modelo behave the
same way -- this is the only cross-language pair the repository has, so
there is no second data point to check it against -- but it is evidence
where the claim previously had none, and the structural reason it should
generalise is sound: AEAT's box-number grid is part of the form's fixed
regulatory template, and only the descriptive label text is localised
within it, which is exactly the pattern this one measurement shows.

**One genuine empirical data point, not zero, and a structural reason to
expect it generalises -- stated as what it is, not overstated as full
coverage.**

### zero-evidence-of-catalan-or-galician-renders-exists-anywhere-in-the-repository | high | the lower bound is entirely inference, confirmed by exhaustive search

Attacked the third named concern directly. Grepped every fixture sidecar
under `justificantes/` and `manual_annexes/` for a `language` or `idioma`
field -- none exists on any of the sixty sidecars, in either family.
Grepped the entire fixture and corpus tree for "catalan", "gallego",
"euskera", or "idioma" in any casing -- zero genuine hits (the file-path
grep also matched PDF binary content on a first pass, which was a probe
error rather than a finding, corrected by restricting the search to text
and JSON files).

The repository holds exactly one non-Spanish real specimen (the Modelo 390
English render) and zero specimens in any co-official language. Every
claim this campaign or any prior one has made about Catalan or Galician
render behaviour is inference from the Spanish-versus-English case, never
a measurement of either language directly. The register should say so
explicitly rather than let "language exposure" read as a claim covering
languages the repository has never actually seen.

### the-extracted-decl-ejercicio-casilla-value-has-no-production-consumer-beyond-the-parser-boundary-tests | critical | this is the finding that resolves the whole scoping question

Traced every production reference to `ejercicio` in `_reconcile.py` and
`_verify.py`. Every one of them reads `declaracion.ejercicio` -- a
top-level `str | None` field on `InboundDeclaracionObservation`, populated
independently during template detection by `_detect.py`'s own header
regex, which runs before and separately from the extraction-profile target
matching. None of them reads `declaracion.values["decl.ejercicio"]`, the
casilla-keyed entry the extraction profile target actually produces.

Separately, `_binding_resolution.py` resolves the informational casilla
carrying `semantic_role = "filing_year"` (which is `decl.ejercicio` on
every one of the seven affected modelos) by synthesising
`Decimal(filing_year)` directly from the work unit's own known filing year
-- a calculation-time mechanism entirely independent of the declaración
parser. This is the second, separate writer for the same concept, and it
is unaffected by anything the extraction profile declares.

None of the seven affected modelos (184, 347, 369, 720, 840, 232 both
revisions) are in `_DECLARATION_CASILLA_RECONCILE_MODELOS`, so there is no
live reconcile consumer that would compare a parsed `decl.ejercicio` value
against anything either.

The only place this campaign found that reads the specific
`values["decl.ejercicio"]` entry the extraction profile produces is the
parser-boundary test suite itself -- confirmed in
`test_parser_synthetic_fixtures_m184.py` and `test_parser_boundary_m369.py`,
both asserting `values[casilla_id] == Decimal("2024")` -- which exists to
prove the extraction mechanism works, not because a downstream consumer
needs the value in that shape.

### the-fix-is-contained-not-a-typed-boundary-change | high | direct consequence of the finding above

Changing `value_kind` from `"amount"` to `"text"` on these seven casillas
changes `_classify_target`'s output for them from `Decimal` to `str`
(`_parser.py:591`, the `"text"` and `"enum"` branch stores the raw captured
token as-is). Given the finding above, that type change reaches no
production consumer: not reconcile, not verify, not the calculation-side
`filing_year` binding, which never reads the parser's output at all.

It does reach the parser-boundary test suite, which currently asserts
`Decimal("2024")` in at least the two files named above (this pass
confirmed both directly; the dispatch brief's "at least five" figure was
not independently reproduced to an exact count, since doing so would
require running the full test file rather than reading it, which this
audit's report-only scope does not include, but the two confirmed cases
establish the assertion shape is real). Each such assertion needs a
one-line change from `Decimal("2024")` to `"2024"`.

`domain/filing/_protocols.py`'s "plain integers" wording describes
`build_draft`'s input contract (`ModeloInputScalar = str | int | Decimal |
bool | date`), a different boundary than the parser's output type, and
this pass found no code path that feeds the parser's extracted
`decl.ejercicio` value into `build_draft` at all -- the filing_year value
`build_draft` would consume, if it consumes one, comes from the work unit's
own known filing year via the calculation-side binding, not from a parsed
PDF. The protocol wording is accurate for what it describes and irrelevant
to this fix.

**Contained: a registry field change plus two-or-more mechanical test
updates, touching no production consumer.**

### text-not-enum-is-the-correct-target-and-the-hazard-is-also-practically-theoretical | medium | both halves of the dispatch brief question resolve in the same direction

Checked whether `"enum"` carries any distinct behaviour from `"text"` that
would make it the more correct choice for a year. It does not:
`_classify_target`'s implementation treats `"text"` and `"enum"`
identically (the same branch, "store the raw captured token as-is"), and
nothing in the schema validates an `"enum"`-kind target against a closed
set of allowed values -- no `enum_values` field or equivalent exists
anywhere in `_schema_extraction.py`. `"enum"` is currently a purely
documentary label with zero enforced distinction from `"text"`. Since a
fiscal year is an open numeric range rather than a closed set of
admissible tokens, `"text"` is the semantically honest choice; `"enum"`
would assert a validated closedness the schema does not provide.

The hazard the guard exists to prevent is also lower-consequence here than
for the M180/M349/M100 boxes it was built for. All seven `decl.ejercicio`
casillas are `required = true`: every one of them is `informational`
metadata that any genuine AEAT document of that modelo must print. A blank
`decl.ejercicio` box is not a legitimate optional omission the way a blank
M180 perceptor-count box is -- it signals a malformed or truncated
document, not a normal filing. The fabrication risk the guard defends
against (a blank box's own printed number silently becoming a plausible-
looking value) is real in principle for any `value_kind = "amount"`
target, but its practical exposure on these seven is close to theoretical:
the scenario requires a genuinely malformed real AEAT document, not a
normal filer's legitimate choice.

## Recommendations

The language-immunity partition is confirmed, not merely repeated: reproduced
by a genuinely different method (raw `tomllib` versus the authority-loaded
sweep), attacked for false negatives on all three fronts the dispatch brief
named, and found exact on every one. This is a stronger result for having
been attacked -- say so plainly when the partition is cited going forward,
rather than treating it as re-derived from scratch each time.

Word the bbox-anchored immunity claim precisely wherever it is cited: "one
empirically confirmed cross-language data point plus a structural reason to
expect it generalises," not "confirmed immune." The distinction matters
because it is the only place this pass found the evidence weaker than the
confidence the claim is usually stated with.

State the Catalan/Galician gap explicitly in any document that discusses R12
closure: the repository has zero evidence for either language, and any
claim about them is inference from the Spanish-English case alone.

`P04.S24` (the `decl.ejercicio` fix) can be closed as a contained change:
flip `value_kind` to `"text"` on the seven casillas, update the parser-
boundary test assertions from `Decimal("2024")` to `"2024"` (at least the
two this pass confirmed directly), and note in the Step's own record that
no production consumer was found to depend on the parser's output type for
this casilla, since both live consumers (reconcile/verify's header field,
and the calculation-side `filing_year` binding) use an entirely separate
mechanism. Leaving it alone, per the dispatch brief's alternative, would
also be defensible given the hazard's near-theoretical practical exposure
on `required` casillas -- either closure is sound; what should not happen
is treating this as a typed-boundary change requiring wider redesign, which
the evidence does not support.
