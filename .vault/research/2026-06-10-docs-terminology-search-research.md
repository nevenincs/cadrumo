---
tags:
  - '#research'
  - '#docs-terminology-search'
date: '2026-06-10'
modified: '2026-06-10'
related:
  - "[[2026-05-30-docs-architecture-adr]]"
  - "[[2026-06-01-docs-educational-surface-adr]]"
  - "[[2026-05-19-spanish-tax-glossary-reference]]"
---

# `docs-terminology-search` research: `precompiled docs terminology search backend`

Operator brief (2026-06-10): the vaultspec-rag semantic vector database has no
applicability in the shipped documentation pipeline as a search interface. The
documentation instead fights hand-maintained glossary and terminology sections
("the plain words you will meet", followed by lists of modelo, casilla, IVA,
IRPF, renta, ...) which are inefficient and unmaintainable at this project's
scale. The request: design a framework that, at build time, enrols search
terminologies from the shipped corpus — the registry data, the legal grounding
files (PDF, XLS, HTML), and the codebase/CLI itself — and precompiles a
comprehensive term-to-result mapping that ships inside the documentation,
replacing the hard-coded sections with a real search interface.

This research grounds that idea against four surfaces: the shipped docs
pipeline, the vaultspec-rag implementation, the current RAG index coverage of
`src/aeat/_data/`, and the machine-readable terminology sources that ship in
the wheel. Discovery was performed by four parallel read-only research agents
on 2026-06-10; all RAG queries ran through the resident service
(`--port 8766 --timeout 30`).

## Findings

### F1. The shipped docs already own the right UX slot, but search is lexical-only

- The docs theme ships a custom Ctrl/Cmd-K command palette (`initPalette`,
  `docs/_static/aeat-docs.js` lines 214-360, already committed). It indexes
  **only** the rendered sidebar nav tree plus on-page TOC anchors
  (`navIndex()`), scores prefix/word/substring matches client-side, and
  appends a "Search the docs for ..." row that deep-links to Sphinx's stock
  `search.html?q=` full-text fallback. The sidebar trigger is
  `docs/_templates/sidebar/aeat-search.html` (registered first in
  `html_sidebars`, `docs/conf.py:252-259`).
- Sphinx/Furo ships the stock precompiled client-side full-text index
  (`searchindex.js`, ~1.54 MB) with **English-only stemming** — Spanish tax
  stems (declaración, justificante, casilla) get no morphological help, and
  there is no cross-vocabulary bridging (vat→iva, box→casilla, form→modelo).
- The build pipeline already has the exact seam for a precompiled artifact:
  `docs/conf.py` `builder-inited` hooks regenerate the entire `docs/cli/`
  reference from the live Typer tree on every build
  (`dev/docs/cli_reference.py`; output gitignored, never committed, cannot
  drift). A compiled terminology artifact can be emitted by the same
  mechanism and gated by the existing `-n -W` docs build gate
  (`dev/docs/tests/test_docs_build.py`) plus the docs-marked conformance
  suite.

### F2. Hand-maintained terminology exists in at least four unsynchronised stores

- `docs/glossary.md` — 114 lines, 26 hand-authored deflist entries. No gate
  ties it to the registry, the `Modelo` enum, the locale catalogue, or the
  CLI tree; nothing reds when a term goes stale or new shipped vocabulary
  (IVA categories, carry/previous_filing, evidencia, recargo de equivalencia)
  lacks an entry.
- `docs/explanation/index.md` lines 15-27 — a second parallel mini-glossary
  ("The plain words you'll meet") re-defining Modelo, Casilla, IVA, IRPF,
  RENTA, Justificante in different words, plus a third definitional section
  ("What 'verify' and 'file' mean here").
- Per-page inline re-definitions: "modelo is a tax form" is hand-stated in at
  least 10 places, "casilla is a numbered box" in at least 6, "AEAT =
  Agencia Estatal de Administración Tributaria" expanded by hand in ~12
  files. `docs/how-to/profile-setup.md` alone carries 51 deflist entries
  hand-mirroring typed enums, registry data, and locale help strings;
  `docs/how-to/filing-periods.md` hand-enumerates the period-token closed set
  that exists as a core enum.
- Vault-side (unshipped): the 849-line Spanish-tax glossary reference with
  per-entry BOE/AEAT citations, and the 294-line quad-lingual i18n glossary
  with an open-ended "expansion protocol".
- The docs-architecture ADR's own "codebase-state-as-truth" principle —
  every surface is either generated from code or pinned by a conformance
  test — is satisfied for commands (conformance gates
  `test_documented_command_conformance.py`,
  `test_educational_docs_conformance.py`) but **violated for terminology**:
  the educational-surface ADR names redeclaration as the central risk and
  solved it for commands only. Terminology is the last documented surface
  still hand-redeclared.

### F3. The vaultspec-rag stack: runtime reuse is not viable; build-time reuse is

Installed package: `vaultspec_rag` 0.2.17 (regular dependency).

- **Dense model** `Qwen/Qwen3-Embedding-0.6B` (1024-d, ~1.2 GB, Apache-2.0)
  — CPU-capable in principle, but the wrapper hard-refuses without CUDA
  (`embeddings.py:75-79`). An ONNX O4 export path exists in the package
  (CUDA-only as wired) proving an exportable artifact exists.
- **Sparse model** `naver/splade-v3` — **CC BY-NC-SA 4.0, gated repo**. Hard
  licensing blocker: nothing SPLADE-derived may ship in a distributed
  artifact.
- **Reranker** `BAAI/bge-reranker-v2-m3` (Apache-2.0) — CUDA-refusal in the
  loader.
- **Store**: qdrant-client embedded local mode, single `storage.sqlite` per
  collection with **pickled** point blobs, exclusive `FileLock`, full-RAM
  brute-force scan. Current footprint: `vault_docs` 6,470 points / 124 MB;
  `codebase_docs` 116,129 chunks from 18,346 files / **1.9 GB** (~20x the
  corpus it serves). Unsuitable as a shipping artifact: pickle fragility,
  lock semantics, RAM residency, size.
- **Query path**: GPU-encoded dense+sparse query → hybrid RRF fusion →
  optional CrossEncoder rerank → vault graph boosts. A query-time-only reuse
  would drag torch (CUDA-13 pinned wheel), transformers, qdrant-client, and
  ~2.5-3 GB of model downloads into the docs reader's machine, with hard
  RuntimeErrors on non-CUDA hosts. Ruled out.
- **Chunkers**: tree-sitter AST chunker for code (pure CPU, the
  `tree-sitter-language-pack` dependency is already locked) and a 512-char
  recursive `TextSplitter` for everything else. Cleanly reusable at build
  time.
- **Lighter shipped-search assets already in the tree**: Sphinx's own
  precompiled `searchindex.js` (today's de-facto shipped search backend);
  stdlib sqlite3 FTS5 (BM25, prefix queries, zero added dependencies);
  tree-sitter. No whoosh/lunr/tantivy/fastembed/onnxruntime in `uv.lock`.

The decisive structural constraint: arbitrary user queries cannot be
pre-embedded. What CAN be precompiled is exactly the operator's framing — a
**term-to-result mapping**: enumerate a finite query vocabulary at build time
(canonical terms, aliases, translations, synonym rings), resolve each to
ranked documentation targets (optionally using embeddings as the build-time
relevance oracle), and ship only the resulting mapping as plain data.
Apache-2.0 model **outputs** are shippable; the SPLADE half is not and must
be excluded from any shipped derivative.

### F4. RAG index coverage of `src/aeat/_data/`: largely covered, with precise gaps

The operator hypothesis that `_data` is absent from the RAG index is
**false**: the code index covers 15,842 of 16,067 files under
`src/aeat/_data/` (98.6%) — `_data` is 86% of the whole code index by file
count. Empirical searches return `_data` hits at the top (registry casilla
TOML at 0.51; corpus normative HTML at 0.86; legal catalogue TOML at 0.97).
The real gaps, with walk/filter rules cited from the installed package:

- **Binary/unsupported extensions are structurally invisible** (extension
  gate `indexer/_chunking.py:158-186`): 74 `.xlsx` + 28 `.xls` (the official
  AEAT Diseños de Registro workbooks — the highest-value grounding files),
  73 `.pdf` (manuals; 3 also exceed the 10 MB cap at `_chunking.py:257`),
  15 `.xsd`, 12 `.properties` (M100 diccionario dictionaries), 8 `.txt`
  (incl. M349 instructions), 1 `.xml` (`fx/eurofxref-bundled.xml`), 1
  `.docx`. Total ~219 files carrying exactly the legal-grounding corpus the
  operator named.
- **Staleness hole**: 6 M390 TOML fragments created hours before the audit
  were missing — the watcher's scoped incremental can miss new files. Any
  precompile step must be preceded by an explicit incremental
  `vaultspec-rag index --type code --port 8766`.
- **Chunking quality**: corpus HTML (13.3 MB, 265 files) is embedded as raw
  markup — works (BOE article headers rank 0.86) but wastes ~30-40% of each
  512-char chunk on tags, and BOE TOC link farms pollute the low-score tail.
  The BOE article delimiter (`<h5 class="articulo">`) is a natural
  split/strip boundary. Large casilla TOML fragments are split mid-table
  losing the `[table]` header context. Locale YAML is indexed but embeds
  poorly (natural-language Catalan queries score 0.01-0.03) and contributes
  4x duplication; it should be excluded from any docs-search collection.
- **Search-side crowding**: per-revision near-duplicate casilla labels
  consume top-k like the 4x locale duplication; consumers need
  `--max-results 20` plus dedupe by casilla number across revisions.

### F5. Enrolment sources: the term axes already ship in the wheel, typed and parseable

The wheel packages the whole `src/aeat/_data/` tree (registry 43 MB, corpus
307 MB), reachable via `importlib.resources` at runtime and trivially
parseable at build time. The authoritative term axes:

| Axis | Source | Count | Labels |
|---|---|---|---|
| Modelos | registry manifests + `Modelo` StrEnum | 30 registry + 31 enum members | `title`, `official_name`, `tax_domain`, legal/source refs |
| Casillas | `.../revisions/<rev>/casillas/*.toml` | **18,885 entries** | Spanish `label`, `number`, `section[]`, `semantic_role`, `legal_refs`, `source_refs` |
| Legal provisions | `registry/aeat/legal/*.toml` | 262 | Spanish `notes`, `required_text[]`, BOE `permalink`, `corpus_ref` → anchored corpus HTML |
| Formulas / deadlines | revision subdirs | ~1,340 | revision labels, citations |
| IVA categories | `IvaCategory` enum + `iva/catalogues/2025.toml` | 17 members | locale-keyed labels/descriptions + BOE article citations |
| Periods, languages, other closed axes | `core/_period.py`, `external_constants` | dozens of axes | member names + docstrings |
| Help topics | `registry/aeat/topics/*.toml` | 13 | slug, `see_also`, legal_refs; prose in locale `topic.*` keys |
| CLI verbs/options | Typer tree introspection (prior art: `dev/docs/cli_reference.py` `_collect_commands`) | full tree | help strings resolve through locales |
| Translations | `src/aeat/locales/{en,es,ca,hu}.yml` | **2,855 leaf keys x 4 languages**, parity-gated | quad-lingual CLI/topic terms for free |
| Registry per-revision locales | `revisions/<rev>/locales/*.toml` | sparse (12 files) | EN/CA/HU casilla labels exist only for e.g. M303 — casilla terms are mostly Spanish-only |

Per the registry-authority-flow rule, the index builder must consume
`RegistrySnapshot` projections via `ValidatedRegistryAuthority`, not re-parse
TOML fragments. Fixture PDFs/sidecars are dev/test-only in purpose and stay
out of the shipped index; corpus PDFs/XLS are grounding evidence to link to
(and to extract for the dev-side RAG), not term records.

## Design pathways assessed

- **Pathway A — reuse the RAG index/service at docs read time: ruled out.**
  CUDA hard-refusal, SPLADE licence taint on every stored hybrid vector,
  pickled exclusive-locked RAM-resident store at 20x corpus size, multi-GB
  reader-side dependency footprint.
- **Pathway B — reuse RAG models at build time, ship a different artifact:
  viable.** Qwen3-Embedding (Apache-2.0) + the chunkers run on the dev GPU
  box (or CPU outside the refusing wrapper) during the docs build to compute
  term→target relevance and to mine synonym rings; only plain-data outputs
  ship. SPLADE must never participate.
- **Pathway C — deterministic build-time terminology extraction, no
  embeddings: lowest risk, partially exists.** The Sphinx index already
  ships; the increment is a compiled term artifact from the typed sources in
  F5, wired into the existing palette.

**Recommended shape: C as the deterministic baseline, B as an optional
build-time enrichment generator, A ruled out.** The deterministic compiler
must be sufficient on its own (CI-buildable without GPU); the embedding pass
only improves alias/relevance quality and runs where a GPU exists, with its
outputs committed or cached as reviewable data.

## Proposed framework: the terminology compiler

A build-time pipeline, `enrol → enrich → compile → gate`, mirroring the
established registry authoring-compiler pattern:

1. **Enrol** (deterministic): walk the typed sources in F5 (registry
   snapshots via the authority, core enums, legal catalogue, IVA catalogue,
   topics, CLI tree, locale catalogues) and emit typed `TermRecord`s
   (pydantic): canonical term (Spanish stem per the naming rule), kind
   (modelo | casilla | legal-ref | concept | cli-verb | period | ...),
   aliases and translations (en/es/ca/hu where available), a definition
   sourced from the authority (registry label / locale topic prose / enum
   docstring), legal grounding (`legal_refs` + BOE permalink + corpus
   anchor), and documentation targets (glossary anchor, how-to/explanation
   pages, generated CLI reference page, API stub).
2. **Enrich** (optional, build-time only, GPU dev box): embed term records
   and doc-page chunks with the Apache-2.0 dense model to (a) rank each
   term's documentation targets, (b) mine cross-vocabulary synonym rings
   (vat→iva, box→casilla, form→modelo, receipt→justificante), (c) flag
   orphan terms (term enrolled, no doc target) and orphan pages (page
   mentions no enrolled term). Outputs are plain JSON reviewed like any
   generated data; no model ships.
3. **Compile**: emit, at the `builder-inited` seam alongside `docs/cli/`:
   (a) a `terminology.json` artifact (term, kind, aliases, definition,
   targets, legal grounding) consumed by the existing Ctrl-K palette —
   palette answers term queries first (definition card + jump targets), nav
   titles second, stock full-text third; (b) a **generated glossary page**
   replacing `docs/glossary.md`, rendered from the same records (gitignored,
   regenerated per build, exactly like the CLI reference, honouring the
   user-docs language rules); (c) optionally a Sphinx-search synonym
   injection so the stock index also benefits from the rings.
4. **Gate** (codebase-state-as-truth, closing the F2 violation): a
   docs-marked conformance test asserting every enrolled term resolves to
   live sources (enum member exists, registry id exists, CLI verb resolves,
   corpus anchor exists), every documentation target resolves in the built
   tree, and — the redeclaration gate — the hand-written docs no longer
   carry inline re-definitions of enrolled terms (they reference the
   generated glossary instead). This is the terminology sibling of the
   command-conformance gates.

Scale control: 18,885 casillas must not become 18,885 glossary entries.
Enrolment is tiered — concepts/modelos/CLI verbs/IVA categories/periods are
first-class palette terms; casillas enrol as a searchable namespace
(modelo + number + label) deduplicated across revisions, surfaced through
search rather than rendered pages.

## Dev-side RAG hardening (prerequisite track, operator-flagged)

For the build-time enrichment (and for every agent working this codebase)
the dev RAG index needs the F4 gaps closed:

- Add `.txt`, `.xml`, `.xsd`, `.properties` to the supported-extension map
  (36 currently-invisible text files, incl. M349 instructions and M100
  diccionario dictionaries) — upstream `vaultspec_rag` change or ignore-level
  workaround.
- **Extraction sidecars for PDF/XLS/XLSX/DOCX** (175 files): materialise
  per-file extracted text (pdfminer/openpyxl — openpyxl is already a
  dependency of the export surface) into a committed sidecar tree mirroring
  the existing `corpus/manuals/**/source.html` convention, so the existing
  walker indexes the sidecars. Highest value: the Diseños de Registro
  workbooks (casilla-number ↔ field-position tables the registry parity
  gates already consume).
- HTML-to-text (or `<h5 class="articulo">`-aware splitting) for the 13.3 MB
  normatives corpus.
- Run an explicit incremental index before any precompile step; do not trust
  the watcher alone (6-file M390 staleness observed).
- Exclude locale YAML from any docs-search collection; budget for
  casilla-revision dedupe in all consumers.

## Open questions for the ADR

- Artifact residency: pure build-time generation (gitignored, like
  `docs/cli/`) vs committed-and-gated (reviewable diffs, like `docs/api/`).
  Build-time generation is the better fit for the deterministic compiler;
  the embedding-derived synonym rings likely need to be committed data since
  CI has no GPU.
- Palette contract: how far the term card goes (definition + links vs
  rendered legal refs) and whether the artifact is sharded for page-load
  budget (26-entry glossary today vs thousands of term records).
- Whether the generated glossary fully deletes `docs/glossary.md` in the
  same change (no-legacy rule says yes — no parallel hand-written copy may
  survive).
- Casilla enrolment depth: all 18,885 vs per-modelo curated subsets vs
  completeness-manifest-required sets only.
- Where the compiler lives: `dev/docs/` (build tooling, like
  `cli_reference.py` and `apidocs`) vs `src/aeat/` (shippable application
  surface). The CLI-surface rule (config/app roots only) argues for
  `dev/docs/` unless an operator-facing search verb is in scope.
- Upstream vs local: the extension-map and HTML-extraction fixes belong in
  the `vaultspec_rag` package — coordinate an upstream release or carry a
  documented local pre-processing layer (sidecars), which works with the
  package as-is.

## Prior art (web research fan-out, 2026-06-10)

Operator-directed second discovery round: five parallel web-research agents
(two opus deep-dives, three sonnet breadth sweeps) surveying existing
codebases and standards. Operator decisions locked before this round: the
compiled search database is NOT committed (mirrors the uncommitted HTML
build); the enrolled terminology — the **Terminology Handbook** — IS
committed, programmatically generated, and continuously curated; the
Handbook is the middle layer between registry compilation and shipped
documentation. Additional grounding directive: search must serve both
CLI/codebase navigation AND text-terminology lookup — a query like
"pro rata" must return the concept's meaning, the legal grounding resources
the code is grounded against, and the modelo casilla schema descriptions
(every casilla has a localised description conforming to the official
casilla descriptions).

### P1. Static-site search engines (opus sweep)

- **Pagefind** (CloudCannon, MIT, v1.5.2 2026-04, Rust→WASM): the only
  candidate satisfying every hard constraint. Native Spanish AND Catalan
  (and Hungarian) stemming with automatic per-language index splitting;
  chunked lazy-loaded index (~100-300 KB read-time payload for 10k+ pages);
  configurable ranking weights + `metaWeights`; and decisively a **NodeJS
  AND Python indexing API with `addCustomRecord`** that injects arbitrary
  synthetic records (our term/casilla/CLI records with metadata, filters,
  weighting) alongside `addDirectory` over built HTML. Sphinx+Furo prior
  art exists (Gandi blog walkthrough: `pagefind.yml` root selector, Furo
  `search.html` template override, post-build index pass); Astro Starlight
  ships Pagefind as default search via its build-done hook. Hermetic-build
  caveat: the binary/wheel must be vendored so the build does no network
  fetch. Repo: `github.com/CloudCannon/pagefind`.
- **Orama** (Apache-2.0, v3.1.18, pure JS ~2 kB engine): strongest
  library alternative; prebuilt-index persistence plugin
  (`@orama/plugin-data-persistence`), custom tokenizer (BYO Snowball-es;
  Catalan stemmer not bundled), field boosting/filters/typo tolerance.
  Whole-index load (no lazy chunking) is the scaling trade-off at 25k
  chunks; persistence round-trip has open issues (#876, #695). Best fit if
  reusing the existing vanilla palette without a separate binary.
- **Rejected**: Stork (unmaintained, wound down Jan 2023), tinysearch (no
  prefix search/synonyms, small-site only), Fuse.js (no precompiled
  inverted index — fuzzy matcher only), Elasticlunr (deprecated),
  FlexSearch (no es/ca stemmer, explicitly no synonym search), Sphinx
  native search (single-stemmer-per-project — confirmed architectural:
  `sphinx.search.SearchLanguage` is chosen once by `language=`; en+es+ca+hu
  cannot co-exist in one `searchindex.js`), readthedocs-sphinx-search
  (deprecated; a client to RTD's hosted Elasticsearch), and all hosted
  services (Algolia DocSearch / Typesense / Meilisearch — network at read
  time violates offline-hermetic).
- Lunr (`lunr-languages` has es but NO Catalan) and MiniSearch
  (`minisearch-synonyms` is the cleanest declarative synonym-ring
  reference: query OR-expansion) remain useful references only.

### P2. Shippable semantics ladder (opus sweep)

- **Rung 1 — build-time-mined synonym rings shipped as plain data**: mine
  near-synonyms with embeddings on the GPU box at build, ship
  Elasticsearch-style `term → aliases` JSON (tens of KB). Mining is NOT
  auto-safe: cosine-NN mining suffers antonym intrusion ("deducible" vs
  "no deducible") and co-hyponym intrusion (sibling modelo codes) even at
  cosine ≥ 0.85; validated method = relative-cosine ranking + a
  human-reviewed allowlist (mirror of the locales
  `_intentional_identical.json` ratchet discipline).
- **Rung 2 — static term-embedding matrix + client-side cosine**: ship a
  precomputed int8/float16 matrix for the closed term vocabulary only
  (~5,000 terms × 256 dims ≈ 1.3-2.5 MB; gzip smaller) + a few-line JS
  cosine. No model, no WASM ships. Model2Vec/potion
  (`potion-multilingual-128M`, MIT, 256-d, 101 languages — es/ca/hu/en all
  confirmed; 90.86% of LaBSE on MTEB) is the build-time embedder; Model2Vec
  inference is tokenize→lookup→average (no neural net). Negative findings:
  NO browser Model2Vec runtime exists (transformers.js #970 never
  implemented; rust port has no published WASM build), and nobody ships a
  curated-vocabulary static term-matrix docs search — the pattern is
  assembled from proven primitives, not copied from a reference deployment.
  Embedding all 25k doc chunks would be 6.4-12.8 MB — that rung approaches
  rung-3 territory.
- **Rung 3 — transformer in the browser** (transformers.js + ONNX
  all-MiniLM-L6-v2 q8 ~23 MB + ~4 MB WASM; SemanticFinder, Ken Hawkins'
  static-site deployment): ~30 MB cold download, live runtime dependency,
  high maintenance. Its only unique capability is embedding uncatalogued
  free text cross-lingually at query time.
- **Cross-lingual verdict (load-bearing)**: our term records already carry
  their four translations as declared aliases, so build-time alias
  expansion delivers exact cross-lingual matching for free; expensive rungs
  buy capability we already have declaratively. Recommendation: ship rung 1;
  hold rung 2 (term-matrix-only scope) behind a measured rung-1 miss-rate
  on a held-out query set; reject rung 3.

### P3. Glossary generation and governance prior art (sonnet sweep)

- **Kubernetes** (`kubernetes/website` `content/en/docs/reference/glossary/`):
  one markdown file per term; frontmatter `id`, `title`,
  `short_description` (tooltip), `aka` aliases, closed 12-value `tags`
  enum, `full_link`; a Hugo `glossary_tooltip` shortcode resolves by exact
  id (a substring-matching bug #14226 forced exact matching). No automated
  redeclaration gate.
- **Sphinx native machinery is the strongest free gate**: `:term:` role →
  undefined term emits warning type `ref.term` → hard build break under
  `-W`; Sphinx ≥ 3.0 also emits duplicate-glossary-entry warnings (same
  `ref.term` type) → `-n -W` catches BOTH missing enrolment and duplicate
  declaration at zero tooling cost. Known: case-sensitive matching;
  `suppress_warnings` for ref.term is partially broken (#13161) — which we
  don't need since we never suppress. `sphinx-hoverxref`
  (`hoverxref_roles = ["term"]`) gives hover tooltip cards on every
  `:term:` reference; multi-term shared definitions misrender (#97) — keep
  one term per entry. `chrisjsewell/sphinx-glossary` generates glossary
  directives from external YAML/JSON — proof the generated-glossary
  directive approach works.
- **glossarify-md**: term files + an auto-linking compile pass over consumer
  markdown (excludes code blocks/headings/existing links) — concept
  transferable to a MyST pass; no governance.
- **GitLab word list + Vale**: CI prose linting where `severity: error`
  fails the build on deprecated/wrong terminology — the only observed
  mechanism approximating a redeclaration gate. **Universal gap across all
  surveyed systems: none automatically detects prose re-declaring a
  canonical definition** — our redeclaration conformance gate is novel and
  must be built (Vale-style substitution rules or AST/regex scan over MyST
  sources).
- **Generated-then-curated merge semantics — the canonical pattern is GNU
  gettext `msgmerge`** with three outcomes: (1) preserve — matching entry
  carries curated prose forward verbatim; (2) scaffold-empty — new source
  term creates an empty entry explicitly marked needing curation (fuzzy
  carry-forward is the documented failure mode — wrong prose ships if the
  fuzzy flag is not cleared; avoid fuzzy auto-fill); (3) retire-as-tombstone
  — removed term becomes an obsolete-marked entry, never silently deleted.
  Five transferable rules: required first-class `short_description` (never
  inferred from first paragraph); msgmerge three-outcome contract for every
  scaffold run; the `:term:`/`-W` gate as the enrolment+uniqueness gate;
  closed tag enums; `--check` as a fast mandatory pre-commit/CI gate (the
  sphinx-apidoc / `dev.docs.apidocs` / `aeat.locales` house pattern).

### P4. Terminology data-model standards (sonnet sweep)

- **Concept-oriented modelling (TBX / ISO 30042 three-tier)**: one concept
  entry → language sections → term sections. Term-first rows break on
  multi-alias languages and missing locales; concept-first matches the
  registry's one-fragment-per-entity compile pattern. TBX-Basic field
  subset worth borrowing: `subjectField` (→ our `domain` closed enum),
  `definition`+`source` per language section, `context` examples,
  `normativeAuthorization` term statuses (preferred | admitted | deprecated
  | forbidden), `partOfSpeech`/`grammaticalGender` (es/ca need gender),
  cross-references.
- **SKOS borrowings**: `prefLabel`/`altLabel` → term status,
  `hiddenLabel` → unaccented/misspelt search-only forms (`declaracion`),
  `broader`/`related` for shallow relations (author `broader` only; derive
  `narrower` at load — no double bookkeeping), `scopeNote`, `exactMatch`
  reserved for IATE/EuroVoc alignment ids only. Skip the cross-scheme
  match properties.
- **Lifecycle**: four states suffice for a git-native handbook (draft |
  approved | deprecated | retired) + `replaced_by` (mandatory when
  retired) + `review_note`; never delete a record — retire it (SNOMED
  immutable-id inactivation pattern). Concept lifecycle and per-term status
  are orthogonal (the TBX insight).
- Proposed full ConceptRecord/language/term field tables with standard
  provenance are in the fan-out agent report; the ADR carries the decided
  subset.

### P5. External seed sources and licences (sonnet sweep)

- **Tier A — machine-readable, licence-clean, ingest at scaffold time**:
  IATE TBX bulk download (24 EU languages incl. es/hu/en; tax+law+finance
  domains; commercial reuse + derivatives explicitly permitted WITH
  attribution — but ONLY for the downloaded file, never website/API
  scraping; filter reliability ≥ 3); UBTERM `Diccionari de fiscalitat`
  (Universitat de Barcelona, ~270 trilingual ca/es/en fiscal entries,
  CC BY 3.0 — the cleanest Catalan fiscal source; confirm bulk-download
  availability); EuroVoc SKOS (es/hu labels for top-level fiscal concept
  hierarchy; verify the licence on the Publications Office downloads page
  before ingestion — labels only, no definitions).
- **Tier B — authoritative, link-only grounding (no bulk ingestion)**:
  AEAT Manuales Prácticos IVA/IRPF (primary authoritative Spanish
  definitions; reuse permitted with attribution + update date under
  Ley 37/2007), AEAT sede glossaries (shallow, 6-18 entries each), AEAT
  INFORMA (no bulk API), DG TAXUD multilingual VAT glossary (web-only),
  BOE API (legal text for `legal_refs` grounding — already in-corpus).
- **Licence red flags — excluded**: TERMCAT Terminologia Oberta is
  CC BY-ND 3.0 (no derivatives — reformatting into handbook records is a
  derivative; contact required, exclude by default); the TERMCAT/UOC
  Catalan-IATE export has no confirmed licence; RAE DPEJ is lookup-only
  (no download permitted); BOE "Digital Legal Library" sub-collection is
  CC BY-NC-ND (distinct from the freely-reusable main legislative texts);
  Microsoft Terminology Collection is IT-domain, no redistribution
  guarantee — verification-only.
- **Hungarian frank assessment**: NAV publishes nothing machine-readable;
  hu coverage realistically comes from IATE + EuroVoc + EUR-Lex
  translations + our own locale catalogue; Spain-specific regimes
  (recargo de equivalencia, módulos) have no hu authority equivalent — the
  handbook's hu entries for those are the project's own contribution.

## Sources

- Web prior-art fan-out 2026-06-10 (five agents: Pagefind/Orama landscape,
  semantics ladder with Model2Vec/potion and transformers.js numbers,
  Kubernetes/Sphinx/gettext glossary governance, TBX/SKOS schema standards,
  IATE/UBTERM/EuroVoc/AEAT/BOE seed-source licences); primary URLs:
  `pagefind.app`, `github.com/CloudCannon/pagefind`,
  `github.com/oramasearch/orama`, `github.com/MinishLab/model2vec`,
  `huggingface.co/minishlab/potion-multilingual-128M`,
  `kubernetes.io/docs/reference/glossary/`,
  `sphinx-hoverxref.readthedocs.io`, `github.com/chrisjsewell/sphinx-glossary`,
  `terminorgs.net/downloads/TBX-Basic-V4.pdf`, `w3.org/TR/skos-reference`,
  `iate.europa.eu/download-iate`, `ub.edu/ubterm/obra/fiscalitat`,
  `op.europa.eu/en/web/eu-vocabularies/eurovoc`,
  `blog.gandi.net/en/posts/sphinx-doc-and-pagefind`.
- Agent discovery reports 2026-06-10 (four parallel read-only researchers:
  docs pipeline, RAG architecture, corpus inventory, RAG index coverage
  audit), grounded via the resident RAG service (`--port 8766 --timeout 30`)
  and confirmed with `rg`/direct reads.
- `docs/conf.py`, `docs/_static/aeat-docs.js`, `dev/docs/cli_reference.py`,
  `dev/docs/apidocs/`, `dev/docs/tests/test_docs_build.py`,
  `src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py`.
- Installed `vaultspec_rag` 0.2.17: `embeddings.py`, `config.py`,
  `store.py`, `search/_searcher.py`, `indexer/_chunking.py`,
  `indexer/_codebase_indexer.py`, `indexer/_chunk_worker.py`;
  `.vault/data/search-data/code_index_meta.json` (18,346 indexed files).
- `src/aeat/_data/` inventory: registry (15,461 files), corpus (603 files,
  307 MB), legal catalogue (18 TOML / 262 provisions), topics (13), IVA
  catalogue; `src/aeat/locales/*.yml` (2,855 keys x 4).
- SPLADE-v3 licence: Hugging Face model card `naver/splade-v3`
  (CC BY-NC-SA 4.0, gated).
