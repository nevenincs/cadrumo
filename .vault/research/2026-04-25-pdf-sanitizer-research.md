---
tags:
  - '#research'
  - '#pdf-sanitizer'
date: '2026-04-25'
modified: '2026-04-25'
related:
  - "[[2026-04-25-aeat-verify-research]]"
  - "[[2026-04-25-aeat-verify-adr]]"
  - "[[2026-04-25-aeat-verify-plan]]"
  - "[[2026-04-24-aeat-verify-reference]]"
---



# `pdf-sanitizer` research: `pdf-sanitizer-prior-art-and-api`

Survey of prior art, library landscape, threat model, and API shape
for a first-class `aeat`-housed PDF sanitiser module. Feeds the
next-step ADR. The parent `aeat-verify` ADR locked a `pikepdf`
token-replacement v1 embedded in `scripts/sanitize_justificante.py`;
the PM has overruled that — the sanitiser must become a testable
subpackage. This research substantiates that promotion and surfaces
the surfaces v1 missed.

## tldr

- **Library:** `pikepdf` (MPL-2.0, QPDF-bundled, cp313 wheels on Win/macOS/Linux). Fallback: `pypdf` (BSD-3, pure-Python, weaker content-stream API). Hard-rule-out: `PyMuPDF` (AGPL — license-incompatible with the project's Apache-2.0 unless commercially relicensed). Hard-rule-out: `pdfrw` (MIT but unmaintained since 2017, no compressed-stream support).
- **Strategy:** token replacement via `pikepdf.parse_content_stream` / `unparse_content_stream` over `Tj` operands. Blackout-rectangle (PyMuPDF `apply_redactions`) is wrong for our use case — it strips text from extraction, breaking the deep extractor's regression contract. Synthetic re-render is overkill and loses layout cues.
- **Subpackage:** `aeat.adapters.inbound.sanitizer`. Single-word, lowercase, domain-noun. Matches existing `aeat.domain.justificante`, `aeat.adapters.inbound.declaracion`, `aeat.application.verification` cadence. Public CLI noun: `aeat sanitize`. The noun is unused (verified against `src/aeat/entrypoints/cli/`).
- **Threat model:** the attacker is a future contributor cloning the repo, a code-review viewer reading a fixture diff, or a downstream consumer reusing a fixture in a public demo. Real PII surfaces at 17 distinct PDF locations beyond the body Tj operands. The parent ADR's v1 plan touches 3 of them.
- **Determinism:** `pikepdf.Pdf.save(deterministic_id=True, compress_streams=True, object_stream_mode=ObjectStreamMode.preserve, linearize=False, recompress_flate=False)` produces byte-stable output for byte-stable input. The parent ADR claims "deterministic pure function" without naming the flags; this research names them.

## context

Phase 4 of the per-modelo verify loop captures a real AEAT
justificante PDF, strips PII, and commits the result as a test
fixture under `tests/fixtures/justificantes/<modelo>/<period>.pdf`.
The fixture must remain parseable by
`aeat.domain.justificante.parse_justificante` and (for modelos with a body)
by the per-modelo casilla extractor under
`aeat.adapters.inbound.declaracion._parsers/<modelo>/`. The sanitiser is therefore a
*rewrite-in-place* operation, not a redaction-blackout.

The captured corpus (2026-04-24, recovered 2026-04-25) is three real
Modelo 100 IRPF justificantes for ejercicios 2021-2023. They are the
only live ground truth the project currently has. Their
characterisation drives every concrete claim in this document.

### empirical capture characterisation

Inspected via `pdfminer` and `pdfplumber` directly against the three
captured PDFs (no rewrite, read-only):

- **2021** (`irpf-2021/justificante.pdf`, 6 pages, 316 KB)
  - Producer: `iText 2.1.4 (by lowagie.com)` — legacy iText 2.x.
  - DocInfo keys: `ModDate`, `CreationDate`, `Producer`. **No** `Title`, `Author`, `Subject`, `Keywords`.
  - Catalog: `Type`, `Pages`, `Version`. No `Metadata` / `OutputIntents` / `Lang` / `MarkInfo` / `StructTreeRoot`. Plain PDF 1.x.
  - Fonts: one Type1 `NimbusSanL-Regu` (no subset prefix).
  - Content streams encode strings as **literal strings** only: `(Y1234567X)Tj`, `(PERSONA PRUEBA UNO)Tj`. Zero hex strings. Zero `TJ` arrays. The taxpayer's NIF and full name appear as plaintext literals at fixed `Tm` matrices.
- **2022** (`irpf-2022/justificante.pdf`, 5 pages)
  - Producer: `AEAT OVCT-IPDF/OVCT-XPDF` (modern AEAT renderer).
  - DocInfo: `Title`, `Subject` (both contain the CSV — `Justificante AEAT. CSV=MZRSYDRL5JMPJPRT`), `Creator`, `Author`, `Keywords`, `Producer`.
  - Catalog: `Type`, `Version`, `Pages`, **`Metadata`** (XMP, 1394 bytes), **`OutputIntents`**, **`Lang`** (`ES`), **`ViewerPreferences`**, **`StructTreeRoot`**, **`MarkInfo`** (`Marked: True`).
  - XMP claims **PDF/A-1B** conformance (`pdfaid:part=1`, `pdfaid:conformance=B`).
  - Fonts: TrueType `NimbusSanL-Regu` and `NimbusSanL-Bold` (no subset prefix).
  - Content streams mix **hex strings** (`<494E464F524D...>` = `INFORMACI...` cp1252-encoded) and literal strings (` 01-02-2024 a las 19:15:34`). All operators are `Tj` — zero `TJ`. Marked-content via `/P /Prop<N> BDC ... EMC` wrappers.
  - Structure tree present; no `/ActualText` or `/Alt` entries observed in initial walk.
- **2023** (`irpf-2023/justificante.pdf`, 5 pages) — structurally identical to 2022, different CSV / NIF / dates.

Critical implications:

- The 2021 path is one regex over UTF-8-decoded literal strings.
- The 2022/2023 path needs **operand-aware** rewriting: hex tokens (cp1252 / PDFDocEncoding bytes) and literal tokens both. The sanitiser must walk `pikepdf.parse_content_stream` results and pattern-match on the decoded operand, not on the raw byte stream.
- The XMP, DocInfo `Title`/`Subject`, and (for the legacy producer) every literal-string Tj are PII surfaces the sanitiser must touch. The ADR's v1 plan covers DocInfo `Title` and the body Tj literals — the XMP, the structure tree, and the hex-string body operands need explicit handling.
- No font subset prefix — the synthetic glyphs (digits, A-Z, basic punctuation, comma, dot, parens, hyphen, colon) are guaranteed present in `NimbusSanL-Regu`/`Bold`. The "synthetic NIF's glyphs missing" failure mode the parent ADR worries about **does not apply to Modelo 100**. It may apply to other modelos once captured.

### state of the dependency tree

Verified by reading `pyproject.toml` at the worktree root:

- `pdfplumber>=0.11.9` is pinned (PDF text extraction for the existing parser).
- `pikepdf` is **not** pinned. Despite the parent plan PR2 saying "existing pikepdf likely already pinned via aeat.domain.justificante", a grep across `src/` returns zero hits in production code. Adding `pikepdf` is therefore a real new dependency, not a piggyback.
- No `pypdf` / `pdfrw` / `pymupdf` / `fitz` anywhere in the tree.
- License posture: project is Apache-2.0. Any sanitiser dep must be permissively licensed (MPL-2.0 / MIT / BSD / Apache / PSF). AGPL is a non-starter without explicit user sign-off.

## threat model

Three threat actors, ordered by likelihood:

1. **Future code reviewer reading a fixture-add PR diff.** Sees the sanitised PDF rendered by `git diff` (binary, opaque) and by GitHub's inline PDF viewer (rendered text). Should see synthetic NIF, name, address, etc. Must not see Kent's real values.
2. **Attacker who clones the public repo.** Runs `pdftotext`, `pdfgrep`, `pdfdetach`, `mutool extract`, `exiftool`, `pdfid.py` over every fixture. Should find synthetic identifiers everywhere; finding anything that decodes to Kent's NIF / name / address / IBAN / NRC is a PII leak. Mitigation surface: every byte of the PDF, including compressed object streams and incremental update history.
3. **Future contributor reusing a fixture in a public demo (slide deck, blog post, conference talk).** Renders the fixture in Acrobat / a browser and screenshots it. The visual rendering is the leak surface. Synthetic values must look plausibly Spanish-format without being a real person's identifier.

The sanitiser is *not* defending against a forensic adversary who
controls the build pipeline. It is defending against passive recovery
from a public artifact.

### PII surfaces in a real AEAT justificante

| # | Surface | Where | Parent v1 covers? |
|---|---------|-------|-------------------|
| 1 | Body Tj **literal** strings | content streams, every page | yes (token-replace) |
| 2 | Body Tj **hex** strings (cp1252) | content streams, 2022+ | **no** — v1 walk does not specify hex-aware decode |
| 3 | DocInfo `/Title` | trailer dict | yes |
| 4 | DocInfo `/Subject` | trailer dict | **no** — also contains CSV in 2022+ |
| 5 | DocInfo `/Author` | trailer dict | partial |
| 6 | DocInfo `/Keywords` | trailer dict | **no** |
| 7 | DocInfo `/Creator`, `/Producer` | trailer dict | **no** — fingerprintable; scrub for cleanliness |
| 8 | DocInfo `/CreationDate`, `/ModDate` | trailer dict | **no** — timestamp leaks (2021 PDF leaks `D:20220411011528+02'00'`, the actual presentation moment) |
| 9 | XMP `dc:title`, `dc:description`, `dc:creator`, `pdf:Keywords` | `Root.Metadata` stream | **no** |
| 10 | Optional Content Groups (`/OCProperties`) | catalog | not observed; CVE-class redaction-failure vector |
| 11 | Embedded files / attachments (`Root.Names.EmbeddedFiles`) | name tree | not observed; sanitiser must `pdf.attachments.clear()` defensively |
| 12 | Embedded JavaScript (`Root.Names.JavaScript`, `/OpenAction`, `/AA`) | name tree + actions | not observed; sanitiser must remove defensively |
| 13 | AcroForm field values (`Root.AcroForm.Fields[*].V`) | form dict | not observed |
| 14 | Annotations (`Page.Annots[*]`) | per-page | not observed; scrub or drop entirely |
| 15 | StructTree `/ActualText`, `/Alt`, `/E` | `Root.StructTreeRoot` | **no** — Tagged-PDF accessibility text is a known leak vector |
| 16 | Page thumbnails (`Page.Thumb`) | per-page | not observed; PII-bearing image bypass — drop |
| 17 | Incremental update history | trailer chain | **no** — `pikepdf.save` consolidates by default but must be verified |
| 18 | Page labels (`Root.PageLabels`) | catalog | not observed |
| 19 | Outlines / bookmarks (`Root.Outlines`) | catalog | not observed |
| 20 | Digital signatures (`Root.AcroForm.SigFlags`, signature dicts) | AcroForm | **verified absent** by `SigFlags` probe |

The parent ADR v1 covers **3 of 20** surfaces. The new sanitiser must
cover the remainder. Rows 11/12/14/15 are defensive scrubs even where
not observed — they are the CVE-class historical failure modes
(Manafort, NSA Russia memo, AstraZeneca contract).

### published-failure cases

- **Manafort 2019** — black rectangles drawn over text without flattening; copy-paste recovered the underlying text. Lesson: visual redaction layered on top of preserved content streams is not redaction. Our sanitiser **rewrites** the content stream and never uses overlay rectangles.
- **NSA Russia memo 2017 / 2014** — same root cause, different agency.
- **AstraZeneca contract 2021** — bookmarks retained the redacted term. Lesson: enumerate every named-tree surface, not just body text.
- **CVE-2026-3774 class** — JS / form actions can re-write content after redaction is applied, defeating it. Lesson: drop all JS, drop all OpenAction/AA, drop AcroForm, *before* doing the content rewrite, not after.

These failure cases anchor the sanitiser's order of operations.

## library landscape

### pikepdf — recommended primary

- **License:** MPL-2.0. Compatible with the project's Apache-2.0 redistribution.
- **Backend:** QPDF (C++) via pybind11. QPDF binaries bundled in the wheel; no system QPDF needed.
- **Wheels:** cp313 wheels for `win_amd64`, `macosx_15_0_x86_64`, `macosx_14_0_arm64`, `manylinux_2_27_x86_64`, `manylinux_2_26_aarch64`. Covers every developer + CI platform in use today.
- **Content-stream API:** `pikepdf.parse_content_stream(page)` returns a list of `(operands, operator)` tuples; `pikepdf.unparse_content_stream(instructions)` round-trips back to bytes. Operators compare against `pikepdf.Operator("Tj")` etc. Operands for `Tj` are `pikepdf.String` instances exposing both raw bytes and decoded text. The library authors *officially recommend against* using `parse_content_stream` for text scraping — but for surgical operand replacement at known offsets the API is stable.
- **Metadata API:** `pdf.docinfo` for legacy DocInfo; `pdf.open_metadata()` context manager for XMP. To wipe: `del pdf.Root.Metadata` and `del pdf.docinfo` (canonical pattern; pikepdf issue #89).
- **Attachments / JS:** `pdf.attachments.clear()`; JS removal idiom walks `Root.Names.JavaScript`, `Root.OpenAction`, `Root.AA`, every `Page.AA`, every `Annot.A`, deleting any sub-dict whose `/S` is `/JavaScript`. Reference: `chmdznr/py-pdf-sanitizer`.
- **Annotation drop:** iterate pages, `del page.Annots`.
- **Determinism:** `Pdf.save(filename, deterministic_id=True, compress_streams=True, object_stream_mode=ObjectStreamMode.preserve, linearize=False, recompress_flate=False)`. `deterministic_id=True` replaces the timestamp-based `/ID` array with a content-only hash. `static_id=True` is debug-only. `linearize=False` avoids fast-web-view reordering.
- **PDF/A:** `Pdf.save(..., preserve_pdfa=True)` exists. Important caveat: rewriting Tj operands almost certainly invalidates the document's PDF/A-1B claim because the conformance check covers XMP+content alignment. The sanitiser should drop the `pdfaid:*` claim from XMP rather than leave a false claim.

### pypdf — recommended fallback

- **License:** BSD-3-Clause. **Backend:** pure Python.
- **Content-stream API:** lower-level than pikepdf. Workable for metadata + attachment + annotation strip; less ergonomic for Tj operand rewriting.
- **Why fallback only:** pikepdf's binary-wheel dep on QPDF is acceptable for the determinism / content-stream ergonomics. pypdf is the escape hatch with the caveat that the content-stream walk has to be hand-rolled.

### PyMuPDF / fitz — ruled out

- **License:** AGPL-3.0 (or commercial via Artifex). Combining an AGPL library at runtime with the project's Apache-2.0 distribution triggers AGPL section 13 obligations on every consumer. Hard rule-out without explicit user sign-off and a paid commercial relicense.
- **Capability:** redaction model (`Page.add_redact_annot`, `Page.apply_redactions`) is wrong shape anyway — `apply_redactions` deletes text from the extraction layer, breaking the deep-extractor regression contract.

### pdfrw — ruled out

- **License:** MIT. **Status:** last release **2017-09-18 (v0.4)**.
- **Capability gaps:** "doesn't support all content-stream compression filters" — caller must run `qpdf --uncompress` before pdfrw and recompress after. Used by `JoshData/pdf-redactor` (CC0) which inherits the same limitations.
- **Why ruled out:** maintenance gap + the qpdf shellout caveat (if we have qpdf, we have pikepdf).

### library scoreboard

| Library | Licence | Cp313 wheels | Content-stream rewrite | Metadata scrub | Attach/JS/Annots removal | Maintained | Verdict |
|---------|---------|--------------|------------------------|----------------|--------------------------|------------|---------|
| `pikepdf` | MPL-2.0 | yes (Win/macOS/Linux) | strong | strong | strong | yes (10.x, 2026) | **primary** |
| `pypdf` | BSD-3 | yes (pure-Py) | weak | adequate | adequate | yes | **fallback** |
| `PyMuPDF` | AGPL / commercial | yes | strong (redaction-shaped) | strong | strong | yes | **ruled out (licence)** |
| `pdfrw` | MIT | yes (pure-Py) | weak; needs qpdf shellout | adequate | weak | **no** (2017) | **ruled out (maint)** |

## strategy decision tree

- **Token replace (rewrite Tj operands).** Preserves layout, fonts, page count, PDF structure — every glyph stays at the same `Tm` position. Deep extractor sees the same shape AEAT produces. **This is our case.**
- **Blackout-rectangle.** Deletes text from the extraction layer; replaces with opaque rectangle (or fixed replacement text). **Wrong for us:** breaks the extractor regression contract.
- **Synthetic re-render.** Generate a brand-new PDF with same metadata + casilla map. **Wrong for us:** loses every layout cue; positional assertions in the extractor become brittle on the synthetic fixture.

Token replace it is. The decision is forced by the extractor's
contract.

### token-replace order of operations

1. **Open** the PDF with `pikepdf.open(source)`. (Don't `allow_overwriting_input` — sanitisation is never in-place.)
2. **Strip dynamic surfaces** before any content rewrite (CVE-2026-3774-class):
   - `pdf.attachments.clear()`
   - delete `Root.Names.JavaScript`, `Root.OpenAction`, `Root.AA` if present
   - walk every page, delete `page.AA` and any `Annot.A` whose `/S` is `/JavaScript`
   - drop every page's `Annots` array entirely
   - if `Root.AcroForm` exists: clear field values (`Fields[*].V`, `Fields[*].DV`) — preserve form structure, otherwise `del Root.AcroForm`
   - if `Root.OCProperties` exists: `del Root.OCProperties`
3. **Drop page thumbnails:** for each page, `del page.Thumb` if present.
4. **Drop bookmarks / outlines:** `del Root.Outlines` if present. Same for `Root.PageLabels`.
5. **Drop StructTreeRoot leak surfaces:** walk `Root.StructTreeRoot`, scrub any `/ActualText`, `/Alt`, `/E` entries against the token map. Drop the entire StructTree as a defensive measure.
6. **Rewrite content streams.** For each page, `pikepdf.parse_content_stream(page)`, walk instructions, and for any `Tj` / `TJ` / `'` / `"` text-show operator, rewrite the operand against the token map. Encode-aware: a `pikepdf.String` operand exposes raw bytes; the sanitiser decodes per the font's encoding (PDFDocEncoding default; cp1252 for hex-encoded `<...>` in observed AEAT corpus), runs the token map, re-encodes preserving the original encoding choice (literal-vs-hex). Reserialise with `pikepdf.unparse_content_stream`. Replace the page's content stream with `Pdf.make_stream`.
7. **Scrub static metadata:**
   - `del pdf.docinfo` (drops Title, Subject, Author, Keywords, Creator, Producer, CreationDate, ModDate)
   - `del pdf.Root.Metadata` (drops the XMP packet wholesale; per-key delete leaves orphan tags per pikepdf #89)
   - if XMP retention is needed for some downstream test: open it, scrub PII-bearing keys, drop the `pdfaid:*` conformance claim
8. **Save** with deterministic flags: `pdf.save(target, deterministic_id=True, compress_streams=True, object_stream_mode=ObjectStreamMode.preserve, linearize=False, recompress_flate=False)`.

The order matters: 2 before 6 because dynamic actions can rewrite
content streams; 6 before 7 because content-stream rewriting can
mutate XMP via `pikepdf.open_metadata()`'s set-pikepdf-as-editor
default (we must opt out of that).

## determinism + reproducibility

`pikepdf` produces non-deterministic output by default. Sources of
non-determinism:

- The `/ID` array in the trailer is timestamp+content seeded. `deterministic_id=True` replaces the timestamp seed with a content-only SHA-256 derivation. **Single most important flag.**
- `linearize=True` triggers fast-web-view reordering; object numbering changes. Pass `linearize=False`.
- `object_stream_mode=ObjectStreamMode.generate` rebuilds object streams; even with deterministic_id, the rebuild can shuffle object insertion order. Pass `ObjectStreamMode.preserve`.
- `recompress_flate=True` re-runs zlib with system default level; preamble bytes can drift across zlib versions. Pass `recompress_flate=False`.
- `fix_metadata_version=True` mutates XMP to match PDF version — moot once XMP is deleted.

Recommended save:

```
pdf.save(
    target,
    deterministic_id=True,
    compress_streams=True,
    object_stream_mode=ObjectStreamMode.preserve,
    linearize=False,
    recompress_flate=False,
    static_id=False,
)
```

The sanitiser's public function must be a pure Python function:
`sanitize_pdf(source: bytes, mapping: TokenMap) -> SanitizationResult`.
No filesystem side effects, no env var reads, no `time.now()` calls.
Tests assert byte-equality across two runs.

## api surface proposal

Subpackage: `aeat.adapters.inbound.sanitizer`. Single-word, lowercase, domain-noun.
Matches `aeat.domain.justificante`, `aeat.adapters.inbound.declaracion`, `aeat.application.verification`,
`aeat.application.filing`. Other candidates considered: `aeat.redact` (wrong
semantics), `aeat.privacy` (too broad), `aeat.scrub` (verb-y),
`aeat.pdf` (too broad).

CLI noun `aeat sanitize` does not collide with any existing CLI group
(verified: 30 existing groups, none of `sanitize` / `sanitizer` /
`redact` / `scrub` / `privacy`).

### proposed public api

All records strict-frozen pydantic v2 with `extra="forbid"`.

Function:

- `sanitize_pdf(source: bytes | Path, mapping: TokenMap, *, drop_attachments: bool = True, drop_javascript: bool = True, drop_annotations: bool = True, drop_outlines: bool = True, drop_optional_content_groups: bool = True, drop_struct_tree: bool = True, drop_acroform: bool = False, scrub_docinfo: bool = True, scrub_xmp: bool = True, scrub_xmp_strategy: Literal["delete", "rewrite"] = "delete") -> SanitizationResult`

Input record `class TokenMap`:

- `nif: tuple[NifReplacement, ...]`
- `name: tuple[NameReplacement, ...]`
- `address: tuple[AddressReplacement, ...]`
- `expediente: tuple[ExpedienteReplacement, ...]`
- `csv: tuple[CsvReplacement, ...]`
- `nrc: tuple[NrcReplacement, ...]`
- `iban: tuple[IbanReplacement, ...]`
- `importe: tuple[ImporteReplacement, ...]`
- `arbitrary: tuple[ArbitraryReplacement, ...]`

`class _ReplacementBase`:

- `real: SecretStr` — never logged in cleartext, only matched against
- `synthetic: str` — visible synthetic token; safe to log
- `surface_label: str` — human-readable surface name for the audit record
- per-subclass validators enforce shape (NIF letter checksum, IBAN ISO 13616, etc.) on the synthetic value so it round-trips through existing validators

Output record `class SanitizationResult`:

- `output_bytes: bytes`
- `source_sha256: str`, `output_sha256: str`
- `replacements_applied: tuple[Replacement, ...]`
- `surfaces_scrubbed: tuple[ScrubbedSurface, ...]`
- `warnings: tuple[SanitizationWarning, ...]`
- `determinism_flags: DeterminismFlags`
- `sanitizer_version: str`

`class Replacement`:

- `surface: Literal["docinfo", "xmp", "content_stream", "annotation", "structtree", ...]`
- `surface_index: tuple[int, ...]` — e.g. `(page_index, instruction_index)`
- `real_sha256: str` — never the cleartext
- `synthetic: str` — IS logged (that's the point)
- `encoding: Literal["literal", "hex", "actualtext", ...]`

`class ScrubbedSurface`: `surface`, `count: int`.
`class DeterminismFlags`: `deterministic_id`, `static_id`, `object_stream_mode`, `linearize`, `recompress_flate`, `compress_streams`.
`class SanitizationWarning`: `code: Literal["unknown_surface_present", "encoding_inferred", "structtree_dropped_lossy", "pdfa_claim_invalidated", ...]`, `detail: str`.

Notes:

- `mapping` is the **declarative input**; the sanitiser does no detection. Detection (Presidio) is overkill — pulls spaCy, large NER, tesseract.
- `output_bytes` is bytes, not a Path. Pure function. CLI shell writes to disk; library function does not.
- `replacements_applied` records `real_sha256`, not the cleartext.
- `mode: Literal["read"]` is *not* applicable here; this is a transformation, not a boundary record. Strict-frozen + `extra="forbid"` discipline still applies.

### token-map sourcing

Two viable shapes:

- **Per-fixture mapping committed alongside the captured PDF.** A YAML at `scratch/sede-discovery/<utc-ts>/<modelo>/<exp>/sanitizer-mapping.yaml`, scaffolded by `aeat sanitize prepare-map <pdf>`.
- **Default project-level mapping** at `aeat.adapters.inbound.sanitizer.fixtures.DEFAULT_MAPPING` — couples the sanitiser to one user's identity.

Recommendation: per-capture mapping. (a) Different captures have different real values; (b) keeps the sanitiser pure; (c) the mapping never gets committed, structurally preventing accidental NIF commits.

## cli surface

`aeat sanitize` group, verbs:

- `aeat sanitize pdf <input> --mapping <yaml-or-json> --output <out> [--report <path>] [--in-place]`
- `aeat sanitize prepare-map <input> --output <yaml>` — scaffolds TokenMap from a `parse_justificante` pass.
- `aeat sanitize verify <output> --against <mapping>` — assert sanitised PDF contains zero hits for any `real:` value (adversarial test, runnable in CI without scratch).
- `aeat sanitize check <output>` — sanity-check structural invariants.

Defaults: `--in-place` defaults **false**. `--report` defaults to writing JSON `SanitizationResult.model_dump_json()` alongside the output PDF.

## test strategy

- **Round-trip parse tests (unit, fixture-bound).** For every sanitised fixture, `parse_justificante(fixture_path)` must produce a `Justificante` whose synthetic NIF / CSV match the deterministic synthetic values from the mapping.
- **Adversarial absence tests (unit, fixture-bound).** For every fixture, every `real:` value must satisfy `real_value not in extracted_text(fixture)` *and* `real_value.encode() not in raw_pdf_bytes(fixture)`. The byte-level check is load-bearing — extracted text misses hex-encoded Tj operands, attachments, structure-tree text. **This is the test the Manafort failure case would have flagged. Don't compromise on it.**
- **Determinism tests (unit, scratch-bound, skip-if-missing).** Run sanitiser twice against a `scratch/` capture; assert byte-equal output. Runs only when scratch captures present (CI-safe).
- **Structural integrity tests (unit, fixture-bound):** `pikepdf.open(fixture)` succeeds without warnings; `pdfplumber.open(fixture)` extracts non-empty text per page; per-modelo deep extractor produces a valid casilla map.
- **Golden-fixture tests (unit, fixture-bound).** One sanitised PDF committed at known SHA; sanitiser produces byte-equal output. Intentional changes update the golden; unintentional changes are caught.

## out-of-scope explicit

The sanitiser does **not**:

- **Image-region redaction.** Justificantes are text PDFs; no PII surfaces in raster regions.
- **OCR over scanned PDFs.** Justificantes are vector text by construction (verified in captures: `Tj` operands with literal/hex strings, no `Im<N> Do` over a rasterised text block).
- **Removing or re-issuing digital signatures.** Verified absent in captures (no `SigFlags` in catalog). If a future modelo carries a signature dict, the sanitiser **must refuse** rather than silently break the signature.
- **Language-aware PII detection (NER).** Presidio is overkill. We do declarative token replacement against a known mapping. The operator supplies the cleartext-to-synthetic map; the sanitiser performs the transformation.
- **PDF/A conformance preservation.** Rewriting Tj operands necessarily breaks PDF/A-1B's content/XMP alignment. Sanitiser drops the `pdfaid:*` claim from XMP rather than leave a false claim.
- **Defending against an adversary with build-pipeline access.** Threat model is passive recovery from a public artifact, not active supply-chain attack.
- **Multi-pass NLP-driven sanitisation of free-text fields.** Casilla values are bounded enums or numerics; no free-text body paragraphs in a justificante.

## open questions for the adr

1. **`pikepdf` as hard runtime dep, or extras?** Hard dep means every CI run + every dev install pulls the wheel (~6 MB Linux, larger Windows). An `extras_require[sanitizer]` shape gates it behind `pip install aeat[sanitizer]`. **Recommendation:** hard dep — sanitiser is part of the test-data pipeline; CI needs it.
2. **Default mapping in `aeat.adapters.inbound.sanitizer.fixtures` or per-fixture?** Per-capture YAML at `scratch/.../sanitizer-mapping.yaml` is more flexible; project-level default couples to one user's identity. **Recommendation:** per-capture, scaffolded by `aeat sanitize prepare-map`.
3. **Refuse to re-sanitise an already-sanitised PDF?** Hash the input; if SHA matches a known-sanitised SHA in `aeat.adapters.inbound.sanitizer.fixtures.SANITIZED_SHAS`, refuse. **Recommendation:** yes — makes accidental "sanitise the fixture again" a hard error.
4. **Drop annotations entirely, or only PII-bearing?** Captures have zero annotations. **Recommendation:** drop entirely when present.
5. **AcroForm strategy when present.** Modelo 100 has none; other modelos may. **Recommendation:** scrub field values, preserve form structure.

## references

- pikepdf root: `https://pikepdf.readthedocs.io/`
- `parse_content_stream` / `unparse_content_stream`: `https://pikepdf.readthedocs.io/en/latest/api/filters.html` and `https://pikepdf.readthedocs.io/en/latest/topics/content_streams.html`
- `Pdf.save` flags: `https://pikepdf.readthedocs.io/en/latest/api/main.html`
- attachments: `https://pikepdf.readthedocs.io/en/latest/topics/attachments.html`
- metadata pattern: `https://pikepdf.readthedocs.io/en/latest/topics/metadata.html` and `pikepdf/pikepdf#89`
- pikepdf PyPI: `https://pypi.org/project/pikepdf/`
- pikepdf license (MPL-2.0): `https://github.com/pikepdf/pikepdf/blob/main/LICENSE.txt`
- pypdf PyPI: `https://pypi.org/project/pypdf/`
- pdfrw PyPI: `https://pypi.org/project/pdfrw/`
- `JoshData/pdf-redactor` (CC0, pdfrw-based): `https://github.com/JoshData/pdf-redactor`
- `chmdznr/py-pdf-sanitizer` (pikepdf, JS-removal recipe): `https://github.com/chmdznr/py-pdf-sanitizer`
- `sypht-team/pdf-anonymizer` (MuPDF-JS, char-randomisation; anti-pattern reference): `https://github.com/sypht-team/pdf-anonymizer`
- `microsoft/presidio`: `https://microsoft.github.io/presidio/`
- Presidio PDF annotation example (uses pdfminer + pikepdf): `https://microsoft.github.io/presidio/samples/python/example_pdf_annotation/`
- PyMuPDF redaction API: `https://pymupdf.readthedocs.io/en/latest/page.html#Page.add_redact_annot`
- PyMuPDF licensing (AGPL / commercial): `https://pymupdf.readthedocs.io/en/latest/about.html#license` and `https://artifex.com/licensing`
- Manafort 2019 redaction failure: `https://www.cjr.org/analysis/manafort-mueller-redacted-document-ukraine.php` and `https://www.vice.com/en/article/paul-manafort-russia-case-redaction-fail/`
- Argelius Labs deep-research on PDF redaction failures: `https://www.argeliuslabs.com/deep-research-on-pdf-redaction-failures-and-security-risks-exploits-and-best-practices/`
- US Court of Federal Claims redaction best practices: `https://www.uscfc.uscourts.gov/sites/cfc/files/pdf_file_redaction_best_practices.pdf`
- CVE-2026-3774 (PDF JS / form actions defeating redaction): `https://cve.circl.lu/vuln/cve-2026-3774`
- PDF specification ISO 32000-2 (PDF 2.0) — content-stream operator semantics
