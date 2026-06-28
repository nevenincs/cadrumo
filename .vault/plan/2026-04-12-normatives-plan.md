---
tags:
  - "#plan"
  - "#normatives"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-normatives-research]]"
  - "[[2026-04-12-normatives-adr]]"
  - "[[2026-04-12-manual-practico-plan]]"
---

# normatives plan: phased delivery of `aeat.domain.normatives` v1

**Plan review:** auto-approved by the executing agent after cross-checking
against the approved ADR and issue `#45`. Every scope item is either
covered by a phase below or listed in the explicit non-goals. No open
questions remain blocking execution. Execution proceeds directly.

## Phase 1 — schema, errors, loader

Deliverables inside `src/aeat/domain/normatives/`:

- `errors.py` — `NormativeError`, `NormativeParseError`,
  `NormativeNotFoundError`, all inheriting from
  `aeat.core.errors.AeatError`.
- `_schema.py` — strict pydantic v2 types:
  - `NormativeKind(StrEnum)`: `LEY`, `REAL_DECRETO`,
    `ORDEN_MINISTERIAL`, `REAL_DECRETO_LEY`.
  - `_StableId` constrained string (kebab-case, lowercase, max 128).
  - `_Reviewer` constrained string.
  - `Articulo` frozen `BaseModel` with
    `numero`, `titulo: Translatable`, `summary: Translatable`,
    `permalink: AnyHttpUrl`, `notes: str = ""`.
    Model validator enforces authoritative `es` on `titulo` /
    `summary`.
  - `NormativeReference` frozen `BaseModel` with the full field set
    from the issue. Model validators enforce:
    - `id` uniqueness is the catalogue's job (validated at the
      aggregate level);
    - every `Articulo.numero` within a single reference is unique;
    - `titulo` carries the authoritative `es` key.
  - `NormativeCatalogue` strict-but-mutable `BaseModel` wrapping
    `dict[str, NormativeReference]`. Model validator enforces unique
    ids and cross-checks that each `Articulo.permalink` starts with
    the parent `boe_url` (same BOE-A page, different fragment).
- `_loader.py` — `load_catalogue()` walks
  `AEAT_NORMATIVES_ROOT`, parses every `*.json`, validates through
  `NormativeReference.model_validate_json`, aggregates, and returns
  a `NormativeCatalogue`. Errors are `NormativeParseError`. Missing
  root directory is `NormativeNotFoundError`.
- `_lookup.py` — `find_articulo(catalogue, ref_id, numero)` raising
  `NormativeNotFoundError` on miss. Overload that accepts the
  `NORMATIVE_CATALOGUE` singleton implicitly for convenience.
- `_cite.py` — `cite(reference, articulo) -> str` producing the
  canonical form *`"{short_title}, art. {numero} ({boe_id})"`*.
- `_verify.py` — `verify_catalogue()` returning a
  `VerificationReport` strict pydantic v2 model (one
  `VerificationIssue` per finding); `raise_on_errors(report)`.
- `__init__.py` — public re-exports + module-level
  `NORMATIVE_CATALOGUE` lazy singleton (computed on first access,
  cached).

## Phase 2 — settings alignment

- Additive `aeat_normatives_root: Path` in
  `src/aeat/config.py` with a `PROJECT_ROOT / "corpus" / "normatives"`
  default and a clear docstring.
- Matching `AEAT_NORMATIVES_ROOT=corpus/normatives` line in
  `env/.env.example`, clearly sectioned under a `# -- Normatives
  corpus (#45) --` header.
- `tests/test_config.py` picks this up automatically via
  `Settings.env_var_names()`.

## Phase 3 — corpus population

Seven hand-reviewed files under `corpus/normatives/`:

- `ley-35-2006.json` — IRPF (BOE-A-2006-20764).
- `rd-439-2007.json` — Reglamento IRPF (BOE-A-2007-6820).
- `ley-37-1992.json` — IVA (BOE-A-1992-28740).
- `rd-1624-1992.json` — Reglamento IVA (BOE-A-1992-28925).
- `ley-58-2003.json` — LGT (BOE-A-2003-23186).
- `rd-1065-2007.json` — Reglamento gestión/inspección (BOE-A-2007-15984).
- `orden-hac-242-2025.json` — modelos IRPF 2024 (BOE-A-2025-5049).

Every file carries:

- the verified BOE consolidated-text URL;
- the verified BOE-A identifier;
- the canonical Spanish title with an English engineering paraphrase
  and a Hungarian user-facing summary;
- the v1 article set listed in the research artefact;
- `reviewed_by: "wgergely"` and `last_reviewed_at: 2026-04-12`;
- tags grouping the normative by tax domain.

Every article permalink uses the fragment form
`.../act.php?id={boe_id}#{anchor}`.

## Phase 4 — CLI wiring

- `src/aeat/entrypoints/cli/normatives.py` — typer sub-app with three commands:
  - `list [--tag TAG]` — renders a `rich.table.Table` of id / kind /
    number / tags / reviewer.
  - `show ID` — prints the full metadata of one reference plus its
    article index.
  - `verify` — runs `verify_catalogue` and exits non-zero on errors.
- `src/aeat/entrypoints/cli/__init__.py` — register the sub-app under
  `aeat normatives`.

## Phase 5 — tests (colocated, unit only)

- `test_schema.py` — happy path + rejection of missing `es`,
  duplicate article `numero`, bad permalink.
- `test_loader.py` — temporary-directory fixture loads + round-trips
  a synthetic normative; corrupt file raises `NormativeParseError`;
  missing directory raises `NormativeNotFoundError`.
- `test_lookup.py` — `find_articulo` hit / miss branches.
- `test_cite.py` — canonical citation string is stable.
- `test_verify.py` — clean report + error report.
- `test_catalogue_corpus.py` — loads the real `corpus/normatives/`
  and asserts all seven ids are present, every article permalink
  matches the expected shape, and `cite` renders without raising
  for every (reference, articulo) pair.
- `test_upgrade_roundtrip.py` — an additive-field JSON with an
  unknown key is rejected by `extra="forbid"` (locks the schema
  against accidental drift).

All tests carry `@pytest.mark.unit`. No mocks, patches, fakes.

## Phase 6 — verify & ship

- `just lint && just typecheck && just test && just hooks` all green
  on Windows.
- Colocated code review per `vaultspec-code-review` with every file
  changed in scope.
- Commit on `feature/45-normatives` referencing `#45`.
- PR opened by the executing agent after review, body containing
  `Closes #45` and wiki-links to the vault artefacts.

## Non-goals (tracked)

- No full-text mirroring of any article body.
- No historical-revision tracking.
- No autonomic (Catalonian / Basque / Galician) normatives.
- No rewire of `aeat.domain.manuals`, `aeat.domain.modelos`, or `aeat.domain.casillas` to
  cite normatives by id.
- No live network tests against BOE.
