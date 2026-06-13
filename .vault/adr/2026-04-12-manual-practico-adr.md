---
tags:
  - '#adr'
  - '#manual-practico'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-manual-practico-research]]'
  - '[[2026-04-12-manual-practico-plan]]'
  - '[[2026-04-12-trilingual-i18n-adr]]'
  - '[[2026-04-12-base-module-structure-adr]]'
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
2. The rule-extraction, chapter-tree extraction, and translation phases
   depend on `aeat.adapters.outbound.llm` (`#21`), which has not landed yet and is stubbed
   via `Protocol` on this branch. An autonomous run on `#25` therefore
   cannot honestly produce real extracted content, and cannot sign
   reviewer metadata without fabricating it.

This ADR resolves that collision by reducing the v1 scope to the
schema, loader, CLI skeleton, settings, and real raw-PDF manifests, and
deferring the extraction / translation phases to follow-up issues that
run with a live human reviewer after `#21` lands.

## Considerations

### Scope partition

The original `#25` deliverable has three layers:

- **Layer A — structure**: schema types, loader, query API, error
  hierarchy, deterministic rule-id generator, settings, CLI skeleton,
  Protocol stubs for `aeat.corpus`/`aeat.adapters.outbound.llm`/`aeat.domain.modelos`, unit tests.
  No dependency on LLM output or human review.
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
but `aeat.domain.manuals`' public surface exposes pydantic models exclusively.
No bare `dict[str, Any]` in public signatures or persisted files. Where
frozen is compatible with the usage, `ConfigDict(strict=True,
frozen=True)` is used; where the loader needs to reshape a field during
validation, strict mode is retained and frozen is relaxed.

### Review contract

`aeat manual verify` enforces a hard review gate. It rejects any
`Manual`, `Section`, or `Rule` record missing `reviewed_by` or
`reviewed_at`. The gate is controlled by
`AEAT_MANUALS_REVIEW_REQUIRED` which defaults to `true`. Setting the
flag to `false` downgrades the rejection to a warning but is never the
default and is never the CI default. This is the structural guarantee
that draft LLM output cannot land in the committed corpus.

### Dependency-graph stubbing

On this branch neither `aeat.adapters.outbound.llm` nor `aeat.corpus.Fetcher` exists. To
keep `aeat.domain.manuals` compiling and testable today without reaching into
sibling branch territory, the `aeat.domain.manuals._stubs` module declares
three `typing.Protocol`s:

- `LLMClientProtocol` — matches `#21`'s planned `LLMClient.complete`
  surface.
- `TranslatorProtocol` / `BulkTranslatorProtocol` — match `#21`'s
  planned single and batch translation surfaces.
- `FetcherProtocol` — matches `#17`'s planned `Fetcher.fetch` surface.

Modelo identifiers are accepted as string fields validated against the
regex `^MODELO_[0-9]{3}(?::[0-9A-Z_]+)?$`, not imported from
`aeat.domain.modelos`. When `#6` lands, a follow-up PR replaces the string
constraint with a real `ModeloId` cross-reference.

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

- Python `>=3.13`. All new code under `src/aeat/`. Public API
  discipline: callers import from `aeat.domain.manuals` only.
- No new runtime dependencies beyond what is already in
  `pyproject.toml`. `httpx`, `pydantic`, `pydantic-settings`, and
  `typer` cover the entire v1 implementation surface. PDF-parsing
  libraries are deferred until the follow-up that actually needs them.
- No hard imports from `aeat.corpus`, `aeat.adapters.outbound.llm`, `aeat.domain.modelos`, or
  `aeat.adapters.persistence.storage`. Only `aeat.core.config`, `aeat.core.errors`, `aeat.core.logging`,
  and `aeat.core.i18n` are consumed from the wider project.
- All tests are `@pytest.mark.unit`, colocated under
  `src/aeat/domain/manuals/`. No mocks, patches, fakes, stubs, shadows, or
  skips. One opt-in `@pytest.mark.live` test is scoped but not
  implemented for v1, because it would need the real `#21` LLM client.
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

1. **Schema package** under `src/aeat/domain/manuals/_schema.py` containing
   `ManualId`, `ManualPart`, `RuleKind` (`enum.StrEnum`), and the
   pydantic v2 strict models `LLMProvenance`, `SectionSource`,
   `RuleSource`, `Paragraph`, `Rule`, `SectionRef`, `Section`,
   `Chapter`, and `Manual`. Every required-review record exposes
   `reviewed_by: str` and `reviewed_at: date`. Every translatable field
   uses `aeat.core.i18n.Translatable`.
2. **Stubs** under `src/aeat/domain/manuals/_stubs.py` with the three
   Protocols. Clearly marked `TODO(#17)`, `TODO(#21)`, `TODO(#6)`.
3. **Errors** under `src/aeat/domain/manuals/errors.py` exposing
   `ManualError(AeatError)`, `ManualParseError(ManualError)`,
   `RuleExtractionError(ManualError)`,
   `ManualNotFoundError(ManualError)`, and
   `ManualReviewRequiredError(ManualError)`.
4. **IDs** under `src/aeat/domain/manuals/_ids.py` exposing
   `generate_rule_id(manual_id, year, part, chapter_id, section_id,
   ordinal) -> str`.
5. **Loader** under `src/aeat/domain/manuals/_loader.py` exposing
   `load_manual(manual_id, year, part=SINGLE) -> Manual` and
   `ManualCatalogue` plus `find_rules(catalogue, *, casilla_id=None,
   kind=None, lang=None) -> Iterator[Rule]`. The loader reads from the
   directory hierarchy above, walks the chapter tree, and constructs
   strict pydantic models from committed JSON files.
6. **Verification** under `src/aeat/domain/manuals/_verify.py` exposing
   `verify_manual_dir(path, *, review_required=True) ->
   VerificationReport`. The report is a pydantic model; the function
   walks the directory, validates every JSON file against the schema,
   and records dangling cross-references and missing reviewer fields.
7. **Fetch + manifest** under `src/aeat/domain/manuals/_fetch.py` exposing
   `fetch_manual_part(manual_id, year, part, *, dest, settings) ->
   FetchedManualPart`. Uses `httpx` synchronously, streams the PDF,
   computes sha256, writes `manifest.json`, and returns a strict
   pydantic model describing the fetched file. A `PartSpec` table
   (`aeat.domain.manuals._fetch.PART_SPECS`) hard-codes the verified AEAT
   URLs for the three v1 parts.
8. **Public `__init__.py`** under `src/aeat/domain/manuals/__init__.py`
   re-exports: `Manual`, `Chapter`, `Section`, `SectionRef`, `Rule`,
   `Paragraph`, `LLMProvenance`, `SectionSource`, `RuleSource`,
   `ManualCatalogue`, `ManualId`, `ManualPart`, `RuleKind`,
   `load_manual`, `find_rules`, `generate_rule_id`,
   `verify_manual_dir`, `fetch_manual_part`, and the error hierarchy.
9. **CLI** under `src/aeat/entrypoints/cli/manual.py` defines a `typer.Typer`
   `app` with seven subcommands. `fetch`, `verify`, `list`, and `show`
   are fully functional. `structure`, `extract-rules`, and `translate`
   raise `RuleExtractionError("pending #21 — not yet implemented")`
   so the interface is locked but the implementation is gated on the
   LLM client landing. `src/aeat/entrypoints/cli/__init__.py` grows an
   `app.add_typer(manual_module.app, name="manual", help="...")` line.
10. **Settings** extends `aeat.core.config.Settings` with `aeat_manuals_
    root: Path = Field(default=PROJECT_ROOT / "corpus" / "manuals", ...)`
    and `aeat_manuals_review_required: bool = Field(default=True, ...)`.
    Matching entries land in `env/.env.example`.
11. **Unit tests** colocated under `src/aeat/domain/manuals/`: one per module
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
- **Why Protocol stubs rather than direct imports.** The worktree has
  confirmed `aeat.adapters.outbound.llm` does not exist yet. Directly importing would
  break the branch build and fail ty. Protocols let the schema and
  the `extract-rules`/`translate` commands declare their dependency on
  `#21` in type-checked form without reaching across the branch
  boundary. When `#21` lands, a follow-up PR replaces `LLMClientProtocol`
  with the real `LLMClient` in a single diff.
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
- `aeat manual structure`, `aeat manual extract-rules`, and `aeat
  manual translate` raise `RuleExtractionError` until `#21` lands.
  Callers must be aware the interfaces are defined but not yet
  implemented; the error message points at `#21`.
- The Protocol stubs create a small maintenance burden: when `#21`
  (and later `#17` and `#6`) lands, a follow-up PR must rebase
  `aeat.domain.manuals` onto the real surfaces. That follow-up is expected
  to be small and mechanical.
- The raw PDFs are git-ignored. A fresh clone needs to run `aeat
  manual fetch --manual renta --year 2025 --part parte1` (and
  siblings) to materialise the blobs. The CLI verifies the resulting
  PDFs against the committed manifest sha256, so tampering is
  detectable.
- The `#17` corpus fetcher is not yet available, so the v1 fetcher is
  implemented directly on top of `httpx` in `aeat.domain.manuals._fetch`.
  When `#17` lands the real `Fetcher`, a follow-up PR re-wires
  `_fetch.py` to delegate through the real fetcher and drops the
  local `httpx` usage. The `FetcherProtocol` in `_stubs.py` is the
  forcing function for that refactor.
