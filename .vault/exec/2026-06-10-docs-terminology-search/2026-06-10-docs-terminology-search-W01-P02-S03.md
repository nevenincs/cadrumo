---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S03'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement the BOE normatives HTML-to-text preprocessor splitting on the BOE article delimiter and stripping TOC link farms, emitting schema-conformant output (or interim sidecars) for the 13 MB normatives corpus (ADR D6)

## Scope

- `dev preprocessing tooling + src/aeat/_data/corpus/normatives`

Implements the ADR D6 index-capability prerequisite for the BOE/legal
grounding surface: a reader query like "pro rata" must reach the actual BOE
article text the code is grounded against (``legal_refs`` resolve into this
corpus), as clean per-article prose rather than raw markup. Reuses the
interim sidecar contract; generalises the ``_example.py`` HTML stub into the
production extractor (the stub stays a worked example only).

## Description

- Ground the BOE document structure via `rg`: confirm `<h5 class="articulo">`
  is the article boundary, the `[Bloque N: #aN]` marker carries the per
  article anchor, the TOC link farm is `<li><a href="#aN">` before the first
  article, and the legal text is wrapped in `<div id="textoxslt">` with a
  `<div id="pie">` page footer to exclude.
- Inventory the corpus: 219 tracked HTML files (~11.5 MB) - 55 full
  multi-article laws/RDs/ordenes plus 164 single-article slices; 8 sibling
  manifests carry the document `boe_url`.
- Author the production extractor module `_html.py`: clip to the
  `textoxslt` content container (dropping page chrome), strip forms /
  scripts / styles / the "Subir" nav, split on `<h5 class="articulo">` into
  one `PreprocessUnit` per article (titled by the heading), stamp the `#aN`
  anchor from the preceding bloque marker, strip all bloque markers and
  residual tags, and decode HTML entities to real Spanish characters.
- Resolve attribution from the sibling `manifest.json` `boe_url` (per
  document) with the standing BOE/AEAT fallback for manifest-less slices.
- Author a real-behaviour test suite (7 tests) over a real multi-article law
  and a real single-article slice: article splitting with anchors, TOC /
  form / footer / entity stripping (boilerplate ABSENT, prose PRESENT),
  dual attribution, walker pickup against the installed package, and an
  anti-tautology tampered-sidecar rejection.
- Run the extractor over all 219 tracked HTML files, writing committed
  `*.extracted.md` + `*.extracted.json` sidecars in place (LF newlines).
- Verify: ruff check + format clean, `ty check` clean, the full preprocess
  suite green, the subtree collect-only clean, plus a whole-corpus dry-run
  asserting zero markup / entity / footer leaks across all 219 files.

## Outcome

### Coverage

- **219 tracked normatives HTML files**, all extracted into **1,060 article
  units** (one `PreprocessUnit` per BOE article), zero failures, zero
  splits. 219 `.md` + 219 `.json` sidecars written, all LF-clean.
- 55 full consolidated laws/RDs/ordenes split into many articles each (the
  IVA law `ley-37-1992` yields 242 article units); 164 single-article slices
  yield one unit each.

### Article splitting approach + sample

Split on `<h5 class="articulo">`; each article runs from its heading to the
next heading. The article anchor `#aN` is read from the `[Bloque N: #aN]`
marker that precedes the heading and stamped on the unit so a hit deep-links
to the specific article on the BOE permalink. Sample (IVA law, Articulo 1):
the unit is titled `Artículo 1. Naturaleza del impuesto.`, anchored `#a1`,
with body text `El Impuesto sobre el Valor Añadido es un tributo de
naturaleza indirecta que recae sobre el consumo y grava ...` - clean,
accented Spanish, no markup. The rendered `.md` carries the heading as a
`#` title line and the article body beneath.

### How TOC stripping (and the other noise) is verified

The TOC link farm lives before the first `<h5 class="articulo">`, so
splitting on the delimiter discards it with the preamble; the per-article
jurisprudence `<form>` controls, `<script>`/`<style>`, the "Subir"
back-to-top nav, the `[Bloque N: #...]` navigation markers, and the
`<div id="pie">` page footer (site chrome / the AEBOE postal address) are
explicitly removed. Verification is a dedicated test asserting the
boilerplate is ABSENT (`<li>`, `href=`, `<a `, `Jurisprudencia`, `[Bloque`,
`Subir`, `Aviso legal`, `Avda. de Manoteras`, `&iacute;`/`&oacute;` entities)
and the real article prose is PRESENT, plus a whole-corpus dry-run that
confirmed zero markup / entity / footer leaks across all 219 files. Two
content-quality issues surfaced by the tests during development were fixed:
a page-footer leak into the last article (fixed by clipping to the
`textoxslt` container) and undecoded HTML entities (fixed with
`html.unescape`).

### Largest sidecar

**0.708 MB** (`ley-35-2006`, the IRPF law) - far under the 10 MB walker cap,
so no article needed the budget splitter (the safety net from the shared
`_parts.py` remains in place).

### Attribution

Per-document BOE permalink from the sibling manifest where present (e.g. the
IVA law pins `https://www.boe.es/buscar/act.php?id=BOE-A-1992-28740`); the
164 manifest-less single-article slices fall back to the standing BOE/AEAT
attribution - never unattributed.

### Verification

- Test: `test_html_extractor.py` - 7 tests, all green. The full preprocess
  suite is 28 green (7 here + 7 PDF + 8 workbook + 6 contract). `ruff check`,
  `ruff format --check`, `ty check`, and the subtree collect-only all clean.
- Sidecar paths verified not gitignored, so the committed sidecars need no
  `.gitignore` change.

### Raw-vs-sidecar dedup flag for the W01.P03 verification step (S08)

FLAG, not acted on here per the brief: the raw `.html` files are ALREADY a
walker-supported extension and ALREADY indexed as raw markup, so the new
clean `*.extracted.md` sidecars are ADDITIVE - the same normatives content
now exists in the index twice (raw markup chunks plus clean article chunks).
The clean sidecars rank better, but the raw markup chunks remain and will
surface duplicate-but-worse hits (the F4-audit low-score-tail pollution).
S08 (retrieval verification) should decide whether to EXCLUDE the raw
normatives `html/*.html` from the docs-search index (e.g. via a
`.vaultragignore` entry for `src/aeat/_data/corpus/normatives/html/*.html`
while keeping the `*.extracted.md` sidecars) so only the clean per-article
text is retrieved. This is a retrieval-quality decision for S08, not an
extraction concern; the extraction here is complete and correct regardless.

## Notes

- No PM wave/phase/step tokens in production code or comments (ADR ids only
  in this exec record). No type escapes (the manifest read uses `isinstance`
  narrowing, no `cast`).
- The shared `_parts.py` budget splitter (added in S05) is reused here, so
  the three corpus extractors (workbook, PDF, HTML) split identically.
- The committed sidecar tree retires when the upstream `vaultspec-rag`
  preprocess-hook lands (the established retirement trigger);
  `PreprocessOutput` precursor-compatibility is intact.
- Commit discipline: all verification ran first; staging and the commit are
  a single chained `git add ... ; git commit ...` as the very last action,
  explicit paths only, never touching `index.lock`. If a peer commit still
  splits the work, the work is intact and the hashes are reported.
