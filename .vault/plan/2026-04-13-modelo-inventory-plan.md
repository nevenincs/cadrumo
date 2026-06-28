---
name: 2026-04-13-modelo-inventory-plan
description: Implementation plan for the authoritative AEAT modelo inventory + pydantic registry under aeat.domain.modelos (#108)
type: plan
tags:
  - "#plan"
  - "#modelo-inventory"
date: 2026-04-13
modified: '2026-04-13'
related:
  - "[[2026-04-13-modelo-inventory-adr]]"
  - "[[2026-04-13-modelo-inventory-research]]"
  - "[[2026-04-12-deadline-engine-adr]]"
  - "[[2026-04-12-trilingual-i18n-adr]]"
  - "[[2026-04-12-casilla-db-adr]]"
---

# modelo-inventory plan (#108)

Date: 2026-04-13
Branch: `feature/108-modelo-inventory-catalogue`
Issue: wgergely/aeat#108

## Goal

Materialise the authoritative AEAT modelo catalogue under `src/aeat/domain/modelos/`
as a strict pydantic v2 registry covering all 20 modelos enumerated in the
research doc, wire it into the `aeat` CLI via four Typer commands
(`list`, `show`, `applicable-to`, `year-plan`), and ship a fully green
local test gate (`just lint`, `just typecheck`, `just test`, `just hooks`)
with zero mocks/skips/patches. The registry closes #108, closes #6, and
gives #77/#93 a stable `ModeloCode` import surface.

## Inputs

- ADR (authoritative): `.vault/adr/2026-04-13-modelo-inventory-adr.md`.
- Research (data): `.vault/research/2026-04-13-modelo-inventory-research.md`
  sections 3.1–3.20 (D1) and 4 (D2 matrix).
- Existing public surfaces consumed by this feature:
  - `src/aeat/domain/deadlines/__init__.py` — `DeadlineEngine`, `CALENDAR`,
    `CanonicalWindow`, `PeriodKind`, `AutonomoProfile`, `IVARegime`,
    `applies_to`, `explain`.
  - `src/aeat/core/i18n/__init__.py` — `Translatable`, `Language`,
    `require_authoritative`.
  - `src/aeat/errors.py` — `AeatError` base.
  - `src/aeat/core/logging/...` — `get_logger`.
  - `src/aeat/domain/casillas/...` — catalogue loader (used only from
    `test_casilla_cross_reference.py`).
  - `src/aeat/entrypoints/cli/__init__.py` — Typer root `app`; sub-apps wired via
    `app.add_typer(...)`.

## Constraints

- **Pydantic v2 strict/frozen** on every model. Every `ConfigDict` carries
  `strict=True`, `frozen=True`, `extra="forbid"`. No dataclasses, no bare
  dicts.
- **Enums only** for closed taxonomies (`ModeloCode`, `ModeloCategory`,
  `ModeloCadence`, `TaxpayerProfile`, `LegalCitationSource`). `StrEnum`,
  never `IntEnum`.
- **Google-style docstrings + full type hints** on every public symbol.
- **Public API discipline.** Consumers import from `aeat.domain.modelos` only;
  `_*` modules are internal. `__all__` is the ADR-locked tuple.
- **Errors.** All new errors inherit from `aeat.core.errors.AeatError` via a
  `ModeloRegistryError` root.
- **Logging.** Every module uses `aeat.core.logging.get_logger(__name__)`.
- **Trilingual contract.** `display_label: Translatable` must carry `es`,
  `en`, `hu` keys. Spanish is authoritative.
- **Testing.** `pytest` only, every test marked `@pytest.mark.unit`,
  colocated under `src/aeat/domain/modelos/`. Zero mocks, patches, fakes, stubs,
  skips. No `type: ignore` bandages.
- **Conventional commits** on every commit — literal messages below.
- **No `.github/workflows/`** files. `tests/test_release_config.py`
  already guards the directory.
- **No new settings** in `src/aeat/config.py` — the catalogue is static.
- **Windows path safety** — tests must not hardcode POSIX separators;
  file lookups use `pathlib.Path`.

### Critical ADR clarification — `DeadlineRule`

The ADR (§7) describes `ModeloMetadata.deadline_rule: DeadlineRule`
imported from `aeat.domain.deadlines`. **No such type exists on `main`.**
`aeat.domain.deadlines` publicly exposes `CanonicalWindow` (a concrete
`(modelo, year, period)` window) and the `CALENDAR` tuple keyed by
modelo code string; rule-shaped abstractions are internal to
`_applies.py` and not re-exported. This plan resolves the contradiction
**without** widening `aeat.domain.deadlines`:

- Drop the `deadline_rule: DeadlineRule` field from `ModeloMetadata` for
  v1. In its place, keep a single typed field
  `cadence: ModeloCadence` plus a helper `year_plan(year, profile)` that
  resolves deadlines **at query time** by calling
  `aeat.domain.deadlines.DeadlineEngine.compute(profile, year=year)` and
  filtering obligations by `modelo == metadata.code.value`.
- `year_plan` is the only public callable that touches
  `aeat.domain.deadlines`; registry construction does not import it, keeping
  `aeat.domain.modelos` import-time free of `aeat.domain.deadlines` as a hard
  dependency.
- The ADR's intent — "the CLI `year-plan` command consumes the deadline
  engine to produce a calendar listing" — is preserved exactly. The
  `ModeloMetadata` change (no `deadline_rule` field) is the minimum
  deviation required to keep the plan faithful to the actual public
  surface on disk.

This deviation is recorded in the plan self-review section and must be
accepted there before execution proceeds.

## Phases

### Phase 1 — Scaffolding

Create the module skeleton with empty bodies and the `pytest.mark.unit`
marker wired on every new test file. No data, no validators, no
re-exports beyond typing stubs.

- Create directories and empty/near-empty files:
  - `src/aeat/domain/modelos/_codes.py`
  - `src/aeat/domain/modelos/_categories.py`
  - `src/aeat/domain/modelos/_citations.py`
  - `src/aeat/domain/modelos/_applicability.py`
  - `src/aeat/domain/modelos/_metadata.py`
  - `src/aeat/domain/modelos/_registry.py`
  - `src/aeat/domain/modelos/_cli.py`
  - `src/aeat/domain/modelos/_errors.py`
  - `src/aeat/domain/modelos/_entries/__init__.py`
  - `src/aeat/domain/modelos/_entries/modelo_036.py`
  - `src/aeat/domain/modelos/_entries/modelo_037.py`
  - `src/aeat/domain/modelos/_entries/modelo_100.py`
  - `src/aeat/domain/modelos/_entries/modelo_111.py`
  - `src/aeat/domain/modelos/_entries/modelo_115.py`
  - `src/aeat/domain/modelos/_entries/modelo_123.py`
  - `src/aeat/domain/modelos/_entries/modelo_130.py`
  - `src/aeat/domain/modelos/_entries/modelo_131.py`
  - `src/aeat/domain/modelos/_entries/modelo_180.py`
  - `src/aeat/domain/modelos/_entries/modelo_190.py`
  - `src/aeat/domain/modelos/_entries/modelo_200.py`
  - `src/aeat/domain/modelos/_entries/modelo_202.py`
  - `src/aeat/domain/modelos/_entries/modelo_232.py`
  - `src/aeat/domain/modelos/_entries/modelo_303.py`
  - `src/aeat/domain/modelos/_entries/modelo_347.py`
  - `src/aeat/domain/modelos/_entries/modelo_349.py`
  - `src/aeat/domain/modelos/_entries/modelo_369.py`
  - `src/aeat/domain/modelos/_entries/modelo_390.py`
  - `src/aeat/domain/modelos/_entries/modelo_720.py`
  - `src/aeat/domain/modelos/_entries/modelo_840.py`
- Create empty test shells:
  - `src/aeat/domain/modelos/test_codes.py`
  - `src/aeat/domain/modelos/test_registry.py`
  - `src/aeat/domain/modelos/test_applicability.py`
  - `src/aeat/domain/modelos/test_citations.py`
  - `src/aeat/domain/modelos/test_metadata.py`
  - `src/aeat/domain/modelos/test_cli.py`
  - `src/aeat/domain/modelos/test_casilla_cross_reference.py`
- Leave `src/aeat/domain/modelos/test_smoke.py` untouched.
- `src/aeat/domain/modelos/__init__.py` remains an empty-`__all__` stub for the
  duration of Phase 1 (final lock happens in Phase 8).
- Each test file carries `pytestmark = pytest.mark.unit` at module
  level; bodies are `def test_placeholder() -> None: ...` passing.

**Success criterion.** `just test` runs green; `just lint` clean; no new
imports from `aeat.domain.modelos` leak outside the package.

**Commit.** `feat(models): scaffold aeat.domain.modelos registry module skeleton (#108)`

### Phase 2 — Enums + primitive pydantic models

Implement the closed taxonomies and the three foundational pydantic
models. No registry data yet; no CLI.

- `_codes.py` — `ModeloCode(StrEnum)` with 20 members named
  `MODELO_036`, `MODELO_037`, `MODELO_100`, `MODELO_111`, `MODELO_115`,
  `MODELO_123`, `MODELO_130`, `MODELO_131`, `MODELO_180`, `MODELO_190`,
  `MODELO_200`, `MODELO_202`, `MODELO_232`, `MODELO_303`, `MODELO_347`,
  `MODELO_349`, `MODELO_369`, `MODELO_390`, `MODELO_720`, `MODELO_840`.
  Values are the three-character strings (`"036"`, ..., `"840"`).
- `_categories.py` —
  - `ModeloCategory(StrEnum)`: `IRPF="irpf"`, `IVA="iva"`,
    `RETENCIONES="retenciones"`, `INFORMATIVA="informativa"`,
    `CENSAL="censal"`, `SOCIEDADES="sociedades"`,
    `PATRIMONIO="patrimonio"`, `OTROS="otros"`.
  - `ModeloCadence(StrEnum)`: `MONTHLY="monthly"`,
    `QUARTERLY="quarterly"`, `ANNUAL="annual"`, `AD_HOC="ad_hoc"`.
  - `TaxpayerProfile(StrEnum)`: the eight members from the ADR §4.
  - `LegalCitationSource(StrEnum)`: `LEY="ley"`,
    `REAL_DECRETO="real_decreto"`,
    `ORDEN_MINISTERIAL="orden_ministerial"`,
    `REGLAMENTO="reglamento"`, `MANUAL_PRACTICO="manual_practico"`,
    `BOE="boe"`.
- `_citations.py` — `LegalCitation(BaseModel)` with
  `model_config = ConfigDict(frozen=True, extra="forbid", strict=True)`;
  fields: `source: LegalCitationSource`, `article: str` (min_length=1),
  `url: HttpUrl | None = None`, `quoted_text_es: str`,
  `retrieval_date: date`, `is_curated_summary: bool`. A
  `field_validator("quoted_text_es")` rejects empty or whitespace-only
  values after `.strip()`.
- `_applicability.py` — `ModeloApplicability(BaseModel)` with the same
  strict/frozen config; fields:
  `mandatory_profiles: frozenset[TaxpayerProfile]`,
  `optional_profiles: frozenset[TaxpayerProfile]`,
  `exempt_profiles: frozenset[TaxpayerProfile]`,
  `trigger_notes_es: str` (min_length=1 after strip). A
  `model_validator(mode="after")` enforces the partition invariant:
  pairwise disjoint AND union equal to `set(TaxpayerProfile)`.
- `_metadata.py` — `ModeloMetadata(BaseModel)` with
  `model_config = ConfigDict(frozen=True, extra="forbid", strict=True, arbitrary_types_allowed=False)`
  (arbitrary types NOT needed — see the `DeadlineRule` clarification
  above). Fields:
  - `code: ModeloCode`
  - `official_name_es: str` (non-empty after strip)
  - `display_label: Translatable` validated to contain non-empty
    `es`, `en`, `hu` keys
  - `category: ModeloCategory`
  - `cadence: ModeloCadence`
  - `legal_basis: tuple[LegalCitation, ...]` with `min_length=1`
  - `applicability: ModeloApplicability`
  - `caps_into: ModeloCode | None = None`
  - `related_modelos: tuple[ModeloCode, ...] = ()`
  - `submission_portal_hint: str` (non-empty after strip)
  - `known_gotchas: tuple[str, ...] = ()`
  The `caps_into` cross-reference invariant is enforced at registry
  finalise time (Phase 5), not on the model itself, so individual
  entries can be constructed in isolation in unit tests.
- Tests authored in this phase:
  - `test_codes.py` — exactly 20 members; every value is a
    three-character digit string; `ModeloCode(f"0{n}")` round-trips
    for the padded 036/037 members; member name equals `MODELO_<value>`.
  - `test_applicability.py` — happy-path construction succeeds; a
    profile appearing in two buckets raises `ValidationError`; a
    partition missing a profile raises `ValidationError`.
  - `test_citations.py` — empty `quoted_text_es` raises; whitespace-only
    raises; `is_curated_summary=True` passes; `HttpUrl` coercion works;
    `extra="forbid"` rejects unknown keys.
  - `test_metadata.py` — construct a minimal valid metadata inline;
    assert `frozen` (attempted field assignment raises); `extra="forbid"`
    rejection; `display_label` missing any of `es`/`en`/`hu` raises;
    `legal_basis=()` raises (min_length=1).

**Success criterion.** `uv run pytest src/aeat/models -q` passes.
`just lint` and `just typecheck` clean.

**Commit.** `feat(models): add ModeloCode/Category/Cadence/Profile enums + LegalCitation/Applicability/Metadata (#108)`

### Phase 3 — Error hierarchy

- `_errors.py` —
  - `ModeloRegistryError(AeatError)` — base.
  - `UnknownModeloError(ModeloRegistryError)` — raised from
    `get_modelo(code)` on unknown codes. Carries the offending string.
  - `RegistryIntegrityError(ModeloRegistryError)` — raised at import
    time from `_registry.py` when completeness or `caps_into`
    invariants are violated.
- No tests in this phase beyond a compile-time import smoke inside an
  existing `test_codes.py` (ensure error classes are importable from
  `aeat.domain.modelos._errors`). Full error-path coverage lands in Phase 5.

**Commit.** `feat(models): error hierarchy for registry lookups (#108)`

### Phase 4 — Registry entries (one file per modelo)

Populate every `_entries/modelo_<code>.py` with a module-level
`ENTRY: ModeloMetadata = ModeloMetadata(...)`. Each entry is
constructed from the research doc §3 data; every `LegalCitation`
carries `is_curated_summary=True` in v1 (the on-disk corpus ships
curated Spanish summaries, not BOE verbatim bodies — ADR §9).

The data for each entry (from research §3 / §4) is:

| Code | Category | Cadence | Primary citations (article → source) | `caps_into` | Mandatory profiles (from D2) | Optional profiles |
|:---:|:---:|:---:|:---|:---:|:---|:---|
| 036 | `CENSAL` | `AD_HOC` | `rd-1065-2007#30` (REAL_DECRETO), `ley-58-2003#29` (LEY) | `None` | `AUTONOMO_ED_UE`, `SL` | all remaining autonomo profiles |
| 037 | `CENSAL` | `AD_HOC` | `rd-1065-2007#30` (REAL_DECRETO), `ley-58-2003#29` (LEY) | `None` | `AUTONOMO_ED_SOLO`, `AUTONOMO_EO` | `AUTONOMO_ED_CON_EMPLEADOS`, `AUTONOMO_ED_CON_PROFESIONALES`, `AUTONOMO_ED_CON_ALQUILER`, `AUTONOMO_ED_BIENES_EXTRANJERO` |
| 100 | `IRPF` | `ANNUAL` | `ley-35-2006#27` (LEY), `orden-hac-242-2025#primero` (ORDEN_MINISTERIAL) | `None` | all seven autonomo profiles | (none) |
| 111 | `RETENCIONES` | `QUARTERLY` | `rd-439-2007#80` (REAL_DECRETO), `rd-439-2007#95` (REAL_DECRETO), `rd-439-2007#109` (REAL_DECRETO) | `MODELO_190` | `AUTONOMO_ED_CON_EMPLEADOS`, `AUTONOMO_ED_CON_PROFESIONALES`, `SL` | `AUTONOMO_EO` |
| 115 | `RETENCIONES` | `QUARTERLY` | `ley-35-2006#99` (LEY), `rd-439-2007#109` (REAL_DECRETO) | `MODELO_180` | `AUTONOMO_ED_CON_ALQUILER`, `SL` | (none) |
| 123 | `RETENCIONES` | `QUARTERLY` | `ley-35-2006#99` (LEY), `rd-439-2007#109` (REAL_DECRETO) | `None` (research notes caps_into 193; 193 is NOT in the registry so v1 stores `None` with a gotcha documenting the gap) | (none) | `SL` |
| 130 | `IRPF` | `QUARTERLY` | `rd-439-2007#110` (REAL_DECRETO), `ley-35-2006#99` (LEY) | `MODELO_100` | `AUTONOMO_ED_SOLO`, `AUTONOMO_ED_CON_EMPLEADOS`, `AUTONOMO_ED_CON_PROFESIONALES`, `AUTONOMO_ED_CON_ALQUILER`, `AUTONOMO_ED_UE`, `AUTONOMO_ED_BIENES_EXTRANJERO` | (none) |
| 131 | `IRPF` | `QUARTERLY` | `rd-439-2007#110` (REAL_DECRETO), `ley-35-2006#31` (LEY) | `MODELO_100` | `AUTONOMO_EO` | (none) |
| 180 | `INFORMATIVA` | `ANNUAL` | `rd-1065-2007#30` (REAL_DECRETO), `rd-439-2007#109` (REAL_DECRETO) | `None` | `AUTONOMO_ED_CON_ALQUILER`, `SL` | (none) |
| 190 | `INFORMATIVA` | `ANNUAL` | `rd-1065-2007#30` (REAL_DECRETO), `ley-35-2006#99` (LEY) | `None` | `AUTONOMO_ED_CON_EMPLEADOS`, `AUTONOMO_ED_CON_PROFESIONALES`, `SL` | `AUTONOMO_EO` |
| 200 | `SOCIEDADES` | `ANNUAL` | `ley-58-2003#29` (LEY) — Ley 27/2014 gap flagged in `known_gotchas` | `None` | `SL` | (none) |
| 202 | `SOCIEDADES` | `QUARTERLY` (3 periods — categorise as `QUARTERLY`; research maps to April/October/December) | `ley-58-2003#29` (LEY) | `MODELO_200` | (none) | `SL` |
| 232 | `INFORMATIVA` | `ANNUAL` | `rd-1065-2007#30` (REAL_DECRETO) | `None` | (none) | `SL` |
| 303 | `IVA` | `QUARTERLY` | `ley-37-1992#164` (LEY), `rd-1624-1992#71` (REAL_DECRETO) | `MODELO_390` | all seven autonomo profiles + `SL` | (none) |
| 347 | `INFORMATIVA` | `ANNUAL` | `rd-1065-2007#30` (REAL_DECRETO), `ley-58-2003#29` (LEY) | `None` | (none) | all eight profiles (threshold-gated) |
| 349 | `INFORMATIVA` | `QUARTERLY` | `rd-1065-2007#30` (REAL_DECRETO), `ley-37-1992#164` (LEY) | `None` | `AUTONOMO_ED_UE` | `SL` |
| 369 | `IVA` | `QUARTERLY` | `ley-37-1992#164` (LEY), `rd-1624-1992#71` (REAL_DECRETO) — OSS Título IX Cap. XI gap flagged | `None` | (none) | all eight profiles (OSS opt-in) |
| 390 | `IVA` | `ANNUAL` | `ley-37-1992#164` (LEY), `rd-1624-1992#71` (REAL_DECRETO) | `None` | all seven autonomo profiles + `SL` | (none) |
| 720 | `INFORMATIVA` | `ANNUAL` | `rd-1065-2007#30` (REAL_DECRETO) — RGAT 42 bis/ter/54 bis gap flagged | `None` | `AUTONOMO_ED_BIENES_EXTRANJERO` | `SL` |
| 840 | `OTROS` | `AD_HOC` | `ley-58-2003#29` (LEY) — TRLHL arts 78–91 gap flagged | `None` | (none) | `SL` |

Notes applied to every entry:

- `display_label` carries `es` / `en` / `hu` from research §3
  (verbatim); `official_name_es` is the es string.
- `exempt_profiles` is computed as `set(TaxpayerProfile) - mandatory -
  optional` so the partition invariant holds.
- `trigger_notes_es` copies the D2 footnote prose (research §4 f1–f20)
  matching the modelo.
- `quoted_text_es` on every citation is the exact Spanish summary
  published in the research doc for that `{file_id}#{articulo}` pair.
- `url` is the `https://www.boe.es/buscar/act.php?id=...` URL from the
  research doc when available; otherwise `None`.
- `retrieval_date = date(2026, 4, 13)`.
- `is_curated_summary = True` for every v1 citation.
- `submission_portal_hint` is the `Channel hint` URL from research §3.
- `known_gotchas` copies the research `Gotchas` bullets as a tuple of
  Spanish strings plus — where applicable — a note for corpus gaps
  (e.g. "RIVA art 81.3 no disponible en corpus on-disk" on 349,
  "Ley 27/2014 no disponible en corpus on-disk" on 200/202,
  "RGAT arts 42 bis/ter/54 bis no disponibles en corpus on-disk" on
  720, "TRLHL arts 78–91 no disponibles en corpus on-disk" on 840,
  "OSS Título IX Cap. XI no disponible en corpus on-disk" on 369,
  "Modelo 193 ausente del registro v1; caps_into deliberadamente None"
  on 123).
- `related_modelos` copies `receives_from`/`replaces`/`related_modelos`
  from research §3.

No tests are added in this phase; every entry's validity is enforced
by the pydantic models at module-import time (a malformed entry causes
the entry file's import to fail during Phase 5 registry assembly).

**Commit.** `feat(models): populate registry with 20 modelo metadata entries (#108)`

### Phase 5 — Registry assembly + invariants + `year_plan`

- `_registry.py` imports every `_entries/modelo_*.py` module and
  collects `ENTRY` objects into a mutable dict, then freezes it as
  `MODELO_REGISTRY: Mapping[ModeloCode, ModeloMetadata] = MappingProxyType(...)`.
- A module-level `_finalise_registry()` function runs at import and:
  - Asserts completeness: every `ModeloCode` member is a key and no
    extra keys exist. Violation raises `RegistryIntegrityError`.
  - Asserts `metadata.code == key` for every entry.
  - Walks every entry; if `caps_into is not None` and the value is not
    in `MODELO_REGISTRY`, raises `RegistryIntegrityError` naming both
    codes.
  - Logs `INFO` "loaded N modelo entries" exactly once.
- Public helpers (re-exported from `__init__.py` in Phase 8):
  - `get_modelo(code: ModeloCode | str) -> ModeloMetadata` — accepts a
    `ModeloCode` or the three-character string; coerces via
    `ModeloCode(code)`; raises `UnknownModeloError` on lookup miss or
    coercion failure.
  - `modelos_for_profile(profile: TaxpayerProfile) -> tuple[ModeloMetadata, ...]`
    — returns every entry where `profile` is in
    `applicability.mandatory_profiles | applicability.optional_profiles`,
    sorted by `ModeloCode` value.
  - `year_plan(year: int, profile: AutonomoProfile) -> Schedule` —
    thin wrapper around
    `DeadlineEngine(_InProcessCatalogue()).compute(profile, year=year)`
    where `_InProcessCatalogue` is a private class inside `_registry.py`
    exposing `known_modelos()`/`is_known()` built from
    `ModeloCode.__members__`. The wrapper does not filter obligations;
    the CLI layer does the per-profile narrowing.
- `test_registry.py` covers:
  - Completeness invariant (both directions).
  - `caps_into` resolution for every non-None value.
  - `get_modelo(ModeloCode.MODELO_303)` round-trips.
  - `get_modelo("303")` round-trips.
  - `get_modelo("999")` raises `UnknownModeloError`.
  - `get_modelo("not-a-code")` raises `UnknownModeloError`.
  - `modelos_for_profile(TaxpayerProfile.AUTONOMO_ED_SOLO)` contains
    `MODELO_303`, `MODELO_390`, `MODELO_130`, `MODELO_037`, `MODELO_100`
    at minimum, and does not contain `MODELO_720` or `MODELO_200`.
  - A synthetic `RegistryIntegrityError` branch — exercised by
    constructing a local `ModeloMetadata` with a bogus `caps_into`
    manually and calling a private `_check_caps_into` helper against a
    hand-built dict (keeping the test hermetic; the actual module-
    import path cannot be re-entered).
  - `year_plan(2026, profile)` returns a `Schedule` whose
    `obligations` are non-empty for an `AutonomoProfile` with
    `iva_regime=GENERAL`.

**Commit.** `feat(models): assemble MODELO_REGISTRY with import-time integrity invariant (#108)`

### Phase 6 — Casilla cross-reference test

- `test_casilla_cross_reference.py` lazily imports `aeat.domain.casillas`,
  enumerates the on-disk casilla catalogues it knows about (the
  loader's public surface), extracts the set of modelo codes referenced
  by those catalogues (currently `"130"`, `"303"`, `"390"`), and
  asserts every such code resolves to a `MODELO_REGISTRY` entry. The
  test is the enforcement direction called out in the issue brief:
  "every modelo the casilla catalogue knows about has a
  MODELO_REGISTRY entry". The richer reverse direction (every
  `ModeloMetadata` references only known casilla codes) lands in a
  later iteration once `ModeloMetadata` carries structured casilla
  references.
- If `aeat.domain.casillas` does not expose a direct "list catalogues" API,
  the test scans `corpus/casillas/modelo_<code>/` directory names
  using `pathlib.Path` relative to the package root, extracts the
  `<code>` part, and asserts each resolves via `get_modelo`.

**Commit.** `test(models): cross-reference casilla catalogue coverage (#108)`

### Phase 7 — CLI commands

- `_cli.py` builds a Typer app:
  ```
  app = typer.Typer(name="modelos", help="...", no_args_is_help=True)
  ```
  with four commands. Each command takes `--json` (default `False`).
  - `list(category: ModeloCategory | None, cadence: ModeloCadence | None, profile: TaxpayerProfile | None, json_out: bool)`
    — filters `MODELO_REGISTRY.values()` and emits either a
    rich-or-plain table (code | category | cadence | display_label.es)
    or JSON via `[m.model_dump(mode="json") for m in rows]`.
  - `show(code: str, json_out: bool)` — resolves via `get_modelo(code)`;
    raises `typer.BadParameter` mapping `UnknownModeloError`. Emits the
    full metadata record.
  - `applicable_to(profile: TaxpayerProfile, json_out: bool)` — calls
    `modelos_for_profile(profile)`.
  - `year_plan(year: int, profile_tax_id: str, iva_regime: IVARegime,
    has_employees: bool, pays_rent_with_retencion: bool,
    does_intracomunitario: bool, bienes_extranjero_above_threshold: bool,
    json_out: bool)` — builds an `AutonomoProfile` from the flags,
    calls the registry's `year_plan(year, profile)`, narrows the
    returned `Schedule.obligations` to those whose `modelo` resolves
    to a modelo whose `applicability.mandatory_profiles` or
    `optional_profiles` intersect the profile's implied
    `TaxpayerProfile` (derived by a small `_profile_from_autonomo`
    helper inside `_cli.py`), and emits either a table or JSON.
- Table rendering:
  - Check `pyproject.toml` for `rich` before committing to it. The
    existing CLI (e.g. `aeat.entrypoints.cli.deadlines`) already uses `rich`; this
    plan assumes it is available but the executor must verify and fall
    back to plain aligned text via `typer.echo` if not.
- Wire-up:
  - Create `src/aeat/entrypoints/cli/modelos/__init__.py` that re-exports the Typer
    `app` from `aeat.domain.modelos._cli`, matching the pattern used by
    `src/aeat/entrypoints/cli/deadlines/__init__.py`.
  - Add a single line to `src/aeat/entrypoints/cli/__init__.py`:
    `from aeat.entrypoints.cli import modelos as modelos_module` and
    `app.add_typer(modelos_module.app, name="modelos", help="AEAT modelo inventory + applicability helpers.")`
    in alphabetical position.
- `test_cli.py` uses `typer.testing.CliRunner` and exercises:
  - `aeat modelos list` (text + `--json`).
  - `aeat modelos list --category iva --json` returns only IVA entries.
  - `aeat modelos show 303 --json` round-trips via
    `ModeloMetadata.model_validate`.
  - `aeat modelos show 999` exits non-zero.
  - `aeat modelos applicable-to autonomo_ed_solo --json` contains 303.
  - `aeat modelos year-plan 2026 --tax-id X1234567L --iva-regime GENERAL ...`
    exits 0 and prints at least one obligation.
  - No mocks; every call hits the real registry and the real
    `DeadlineEngine`.

**Commit.** `feat(models): CLI subcommands list/show/applicable-to/year-plan (#108)`

### Phase 8 — Public API lock + docstrings

- `src/aeat/domain/modelos/__init__.py` sets `__all__` to the exact tuple from
  the ADR §12 **minus any symbol that the `DeadlineRule` clarification
  removes**. The v1 `__all__` is:
  ```
  __all__ = (
      "ModeloCode",
      "ModeloCategory",
      "ModeloCadence",
      "TaxpayerProfile",
      "LegalCitationSource",
      "LegalCitation",
      "ModeloApplicability",
      "ModeloMetadata",
      "MODELO_REGISTRY",
      "ModeloRegistryError",
      "UnknownModeloError",
      "RegistryIntegrityError",
      "get_modelo",
      "modelos_for_profile",
      "year_plan",
  )
  ```
- Every public symbol carries a Google-style docstring with
  `Attributes:` / `Args:` / `Returns:` / `Raises:` sections as
  appropriate. Every public signature is fully typed.
- The package docstring (top of `__init__.py`) describes the
  registry's role and links (prose, not wiki) to
  `2026-04-13-modelo-inventory-adr`.

**Commit.** `docs(models): public API docstrings + __all__ lock (#108)`

### Phase 9 — Green gates

- Run, in order, `just lint`, `just typecheck`, `just test`,
  `just hooks`. Fix any root cause; never add `type: ignore` or
  `# noqa` without a comment pointing to a concrete upstream
  limitation.
- Verify `.env.example` and `tests/test_config.py` are untouched —
  this feature introduces no new settings.
- Verify `.github/workflows/` is absent.
- Verify `tests/test_release_config.py` still passes.
- Only commit if cleanup was needed.

**Commit (conditional).** `chore(models): lint + typecheck + test green gates (#108)`

## File change map

| Path | Status | Purpose |
|:--|:--|:--|
| `src/aeat/domain/modelos/__init__.py` | modified | Public re-exports + locked `__all__` + package docstring |
| `src/aeat/domain/modelos/_codes.py` | new | `ModeloCode` `StrEnum` |
| `src/aeat/domain/modelos/_categories.py` | new | `ModeloCategory`, `ModeloCadence`, `TaxpayerProfile`, `LegalCitationSource` `StrEnum`s |
| `src/aeat/domain/modelos/_citations.py` | new | `LegalCitation` pydantic model + `quoted_text_es` validator |
| `src/aeat/domain/modelos/_applicability.py` | new | `ModeloApplicability` model + partition validator |
| `src/aeat/domain/modelos/_metadata.py` | new | `ModeloMetadata` model + trilingual label validator |
| `src/aeat/domain/modelos/_errors.py` | new | `ModeloRegistryError` / `UnknownModeloError` / `RegistryIntegrityError` |
| `src/aeat/domain/modelos/_registry.py` | new | `MODELO_REGISTRY`, `_finalise_registry`, `get_modelo`, `modelos_for_profile`, `year_plan` |
| `src/aeat/domain/modelos/_cli.py` | new | Typer sub-app with `list` / `show` / `applicable-to` / `year-plan` commands |
| `src/aeat/domain/modelos/_entries/__init__.py` | new | Empty marker (entries imported explicitly by `_registry.py`) |
| `src/aeat/domain/modelos/_entries/modelo_036.py` | new | `ENTRY: ModeloMetadata` for modelo 036 |
| `src/aeat/domain/modelos/_entries/modelo_037.py` | new | `ENTRY` for modelo 037 |
| `src/aeat/domain/modelos/_entries/modelo_100.py` | new | `ENTRY` for modelo 100 |
| `src/aeat/domain/modelos/_entries/modelo_111.py` | new | `ENTRY` for modelo 111 |
| `src/aeat/domain/modelos/_entries/modelo_115.py` | new | `ENTRY` for modelo 115 |
| `src/aeat/domain/modelos/_entries/modelo_123.py` | new | `ENTRY` for modelo 123 |
| `src/aeat/domain/modelos/_entries/modelo_130.py` | new | `ENTRY` for modelo 130 |
| `src/aeat/domain/modelos/_entries/modelo_131.py` | new | `ENTRY` for modelo 131 |
| `src/aeat/domain/modelos/_entries/modelo_180.py` | new | `ENTRY` for modelo 180 |
| `src/aeat/domain/modelos/_entries/modelo_190.py` | new | `ENTRY` for modelo 190 |
| `src/aeat/domain/modelos/_entries/modelo_200.py` | new | `ENTRY` for modelo 200 |
| `src/aeat/domain/modelos/_entries/modelo_202.py` | new | `ENTRY` for modelo 202 |
| `src/aeat/domain/modelos/_entries/modelo_232.py` | new | `ENTRY` for modelo 232 |
| `src/aeat/domain/modelos/_entries/modelo_303.py` | new | `ENTRY` for modelo 303 |
| `src/aeat/domain/modelos/_entries/modelo_347.py` | new | `ENTRY` for modelo 347 |
| `src/aeat/domain/modelos/_entries/modelo_349.py` | new | `ENTRY` for modelo 349 |
| `src/aeat/domain/modelos/_entries/modelo_369.py` | new | `ENTRY` for modelo 369 |
| `src/aeat/domain/modelos/_entries/modelo_390.py` | new | `ENTRY` for modelo 390 |
| `src/aeat/domain/modelos/_entries/modelo_720.py` | new | `ENTRY` for modelo 720 |
| `src/aeat/domain/modelos/_entries/modelo_840.py` | new | `ENTRY` for modelo 840 |
| `src/aeat/domain/modelos/test_codes.py` | new | `ModeloCode` unit tests |
| `src/aeat/domain/modelos/test_citations.py` | new | `LegalCitation` validator tests |
| `src/aeat/domain/modelos/test_applicability.py` | new | Partition invariant tests |
| `src/aeat/domain/modelos/test_metadata.py` | new | `ModeloMetadata` strict/frozen tests |
| `src/aeat/domain/modelos/test_registry.py` | new | Registry completeness + `caps_into` + helper tests |
| `src/aeat/domain/modelos/test_cli.py` | new | Typer `CliRunner` smoke tests |
| `src/aeat/domain/modelos/test_casilla_cross_reference.py` | new | Casilla catalogue cross-ref test |
| `src/aeat/domain/modelos/test_smoke.py` | untouched | Existing smoke test preserved |
| `src/aeat/entrypoints/cli/modelos/__init__.py` | new | Re-exports the Typer app from `aeat.domain.modelos._cli` |
| `src/aeat/entrypoints/cli/__init__.py` | modified | Wires `modelos_module.app` into the root Typer app |

## Risks + mitigations

- **`DeadlineRule` does not exist on `aeat.domain.deadlines`.** The ADR names
  a `DeadlineRule` type that is nowhere in the current public API
  (`src/aeat/domain/deadlines/__init__.py` exposes `CanonicalWindow`, `CALENDAR`,
  `DeadlineEngine`, `applies_to`, `explain` only). **Mitigation:** drop
  the `deadline_rule` field from `ModeloMetadata` for v1 and resolve
  deadlines at query time through `DeadlineEngine.compute`. The
  deviation is documented in the constraints section and must be
  accepted in the self-review below. No new public surface is added to
  `aeat.domain.deadlines`.
- **Two-pass `caps_into` validation needs careful import ordering.**
  **Mitigation:** centralise all entry imports inside `_registry.py`'s
  module body and run `_finalise_registry()` as the last top-level
  statement. No entry imports another entry.
- **`rich` availability.** The CLI plan assumes `rich` is already a
  dependency because `aeat.entrypoints.cli.deadlines` uses it. **Mitigation:** the
  executor must `rg -n "^rich" pyproject.toml` before committing to
  `rich.table.Table`; fall back to plain aligned `typer.echo` if not.
- **Casilla catalogue API shape.** The test in Phase 6 may find that
  `aeat.domain.casillas` does not expose a "list catalogues" function.
  **Mitigation:** the plan allows the test to scan
  `corpus/casillas/modelo_*/` directories directly via `pathlib.Path`.
- **Preserving `test_smoke.py`.** **Mitigation:** the file is listed
  as "untouched" in the file change map; Phase 1 explicitly leaves it
  alone.
- **Windows path separators in tests.** **Mitigation:** every path
  lookup uses `pathlib.Path` and joins via `/`. No string-concatenated
  paths.
- **Modelo 123 `caps_into = 193` dangling reference.** Research §3.10
  says 123 caps into 193, but 193 is not in the v1 registry. **Mitigation:**
  store `caps_into=None` and surface the gap as a gotcha. The ADR's
  `caps_into` invariant (every non-None value resolves inside the
  registry) is honoured.
- **Categorising 202's three-period cadence.** Research §3.19 says
  202 is filed in April/October/December (three periods). **Mitigation:**
  the `ModeloCadence` enum has no `TRIMANUAL` member and the ADR locks
  the closed set; store 202 as `QUARTERLY` and put the three-period
  nuance in `trigger_notes_es` / `known_gotchas`.
- **`exempt_profiles` closure for profiles not named in D2.** D2's
  `y` (optional) and `-` (n/a) rows collapse into `optional` and
  `exempt` buckets respectively. **Mitigation:** executor computes
  `exempt_profiles = set(TaxpayerProfile) - mandatory - optional` to
  satisfy the partition invariant mechanically.

## Plan self-review (2026-04-13)

**Reviewer.** Plan author (vaultspec-write-plan persona).

**Scope checked.** Issue #108 acceptance criteria; every ADR decision
(§1–§17); CLAUDE.md rules (`src/aeat/` layout, pydantic v2 mandate,
trilingual contract, conventional commits, colocated tests, no GitHub
workflow files, live-tests env var, public-API discipline); vaultspec
frontmatter + tagging rules (two tags, `related` as quoted wiki-link
list); sibling-branch promises to #77 and #93 (stable `ModeloCode`
import surface via the locked `__all__` tuple).

**Findings.**

- **ADR deviation required.** ADR §7 names `DeadlineRule` as a field
  on `ModeloMetadata` imported from `aeat.domain.deadlines`. **No such type
  exists on `main`.** The plan resolves this by dropping the field
  from `ModeloMetadata` for v1 and resolving deadlines at query time
  via `DeadlineEngine.compute`. This is the minimum deviation that
  keeps the plan executable without widening `aeat.domain.deadlines`'s
  public surface (which would be scope creep out of #108). The ADR's
  functional intent — CLI `year-plan` consumes the deadline engine —
  is preserved exactly. **The executor must NOT add a `DeadlineRule`
  type to `aeat.domain.deadlines`; any such addition is scope creep and
  should be rejected in code review.**
- **Modelo 123 `caps_into` gap.** The research says `caps_into=193`;
  193 is not in the v1 registry. The plan stores `None` with a
  gotcha. Consistent with ADR §8 (`caps_into must resolve inside the
  registry`).
- **Cadence taxonomy matches ADR §3 exactly.** Monthly-only modelos
  (349 rolling-threshold escalation) are stored as `QUARTERLY` with
  a gotcha, matching research §3.6's default.
- **Trilingual contract honoured.** `display_label` is the only
  `Translatable`; every entry carries `es` / `en` / `hu` per research
  §3.
- **Curated-summary policy honoured.** Every v1 citation carries
  `is_curated_summary=True`. ADR §9 accepts this explicitly.
- **Sibling-branch stability.** The locked `__all__` tuple matches
  ADR §12 exactly except for `DeadlineRule` removal (which is not in
  the ADR's `__all__` either). `ModeloCode` member names are
  `MODELO_<code>` as ADR §2 locks. #77 and #93 can import
  `aeat.domain.modelos.ModeloCode` without surprise.
- **No CI workflows; no config drift; no new settings.** Verified in
  Phase 9.
- **Commit messages** follow conventional-commits with
  `feat(models): …` / `test(models): …` / `docs(models): …` /
  `chore(models): …` prefixes.
- **Vaultspec frontmatter.** Two tags (`#plan`, `#modelo-inventory`);
  `related` is a YAML list of quoted wiki-links; date in
  `yyyy-mm-dd`; no `feature:` key. Compliant.
- **No wiki-links in the body.** Only frontmatter `related` carries
  them. Compliant.
- **Scope creep check.** The plan touches only `src/aeat/domain/modelos/`
  plus two lines in `src/aeat/entrypoints/cli/__init__.py` and one new thin
  `src/aeat/entrypoints/cli/modelos/__init__.py`. No sibling branches touched;
  no `aeat.domain.deadlines` widening; no builder work; no workflow files.

**Verdict.** **Approved — execution may proceed**, with the single
documented deviation on `DeadlineRule` explicitly accepted. No
further ADR clarification is required; the deviation is minimal,
localised to `aeat.domain.modelos`, and preserves the ADR's functional
intent.

## Acceptance checklist

- [ ] `ModeloCode` StrEnum with 20 members, stable import surface — Phase 2.
- [ ] `ModeloMetadata` strict/frozen pydantic v2 record — Phase 2.
- [ ] `LegalCitation` with non-empty `quoted_text_es` invariant — Phase 2.
- [ ] `ModeloApplicability` partition invariant — Phase 2.
- [ ] All 20 modelos populated with citations, applicability, gotchas — Phase 4.
- [ ] `MODELO_REGISTRY` frozen, complete, `caps_into`-verified — Phase 5.
- [ ] `get_modelo` / `modelos_for_profile` / `year_plan` public helpers — Phase 5.
- [ ] Error hierarchy rooted at `AeatError` — Phase 3.
- [ ] Casilla catalogue cross-reference coverage — Phase 6.
- [ ] CLI: `aeat modelos list/show/applicable-to/year-plan` + `--json` — Phase 7.
- [ ] Trilingual display labels (`es`/`en`/`hu`) on every entry — Phase 4.
- [ ] Public `__all__` locked per ADR §12 (minus the `DeadlineRule` deviation) — Phase 8.
- [ ] Every test `@pytest.mark.unit`, zero mocks/patches/fakes/stubs — Phases 2/5/6/7.
- [ ] Google-style docstrings + type hints on every public signature — Phase 8.
- [ ] Conventional commits on every commit — every phase.
- [ ] `just lint` / `just typecheck` / `just test` / `just hooks` green — Phase 9.
- [ ] No `.github/workflows/` files — Phase 9.
- [ ] No new settings in `src/aeat/config.py` / `.env.example` — Phase 9.
