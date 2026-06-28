---
tags:
  - '#adr'
  - '#resource-management-api'
date: '2026-05-16'
modified: '2026-05-16'
related:
  - "[[2026-05-16-resource-management-api-research]]"
  - "[[2026-05-16-resource-management-api-audit]]"
  - "[[2026-05-15-corpus-registry-packaging-adr]]"
  - "[[2026-05-15-corpus-registry-packaging-research]]"
  - "[[2026-05-15-corpus-registry-packaging-plan]]"
---

> **Updated 2026-05-19**: Identifier mentions of vat_catalogues, VatCatalogueRepository, vat_rate_tables, VatRateTableRepository, and VAT_CATALOGUES_BY_YEAR in this ADR follow the Spanish-stem terminology authority and rename per the canonical rename ledger when the IVA cluster migration lands. The resource-management API direction (typed accessor surface, single env-override seam, repository taxonomy) is independent of the VAT-vs-IVA stem and is unaffected.
> See `2026-05-19-spanish-stem-terminology-authority-adr` for the canonical
> rename ledger and Spanish-stem terminology authority.




# `resource-management-api` adr: Centralised typed Repository-per-type resource registry | (**status:** `accepted`)

## Problem Statement

The corpus-registry-packaging feature consolidated the on-disk
data trees behind a single resource-access boundary at
`src/aeat/core/resources.py` exposing `packaged_data`,
`bundled_path`, and `as_path`. The exhaustive call-site audit
performed for this ADR confirms that the boundary works as
intended at the data-location level but does not address the
loader-and-cache surface that sits on top of it.

The audit enumerates 31 named public loaders defined across 13
domain modules, 11 production module-level `_DEFAULT_*_ROOT`
constants, 30+ test-file `_REGISTRY_ROOT` constants, and 20+
scattered `@lru_cache`/`@cache` decorators with arbitrary
heuristic sizes ranging from 1 to 4096. The Settings env-override
seam covers three of the resource roots (manuals, normatives, VAT
catalogue) but not the rest; the VAT catalogue field is declared
in Settings yet never consumed via the Settings path in
production. Five separate construction paths exist for
`ValidatedRegistryAuthority` across application, adapters, and
CLI layers. Nine typer.Argument/Option defaults in the CLI bind
to module-level bundled-path constants.

The result is a correct system whose resource-access policy is
scattered across the codebase. Every consumer that wants a piece
of bundled data must know which loader to import, which root
constant to pass, which cache layer applies, which error class
to catch, and how to override the resource for tests. Adding a
new resource kind requires touching three layers; relocating an
existing resource requires editing every consumer.

This ADR introduces a single typed Repository-per-resource
registry at `aeat.core.resources` as the canonical surface for
all read-only bundled-data access. Mutable persisted state
(`var/`, secure-storage write surfaces, ledgers) is explicitly
out of scope.

## Considerations

The research artefact surveyed twelve industry patterns and
identified three concrete API sketches. The leading candidate
was Sketch A — a `Repository[T, K]` per resource type with a
central `ResourceRegistry` aggregating them and a process-wide
`resources()` factory. The runner-up was Sketch B — a single
discriminated `request(key)` method. The third option was
Sketch C — a `Resource.load(key)` classmethod per model.

The audit ratifies Sketch A as the right fit. The 31 named
public loaders, the 11 production module-level root constants,
and the 20+ cache decorators all map one-to-one onto Repository
methods. The cache sizing noise collapses behind a single
Repository-owned Identity Map per resource kind. The
`ValidatedRegistryAuthority` aggregate becomes the modelos
Repository's backing implementation, preserving its existing
validator and snapshot caches. The Settings env-override seam
stays external; the `resources()` factory reads Settings once at
construction.

Eight open questions were left for this ADR. Each is decided
below with rationale.

## Constraints

Pydantic v2 is the boundary-modelling mandate. Every Repository
key, every cross-resource reference, every resource model is a
strict frozen Pydantic v2 model. The Settings env-override seam
is preserved verbatim for the three corpus-mediated roots; tests
that use `override_settings(...)` continue to work without
modification.

The hexagonal layering rule places cross-cutting concerns in
`core/`. The new `ResourceRegistry`, its `Repository[T, K]`
base, the typed `ResourceKey` discriminated union, and the
shared `ResourceLoadError` hierarchy all live under
`src/aeat/core/resources/`. Domain models stay in their domain
packages; Repository implementations reference them but the
Repository class hierarchy itself is core-layer infrastructure.

The single-resource-boundary rule means the `ResourceRegistry`
replaces or wraps the existing `packaged_data`/`bundled_path`
surface. The audit confirms there is exactly one public
resource-access boundary today; the migration ends with exactly
one boundary still. No parallel locator is introduced under
`adapters/`, `application/`, `domain/`, or `entrypoints/`.

The no-mocks rule applies. Repository implementations are
testable with real bundled data; tests do not mock the boundary.
Tests that need a different bundled root use Settings overrides
or construct an alternate Repository directly.

The audit reports approximately 25-30 production consumer
modules and ~100 test modules to migrate. The diff shape mirrors
the corpus-registry-packaging migration and is mechanical once
the Repository base lands.

## Implementation

The new resource-management surface lives under
`src/aeat/core/resources/` as a package (replacing the current
single-file `src/aeat/core/resources.py`). The package exposes:

```python
# src/aeat/core/resources/__init__.py
from ._boundary import packaged_data, bundled_path, as_path
from ._registry import ResourceRegistry, resources
from ._errors import (
    ResourceLoadError,
    ResourceNotFoundError,
    ResourceValidationError,
    ResourceBackendError,
)
from ._keys import ResourceKey  # discriminated union
from ._repository import Repository

__all__ = [
    "packaged_data", "bundled_path", "as_path",
    "ResourceRegistry", "resources",
    "ResourceLoadError", "ResourceNotFoundError",
    "ResourceValidationError", "ResourceBackendError",
    "ResourceKey", "Repository",
]
```

The base `Repository[T, K]` is a `Protocol`-flavoured generic
plus a default base class that owns the Identity Map cache:

```python
# src/aeat/core/resources/_repository.py
class Repository[T, K](Protocol):
    """A typed read-only resource repository."""

    def get(self, key: K) -> T: ...
    def find(self, **criteria: object) -> Iterable[T]: ...
    def all(self) -> Iterable[T]: ...
    def clear_cache(self) -> None: ...
```

Each Repository implementation owns its loader and its cache;
the cache is one `dict[K, T]` (the Identity Map) populated lazily
on `get(key)`. `clear_cache()` is callable per-Repository and
also bubbles up to the `ResourceRegistry.clear()` aggregate.

The central registry:

```python
# src/aeat/core/resources/_registry.py
@dataclass(slots=True, frozen=True)
class ResourceRegistry:
    modelos: ModeloRepository
    manuals: ManualRepository
    normatives: NormativeRepository
    vat_catalogues: VatCatalogueRepository
    vat_rate_tables: VatRateTableRepository
    holiday_calendars: HolidayCalendarRepository
    recargo_bands: RecargoBandsRepository
    category_profiles: CategoryProfileRepository
    topics: TopicCatalogueRepository
    user_profile_schema: UserProfileSchemaRepository
    apoderamientos: ApoderamientosRepository
    legal_parameters: LegalParameterRepository

    def clear(self) -> None:
        """Clear every Repository's Identity Map."""
        for repo in (self.modelos, self.manuals, ...):
            repo.clear_cache()


@cache
def resources() -> ResourceRegistry:
    """Process-wide resource registry; one Identity Map per Repository."""
    settings = load_settings()
    return ResourceRegistry(
        modelos=ModeloRepository(),
        manuals=ManualRepository(root=settings.aeat_manuals_root),
        normatives=NormativeRepository(root=settings.aeat_normatives_root),
        vat_catalogues=VatCatalogueRepository(root=settings.aeat_vat_catalogue_root),
        vat_rate_tables=VatRateTableRepository(),
        holiday_calendars=HolidayCalendarRepository(),
        recargo_bands=RecargoBandsRepository(),
        category_profiles=CategoryProfileRepository(),
        topics=TopicCatalogueRepository(),
        user_profile_schema=UserProfileSchemaRepository(),
        apoderamientos=ApoderamientosRepository(),
        legal_parameters=LegalParameterRepository(),
    )
```

Consumers call `resources().modelos.get(ModeloKey(id="100"))`
instead of `load_registry_tree(bundled_path("registry", "aeat"))`
or `default_registry_authority()`. The
`ValidatedRegistryAuthority` class stays — `ModeloRepository`
delegates `get(...)` to it and preserves its existing validator
and snapshot caches. The audit's "5 separate construction paths"
collapse to one factory call.

The eight open questions are decided as follows.

**Q1 — Resource taxonomy enumeration. Decision: closed.** The
`ResourceKey` discriminator is a `Literal`-tagged union with
twelve current variants (one per Repository attribute on the
registry). Adding a new resource kind means adding a Repository
class, a key model, and a registry attribute. Open plugin
discovery is rejected; no plugin-resource use case exists in
the codebase.

**Q2 — Cache key strategy. Decision: typed `ResourceKey` Pydantic
models with `frozen=True` so they are hashable.** Each
Repository defines its own `Key` model (or uses `int`, `str`,
`None` for trivial cases). The Identity Map uses the key model
directly as a dict key. The existing `(path, size, mtime_ns)`
fingerprint pattern is dropped — the bundled tree is immutable
per install and the path alone is sufficient to identify the
resource.

**Q3 — Cache backend. Decision: a plain
`dict[K, T]` Identity Map per Repository, unbounded.** No LRU,
no TTL, no size cap. The bundled data is small (26 modelos, 7
manuals, 200 normatives, 10 VAT catalogues, ~15 other TOMLs)
and immutable; eviction adds complexity without benefit. The
Repository owns its dict and exposes a `clear_cache()` method
for test-side resets.

**Q4 — Association mechanism. Decision: defer.** The first
iteration does not introduce typed `ResourceKey` cross-resource
references inside registry data; the existing string-based
`corpus_ref`, `legal_refs`, and `source_refs` fields stay as
strings. A follow-up ADR may add typed references once the
Repository surface is stable. Migrating data shapes alongside
the API migration would inflate the blast radius beyond what
the audit currently anticipates.

**Q5 — Lazy vs eager loading. Decision: per-Repository, default
lazy.** Each Repository's `get(key)` loads on demand and caches.
Two existing module-level eager loads (
`VAT_CATALOGUES_BY_YEAR` in `domain.vat._catalogue` and
`LIRPF_ART_85_IMPUTACION` in `domain.rental._imputacion_parameters`)
migrate to Repository.get calls at first use; the eager imports
disappear. The lazy default avoids registry-construction-time
file IO for resources the consumer never asks for.

**Q6 — Error model. Decision: introduce three top-level error
types that superclass the existing per-domain errors.**
`ResourceLoadError` is the base. `ResourceNotFoundError` covers
"the key does not resolve to any bundled file";
`ResourceValidationError` covers "the file exists but fails
Pydantic validation"; `ResourceBackendError` covers IO failures
during read. The existing per-domain error classes
(`RegistryLoadError`, `ManualParseError`, `NormativeParseError`,
`VatCatalogueError`, `DeadlineValidationError`,
`CategoryValidationError`, `UserProfileSchemaLoadError`,
`ApoderamientosCatalogueError`) become subclasses of the
appropriate top-level error. Existing `except` clauses continue
to work; new consumers can catch the top-level error if they do
not care about the domain.

**Q7 — Settings env-override placement. Decision: external.**
The `resources()` factory reads `load_settings()` once at
construction and passes the resolved roots to the three
env-overridable Repository constructors (manuals, normatives,
VAT catalogue). Settings remains the single env-override
surface; Repositories do not read environment variables
directly. The VAT catalogue field, currently declared in
Settings but unused in production, becomes the canonical input
to `VatCatalogueRepository` — closing the existing
inconsistency.

**Q8 — Singleton-resource convention. Decision: `K = None` plus
a `.singleton` convenience property.** Repositories that
represent a single resource (`vat_rate_tables`, `topics`,
`apoderamientos`, `user_profile_schema`, `recargo_bands`,
`legal_parameters`) define `K = type(None)` and expose
`.singleton -> T` as sugar over `get(None)`. The `get(None)`
form remains valid for code paths that prefer the uniform
Repository interface.

The migration sequence the plan should follow:

1. **Foundation.** Land `src/aeat/core/resources/` as a package
   (replacing the single-file module); land the
   `Repository[T, K]` base, the typed `ResourceKey` union, the
   `ResourceLoadError` hierarchy, the empty `ResourceRegistry`
   shell, and the `resources()` factory. Re-export the existing
   `packaged_data`, `bundled_path`, `as_path` from
   `_boundary.py` so the existing imports keep working. No
   consumer migrates yet.

2. **Singleton repositories.** Implement the eight singleton
   Repositories first because they are the simplest:
   `apoderamientos`, `user_profile_schema`, `topics`,
   `recargo_bands`, `vat_rate_tables`, `legal_parameters`, plus
   the two that already have eager loads to retire
   (`VAT_CATALOGUES_BY_YEAR`'s consumer chain and the rental
   `LIRPF_ART_85_IMPUTACION`).

3. **Year-keyed repositories.** Implement
   `holiday_calendars` (key = `int` year) and
   `category_profiles` (key = `int` year) and
   `vat_catalogues` (key = `int` year).

4. **Manual repository.** Implement `ManualRepository` with the
   composite `(manual_id, year, part)` key model. This is the
   richest key; it must satisfy `resolve_part_root`,
   `load_manual`, `load_section`, `iter_sections`, and
   `find_rules`.

5. **Normative repository.** Implement `NormativeRepository`
   with a singleton catalogue plus typed lookup methods
   (`find_reference`, `find_articulo`).

6. **Modelo repository (heaviest).** Implement
   `ModeloRepository` as a thin façade over
   `ValidatedRegistryAuthority`. Preserve the existing
   `default_registry_authority()` cache behind the Repository's
   Identity Map. Migrate the 5 separate `ValidatedRegistryAuthority.load(...)`
   construction paths to `resources().modelos`.

7. **Consumer migration, production.** Per the audit's 25-30
   production consumer modules, replace `load_*` imports with
   `from aeat.core.resources import resources`. Order: domain
   layer first (already self-contained), then application layer,
   then adapters layer, then entrypoints (CLI typer defaults
   last).

8. **Consumer migration, tests.** ~100 test modules migrate
   their `_REGISTRY_ROOT` constants and direct loader calls to
   `resources()`. Tests that override Settings continue to work
   because the factory reads Settings at the override point;
   conftest fixtures invoke `resources.cache_clear()` between
   cases to reset the Identity Map.

9. **Retirement.** Delete the per-module `_DEFAULT_*_ROOT`
   constants. Delete the per-module `@lru_cache` decorators
   (the Repository owns the cache now). Remove the public
   `load_*` re-exports from domain `__init__.py` files.

10. **Quality gate and structural guard.** Run ruff, ty, and
    pytest. Add a structural test that asserts the registry is
    the only resource-access surface in the project (greps for
    `bundled_path` and `_DEFAULT_*_ROOT` outside
    `core/resources/`).

11. **Release docs.** Update `RELEASING.md` if any new operator-
    facing surface change requires it; this is not expected
    because the Settings env-override surface is preserved.

## Rationale

The Repository-per-type registry is the only sketch that
preserves both static typing and a central registry surface.
The 31 loader functions map one-to-one onto Repository methods;
the cache surface consolidates from 20+ scattered decorators to
12 Repository-owned Identity Maps; the construction path
collapses from 5 sites to one factory.

The closed `Literal`-tagged taxonomy is justified by the
absence of any plugin-resource use case. The audit identified
zero entry-point-discovered resource consumers across the
codebase. A closed taxonomy is simpler, makes the registry
fields statically typed, and prevents accidental third-party
extension. Reopen the decision when a plugin-resource ADR
materialises.

Unbounded dict-based caching is justified by the size of the
bundled data. The largest single resource is the modelo
registry tree (~26 modelos × ~13 casillas each on average), and
the largest individual file is a 1 MB TOML. The total in-memory
working set after fully populating every Repository is in the
single-digit megabytes; eviction policies add complexity that
the data volume does not justify.

The three top-level error types layered above the existing
per-domain errors give consumers a typed hierarchy without
breaking the existing `except RegistryLoadError` /
`except ManualParseError` catches. This is a deliberately
additive shape.

The external-Settings placement preserves the current
operator-override seam (operators set `AEAT_MANUALS_ROOT=/path`,
the Settings field overrides the bundled default, the factory
hands the override to `ManualRepository`). The factory call is
cached at process scope; test code that mutates Settings must
call `resources.cache_clear()` to rebuild the registry with the
new override, which is a deliberate and visible test-side
invariant.

## Consequences

Every consumer of bundled data changes import shape from
`from aeat.domain.X import load_Y` to
`from aeat.core.resources import resources`. The diff is wide
(~125 files: 25-30 production + ~100 tests) but mechanical and
sliceable Repository-by-Repository. The corpus-registry-packaging
migration is the most recent precedent and its quality-gate
shape transfers directly.

The two existing module-level eager loads
(`VAT_CATALOGUES_BY_YEAR`, `LIRPF_ART_85_IMPUTACION`)
disappear. Consumers that import the eager value migrate to
`resources().vat_catalogues.all()` and
`resources().legal_parameters.get(...)` respectively. Module-
import time becomes faster (no eager TOML parse) but tests
that depended on the eager value being already loaded must call
`get` explicitly.

The five `ValidatedRegistryAuthority.load(...)` construction
sites collapse to one factory. The cached singleton at
`default_registry_authority()` becomes a wrapper around
`resources().modelos.authority` (or equivalent). Code that
imports `default_registry_authority` directly continues to work
through a thin shim that delegates to `resources().modelos` —
note that this is a one-line wrapper, not the kind of
shim/duplication forbidden by the architecture rule, because it
exists only to keep `import` paths backwards-compatible during
the migration. The shim is removed in the retirement step.

The Settings env-override seam preserves backwards compatibility
for operators with external corpus mirrors. The three
override-able fields (manuals, normatives, VAT catalogue) keep
their current env-var names and override semantics. The VAT
catalogue field becomes an actually-consumed Settings input,
closing the existing inconsistency where the field was declared
but not used in production.

The cache-clear surface (`resources.cache_clear()` and
`resources().clear()`) gives tests a uniform invalidation point.
Tests that override Settings now have a deterministic way to
rebuild the registry; the previous per-loader `@lru_cache.cache_clear()`
pattern (which most tests did not call) becomes one call. Test
flakiness around stale cache state should improve.

The error-type hierarchy is additive. Existing `except`
clauses for per-domain errors continue to catch. New consumers
can catch `ResourceLoadError` for any failure or narrow to
`ResourceNotFoundError` / `ResourceValidationError` /
`ResourceBackendError` as needed. No existing test changes its
expected exception type.

Future plug-in resource discovery, typed cross-resource
references inside data, and write-side Repositories for
mutable persisted state remain possible future ADRs. None of
them are decided here; the surface introduced is deliberately
minimal and read-only.

The build-time consequence is a new `src/aeat/core/resources/`
package replacing the single-file `src/aeat/core/resources.py`
module. The hatchling wheel-build target unchanged; the new
package directory rides along inside `packages = ["src/aeat"]`.
The wheel-bundling tripwire test continues to pass because the
data layout under `src/aeat/_data/` is unaffected.
