---
tags:
  - '#reference'
  - '#evidence-corpus'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:063701f89c75d7a7ea75ebc0544c837d39629a2708c9b34aef43c7b6ce2d7679'
related:
  - '[[2026-09-14-registry-corpus-pruning-ownership-reference]]'
---
# `evidence-corpus` reference: `ownership`

## Summary

This is a read-only review of evidence files and their consumers across `dev/`, `src/`, `docs/`, packaging and development-index configuration. No corpus payload, registry declaration or source implementation was changed in this pass. Concurrent authority work makes these counts a snapshot, not a frozen completion gate. The reproducible census is `.logs/audit-runs/2026-09-14/evidence-corpus-census.py`; its summary is `.logs/audit-runs/2026-09-14/evidence-corpus-census.json`.

### Scale and what the measurements mean

The corpus contains 2505 files on disk: 2495 tracked files and 10 bytecode files. There are 140 PDFs, 570 HTML-named files, 114 XLS/XLSX workbooks, two XLSM workbooks, 34 XML files and 19 XSD files. Of the corpus files, 1400 carry extraction-sidecar names; two are actually authored Renta overlays. The separate `manual_corpus_text` tree carries 140 normalized PDF-text derivatives.

All 1300 explicit registry `corpus_path` and `corpus_ref` occurrences resolve to existing files, covering 791 distinct paths. All 568 source-pin declarations, reduced to 523 distinct path/hash/size tuples, match the files on disk. This proves neither anchor validity nor legal applicability. A separate heuristic scan found 4681 path mentions inside prose; the 11 unresolved distinct spellings all contain ellipsis abbreviations. These are non-machine-resolvable evidence citations, not 11 proven missing payloads. Zero broken typed paths must not be described as a fully grounded registry.

### Consumer and ownership map

Raw official payloads are authoring inputs for compiler source verification and record-design parsing. `dev/registry/compiler/corpus_catalogue.py:48` verifies source bytes; its manifest identity join at line 104 is scoped to record-design paths, not a universal acquisition catalogue. Full corpus acquisition ownership remains split among manifests, registry source pins, prose provenance and extractor defaults.

Anchored legal evidence is read by `dev/registry/compiler/legal_grounding.py:298` from a sibling extracted JSON. It resolves a unit and protects against fused redactions. Runtime exact-citation lookup instead reads published authority evidence through `src/cadrumo/application/corpus_search/citation_lookup.py:117`. These are separate publication-time and runtime responsibilities.

Runtime free-text retrieval scans only top-level `corpus/normatives/html/*.html.extracted.json` through `application/corpus_search/lexical_index.py:80`. Manuals, instructions, workbooks, EU files and Facturae are not in that lexical population. Development RAG uses `.vaultragpreprocess.toml` to extract raw PDFs, workbooks and normative HTML; `.vaultragignore` excludes their committed derivatives to prevent duplicate indexing. Every preprocess rule uses `on_error = "skip"`, so an extraction refusal can make a source invisible there even though it exists on disk.

`manual_corpus_text` is a separate normalized representation read by `dev/registry/compiler/validate_evidence.py:104`; invalid or absent derivatives fall back to raw PDF extraction. Manual `structure/` JSON is consumed by `domain/manuals/loader.py:170` and required by the compiler's practical-manual enrollment check. Manual-oracle JSON and Facturae enumeration resources have backend/parity/test consumers despite no explicit registry corpus locators. GROI samples are parser fixtures. Neither no registry path nor no search hit proves any of these unused.

Companion distributions are suffix-partitioned portions of one logical resource tree, resolved by `core/resources/bundled_data.py`; they are not duplicate authoring homes. User documentation describes the search capability and source-derived legal reference surfaces, but is not itself acquisition authority. `dev/corpus/build_evidence_corpus.py` names a different corpus entirely: invoice test fixtures under `application/ledger/tests/_evidence_corpus`, not legal grounding sources.

### Confirmed defects and priorities

1. **Format and version boundaries are blurred.** Sixty-one files named HTML are valid XML API responses. All 61 extraction records report status ok; 59 hold one unit and include the response status text `200 / ok`. Eighteen source responses contain multiple dated versions. The HTML extractor strips markup rather than interpreting the response/version structure. `legal_grounding.py:336` refuses multi-version evidence, but the lexical reader does not run that guard. Rename alone is insufficient: preserve the raw response, parse the envelope explicitly, retain version identity and route each supported representation consistently to validation and search.

2. **Attribution can name the wrong authority.** `dev/docs/preprocess/_pdf.py:59` falls back to generic AEAT attribution. Nineteen current PDFs take that fallback, including BOE and EU documents. Missing acquisition metadata must remain missing or be resolved from its true owner; it must not be converted into an institutional assertion. Source bytes and hashes cannot validate the truth of that wrapper.

3. **Search survives corpus changes without invalidation.** `application/corpus_search/runtime.py:56` considers an existing SQLite index current solely because it exists. Removed files and old extraction text can therefore survive upgrades or corpus revisions. Use an indexed-input/extractor identity and rebuild on mismatch. Also make the search population explicit: broaden enrollment where intended or accurately describe its narrower coverage.

4. **Authored evidence is disguised as generated output.** Two Renta 2025 `source.pdf.extracted.md.extracted.json` files are units-only authored overlays. Live legal references depend on them, while freshness discovery explicitly excludes the shape. Move the authored content to an explicit annotation representation and update consumers atomically; do not overwrite it by extraction or label it verified source text merely because the filename says extracted.

5. **Manual structures are not complete manuals.** All 18 structure directories were traced. Sixteen have one chapter, one section, one paragraph and no rules; Sociedades 2022 and 2023 have no chapters or sections. These structures carry review metadata and are load-bearing for manual-source enrollment. Source availability/hash validation should not imply semantic structure completeness, nor should acquiring a valid PDF require manufacturing a skeletal manual model.

6. **Evidence locators remain mixed with prose and filenames.** The ellipsis paths above cannot support mechanical dependency analysis. Filename suffixes and size floors also participate in `corpus_tier` checks in `corpus_catalogue.py:137`; renaming can change acceptance despite identical evidence. Separate stable identity, actual media type, source granularity and optional descriptive filenames. Replace abbreviated citations with exact typed references without inventing historical inspections.

7. **Retired preprocessing remains present.** `dev/docs/preprocess/_text.py` declares itself retired and has an empty enrollment set but retains extractor functions and tests as a migration precursor. Its documented CP1252 dictionary concern needs an encoding check at the actual reader before retiring that module. Stale comments also describe a future preprocess hook that already exists and runtime sidecar reads that have moved to the authority artifact.

### What not to prune on this evidence

Retain the formula-bearing, currently unattested Modelo 200 XLSX until its derivation is established or its consumer replaced. Preserve dated legal sources needed by supported filing periods; a superseded law or retired Modelo 037 document can be necessary historical evidence. Preserve dynamically loaded oracles, locale-independent terminology and package mirrors. Exact duplicate comparisons found repeated annual chapter structures and per-binary M190 corrections, not additional safe binary deletions after the preceding Modelo 720 cleanup.

### Remediation sequence and acceptance

First define distinct source, derivative, annotation, semantic-structure and test-fixture roles using the existing artifact catalogue where appropriate. Then correct XML/media routing and attribution, make discovery failures visible and invalidate runtime search on corpus changes. Decouple manual-source evidence from optional structured-manual coverage. Only then consolidate duplicate representations and retire obsolete tools with their consumers updated.

Acceptance must compare canonical source hashes, anchored/versioned text, exact citations and indexed population before and after; it must report lost or newly excluded evidence. A directory census, zero dangling paths or matching hashes alone is not an evidence-quality completion signal. The independent consumer audit and direct probes support the findings above; no live index contents, external legal freshness or whole-authority recompilation were claimed.

### Follow-up: separate manual source identity from authored structure

`verify_source_file` no longer calls the structured-manual loader. The previous call made byte-identity verification depend on authored chapter availability and review metadata, and ran only for local sources, not companion-resolved binaries. The separate legal-reference manual-section validator remains unchanged. No manual structures or primary PDFs were deleted. Removed the unused loader protocol, helper and helper-only tests; replacement tests prove absent/corrupt optional structure cannot alter source identity while same-length byte tampering and size changes still fail.

All 23 declared manual PDFs pass exact source verification. The targeted source-identity, companion and structured-section checks completed with 10 passed (exit 0); targeted Ruff and diff checks passed. The wider catalogue-verifier run completed with 25 passed and 26 failures, including obsolete calls missing required `source_root` and `effective_date` arguments; this is not a whole-catalogue success claim. Search descriptions now distinguish normative lexical coverage from signed exact citations and broader development RAG. The environment reference was regenerated through its owner and passes its freshness check.

### Follow-up: replace disguised authored overlays with source-bound page selections

The two Renta 2025 `source.pdf.extracted.md.extracted.json` overlays were removed. Their nine `title`/`section`/`text` records were manually composed and none was an exact contiguous extraction from the official manuals, so preserving those bytes would have preserved an unsupported authored evidence copy. They are replaced by two minimal `source.pdf.annotation.json` files containing only schema version, source SHA-256, stable anchors and exact page numbers. Text is reconstructed from the hash-bound `source.pdf.extracted.json`; the annotation schema forbids embedded prose.

All nine legal references now cite the underlying `source.pdf#anchor`. Every required clause resolves from exact selected pages. Resolved bodies intentionally grow from the former 729–1002-character recompositions to complete 1824–4174-character page selections; this is a provenance correction, not byte parity. Both annotations are catalogued as `SemanticAnnotation` against the PDFs, with independent manual-manifest and registry-source identity agreement. Orphan annotations, malformed metadata, stale source/extraction hashes and undeclared targets refuse validation.

The resolver accepts physically separate source, annotation and extraction paths, preserving the installed split-wheel contract: the command wheel contains annotations and extractions while `cadrumo-data-manuals` supplies PDFs. A real wheel build proved both annotations present and the existing PDF exclusion intact. The freshness gate now rejects any units-only `*.extracted.json` lacking provenance instead of silently excluding it, and `.vaultragignore` excludes `*.annotation.json` because selectors are metadata rather than indexable prose. Focused proofs passed: 6 core annotation tests, 5 compiler/catalog tests, 26 preprocessing/freshness tests, the wheel membership test, and direct resolution of all nine real legal references.

### Follow-up: normalize BOE legal XML without committed derivatives

The BOE legal XML family now has one physical and semantic home: `corpus/normatives/xml/`. Sixty-one response-envelope documents formerly named `*.html` and twenty-eight already-sliced `<version>` documents formerly stored below `normatives/html/` were moved there. The resulting population is 89 XML files; `normatives/html/` contains zero XML extensions and zero XML-signature HTML files.

The raw XML is now the authority. The 122 committed `*.extracted.json` and `*.extracted.md` derivatives belonging to the sixty-one response documents were removed. The preprocessing hook parses both BOE response envelopes and sliced version roots from raw XML, keeps dated redactions separate, excludes envelope status text, and emits source-stated article or ordinal boundaries. A corpus-wide proof produced 89 outputs, 144 units, and zero parse failures.

The registry compiler resolves XML legal citations through that same extractor without requiring committed sidecars. It refuses any response carrying two or more dated redactions because an article fragment selects the provision but not one temporal version. One-redaction responses remain valid and use the literal BOE block id. The live `ley-41-1994:art-78-segundo` and `ley-58-2003:art-94` citations resolve directly from XML.

Twenty-six catalogued sliced versions retained exact source identity after relocation: all 26 paths exist and all 26 byte counts and SHA-256 values match their existing declarations. A migration-added terminal LF was detected by this proof and mechanically removed rather than changing the pinned identities. Sixty-one renamed response documents are byte-identical to their former Git blobs.

Six uncatalogued post-2024 DT32 captures were deleted because no code, fact, source declaration, or document consumed them and the registry already records that those attempted extensions had no legal effect. Two uncatalogued historical article-31 snapshots (2007 and 2012) remain on semantic-retention hold.

The normative acquisition tool now enforces direct-child filenames and format-correct suffixes before network acquisition: consolidated/as-published documents require `.html`, article responses and exact redactions require `.xml`. Focused proofs: preprocessing/acquisition 52 passed, fused-redaction contract 5 passed, evidence-vintage audit 44 passed, 732 authored legal references grounded with zero failures, and the structural compile produced 58 modelos and 567 sources.

### Follow-up: exclude interpreter caches from evidence identity

The final residual sweep found only ignored CPython bytecode beneath the corpus. Those files were removed, and the source-evidence fingerprint walker now prunes `__pycache__` and `.pytest_cache` directories and excludes loose `*.pyc` files. These are interpreter outputs rather than legal evidence; admitting them made authority publication invalidate its own pre-validation receipt when imports regenerated bytecode. A focused test proves both nested and loose bytecode are absent while the real specimen remains fingerprinted.

The fresh full validated compilation succeeds with 58 modelos, 567 sources, and 1,402 legal references. Runtime publication was attempted three times through the canonical owner command and refused transactionally each time because concurrent authority-store/compiler edits changed the complete candidate receipt during validation. No receipt bypass or generated-artifact hand edit was made; publication remains a separate external-concurrency residual.
