---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
step_id: 'S05'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Implement PDF text extraction over the 73 corpus manual/instruction PDFs including the over-10MB tail, emitting schema-conformant output with per-file provenance (ADR D6)

## Scope

- `dev preprocessing tooling + src/aeat/_data/corpus manuals and aeat_official`

Implements the ADR D6 index-capability prerequisite for the largest
remaining invisible corpus gap: the corpus PDFs were not a walker-supported
extension, so zero of them were indexed. The Manuales Practicos are the
authoritative BOE/AEAT Spanish definition prose a "what does X mean" query
needs. Reuses the interim sidecar contract; the worked-example HTML stub
stays a worked example only.

## Description

- Ground the reader question via RAG + `rg`: confirm `pdfplumber` 0.11.9
  (pure-Python `pdfminer.six` backend, locked dependency) and an existing
  in-repo pdfplumber extraction precedent; confirm the import works.
- Locate the corpus PDFs: 72 tracked under `src/aeat/_data/corpus` (64
  Diseno-de-registro instruction PDFs plus 8 Manuales Practicos PDFs); the
  over-10MB tail is the renta manuals (32 MB, 26 MB, 11.6 MB).
- Author the production extractor module `_pdf.py`: one `PreprocessUnit`
  per non-empty page (titled by page number), `source_kind = CORPUS_PDF`,
  attribution resolved from the source `manifest.json` in both shipped
  shapes (per-artefact diseno manifest and flat manuales manifest).
- Factor the budget splitter, part-naming, part-anchor stamping, and the
  multi-part sidecar writer into a shared `_parts.py` so the PDF extractor
  splits identically to the workbook extractor and an over-cap manual would
  yield several sidecar parts, each under the 10 MB walker file cap.
- Author a real-behaviour test suite (7 tests) over one real small
  Diseno-de-registro PDF, asserting schema validity, readable per-page
  text, dual-shape attribution, walker pickup against the installed
  package, the splitter under the cap, and an anti-tautology
  tampered-sidecar rejection plus a non-PDF refusal.
- Run the extractor over all 72 tracked PDFs, writing committed
  `*.extracted.md` + `*.extracted.json` sidecars in place (LF newlines).
- Verify: ruff check + format clean, `ty check` clean, the full preprocess
  suite green, the subtree collect-only clean.

## Outcome

### Coverage

- **72 tracked corpus PDFs**, all extracted: 64 Diseno-de-registro
  instruction PDFs plus 8 Manuales Practicos PDFs. The research's "73" count
  included a count discrepancy; the authoritative tracked set
  (`git ls-files`) is 72, and every one is processed. No tracked PDF was
  skipped.
- The 7 manuals `source.pdf` are tracked despite the `**/source.pdf`
  `.gitignore` rule because the negated-keep (`!...renta/.../source.pdf`)
  lines re-include them; they are in the tracked set and extracted. No
  tracked-but-skipped PDFs.

### Reader library: locked, no coordinator decision needed

`pdfplumber` (`pdfplumber>=0.11.9,<1`) is already a locked dependency and
backs an existing in-repo extraction surface
(`adapters/inbound/pdf/_pdfplumber.py`). It is built on the pure-Python
`pdfminer.six` (also locked) - no native runtime - so it honours the
offline-hermetic build constraint. No heavy dependency was added; nothing
flagged.

### The over-10MB tail and the splitter

The over-10MB source PDFs do NOT produce over-cap text: the largest manual
(renta 2020, 32 MB, 1466 pages) extracts to ~3.09 MB of text, well under
the 10 MB walker cap. So no real corpus PDF needed splitting; every PDF
emitted a single sidecar pair. The byte-budget splitter (8 MB threshold,
factored into the shared `_parts.py`) remains implemented, anchor-stamps
multi-part units, and is tested with synthetic oversized units as the safety
net for any future larger document.

### The extractor and the shared parts module

`_pdf.py` exposes `extract_pdf(source, *, repo_root)` and the pure
`build_outputs(...)`. Text is read page-by-page with `pdfplumber`; one
`PreprocessUnit` per non-empty page, titled `Pag. N`. Attribution is
resolved from the source `manifest.json` in both shipped shapes - the
Diseno-de-registro manifest (per-artefact `url` matched by `stored_path`)
and the manuales manifest (flat `source_pdf_url`, matched against
`relative_pdf_path`) - with a standing AEAT fallback so corpus text never
ships unattributed (the BOE/AEAT reuse-with-attribution obligation). The
budget splitter, part naming, anchor stamping, and the multi-part writer
live in the new shared `_parts.py` consumed by this extractor.

### Sample manual reads correctly

The Modelo 131 design instruction PDF extracts to readable Spanish - the
unit text carries "Modelo 131", "Agencia Tributaria", and the field-table
header - and its attribution pins the official AEAT download URL
(`.../ant_100_199/archivos/dr131.09.pdf`). A manuales PDF resolves its
`ManualRenta2025Parte1_es_es.pdf` URL through the flat-manifest path.

### Verification

- Test: `test_pdf_extractor.py` - 7 tests, all green. The full preprocess
  suite is 21 green (7 here + 8 workbook + 6 contract). `ruff check`, `ruff
  format --check`, `ty check`, and the subtree collect-only all clean.
- Sidecar paths verified not gitignored, so the committed sidecars need no
  `.gitignore` change. Source PDFs stay tracked as before; the derived text
  sidecars are the committed, reviewable build inputs.

## Notes

- The PDF reader is HANDLED, not flagged: `pdfplumber` was already locked,
  so no add/which-library coordinator decision was required.
- pdfplumber/pdfminer emit benign `CropBox missing` and font warnings on
  some PDFs; they are suppressed only at the bulk-run command level
  (`-W ignore`), not in library code.
- The S04 commit-integrity lesson is applied: this commit stages ONLY my own
  files with explicit `git add -- <path>`, and on any `index.lock`
  contention I WAIT and RETRY the same git command rather than removing the
  lock (a present lock means a peer is mid-commit).
- No PM wave/phase/step tokens in production code or comments (ADR ids only
  in this exec record). The single `cast` in `_pdf.py` is the documented
  untyped-JSON-manifest boundary escape, with an inline rationale.
- The committed sidecar tree retires when the upstream `vaultspec-rag`
  preprocess-hook lands (the established retirement trigger);
  `PreprocessOutput` precursor-compatibility is intact.

