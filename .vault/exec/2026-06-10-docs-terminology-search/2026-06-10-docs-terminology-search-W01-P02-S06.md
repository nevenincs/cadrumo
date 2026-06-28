---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S06'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Close the unsupported-text-extension tail (txt, xml, xsd, properties - 36 files incl. M349 instructions and the M100 diccionario dictionaries) via the upstream extension map or interim sidecar emission (ADR D6)

## Scope

- `upstream request + dev preprocessing tooling`

Implements the ADR D6 index-capability prerequisite for the small
text-extension tail. These files are already text but their extensions are
invisible to the walker. Closes W01.P02 (the four corpus-preprocessor steps
S03-S06). The upstream extension-map addition is still pending, so the
interim sidecar path is taken, consistent with S03/S04/S05.

## Description

- Reaffirm the walker's supported-extension set: confirm `.txt`, `.xml`,
  `.xsd`, and `.properties` are ALL absent (genuinely invisible); `.md` is
  supported (the sidecar pickup surface).
- Inventory the target set: 36 tracked files under `src/aeat/_data` - 8
  `.txt`, 1 `.xml`, 15 `.xsd`, 12 `.properties` (incl. the M349/M232
  instruction txt and the M100 diccionario `.properties`).
- Survey encodings: 8 UTF-8, 27 cp1252, 1 latin-1 - the AEAT `.properties`
  diccionarios and several `.xsd` are not UTF-8, so a decode fallback is
  required or the accented text corrupts.
- Author the passthrough extractor module `_text.py`: read with a UTF-8 ->
  cp1252 -> latin-1 fallback chain, lightly normalise whitespace, keep the
  structured text verbatim, emit one `PreprocessUnit` per file (titled by
  the filename), `source_kind = UNSUPPORTED_TEXT`.
- Resolve attribution from the sibling Diseno `manifest.json` artefact URL
  where catalogued (the M100 diccionarios/schemas), else the standing
  AEAT/BOE fallback.
- Author a real-behaviour test suite (6 tests): cp1252 `.properties` decodes
  with accents intact, `.txt` extracts readable text, the
  invisible-extension premise is pinned, walker pickup against the installed
  package, dual attribution, and an anti-tautology tampered-sidecar
  rejection.
- Run the extractor over all 36 files, writing committed `*.extracted.md` +
  `*.extracted.json` sidecars in place (LF newlines).
- Verify: ruff check + format clean, `ty check` clean, the full preprocess
  suite green, the subtree collect-only clean.

## Outcome

### Files covered by extension

- **36 tracked files**, all extracted: **8 `.txt`** (M349/M232 instructions,
  groi response samples, the M037 supresion BOE txt, an internal audit txt) +
  **1 `.xml`** (the ECB eurofxref bundle) + **15 `.xsd`** (M100/M390 fichero
  schemas) + **12 `.properties`** (the M100 diccionario dictionaries -
  casilla-path to description mappings, the highest-value members). Zero
  failures, zero splits. 36 `.md` + 36 `.json` sidecars, all LF-clean.

### Which extensions were genuinely invisible vs already-indexed (for S08)

ALL FOUR extensions (`.txt`, `.xml`, `.xsd`, `.properties`) are GENUINELY
INVISIBLE - none is in the walker's `SUPPORTED_EXTENSIONS`. So unlike the
S03 normatives HTML (which the walker already indexes raw, creating the
raw-vs-sidecar duplicate), these 36 sidecars are PURELY ADDITIVE coverage of
files the index had zero visibility into. There is NO raw-vs-sidecar
dedup question for S06's extensions - the sidecar is the only index entry.
This is pinned by a regression test
(`test_all_four_extensions_are_walker_invisible`) that fails if a peer ever
adds one of these to the walker, at which point the dedup question would have
to be revisited. Feed into S08: S06 adds no dedup burden; only S03's HTML
carries the raw-vs-clean exclusion decision.

### Encoding handling

The AEAT `.properties` diccionarios and several `.xsd` ship as cp1252/latin-1
(27 of 36 files are not UTF-8). The extractor tries UTF-8, then cp1252, then
latin-1 (which decodes any byte sequence, so a readable file is never
dropped). Verified: the M100 diccionario decodes `declaración individual`
with the accent intact and no replacement characters.

### Largest sidecar

**0.928 MB** (an M100 toma-de-datos diccionario `.properties`) - under the
10 MB walker cap, no splits (the shared `_parts.py` splitter remains as the
safety net).

### Attribution

The M100 diccionario `.properties`/`.xsd` are catalogued in the modelo Diseno
`manifest.json`, so their attribution pins the official AEAT download URL.
The manifest-less files (instruction txt, groi samples, eurofxref xml, the
internal audit txt) fall back to the standing AEAT/BOE attribution - never
unattributed.

### Verification

- Test: `test_text_extractor.py` - 6 tests, all green. The full preprocess
  suite is 34 green (6 here + 7 HTML + 7 PDF + 8 workbook + 6 contract).
  `ruff check`, `ruff format --check`, `ty check`, and the subtree
  collect-only all clean.
- Sidecar paths verified not gitignored.

### W01.P02 status

S06 closes W01.P02: all four corpus-preprocessor steps (S03 normatives HTML,
S04 Diseno workbooks, S05 corpus PDFs, S06 text tail) are landed. Only
W01.P03 (S07 reindex-before-sweep gate + S08 retrieval verification) remains
to close W01. S08 inherits one raw-vs-sidecar dedup flag (S03's HTML); S06
adds none.

## Notes

- No PM wave/phase/step tokens in production code or comments, and the one
  that slipped into a test docstring was removed before commit (ADR ids only
  in this exec record). The single `cast` in `_text.py` is the documented
  untyped-JSON-manifest boundary escape, with an inline rationale.
- The shared `_parts.py` budget splitter is reused, so all four corpus
  extractors split identically.
- The committed sidecar tree retires when the upstream `vaultspec-rag`
  preprocess-hook (or its extension-map addition) lands - for these four
  extensions, adding them to the upstream extension map would make the raw
  files directly indexable and the sidecars redundant, a clean retirement.
  `PreprocessOutput` precursor-compatibility is intact.
- Commit discipline: all verification ran first; staging and the commit are a
  single chained `git add ... ; git commit ...` as the very last action,
  explicit paths only, never touching `index.lock`.
