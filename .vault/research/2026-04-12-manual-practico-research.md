---
tags:
  - '#research'
  - '#manual-practico'
date: '2026-04-12'
modified: '2026-04-12'
related:
  - '[[2026-04-12-manual-practico-adr]]'
  - '[[2026-04-12-manual-practico-plan]]'
  - '[[2026-04-12-trilingual-i18n-adr]]'
  - '[[2026-04-12-base-module-structure-adr]]'
---

# `manual-practico` research: ingest, structure, and trilingualise the AEAT Manual práctico (Renta + IVA)

Research for issue `#25`. The goal is a structured, trilingual, queryable
corpus of the AEAT *Manual práctico* that the rest of the project can reason
against. This document captures ground-truth facts pulled directly from the
worktree and from AEAT's published handbook index, plus the constraints
imposed by sibling in-flight branches. Opinions and trade-offs are recorded
in the companion ADR.

## Findings

### 1. Source material (AEAT Sede electrónica)

AEAT publishes the *Manual práctico* every tax year on the Sede electrónica
landing page for handbooks. For 2025 (the most recent complete year) the
authoritative PDF URLs are:

- `Renta 2025 Parte 1` (general volume) —
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf`
- `Renta 2025 Parte 2 (Deducciones autonómicas)` —
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025-Deducciones-autonomicas/ManualRenta2025Parte2_es_es.pdf`
- `IVA 2025` —
  `https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/Manual_IVA_2025.pdf`

Renta is split into two parts from 2024 onward (Parte 2 is the autonómica
deductions volume). IVA remains a single volume. Each PDF is several
hundred pages of Spanish legal prose organised as chapters ("capítulos") →
sections → subsections → paragraphs, plus tables and worked examples.
Sociedades and Patrimonio also exist but are explicitly out of scope per
`#25`.

An HTML edition mirrors the PDF chapter-by-chapter at the same host. The
HTML mirror is easier to structure than the PDF (no column flow, no page
breaks in the middle of paragraphs), but it requires a chapter-by-chapter
crawl, not a single file fetch. The ADR decides which surface is the
primary structuring input for `#25`.

### 2. Repository conventions in force on this branch

Ground-truth facts collected from the worktree on `2026-04-12`:

- `src/aeat/` is the locked layout (per `#12`). Subpackages currently
  present: `auth`, `browser`, `cli`, `corpus`, `i18n`, `models`, `portals`,
  `schema`, `storage`, `sync`. `corpus`, `models`, and `storage` are empty
  stubs with no exports, safe to extend without collision. No `src/aeat/
  manuals/` subpackage exists yet.
- `aeat.core.errors` defines a single `AeatError(Exception)` root with no
  subclasses yet. New domain errors must inherit from it.
- `aeat.core.logging` exposes `get_logger(name: str) -> logging.Logger` backed
  by a `dictConfig` initialised lazily. Every module uses
  `get_logger(__name__)`.
- `aeat.core.config.Settings` is a `pydantic_settings.BaseSettings` subclass
  with 24 fields, one per `.env` variable. `tests/test_config.py` enforces
  exact alignment with `env/.env.example` in both directions, and also
  verifies `Settings()` instantiates with no env at all. New settings must
  have defaults and matching `env/.env.example` entries.
- `aeat.core.i18n` exposes `Translatable` as a `TypedDict(total=False)` with
  optional `es`, `en`, `hu` keys, plus `Language` (`StrEnum`),
  `TranslationFallback`, `get_translation`, `require_authoritative`, and a
  `TranslationError(AeatError)`. The trilingual ADR (`#20`) decided that
  Spanish is authoritative for AEAT-domain terminology and English is
  authoritative for code/docs, so manual content keyed under a Spanish
  source must satisfy `require_authoritative(..., domain="aeat")` — i.e.
  the `es` key must be present. Missing `en`/`hu` are warnings, not
  errors.
- `aeat.entrypoints.cli` is a `typer.Typer` app with the root registered at
  `aeat.entrypoints.cli:app` (`pyproject.toml [project.scripts]`). Subgroups are
  registered via `app.add_typer(sub.app, name="…", help="…")`. Existing
  subgroups: `drive`, `sheets`, `docs`, `cloud`, `oauth-client`. The
  `[tool.ruff.lint.per-file-ignores]` already waives `B008` for
  `src/aeat/entrypoints/cli/**/*.py` so `typer.Argument(...)`/`typer.Option(...)` in
  defaults is the idiomatic pattern.
- Tests are colocated inside each subpackage (Rust-style). Every test
  function is marked exactly once with `@pytest.mark.unit` or
  `@pytest.mark.live`. Default `pytest` invocation runs `-m 'not live'`.
  `tests/test_config.py` lives in the repo-level `tests/` folder, not
  colocated, because it is a cross-cutting alignment check.
- Dev loop: `just lint` (ruff check), `just fmt` (ruff format),
  `just typecheck` (ty check), `just test` (pytest default), `just test-
  live`, `just hooks` (prek). Python 3.13+. Line length 120. Ruff lint
  selects `E W F I N UP B S T20 SIM RUF`. `ty` runs with `all = "error"`.

### 3. Sibling in-flight branches (what NOT to import)

The handover prompt enumerates active sibling branches; confirming the
territory the `#25` branch must stay out of:

- `#17 corpus` (feature/17-corpus-rulebook, in progress) owns
  `src/aeat/corpus/` and the root `corpus/` directory plus the `Fetcher`
  ABC and the raw-PDF manifest schema. `#25` stores under
  `corpus/manuals/<id>/<year>/` which is a new subtree. The `Fetcher`
  surface is not yet on disk, so `#25` must stub it via a local
  `typing.Protocol`.
- `#21 llm` (feature/21-llm-client, in progress) owns `src/aeat/adapters/outbound/llm/`
  and the `LLMClient`/`Translator`/`BulkTranslator` surface. The subpackage
  does not exist on this branch yet — confirmed by the absence of
  `src/aeat/adapters/outbound/llm/` in the worktree. `#25` must stub these via local
  Protocols and cleanly fail any workflow that needs the real LLM with a
  domain error until `#21` lands.
- `#6 models` (feature/6-modelo-enum, in progress) owns `src/aeat/
  models/` and the `ModeloId` enum. Currently empty. `#25` cross-
  references casilla identifiers like `MODELO_130:01`; the validation
  contract must accept a string-typed identifier with a structural
  shape check, not a hard import from `aeat.domain.modelos`.
- `#10 storage` (PR #28, ready) owns `src/aeat/adapters/persistence/storage/`. `#25` does not
  persist through storage; its corpus is plain files on disk.
- `#15 testing` owns `[tool.pytest]` config, `conftest.py`, and
  `tests/README`. `#25` must not modify any of those.
- `#14, #13, #8, #7, #24` have no overlap with `#25`.

### 4. Pydantic v2 mandate (project-wide)

Reinforced on `#25` itself: every boundary-crossing record, every
manifest, every test fixture, every wire payload that `#25` produces or
consumes **must** be a strict pydantic v2 model. Enums are `enum.StrEnum`
for closed catalogues. No bare `dict[str, Any]` in public signatures or
persisted files. No dataclasses on the public surface. Strict mode
(`ConfigDict(strict=True, frozen=True)`) is preferred where frozen is
compatible with the usage.

### 5. PDF structuring toolchain survey

The Python ecosystem offers several well-maintained libraries for
breaking a large PDF into a chapter tree plus per-paragraph prose:

- `pdfplumber` — text + table extraction with coordinate metadata,
  mature, pure-Python on top of `pdfminer.six`. Good for paragraph
  extraction and table detection. Slower on 500-page handbooks.
- `pypdf` — lightweight reader; fine for page count and raw text but has
  no table layer and weak paragraph reconstruction.
- `PyMuPDF`/`fitz` — AGPL-licensed (a concern for this repo's Apache-2.0
  licence) but extremely fast and ships a usable paragraph + block
  extractor. Licence makes it ineligible here.
- `unstructured` — high-level chunker with heading detection. Pulls in a
  very large dependency tree (including some optional ML models). Too
  heavy for this project's current dependency budget.
- `camelot` — table-only extractor. Useful for casilla tables inside
  the handbook but not for chapter structure.

None of these are currently project dependencies. The ADR decides which
one (if any) this PR pulls in. Given the v1 scope reduction (see below),
the answer is likely **none** — this PR only needs to `httpx` a PDF and
sha256 it, which `httpx` (already present) handles alone.

### 6. LLM-assisted extraction strategies (for follow-up context)

Relevant even though the LLM phases are deferred for v1:

- **Chapter-tree extraction** is the most error-prone phase because
  mistakes propagate everywhere downstream. Best practice is a two-pass
  approach: (1) extract a draft outline from the PDF bookmarks / table
  of contents if present, (2) validate against sampled page headers.
  Always human-reviewed.
- **Rule extraction** benefits from few-shot prompting with anchor
  examples (one per `RuleKind`: obligation, computation, exemption,
  deduction, deadline, definition, example) and structured output
  constraints (JSON schema conforming to the `Rule` model). Cross-
  referenced casilla identifiers must be validated against `#23` once
  the casilla DB lands.
- **Translation** from authoritative Spanish into English + Hungarian
  is cache-friendly at the sentence level and should run via `#21`'s
  `BulkTranslator` with the glossary constraint.

All three phases are draft-only; every committed record must carry
`reviewed_by` and `reviewed_at` populated by a real human.

### 7. Human-review gate (structural)

`#25` makes `reviewed_by` and `reviewed_at` required fields on every
persisted `Manual`, `Section`, and `Rule`. The `aeat manual verify`
command must reject any record missing these fields when
`AEAT_MANUALS_REVIEW_REQUIRED=true` (the default). This is the structural
guarantee that LLM drafts cannot leak into the committed corpus without
an explicit human sign-off. It is *also* the structural reason the v1
scope must be reduced: an autonomous pipeline cannot honestly populate
`reviewed_by`.

### 8. Scope reduction for v1 (this PR)

Agreed with the operator on `2026-04-12`: this PR does **not** attempt
to extract, translate, or commit real chapter trees or rule files. Doing
so would either require a live human reviewer in the loop (incompatible
with the autonomous handover) or fabricated reviewer metadata (rejected
by the verify CLI and by the pydantic mandate). Instead, `#25` v1
delivers:

- The full `src/aeat/domain/manuals/` schema + loader + query API + error
  hierarchy + deterministic rule-id generator, grounded in strict
  pydantic v2.
- Local `Protocol` stubs for the `#17` `Fetcher`, the `#21` `LLMClient`/
  `Translator`/`BulkTranslator`, and the `#6` modelo identifiers, clearly
  marked `TODO(#17|#21|#6)` so they can be replaced on rebase.
- CLI subcommands under `src/aeat/entrypoints/cli/manual.py` with **real**
  implementations for `fetch`, `verify`, `list`, and `show`, and
  **planned-blocker** implementations for `structure`, `extract-rules`,
  and `translate` that raise a typed `RuleExtractionError` until `#21`
  lands.
- New settings `AEAT_MANUALS_ROOT` and `AEAT_MANUALS_REVIEW_REQUIRED`,
  aligned with `env/.env.example`.
- Real fetched raw PDFs + sha256-verified `manifest.json` per part for
  Renta 2025 Parte 1, Renta 2025 Parte 2, and IVA 2025. The manifests
  are committed; the raw PDFs themselves are git-ignored under
  `corpus/manuals/` because `#17` owns the raw-binary policy and will
  land either LFS or an alternative binary strategy on its own schedule.
  The `fetch` CLI re-materialises them on demand and validates sha256
  against the committed manifest.
- Unit tests (`@pytest.mark.unit`) covering the loader, the cross-
  reference validator, trilingual completeness, schema round-trip,
  deterministic IDs, and the verify-CLI rejection of unreviewed records.
  No mocks, patches, fakes, or stubs.
- Vault research (this document), ADR, plan with explicit review record,
  exec step records, and a mandatory code-review report.

Follow-up issues (not this PR) will run the structure → extract-rules →
translate phases per chapter, with a human in the loop, after `#21`
lands and the operator can sign `reviewed_by`.
