---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S27'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the redeclaration conformance gate - the terminology sibling of the command-conformance gates - scanning MyST sources for prose re-declarations of enrolled terms and failing on inline redefinition (ADR D7/D8)

## Scope

- `docs conformance test suite`

Implements ADR D7 + D8: the novel redeclaration conformance gate that locks in
the cutover. No surveyed docs system detects prose redeclaration (research P3);
this gate makes "terminology is codebase-state-as-truth" a tested invariant -
once a term is approved in the Handbook, docs must reference it with `{term}`,
never inline-redefine it. The terminology sibling of the command-conformance
gates. Only the prorrata end-to-end smoke gate remains in W04.P12.

## Description

- Ground the house conformance-test pattern from
  `test_educational_docs_conformance` / `test_documented_command_conformance`
  (docs/integration marked, `PROJECT_ROOT` doc discovery, per-doc parametrise,
  precise assert messages, code-block stripping).
- Load the APPROVED enrolled term labels from the Handbook (preferred +
  admitted, filtered to `lifecycle == approved`) - the rendered `:term:`
  anchors the gate enforces.
- Prototype the detector against the real docs to CALIBRATE for precision:
  a loose "term is a ..." detector over-flagged (false positives on
  descriptive prose like "Modelo 303 is the quarterly return" and on the
  different-referent "AEAT is a tax-filing application" describing the app); a
  TIGHT inline-glossary-shape detector found exactly the genuine missed
  conversions.
- Fix the 4 genuine missed redeclarations the tight detector found (all
  `justificante` glossary-shape glosses S26 missed), converting them to
  `{term}` references.
- Author the gate `test_terminology_redeclaration_conformance.py` with the
  three detector shapes, the exclusion of generated surfaces, code-block /
  `{term}`-reference stripping, the per-doc scan, plus positive/negative
  anti-tautology fixtures.
- Verify: the gate green on the real docs, the fixtures green, ruff + format +
  ty clean, the sibling conformance still green.

## Outcome

### Detector approach + how false positives were avoided

The gate flags the inline-GLOSSARY SHAPE, not ambiguous descriptive prose -
three patterns per term: (1) an emphasised term + a definitional separator
(`*justificante* - the receipt ...`, `**casilla**: a numbered box`), (2) an
emphasised term + a definitional clause (`*casilla* is a / means ...`), (3) a
term immediately followed by a parenthetical gloss (`justificante (the official
receipt ...)`). These are the exact shapes the cutover deleted.

Precision was the design priority (the brief: a false positive that reds the
build is worse than a missed borderline). A loose "`<term> is a/the ...`"
detector produced false positives - "Modelo 303 is the quarterly VAT return" on
a Modelo-303 how-to (legitimate descriptive framing) and "AEAT is a Spanish
tax-filing application" (describing the app `aeat`, a DIFFERENT referent than
the AEAT agency term). The tight glossary-shape detector flags none of these:
it requires the emphasis/parenthetical glossary form, so a plain prose sentence
that merely uses a term is not flagged. Three further precision guards: fenced
code blocks and inline code are stripped (a term in a command example is not a
redeclaration), correct `{term}` / `:term:` references are stripped before
scanning (a reference is never a flag), and the generated glossary / CLI / API
surfaces are excluded (they legitimately define terms).

### The approved-term set enforced + the unapproved exclusion

The gate drives off the APPROVED enrolled terms only - the 35 rendered
`:term:` anchors (preferred + admitted labels of the 20 approved concepts:
`casilla`, `AEAT`, `justificante`, `modelo 100/130/303/390`, `prorrata`, `RE`,
`ISP`, `recargo de equivalencia`, `regimen del recargo de equivalencia`, etc.).
These are distinctive Spanish-stem terms, not generic English words, so a
definitional clause adjacent to one is genuinely a redeclaration. The 16
unapproved gap terms (`IVA`, `IRPF`, generic `modelo`, `renta`, `NIF`,
`asesor fiscal`, `autonomo`, `binding`, `fichero-BOE`, `formula`, `ledger`,
`preflight`, `revision`, `verificado completo`, `VIES`, `work unit`) are NOT in
the enforced set - they have no anchor, so their inline mentions are legitimate
until approved, and the gate must not flag them. Because the gate loads the
approved set live, it WIDENS automatically as concepts get approved.

### Real-docs run: green, with 4 missed conversions found and fixed

The tight detector flagged 4 genuine glossary-shape redeclarations of
`justificante` that the S26 cutover missed (outside the educational dirs S26
focused on): `*justificante* - the receipt that proves you filed`
(`explanation/index.md`), and `justificante (the official receipt ...)` in
`how-to/file-at-aeat.md`, `how-to/reconcile.md`, and
`how-to/review-calculation-values.md`. All 4 were converted to `{term}`
`justificante`` references (the definition lives in the glossary). After the
conversions the gate is GREEN on the full docs tree - zero redeclarations of
any approved term remain.

### Positive / negative fixtures (anti-tautology)

`test_positive_fixture_detects_inline_redeclaration` - the detector FIRES on
all three shapes (emphasised+separator, emphasised+clause, parenthetical),
proving it can catch a real redeclaration. `test_negative_fixture_passes_
legitimate_prose` - the detector stays SILENT on a correct `{term}` reference,
a non-definitional mention ("Each casilla holds one figure"), a code example,
and an unapproved-term inline definition ("IVA is a value-added tax ...") -
proving no false positives. Both green.

### Tests + pass

`test_terminology_redeclaration_conformance.py` - 41 green (the
approved-terms-loaded guard + the positive/negative fixtures + the per-doc scan
across the user-docs tree). The sibling `test_educational_docs_conformance.py`
stayed 65 green (the justificante conversions did not break any link). ruff /
format / ty clean; collect-only clean.

## Notes

- SCOPE FENCE honoured: S27 is the gate. It does NOT build the prorrata
  end-to-end smoke gate (S28).
- A peer's uncommitted WIP (an incomplete `PeriodError` error-code registry
  binding in `src/aeat/core/_period.py`) transiently blocked the `aeat` package
  import, so the gate test could not run via pytest for part of the session;
  the detector logic was proven correct in isolation (pure-regex, no `aeat`
  import) in the interim, and once the peer completed the binding the full gate
  test ran green (41 passed). I did not touch the peer files.
- No PM wave/phase/step tokens in production code (ADR ids only in this exec
  record).
- THE CURATION LEVER (richness backlog for W05 / curation): the gate's coverage
  is exactly the approved-concept set. Approving the high-frequency gap terms -
  especially `IVA`, `IRPF`, and a generic `modelo` concept - would let the gate
  enforce `{term}` references on their many current plain mentions too, and let
  a future conversion pass convert them. The gate widens automatically the
  moment those concepts reach `approved`; no gate change is needed.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` over ONLY my explicit paths
  (the gate test + the 4 justificante doc conversions + exec record).
