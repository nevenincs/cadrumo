---
tags:
  - "#adr"
  - "#normatives"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-normatives-research]]"
  - "[[2026-04-12-normatives-plan]]"
  - "[[2026-04-12-manual-practico-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
  - "[[2026-04-12-base-module-structure-adr]]"
---

# `normatives` adr: link-only typed catalogue of spanish tax normatives | (**status:** `accepted`)

## Problem Statement

Issue `#45` asks for a machine-readable catalogue of the Spanish tax
normatives that govern the autónomo regime. The project's casilla DB,
rule extractor, deadline engine, and filing reports all need to emit
citations of the form *"Ley 35/2006, art. 32.1 (BOE-A-2006-20764)"*.
Today those citations are free-text strings; no validator can check
them, no renderer can link them, no regression test can pin them. A
typed, strictly-validated catalogue closes the gap.

Three structural questions collide inside `#45`:

1. **Mirror or link?** Should the project mirror the full text of
   every in-scope law, or link to the BOE's consolidated texts?
2. **Revisions?** Should the catalogue track the full amendment
   history of every law, or always resolve to the consolidated
   (currently-in-force) text?
3. **Review gate?** Who guarantees that a committed record is
   correct, and how does CI prevent drift?

This ADR resolves all three.

## Considerations

### Link-only (no full-text mirroring) for v1

The BOE publishes a stable, canonical consolidated text for every law
at `https://www.boe.es/buscar/act.php?id=BOE-A-YYYY-NNNNN`. The text
is updated in place every time an amendment passes, and article-level
anchors (`#a32`, `#a27bis`, `#dt-1`) resolve deterministically. The
seven in-scope normatives total ~3,000 printed pages.

Mirroring the bodies inside the repo would:

- bloat every PR diff adjacent to `corpus/normatives/`;
- require a continuous sync job to stay honest against BOE amendments;
- step into the grey area of verbatim re-publication;
- deliver ~zero value beyond the canonical link for v1 consumers
  (every downstream user cares about the citation and a human-
  followable URL, not a body blob).

v1 therefore ships **link-only**. Every record carries
`boe_url: AnyHttpUrl` and `boe_id: str` for the normative as a whole,
and every codified `Articulo` carries `permalink: AnyHttpUrl`. If a
future use case demands article bodies, the schema tolerates additive
fields and a follow-up PR can land a body column without reshuffling
the existing records.

### Always resolve to the consolidated text

The catalogue is a pointer to *the law as it applies today*. It does
not model historical revisions. When a casilla rule needs to reference
a specific past state of an article, that is a different feature with
its own schema (likely a `VigenciaReference` wrapper). The explicit
non-goal keeps v1 small and keeps the guarantee simple: every `cite(...)`
call returns the currently-in-force citation.

### In-repo JSON as the storage surface

The catalogue lives at `corpus/normatives/<id>.json`, one file per
normative. JSON is chosen for:

- diff friendliness (one file per normative keeps PR diffs surgical);
- reviewability (hand-review of legal content is non-negotiable;
  JSON is human-readable without tooling);
- loader symmetry (`aeat.domain.manuals` already uses the same shape under
  `corpus/manuals/`; the loader idiom carries over intact);
- tool independence (no database, no external service, no network
  round-trip to verify a citation).

The directory is sibling to `corpus/manuals/` and coexists with
whatever `#17` lands for the corpus root. The root is configurable
via `AEAT_NORMATIVES_ROOT` (default `<repo>/corpus/normatives`).

### Hand-review before commit

Every committed record carries `reviewed_by` and `last_reviewed_at`
fields. A reviewer opens the JSON file, cross-checks the title, the
BOE-A identifier, the publication date, and every article's permalink
against the live BOE consolidated text, and only then commits the
record. The `aeat normatives verify` CLI is a belt-and-braces gate that
validates schema conformance and article cross-references; it is not
a substitute for human review, and it does not fetch the BOE to
verify content — drift from the BOE is tracked by a future sync job,
not by v1 `verify`.

### Pydantic v2 strict everywhere (mandate)

Per the project-wide pydantic v2 mandate reinforced on `#45`, every
record in `aeat.domain.normatives` — `NormativeKind`, `NormativeReference`,
`Articulo`, `NormativeCatalogue` — is a strict pydantic v2 model with
`ConfigDict(strict=True, frozen=True, extra="forbid")`. Closed
catalogues are `enum.StrEnum`. No dataclasses for boundary-crossing
types. No bare `dict[str, Any]` in public signatures or persisted
files. The `NormativeCatalogue` aggregate is the single exception
to `frozen=True` so the loader can populate it incrementally; the
individual `NormativeReference` records it holds are frozen, so
callers cannot corrupt loaded records in place.

### Trilingual fields (leverage `#20`)

Every free-text field that surfaces to users is a
`Translatable` (nested dict: `es`, `en`, `hu`) imported directly
from `aeat.core.i18n` — which is already on `main` via `#20`. Spanish is
authoritative for AEAT domain terminology; Hungarian is the target
output language; English is the authoritative engineering language.
The schema enforces presence of the authoritative `es` key on every
title and summary at load time.

### Public API discipline

`aeat.domain.normatives` is a new sibling subpackage under `src/aeat/`. It
re-exports a tight surface from its `__init__.py`:

- types: `NormativeKind`, `Articulo`, `NormativeReference`,
  `NormativeCatalogue`;
- loader: `load_catalogue`;
- query: `find_articulo`;
- renderer: `cite`;
- module-level singleton: `NORMATIVE_CATALOGUE`;
- errors: `NormativeError`, `NormativeParseError`,
  `NormativeNotFoundError`.

Callers from other subpackages must import only from `aeat.domain.normatives`
— never from `aeat.domain.normatives._schema`, `._loader`, etc. This mirrors
the `aeat.domain.manuals` public-surface discipline.

### Stub policy for in-flight siblings

`#17` corpus-rulebook is in-flight and will eventually own `corpus/`
plus `src/aeat/corpus/`. `aeat.domain.normatives` **does not import**
`aeat.corpus` on this branch. The corpus root is resolved from a
settings Path default (`AEAT_NORMATIVES_ROOT`) with no dependency on
the unwritten subpackage. When `#17` lands, the constant can be
rewired to delegate to `aeat.corpus` via a one-line change in
`_loader.py` with no knock-on effects on downstream consumers.

Similarly, `aeat.domain.manuals` rules will eventually cite normatives by
id. That rewire is a follow-up to `#25`, not v1 of `#45`, and does
not require any change to the `aeat.domain.normatives` surface.

## Constraints

- Python `>=3.13`. All new code under `src/aeat/`. Public API
  discipline.
- No new runtime dependencies. `pydantic`, `pydantic-settings`,
  `typer`, and the in-tree `aeat.core.i18n` cover the entire surface.
- Every committed JSON file references a real BOE consolidated-text
  URL and a real BOE-A identifier, verified by hand against the BOE
  website at commit time.
- Every test is `@pytest.mark.unit`; no live tests; no mocks, fakes,
  patches, or stubs anywhere.

## Decision

Deliver v1 of `aeat.domain.normatives` as:

1. **Schema**: strict pydantic v2 types for `NormativeKind`,
   `Articulo`, `NormativeReference`, `NormativeCatalogue`. All
   boundary-crossing types are pydantic models; all closed
   catalogues are `enum.StrEnum`. Authoritative `es` translations
   enforced at load time.
2. **Errors**: `NormativeError` (+ `NormativeParseError`,
   `NormativeNotFoundError`) inheriting from `aeat.core.errors.AeatError`.
3. **Loader**: `load_catalogue()` reads every
   `corpus/normatives/<id>.json` into a `NormativeCatalogue`
   keyed by stable id. The aggregate validates id uniqueness and
   permalink shape. A module-level `NORMATIVE_CATALOGUE` singleton
   is exposed for callers that want the loaded state without
   plumbing a Settings instance.
4. **Query helpers**: `find_articulo(id, numero)` returns an
   `Articulo` or raises `NormativeNotFoundError`; `cite(reference,
   articulo)` produces the canonical string
   *`"{short_title}, art. {numero} ({boe_id})"`*.
5. **Storage**: `corpus/normatives/<id>.json`, one file per
   normative, hand-reviewed before commit. Seven files ship in v1:
   Ley 35/2006, RD 439/2007, Ley 37/1992, RD 1624/1992, Ley 58/2003,
   RD 1065/2007, Orden HAC/242/2025.
6. **CLI**: `aeat normatives list [--tag ...]`, `aeat normatives
   show <id>`, `aeat normatives verify`, wired into the existing
   `aeat.entrypoints.cli` root app.
7. **Settings**: additive `AEAT_NORMATIVES_ROOT: Path` in
   `src/aeat/config.py`, documented in `env/.env.example`,
   enforced by `tests/test_config.py`.
8. **Tests**: colocated unit tests inside
   `src/aeat/domain/normatives/` exercising the loader, the lookup
   helpers, the citation formatter, the verify report, and a
   schema upgrade round-trip. No live tests. No mocks.

## Consequences

- Downstream subpackages gain a typed legal anchor for every
  citation they emit. Casilla rules, deadline obligations, filing
  reports, and LLM-drafted manual rules can all rewire their
  free-text citations into `NormativeReference` lookups at their own
  pace.
- The corpus grows by one human-reviewed file per new normative.
  Adding the next annual Orden Ministerial is a single PR.
- When full-text mirroring becomes a real requirement, the schema
  absorbs a body field additively without touching the loader
  contract or existing records.
- The explicit "consolidated-text always" rule means the catalogue
  cannot answer "what did art. 32 say in 2019?". That is a known
  non-goal and is documented in the research artefact.
