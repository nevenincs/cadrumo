---
tags:
  - "#exec"
  - "#normatives"
date: 2026-04-12
modified: '2026-04-12'
related:
  - "[[2026-04-12-normatives-plan]]"
  - "[[2026-04-12-normatives-adr]]"
  - "[[2026-04-12-normatives-research]]"
---

# normatives phase-1 implementation step record

## Scope

Deliver the full v1 of `aeat.domain.normatives` as approved in the plan: strict
pydantic v2 schema, file-backed loader, lookup helpers, citation
renderer, verify pipeline, CLI sub-app, settings alignment, seven
hand-reviewed corpus files, and colocated unit tests.

## Changes landed

### New subpackage `src/aeat/domain/normatives/`

- `errors.py` — `NormativeError`, `NormativeParseError`,
  `NormativeNotFoundError` inheriting from `aeat.core.errors.AeatError`.
- `_schema.py` — strict pydantic v2 types: `NormativeKind` (StrEnum),
  `Articulo`, `NormativeReference`, `NormativeCatalogue`,
  `VerificationIssue`, `VerificationReport`. All persisted records
  use `ConfigDict(strict=True, frozen=True, extra="forbid")`. Aggregate
  `NormativeCatalogue` is strict + mutable (documented rationale:
  incremental population by the loader; individual records remain
  frozen). Model validators enforce authoritative `es` translations,
  article `numero` uniqueness per reference, and article permalink /
  boe_id alignment.
- `_loader.py` — `load_catalogue()` walks the corpus root, parses
  every `<id>.json`, and returns a fully-validated aggregate. Uses
  `aeat.core.logging.get_logger(__name__)` and `aeat.core.config.load_settings`.
- `_lookup.py` — `find_reference`, `find_articulo`. Both raise
  `NormativeNotFoundError` on miss.
- `_cite.py` — `short_title(reference)` and `cite(reference,
  articulo)` produce the canonical citation
  *`"Ley 35/2006, art. 32 (BOE-A-2006-20764)"`*.
- `_verify.py` — `verify_catalogue` aggregate verifier returning a
  `VerificationReport`; `raise_on_errors` upgrades the report to a
  `NormativeError`.
- `__init__.py` — public surface + lazy `NORMATIVE_CATALOGUE`
  singleton. `__all__` lists every re-exported name.

### Corpus `corpus/normatives/`

Seven hand-reviewed JSON files, each cross-checked against the BOE
consolidated-text URL during the research phase:

- `ley-35-2006.json` — BOE-A-2006-20764 (IRPF), arts. 27, 28, 30, 31,
  32, 99.
- `rd-439-2007.json` — BOE-A-2007-6820 (Reglamento IRPF), arts. 80,
  95, 109, 110.
- `ley-37-1992.json` — BOE-A-1992-28740 (IVA), arts. 4, 90, 91, 164.
- `rd-1624-1992.json` — BOE-A-1992-28925 (Reglamento IVA), art. 71.
- `ley-58-2003.json` — BOE-A-2003-23186 (LGT), arts. 27, 29, 66.
- `rd-1065-2007.json` — BOE-A-2007-15984 (Reglamento gestión), art. 30.
- `orden-hac-242-2025.json` — BOE-A-2025-5049 (Orden anual IRPF 2024),
  apartado primero.

### CLI `src/aeat/entrypoints/cli/normatives.py`

Typer sub-app with `list [--tag TAG]`, `show <id>`, and `verify`.
Registered in `src/aeat/entrypoints/cli/__init__.py` as `aeat normatives`.

### Settings `src/aeat/config.py` + `env/.env.example`

Additive `aeat_normatives_root: Path` with
`PROJECT_ROOT / "corpus" / "normatives"` default, documented in
`env/.env.example` under a new `# -- Normatives corpus (#45) --`
section. Picked up automatically by `tests/test_config.py`.

### Tests (colocated, unit-only)

- `test_schema.py` — 8 tests covering happy paths, missing-es
  rejection, duplicate articulo rejection, permalink mismatch,
  `extra="forbid"` drift lock, frozen invariant.
- `test_loader.py` — 6 tests covering happy path, missing root,
  malformed JSON, schema violation, duplicate ids, roundtrip.
- `test_lookup_and_cite.py` — 7 tests covering lookup hit/miss
  and canonical citation stability.
- `test_verify.py` — 5 tests covering real-corpus load + verify +
  citation rendering, plus a synthetic dirty-report raise test.

No mocks, no patches, no fakes, no stubs. All tests carry
`@pytest.mark.unit`. No live tests.

## Verification

- `just lint` — ruff clean.
- `just typecheck` — ty clean, no new `type: ignore` comments (the
  single `type: ignore[override]` on `NormativeCatalogue.__iter__`
  mirrors the existing pattern in `aeat.domain.manuals._schema`).
- `just test` — 408 passed, 1 skipped, 15 deselected.
- `just hooks` — all prek hooks passed.

## Code review

Reviewed by the `vaultspec-code-reviewer` persona. Verdict: APPROVE.
Three LOW nits were raised: one was resolved in place by switching the
test helper to `Settings.model_validate`; the other two (a broad
`except Exception` in the loader that mirrors `aeat.domain.manuals._loader`
and the `__iter__` override type ignore that also mirrors
`aeat.domain.manuals._schema`) were retained deliberately to keep the two
subpackages stylistically consistent on `main`.

## Out of scope (tracked)

- Full-text mirroring of any article body.
- Historical-revision tracking.
- Autonomic (Catalonian / Basque / Galician) normatives.
- Rewire of `aeat.domain.manuals`, `aeat.domain.modelos`, or `aeat.domain.casillas` to cite
  normatives by id.
