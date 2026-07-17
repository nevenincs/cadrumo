---
tags:
  - '#adr'
  - '#manual-practico'
date: '2026-04-12'
modified: '2026-07-17'
related:
  - '[[2026-04-12-manual-practico-research]]'
  - '[[2026-04-12-manual-practico-plan]]'
  - '[[2026-04-12-trilingual-i18n-adr]]'
---

# `manual-practico` adr: structured trilingual AEAT handbook corpus + v1 schema-first delivery | (**status:** `accepted`)

## Problem Statement

Issue `#25` requires ingesting the AEAT *Manual práctico de Renta* and
*Manual práctico de IVA* into a structured, trilingual, queryable corpus
the rest of the project can reason against. Every modelo the project
will eventually file is explained inside the handbook, and every
downstream issue (casilla DB `#23`, schema extractor `#9`, self-healing
sync `#11`, any filing module) is drastically easier once the handbook
is structured. The handbook is the *de facto* regulation — more legally
precise than third-party guides, more readable than the BOE orders,
more current than any community resource. A coherent schema and loader
for it is load-bearing infrastructure.

Two structural constraints collide inside the original `#25` scope:

1. Every committed record must carry `reviewed_by` and `reviewed_at`
   populated by a real human; the `aeat manual verify` CLI must reject
   records lacking these fields. LLM output is a draft accelerant,
   never the source of truth.
2. Rule extraction, chapter-tree extraction, and translation may use the
   canonical `cadrumo.adapters.outbound.llm` boundary, but generated output is
   always draft material. An autonomous run cannot sign reviewer metadata or
   promote generated content without a real human review.

This ADR resolves that collision by making schema, loader, verified source
manifests, and the human review gate authoritative. Extraction and translation
may ship only as complete integrations backed by the real provider boundary
and a real human reviewer; placeholder command paths are not an accepted
delivery mechanism.

## Considerations

### Scope partition

The original `#25` deliverable has three layers:

- **Layer A — structure**: schema types, loader, query API, error
  hierarchy, deterministic rule-id generator, settings, and verified CLI
  operations. Dependencies resolve through the canonical public resource,
  LLM, and modelo contracts. This layer does not depend on generated content.
- **Layer B — raw corpus**: fetched source PDFs, sha256-verified
  `manifest.json` per manual part, git-ignored PDF blobs (binary policy
  is `#17`'s). No dependency on LLM output or human review.
- **Layer C — structured content**: chapter trees, per-section rule
  extractions, trilingual translations for the first three Renta 2025
  Parte 1 chapters and one IVA 2025 chapter. Hard dependency on `#21`
  LLM client and on a human reviewer.

Layer A and Layer B are delivered in this PR. Layer C is explicitly
deferred to follow-up issues (one per chapter or chapter cluster) that
run after `#21` merges and that land with a real `reviewed_by` on every
record.

### Pydantic v2 mandate

Reinforced on `#25` itself: every record, every manifest, every fixture
must be a strict pydantic v2 model. Closed catalogues are
`enum.StrEnum`. Internal-only value objects may remain plain dataclasses,
but `cadrumo.domain.manuals`' public surface exposes pydantic models exclusively.
No bare `dict[str, Any]` in public signatures or persisted files. Where
frozen is compatible with the usage, `ConfigDict(strict=True,
frozen=True)` is used; where the loader needs to reshape a field during
validation, strict mode is retained and frozen is relaxed.

### Review contract

`aeat manual verify` enforces a hard review gate. It rejects any
`Manual`, `Section`, or `Rule` record missing `reviewed_by` or
`reviewed_at`. The gate is controlled by
`CADRUMO_MANUALS_REVIEW_REQUIRED` which defaults to `true`. Setting the
flag to `false` downgrades the rejection to a warning but is never the
default and is never the CI default. This is the structural guarantee
that draft LLM output cannot land in the committed corpus.

### Dependency authority

`cadrumo.domain.manuals` consumes resources, LLM execution, translation, and
modelo identity only through their canonical public package contracts. It does
not define substitute implementations or duplicate identifiers. Persisted
manual records use the canonical modelo identity vocabulary and validation
owned by `cadrumo.domain.modelos`.

### Primary structuring surface (PDF vs HTML)

Decision deferred. This PR does not parse a handbook body; it only
downloads the PDF and writes a manifest. The follow-up issue that
introduces the chapter-tree extraction will decide whether PDF-first
or HTML-mirror-first is the primary structuring surface. Research
findings on `pdfplumber`, `pypdf`, `PyMuPDF`, `unstructured`, and the
HTML mirror shape are recorded in the research artefact and are not
acted on here.

### Storage layout

Directory shape under `corpus/manuals/` is as laid out in `#25`:

```
corpus/manuals/
  renta/
    2025/
      parte1/
        source.pdf          # git-ignored; materialised by `aeat manual fetch`
        manifest.json       # committed; sha256 + source URL + fetched_at
        structure/          # empty in v1; populated by follow-ups
      parte2-deducciones-autonomicas/
        source.pdf          # git-ignored
        manifest.json
  iva/
    2025/
      source.pdf            # git-ignored
      manifest.json
```

The Renta split is honoured at the directory level so each part is
independently fetchable, hashable, and reviewable. IVA is a single
volume and keeps the flat shape. Rule files, section files, and the
chapter tree live under `structure/` and are not populated in this PR.

### Rule identifiers

Rule identifiers are deterministic and stable across extraction runs.
The generator produces `{manual_id}-{year}-{part}-{chapter_id}-{section_
id}-rule{ordinal:04d}` in lowercase kebab case; the `SINGLE` part
variant collapses the `-single-` segment. Deterministic generation is
tested directly; the v1 PR does not produce real rule records but the
generator is covered by colocated unit tests so the contract is locked
before any follow-up lands structured content.

## Constraints

- Python `>=3.13`. All new code under `src/cadrumo/`. Public API
  discipline: callers import from `cadrumo.domain.manuals` only.
- No new runtime dependencies beyond what is already in
  `pyproject.toml`. `httpx`, `pydantic`, `pydantic-settings`, and
  `typer` cover the entire v1 implementation surface. PDF-parsing
  libraries are deferred until the follow-up that actually needs them.
- Cross-package dependencies are imported from their canonical public facades;
  private submodule reaches and parallel implementations are prohibited.
- Offline tests exercise real schema, loader, verification, manifest, and
  filesystem behavior. Provider-backed verification is an explicit opt-in
  surface and failures remain failures when it is enabled.
- `just lint && just typecheck && just test && just hooks` must be
  green on Windows before the PR opens.
- `tests/test_config.py` must stay green: every new `Settings` field
  must have a matching `.env.example` entry.
- Feature branches currently in flight (`#6`, `#7`, `#8`, `#10`, `#13`,
  `#14`, `#15`, `#17`, `#21`, `#24`) must not have their territory
  touched by this PR.

## Implementation

The implementation is laid out in detail by the companion plan
(`2026-04-12-manual-practico-plan`). High-level slices, in the order
they will be executed:

1. **Schema package** under `src/cadrumo/domain/manuals/_schema.py` containing
   `ManualId`, `ManualPart`, `RuleKind` (`enum.StrEnum`), and the
   pydantic v2 strict models `LLMProvenance`, `SectionSource`,
   `RuleSource`, `Paragraph`, `Rule`, `SectionRef`, `Section`,
   `Chapter`, and `Manual`. Every required-review record exposes
   `reviewed_by: str` and `reviewed_at: date`. Every translatable field
   uses `cadrumo.core.i18n.Translatable`.
2. **Dependency boundaries** bind directly to the canonical public resource,
   LLM, translation, and modelo surfaces. No substitute module or duplicate
   authority is part of this package.
3. **Errors** under `src/cadrumo/domain/manuals/errors.py` exposing
   `ManualError(CadrumoError)`, `ManualParseError(ManualError)`,
   `RuleExtractionError(ManualError)`,
   `ManualNotFoundError(ManualError)`, and
   `ManualReviewRequiredError(ManualError)`.
4. **IDs** under `src/cadrumo/domain/manuals/_ids.py` exposing
   `generate_rule_id(manual_id, year, part, chapter_id, section_id,
   ordinal) -> str`.
5. **Loader** under `src/cadrumo/domain/manuals/_loader.py` exposing
   `load_manual(manual_id, year, part=SINGLE) -> Manual` and
   `ManualCatalogue` plus `find_rules(catalogue, *, casilla_id=None,
   kind=None, lang=None) -> Iterator[Rule]`. The loader reads from the
   directory hierarchy above, walks the chapter tree, and constructs
   strict pydantic models from committed JSON files.
6. **Verification** under `src/cadrumo/domain/manuals/_verify.py` exposing
   `verify_manual_dir(path, *, review_required=True) ->
   VerificationReport`. The report is a pydantic model; the function
   walks the directory, validates every JSON file against the schema,
   and records dangling cross-references and missing reviewer fields.
7. **Fetch + manifest** under `src/cadrumo/domain/manuals/_fetch.py` exposing
   `fetch_manual_part(manual_id, year, part, *, dest, settings) ->
   FetchedManualPart`. Uses `httpx` synchronously, streams the PDF,
   computes sha256, writes `manifest.json`, and returns a strict
   pydantic model describing the fetched file. A `PartSpec` table
   (`cadrumo.domain.manuals._fetch.PART_SPECS`) hard-codes the verified AEAT
   URLs for the three v1 parts.
8. **Public `__init__.py`** under `src/cadrumo/domain/manuals/__init__.py`
   re-exports: `Manual`, `Chapter`, `Section`, `SectionRef`, `Rule`,
   `Paragraph`, `LLMProvenance`, `SectionSource`, `RuleSource`,
   `ManualCatalogue`, `ManualId`, `ManualPart`, `RuleKind`,
   `load_manual`, `find_rules`, `generate_rule_id`,
   `verify_manual_dir`, `fetch_manual_part`, and the error hierarchy.
9. **CLI** under `src/cadrumo/entrypoints/cli/manual.py` exposes the fully
   implemented `fetch`, `verify`, `list`, and `show` operations. Structuring,
   rule extraction, and translation commands are registered only when they
   have a complete provider-backed implementation and preserve the mandatory
   human review gate. A command that exists only to report unfinished work is
   not part of the accepted surface.
10. **Settings** extends `cadrumo.core.config.Settings` with `aeat_manuals_
    root: Path = Field(default=PROJECT_ROOT / "corpus" / "manuals", ...)`
    and `cadrumo_manuals_review_required: bool = Field(default=True, ...)`.
    Matching entries land in `env/.env.example`.
11. **Unit tests** colocated under `src/cadrumo/domain/manuals/`: one per module
    under test. Coverage: loader round-trip on a temp-directory fixture,
    malformed-record rejection, cross-reference validator, trilingual
    completeness, deterministic rule ID, verify rejects unreviewed,
    fetch manifest model rejects bad sha256, settings alignment.
12. **Raw PDFs + manifests**: `aeat manual fetch --manual renta --year
    2025 --part parte1` (and the two siblings) is run once locally to
    materialise the three PDFs and their manifests. The manifests are
    committed; the PDFs are git-ignored via a new
    `corpus/manuals/**/source.pdf` entry in `.gitignore`.
13. **Vault artefacts**: research (landed), ADR (this doc), plan,
    exec steps, code-review report.

## Rationale

Why this shape over the alternatives:

- **Why scope-reduce to Layer A + Layer B rather than fabricate reviewer
  metadata.** Fabricated `reviewed_by` strings would silently poison
  the corpus with LLM drafts masquerading as vetted content. The verify
  CLI is specifically designed to reject this, and the code-review step
  will reject any attempt to soften the gate. The only honest
  autonomous delivery is one that does not touch Layer C.
- **Why land the schema now rather than wait for `#21`.** Every sibling
  issue — casilla DB, schema extractor, self-healing sync, filing
  modules — benefits from a stable, strict schema for the handbook even
  if the structured content is empty. Locking the shape early also
  forces follow-ups to respect the review gate; they cannot bypass it
  by landing ad-hoc JSON.
- **Why canonical public dependencies.** Manual ingestion is legal-source
  infrastructure. It must use the same resource, modelo, and LLM authorities
  as the rest of the codebase so there is one behavior to review and no
  alternate path that can bypass provenance or review enforcement.
- **Why `httpx` for fetching rather than `pdfplumber`/`pypdf`.** The
  v1 fetcher only needs to stream a PDF and sha256 it; it does not
  parse the body. `httpx` is already a dependency. Adding a PDF-parser
  dependency for work that does not happen until a follow-up violates
  the "no speculative dependencies" rule.
- **Why git-ignore the raw PDFs rather than commit them.** `#17` owns
  the raw-binary policy and will land either LFS or an alternative
  binary strategy on its own schedule. Committing ~60 MB of PDF blobs
  from this PR pre-empts that decision and pollutes the repo. The
  sha256 + URL + fetched_at manifest is the authoritative contract;
  the `fetch` CLI re-materialises the blobs on demand and verifies.
- **Why deterministic rule IDs even in v1.** The ID contract must be
  locked before any follow-up lands real rule records, otherwise early
  extractions will collide with late ones. Deterministic generation +
  a colocated unit test locks it today.
- **Why strict pydantic + frozen where possible.** The `#25` record
  types are loaded from disk, passed through the query API, and
  consumed by downstream sibling issues. Mutability at the boundary
  would let a caller accidentally mutate loaded `Chapter` instances
  and corrupt cached catalogue state. Freezing at the boundary is
  cheap and safe.

## Consequences

### Positive

- Schema and loader are unblocked for downstream consumers (casilla DB,
  schema extractor, sync diff, filing modules) without waiting for
  `#21` or a full manual review cycle.
- The review gate is structurally enforced by the verify CLI and by
  the required `reviewed_by`/`reviewed_at` fields on every record.
- Layer C follow-ups can land one chapter at a time, each with a real
  human review, without re-opening the schema discussion.
- Zero new runtime dependencies. Zero modifications to sibling branch
  territory. Zero modifications to pyproject pytest config (`#15`'s
  territory).

### Negative / to-watch

- The PR does not deliver on the original `#25` acceptance criterion
  for Layer C (first three Renta chapters + one IVA chapter, fully
  extracted, translated, reviewed). Follow-up issues must explicitly
  track that work with a real human reviewer. The deferral is
  documented here and called out in the PR body.
- Structuring, extraction, and translation remain outside the accepted CLI
  surface until their complete implementations are grounded in the canonical
  provider and resource contracts and retain human review.
- The raw PDFs are git-ignored. A fresh clone needs to run `aeat
  manual fetch --manual renta --year 2025 --part parte1` (and
  siblings) to materialise the blobs. The CLI verifies the resulting
  PDFs against the committed manifest sha256, so tampering is
  detectable.
- Fetching uses the canonical resource-fetch boundary and preserves the
  committed URL, content hash, byte length, and retrieval timestamp. A second
  manual-specific network path is prohibited.
