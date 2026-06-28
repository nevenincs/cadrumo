---
tags:
  - '#exec'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
step_id: 'S02'
related:
  - "[[2026-06-10-docs-terminology-search-plan]]"
---




# Adjudicate and document the interim path while the upstream hook is pending: a committed extraction-sidecar tree mirroring the existing corpus/manuals source-extraction convention, consumed by the existing walker, with the explicit retirement trigger being the upstream hook landing (ADR D6)

## Scope

- `.vault/exec record + src/aeat/_data/corpus layout`

This Step implements the ADR D6 index-capability prerequisite (the dev RAG
graduates from optional tooling to a build-input dependency). It is the
DESIGN GATE for the four preprocessor Steps that follow (W01.P02 S03-S06);
those Steps implement format-specific extractors against the contract
defined here. No extractor is implemented here beyond one minimal worked
example proving the contract shape end to end.

## Description


- Ground the walker pickup against the installed `vaultspec_rag` 0.2.17:
  confirm `SUPPORTED_EXTENSIONS` is derived from `LANGUAGE_MAP` and that the
  per-file accept gate is `suffix.lower() in SUPPORTED_EXTENSIONS` plus the
  gitignore, 10 MB size cap, and null-byte binary filters.
- Confirm `.md`, `.html`, `.json` are supported and the named gaps (`.pdf`,
  `.xls`, `.xlsx`, `.txt`, `.xml`, `.xsd`, `.properties`) are not.
- Inspect the existing corpus convention: the `source.pdf` binaries are
  gitignored while their derived siblings are kept; the disenos
  `manifest.json` already carries rich provenance (source URL, sha256,
  retrieved_at, attribution string).
- Adjudicate the interim sidecar path: committed `*.extracted.md` text
  sidecars (indexed by the existing walker, zero upstream change) plus
  `*.extracted.json` provenance sidecars, sibling to each source file.
- Author the versioned `PreprocessOutput` strict pydantic v2 schema, the
  closed `SourceDocumentKind` / `ExtractionStatus` StrEnums, and the
  `PreprocessUnit` pre-chunked-unit model in `dev/docs/preprocess/`.
- Author the thin sidecar writer/loader (`write_sidecar`, `load_sidecar`,
  `sidecar_paths_for`, `sha256_of`) - serialisation and round-trip only,
  not extraction.
- Author one minimal worked-example extractor stub over a real 347-byte BOE
  normatives HTML article and a real-behaviour test suite (6 tests).
- Verify: ruff check + format clean, `ty check` clean, the test suite green,
  the new subtree collect-only clean.

## Outcome

### Adjudication: the interim sidecar path

**Decision.** While the upstream `vaultspec-rag` preprocess-hook is pending
(requested in W01.P01.S01), each binary or unsupported-extension grounding
file gains two committed sibling sidecars:

- `<full-filename>.extracted.md` - the rendered plain text the existing
  walker indexes. `.md` is already in the walker's `SUPPORTED_EXTENSIONS`,
  so no upstream change is needed for pickup.
- `<full-filename>.extracted.json` - the serialised `PreprocessOutput`
  provenance record (origin path, origin sha256, extractor id/version,
  source kind, status, attribution, pre-chunked units).

The sidecar name is taken from the source's full filename (suffix included)
so the same diseno shipped as both `.xls` and `.txt` never collides on one
sidecar.

**Where they live.** Beside each source file, mirroring the established
`corpus/manuals/**/source.pdf` + derived-sibling convention. The normatives
HTML article `.../normatives/html/orden-hap-2250-2015-art-4.html` would gain
`.../orden-hap-2250-2015-art-4.html.extracted.md` and `.extracted.json`; a
diseno `.../disenos_registro/modelo_123/files/DR123e24.xls` would gain
`DR123e24.xls.extracted.md` and `.extracted.json` next to it. No parallel
`_extracted/` tree - the sibling layout keeps each sidecar physically next
to the source whose hash it is bound to, so a reviewer reads them together.

**How the walker picks them up.** The walker's only structural gate is
`p.suffix.lower() in SUPPORTED_EXTENSIONS` (`indexer/_codebase_indexer.py`
`_process_scan_files`), plus the gitignore/size/binary filters. Because the
text sidecar ends in `.md`, it passes the extension gate unchanged. The
`.json` provenance sidecar is also walker-supported, but it is named so a
consumer treats it as inert metadata; the indexed surface is the `.md`. The
test reproduces the real walker accept predicate against a real rendered
sidecar (supported extension, under the size cap, not binary) using the
installed package, not a copy.

**Committed, not gitignored - and why.** The sidecars are committed and
reviewable, NOT gitignored-and-regenerated. The binding reason (research F3
/ ADR D6 constraints): CI and the docs build have no GPU and no RAG service,
so the sweep that consumes the hardened index (W03.P09) runs only on the dev
box; the index it sweeps must therefore be buildable from committed inputs.
A gitignored sidecar tree would force every CI run and every fresh clone to
re-extract (and the extraction of PDFs/workbooks is exactly the expensive,
tool-heavy step). Committed sidecars are build inputs with reviewable diffs,
exactly like the committed sweep outputs the ADR mandates downstream. The
proposed sidecar paths are NOT caught by any existing `.gitignore` pattern
(verified with `git check-ignore`: the disenos and normatives sidecar paths
both report not-ignored), so committing them needs zero `.gitignore` change.
The source binaries stay gitignored (the `source.pdf` rule is untouched);
only their derived text sidecars are committed - the same binary-ignored /
derived-text-kept split the existing convention already encodes.

**Retirement trigger and migration path.** The explicit retirement trigger
is the upstream `vaultspec-rag` preprocess-hook landing (the W01.P01.S01
request). When it lands, the preprocessors register against the upstream
file-pattern-to-preprocessor hook and emit the upstream versioned
preprocess-output schema directly; the walker consumes preprocessed output
through the hook rather than through committed `.md` siblings. Migration is
mechanical because `PreprocessOutput` is a field-compatible precursor of the
upstream schema (mapping below): the retirement is (1) point the extractors
at the upstream sink, (2) delete the committed `*.extracted.md` /
`*.extracted.json` tree in one commit, (3) delete this `dev/docs/preprocess`
sidecar package. Per the no-legacy rule the sidecar tree is forward-
functional scaffolding (it produces current-shape extracted text), not a
legacy bridge; its retirement is designed in, not carried forever.

### The contract: `PreprocessOutput`

Defined in `dev/docs/preprocess/_schema.py` as a strict (`strict=True,
extra="forbid", frozen=True`) pydantic v2 model. Fields:

- `schema_version: str` - defaults to `PREPROCESS_SCHEMA_VERSION` ("1.0");
  the loader refuses an unknown version rather than coercing.
- `source_kind: SourceDocumentKind` - closed StrEnum
  (`normatives_html | diseno_registro_workbook | corpus_pdf |
  unsupported_text`), one member per W01.P02 preprocessor family.
- `status: ExtractionStatus` - closed StrEnum (`ok | empty | partial`); the
  skip-and-report axis. A preprocessor that cannot extract at all raises;
  it never writes an `ok` sidecar.
- `source_relpath: str` - POSIX-relative origin path from the repo root (the
  source locator).
- `source_sha256: str` - 64-hex of the origin bytes (the staleness key); a
  gate cross-checks it against the live file to detect a stale sidecar
  without an allowlist (the fixture-provenance-declared-in-sidecar
  discipline).
- `preprocessor_id` + `preprocessor_version: str` - the producing
  extractor's identity (the other half of the upstream cache key).
- `attribution: str` - the BOE/AEAT licence obligation carried with the
  extracted text (research P5: corpus text reuse requires attribution).
- `units: tuple[PreprocessUnit, ...]` - the pre-chunked units, each
  `text` (non-empty) plus optional `title` / `section` / `anchor`.

`render_text()` deterministically renders the units (title as a `#` heading
when present) into the `.md` body, so the text sidecar round-trips and a
drift gate can compare a regenerated render against the committed one.

### Compatibility with the upstream generic schema

`PreprocessOutput` is a compatible subset/precursor of the W01.P01.S01
upstream contract, so migration is a re-serialisation, not a re-extraction:

| Upstream generic field | `PreprocessOutput` precursor |
| --- | --- |
| versioned-envelope version | `schema_version` |
| pre-chunked units (text + optional title/section/anchor) | `units` of `PreprocessUnit` |
| source locator | `source_relpath` |
| cache key: source content hash | `source_sha256` |
| cache key: preprocessor identity + version | `preprocessor_id` + `preprocessor_version` |
| record metadata | `source_kind` |
| hard-fail vs skip-and-report | `status` (`ok/empty/partial`); raise on total failure |
| (project extension) licence obligation | `attribution` |

The only project-specific field is `attribution` (a leaf the upstream
schema can carry in its open metadata map or drop); everything else is a
named subset of the upstream contract. No field here has a shape the
upstream schema cannot represent.

### Worked example + verification

- Worked-example file: `src/aeat/_data/corpus/normatives/html/
  orden-hap-2250-2015-art-4.html` (347 bytes; one `<h5 class="articulo">`
  title + one `<p class="parrafo">` body - the exact markup S03 splits on).
- Extractor stub: `dev/docs/preprocess/_example.py`
  (`extract_normatives_html`), explicitly NOT the S03 preprocessor - it
  proves the contract with one real file.
- Test: `dev/docs/preprocess/tests/test_sidecar_contract.py` (6 tests, all
  green): source-exists guard; extractor-yields-valid-record;
  sidecar-round-trips-through-schema (strict pydantic equality across the
  json boundary); text-sidecar-indexable-by-the-installed-walker (real
  installed `SUPPORTED_EXTENSIONS` + accept predicate, no mock);
  tampered-sidecar-rejected (anti-tautology: truncated sha256 and a
  forbidden extra field both raise); paths-disambiguate-by-full-filename.
- Gates: `ruff check` clean, `ruff format --check` clean, `ty check
  dev/docs/preprocess/` clean, the suite green, the new subtree
  collect-only clean.

### Handoff spec for S03-S06

Every preprocessor builds a `PreprocessOutput`, computes `source_sha256` via
`sha256_of`, and calls `write_sidecar(source, output)`. Each:

- S03 (normatives HTML): split on `<h5 class="articulo">`, strip TOC link
  farms, one `PreprocessUnit` per article (title = articulo heading),
  `source_kind = NORMATIVES_HTML`, attribution resolved from the sibling
  normatives manifest BOE permalink. Generalise the worked-example stub;
  do not ship the stub as the real preprocessor.
- S04 (Disenos de Registro workbooks): openpyxl over the 74 xlsx + 28 xls;
  one `PreprocessUnit` per sheet rendering the casilla-number-to-field
  table as text, `source_kind = DISENO_REGISTRO_WORKBOOK`, attribution from
  the disenos `manifest.json` source/url.
- S05 (corpus PDFs): pdf text extraction over the 73 PDFs including the
  over-10MB tail (note: the rendered `.md` sidecar must itself stay under
  the walker's 10MB cap or be split into multiple unit-bearing sidecars),
  one unit per page/section, `source_kind = CORPUS_PDF`, attribution from
  the manuals `manifest.json`.
- S06 (unsupported-text tail): txt/xml/xsd/properties (36 files); either
  request the upstream extension-map addition or emit a passthrough
  `.extracted.md` sidecar, `source_kind = UNSUPPORTED_TEXT`. Prefer the
  upstream extension map for plain text where it lands first.

## Notes

- Collect-only at the repo root currently errors on
  `aeat.application.ledger._evidence_input.EvidenceInputError` missing an
  error-code registry entry. This is uncommitted peer-agent WIP in
  `src/aeat/application/ledger/` (a large in-flight ledger refactor; none of
  those files are mine) and is exactly the "class added by a peer agent
  mid-flight" condition the error message itself names. Per the
  worktree-safety rule I did not touch peer WIP. My own subtree
  (`dev/docs/preprocess/`) collects cleanly (6 tests) and the contract test
  suite is green.
- Decision flagged for coordinator awareness (recommended, not blocking):
  committed sidecars over gitignored-and-regenerated. Recommended committed
  for the no-GPU-CI reason above; the proposed paths need zero `.gitignore`
  change. If the coordinator later prefers a gitignored tree, only the
  commit-status decision changes - the schema, walker pickup, and retirement
  trigger are unaffected.
- No format-specific extractor was implemented (S03-S06 own those). The
  `_example.py` stub is clearly scoped and named as a worked example, not a
  production preprocessor.
