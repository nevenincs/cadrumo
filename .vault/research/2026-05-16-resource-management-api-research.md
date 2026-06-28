---
tags:
  - '#research'
  - '#resource-management-api'
date: '2026-05-16'
modified: '2026-05-16'
related:
  - "[[2026-05-15-corpus-registry-packaging-adr]]"
  - "[[2026-05-15-corpus-registry-packaging-research]]"
  - "[[2026-05-15-corpus-registry-packaging-plan]]"
---



# `resource-management-api` research: centralised typed resource registry over the corpus-registry boundary

The corpus-registry-packaging feature landed a single resource-
access boundary at `src/aeat/core/resources.py` exposing
`packaged_data`, `bundled_path`, and `as_path`. Each domain module
that consumes bundled data continues to define its own
`_DEFAULT_*_ROOT` module-level constant, its own loader function,
and its own `@lru_cache` decorator. The result is correct under
the new packaging contract but distributes the resource-access
policy across ~13 modules: every taxonomy decision, every cache
sizing decision, every error-handling convention, and every
identity-map invariant lives at each call site.

This research surveys industry patterns for centralising that
policy behind one typed application surface, evaluates them
against this codebase's constraints (Pydantic v2 mandate, no
mocks rule, hexagonal layering, single-resource-boundary rule),
and proposes a leading-candidate pattern with two runner-up
alternatives. The output feeds the next ADR. Scope is fixed by
the user to read-only bundled resources; mutable persisted state
(secure-storage write surface, `var/`, ledgers) is excluded.

## Findings

### 1. Inventory of the existing scattered surface

Thirteen production modules define their own resource entry point.
Each pairs a `load_<thing>(...)` public function with an
`@lru_cache(maxsize=<n>)` private cached inner function, sometimes
keyed on a Path string, sometimes on a fingerprint tuple
(`path, size, mtime_ns`). The current inventory:

The calculations-registry surface in
`aeat.domain.calculations.registry._loader` ships
`load_modelo_file(path) -> ModeloDefinition` (maxsize=256),
`load_modelo_directory(directory) -> ModeloDefinition`
(maxsize=64), `load_catalogue_file(path) -> RegistryCatalogues`
(maxsize=128), `load_legal_parameters_only(root) -> Mapping[str, LegalParameter]`
(no own cache, defers to the inner catalogue cache), and
`load_registry_tree(root) -> tuple[modelos, RegistryCatalogues]`
(maxsize=32). Above that sits
`aeat.domain.calculations.registry._authority.ValidatedRegistryAuthority`
(an `@dataclass(slots=True)` aggregating modelos + catalogues +
a `RegistryValidator`), itself built behind
`_load_authority(root, source_root)` (maxsize=16) and exposed
through the `@cache`d singleton `default_registry_authority()`.

The manuals surface in `aeat.domain.manuals._loader` ships
`resolve_part_root(*, manual_id, year, part, settings=None) -> Path`,
`load_manual(*, manual_id, year, part, settings=None) -> Manual`
(maxsize=128), `load_section(part_root, section_ref) -> Section`
(maxsize=2048), `load_catalogue(*, settings=None) -> ManualCatalogue`
(maxsize=1024), plus iterator and finder helpers (`iter_sections`,
`find_rules`). The normatives surface in
`aeat.domain.normatives._loader` ships
`load_catalogue(*, settings=None) -> NormativeCatalogue`
(maxsize=16) plus lookup helpers under `_lookup.py`.

The VAT subsurface ships `load_vat_catalogue(path) -> VATCatalogue`
(maxsize=32), `load_vat_catalogues(root) -> Mapping[int, VATCatalogue]`
(maxsize=8), and `load_vat_rate_table(path) -> Mapping[EUMemberState, tuple[VATRate, ...]]`
(maxsize=16). The deadlines subsurface ships `load_recargo_bands`
(maxsize=16), `load_holiday_calendar(year)` (maxsize=64), and the
`DeadlinesEngine` aggregate class that internally calls
`ValidatedRegistryAuthority.load(...)`. Categories ships
`load_category_profile_file` (maxsize=32) and
`load_category_profile_registry` (maxsize=8) plus
`resolve_category_profiles(year)`. User-profile ships
`load_user_profile_schema(path=DEFAULT_USER_PROFILE_SCHEMA_PATH) -> ProfileSchemaDefinition`
(maxsize=16). Topics ships `load_topic_catalogue(root=None) -> TopicCatalogue`
(maxsize=16). Apoderamientos ships `load_default_catalogue(path=None) -> ApoderamientosCatalogue`.

Patterns visible in the surface:

The fingerprint-keyed cache (`path, size, mtime_ns`) is the
dominant pattern for leaf-file loaders (`load_modelo_file`,
`load_catalogue_file`, `load_section`). The path-string-keyed
cache is used for directory aggregates (`load_registry_tree`,
`load_vat_catalogues`). The pure no-argument `@cache`d singleton
is used for the registry authority. Three Settings-mediated
loaders (manuals, normatives, registry/_corpus) read their root
from the `Settings` env-overridable field; the other ten loaders
take a `root: Path = _DEFAULT_*` parameter where `_DEFAULT_*` is
a module-level `bundled_path(...)` call. The two patterns coexist
because manuals and normatives have an operator-override use case
(point at an external mirror) and the rest do not.

The cache sizing is heuristic: maxsize values range from 8 to
2048 with no apparent rationale captured in code or comments.
Some loaders are cached at two levels (`load_vat_catalogues`
caches the directory aggregate AND its `load_vat_catalogue` leaf
cache). The cache surfaces also do not implement a uniform
invalidation surface; in production they are process-lifetime by
construction because the bundled data is immutable per install,
but in tests that override Settings the lack of an invalidation
hook means stale caches leak across test cases unless the test
manually constructs the loader.

The error model is per-domain: `RegistryLoadError`,
`ManualParseError`, `NormativeParseError`, `VatCatalogueError`,
`DeadlineValidationError`, `CategoryValidationError`,
`UserProfileSchemaLoadError`, `ApoderamientosCatalogueError`.
Each loader wraps `tomllib.TOMLDecodeError`, `OSError`, and
`pydantic.ValidationError` into its domain-specific error type.

### 2. Repository pattern (Evans, DDD)

Eric Evans's Repository pattern (`Domain-Driven Design`, 2003)
abstracts persistence behind a typed collection-like interface:
`Repository[T, ID]` with operations like `get(id) -> T`,
`find(criteria) -> Iterable[T]`, `add(entity)`, `remove(entity)`.
Spring Data popularised the contract in Java via
`@Repository` interfaces and method-name-derived queries.
In Python the closest equivalents are SQLAlchemy's `Session.query`
+ ORM mapper combination and the
`returns.contrib.repository` micro-library.

For read-only static data the write side (`add`, `remove`) is
empty. The remaining surface is `get(id) -> T` plus `find` for
queries. The typing works cleanly: one `Repository[Manual, ManualKey]`,
one `Repository[VATCatalogue, int]` (year-keyed), one
`Repository[Modelo, ModeloId]`, etc. Each repository encapsulates
its own loader and cache. The Repository pattern is the canonical
choice when the resource type is closed (a known finite set of
domain types) and each type benefits from type-specific find
methods.

Tradeoffs for this codebase: clean typed surface with one
interface per resource type aligns with the Pydantic v2 mandate
and hexagonal layering (each Repository can live in its domain
package while the central registry assembling them lives in
`core/`). The downside is that thirteen interfaces (one per
resource type) add API surface area; consumers must know which
Repository to import. The compositional opposite is one big
registry where consumers ask by typed key — covered in §3.

### 3. Service Locator / Application Context

Fowler's Service Locator pattern (`PoEAA`, 2002) centralises a
typed registry of services that consumers ask for by key. Spring
Framework's `ApplicationContext` (Java) is the canonical example;
in the Python world, FastAPI's `Depends` mechanism, Flask's
application factory + extensions, and Django's `apps` registry
implement variants. Fowler subsequently published a critique
(`Inversion of Control Containers and the Dependency Injection
Pattern`, 2004) preferring constructor injection over locator
calls because the locator hides dependencies from a class's
public surface.

For read-only resources, the locator's hidden-dependency problem
softens significantly: every consumer of the resource API is
asking for read-only data, not requesting a runtime collaborator
that could be swapped. The hidden dependency is the bundled data
shape, which is invariant across the process lifetime and
asserted by the existing locator-leaf-presence test.

A service-locator-shaped API for this codebase could look like
`ResourceLocator.request(kind: ResourceKind, **selector) -> Resource`
where `kind` is an enum and `selector` is a typed `kwargs`
matching the resource's identity. The return type is then a
discriminated-union model — see §7. Tradeoffs: one API surface
to learn, no per-resource Repository import; but loss of compile-
time type assurance (the `kind` enum and the return type are
linked at runtime via the discriminator, not statically). Python
3.13's type narrowing on `TypeIs` predicates partially recovers
the assurance.

### 4. Identity Map (Fowler, PoEAA)

Identity Map caches loaded objects by their identity so the same
identifier resolves to the same in-memory object across the unit
of work. SQLAlchemy's `Session` implements an Identity Map per
session; Hibernate (Java) does the same.

For read-only static data the Identity Map collapses to a
process-lifetime memoisation map keyed on resource identity. The
existing `@lru_cache` decorators are an implicit Identity Map per
loader. A centralised Identity Map at the API surface would
unify the per-loader caches and give consumers a single
invalidation point (useful in tests that override Settings).

The Identity Map pattern is not an alternative to Repository or
Service Locator; it is a complementary mechanism that sits inside
either. A clean design uses both: Repository (or Locator) for the
typed access surface; Identity Map for the cache.

### 5. Resource-Oriented Architecture and SDK resource models

ROA (Richardson, `RESTful Web Services`, 2007) defines resources
as first-class typed entities accessed via a uniform interface.
The boto3 AWS SDK adopts the pattern in-process: `s3.Bucket(name)`
returns a typed `Bucket` resource that exposes typed sub-resources
and methods. The Stripe Python SDK uses a similar resource-class
pattern.

The ROA fit for in-process Python resources is partial. The
`Resource(id) -> typed instance with sub-resources and methods`
pattern works well when there is a natural hierarchical
relationship between resources (e.g. `s3.Bucket.Object`). For
this codebase the hierarchies are shallow (a `Manual` has
`Section`s; a `VATCatalogue` has `VATCategory` entries). The
uniform-interface aspect is more interesting: every resource
type would respond to the same small set of methods (`get`,
`list`, `find`, `iter`). The downside is that introducing a base
resource class often pulls callers into a metaclass / framework
pattern that the rest of the codebase does not use.

### 6. DI containers in Python

Five mature Python DI containers exist:
`dependency-injector` (declarative providers, has its own DSL),
`punq` (small, type-hint-based), `lagom` (type-hint-based,
zero-config), `returns.contrib.containers` (functional flavour),
and FastAPI's `Depends` (request-scoped, not application-scoped).

For a codebase that currently uses no DI framework, introducing
one for a read-only resource registry is heavy. DI containers
shine when the dependency graph is dynamic (request-scoped,
test-overridable, environment-specific). For static resources
that are computed once per process from the bundled tree, the
container's runtime resolution is overhead without benefit. The
Pydantic Settings already plays the role of an environment-aware
configuration container for the three env-overridable corpus
roots.

Conclusion: DI containers are not the right fit. The new API
should not require a container; tests can override the API via
Settings (for env-overridable resources) or via direct
construction (for everything else).

### 7. Pydantic-discriminated-union resource taxonomy

Pydantic v2 supports tagged-union models via
`Annotated[Union[ModelA, ModelB, ModelC], Field(discriminator="kind")]`.
The taxonomy of resource types fits the pattern naturally: a
top-level `Resource` is a discriminated union of `Manual`,
`NormativeCatalogue`, `VATCatalogue`, `Modelo`, `HolidayCalendar`,
`CategoryProfileRegistry`, `TopicCatalogue`, `ProfileSchemaDefinition`,
`ApoderamientosCatalogue`, `RecargoBands`, `VATRateTable`,
`LegalParameter` (plus possibly more), each tagged by a
`kind: Literal["manual", "normative_catalogue", ...]` field.

The discriminator gives the API a Pydantic-validated taxonomy
without writing a separate enum (the Literal values do the work).
Combined with a `ResourceKey` discriminated union the load
surface becomes:

```
Resource = Annotated[
    Union[Manual, NormativeCatalogue, VATCatalogue, ...],
    Field(discriminator="kind"),
]

ResourceKey = Annotated[
    Union[ManualKey, NormativeCatalogueKey, VATCatalogueKey, ...],
    Field(discriminator="kind"),
]
```

This composes cleanly with the Repository pattern: a typed
`Repository[T, K]` per variant, all uniformly accessible via the
discriminated union. It also composes with the Service Locator:
`locator.request(key: ResourceKey) -> Resource` with the return
type narrowed by the discriminator.

### 8. Caching strategies and the cache-invariants of static data

`functools.lru_cache` (stdlib): identity-keyed via call-argument
hashing; size-bounded; thread-safe by default; no introspection
of the underlying file mtime. Suitable when the cache key is the
argument tuple and arguments fully determine the result.
`cachetools` extends to LFU, TTL, and arbitrary keying functions
including thread-safe variants. `aiocache` adds async-aware
multi-backend (memory, Redis, memcached). `weakref.WeakValueDictionary`
implements a weak-reference identity map.

Cache invariants for read-only bundled static data:

The bundled tree is immutable per install. The data does not
change at runtime; `mtime_ns` is captured at build time and never
mutates. A correct cache for this scenario is therefore:

(a) Keyed on a stable identity (a Pydantic key model or its hash).
(b) Process-lifetime (no eviction needed for correctness; eviction
    only matters for memory pressure).
(c) No invalidation surface required for production; tests that
    override Settings need a `clear()` hook.

The existing `(path, size, mtime_ns)` fingerprint is a poor
match: it adds a `stat()` call per get to compute the key. For
truly immutable bundled data the fingerprint is redundant; the
path alone (resolved) is sufficient. The current pattern protects
against tests that mutate corpus files between test cases, which
the new API can address explicitly via a `clear()` method.

Recommendation for the ADR: process-lifetime memoisation with a
deterministic key derived from the typed `ResourceKey`. Either
`functools.cache` (no size bound) or `cachetools.LRUCache` with
a generous bound (memory bounds rarely matter for ~26 modelo
records + ~7 manuals + ~200 normatives + small TOMLs). The cache
exposes a `clear()` method on the API surface.

### 9. Resource association

Cross-resource references in this codebase already exist as
string identifiers inside the data: a registry casilla's
`source_refs` points at a normatives id; a registry binding
declares a `corpus_ref` string that the validator joins against
`source_root`; a manual section references its `manual_id`.

Industry patterns for associations:

SQLAlchemy relationships materialise foreign keys into typed
attributes on the ORM model (lazy or eager). GraphQL federation
uses external typed identifiers across services. IPLD uses
content-addressed CIDs as universal identifiers.

For an in-process resource API, two primitives are sufficient:

(a) A typed `ResourceKey` Pydantic model that any cross-resource
    reference uses. The legal-parameter catalogue declares its
    citations as `LegalCitationKey` values, not bare strings.

(b) A `resolve(key: ResourceKey) -> Resource` method on the API
    so consumers can dereference a foreign key without knowing
    which Repository owns it.

The current codebase's `corpus_ref` strings would migrate from
bare strings to a typed `SourceReferenceKey` field whose
`resolve()` method goes through the central API. This is a
substantial migration but it eliminates an entire class of broken-
link errors at validation time.

For the first iteration of the API, association can be deferred:
the typed Key + resolve mechanism is the most valuable affordance;
relationships between resources can stay as opaque string
references until a follow-up adds them.

### 10. Backend abstraction over importlib.resources

Spring's `ResourceLoader` indirects between `ClassPathResource`,
`FileSystemResource`, `UrlResource`, `ServletContextResource` via
a URI scheme (`classpath:`, `file:`, `http:`). The pattern lets
the same `Resource` interface load from multiple backends.

For this codebase the backend is single: `importlib.resources`
via the corpus-registry-packaging boundary at
`aeat.core.resources.packaged_data`. Multi-backend is unlikely
to ever be needed for read-only bundled data. The right
architecture is therefore the inverse: the new API uses the
existing locator as its only backend; the backend is encapsulated
behind the API surface but not exposed for indirection.

If a future need arises (e.g. an external corpus mirror via the
Settings env-override, or a Drive-mounted alternative location),
the API can grow a per-resource-type override that consults
Settings first and falls back to the bundled root. The manuals
and normatives loaders already do this; the new API absorbs
their override pattern without externalising a backend abstraction.

### 11. Failure handling

Industry conventions split between:

(a) `Optional[T]` returns: callers test `is None`. Used by Rust's
    `Result`, Scala's `Option`, Java 8's `Optional`. Forces the
    caller to think about absence. Less ergonomic in Python where
    the surrounding code may use exceptions.

(b) Raising domain exceptions: caller catches a typed error.
    The default Python convention. The existing per-domain error
    classes (`RegistryLoadError`, `ManualParseError`, etc.)
    follow this convention.

(c) Lazy validation: the resource model validates on construction
    (Pydantic's default), but the loader returns the model only
    if validation passes; otherwise raises.

The new API should keep convention (b) + (c) — they match the
codebase's existing surface and the Pydantic v2 default. A single
top-level `ResourceLoadError` with typed subclasses per resource
kind (or per failure mode: `ResourceNotFoundError`,
`ResourceValidationError`, `ResourceBackendError`) gives consumers
a typed hierarchy without a separate exception per loader.

### 12. Three concrete API sketches

The following three sketches are evaluated against the codebase's
constraints. Each is shown at module-import level; cache details
are deferred to §8's recommendation.

**Sketch A — Repository-per-type registry**

```python
class Repository[T, K]:
    def get(self, key: K) -> T: ...
    def find(self, **criteria) -> Iterable[T]: ...
    def all(self) -> Iterable[T]: ...
    def clear_cache(self) -> None: ...

class ResourceRegistry:
    modelos: Repository[Modelo, ModeloKey]
    manuals: Repository[Manual, ManualKey]
    normatives: Repository[NormativeCatalogue, NormativeKey]
    vat_catalogues: Repository[VATCatalogue, int]  # keyed by year
    vat_rate_tables: Repository[VATRateTable, None]  # singleton
    holiday_calendars: Repository[HolidayCalendar, int]
    category_profiles: Repository[CategoryProfileRegistry, int]
    topics: Repository[TopicCatalogue, None]
    user_profile_schema: Repository[ProfileSchemaDefinition, None]
    apoderamientos: Repository[ApoderamientosCatalogue, None]
    recargo_bands: Repository[RecargoBands, None]
    legal_parameters: Repository[Mapping[str, LegalParameter], None]
```

Pros: most typed surface; each Repository encapsulates its
loader; clean migration (existing `load_*` functions become
Repository methods); easy to test in isolation; aligns with the
Pydantic v2 mandate.

Cons: thirteen Repository properties to compose on the registry;
introduces a small framework (the `Repository[T, K]` base class
or Protocol); singleton resources (no key) require a `K = None`
or `K = Singleton` convention.

**Sketch B — Single-method discriminated locator**

```python
class ResourceLocator:
    def request(self, key: ResourceKey) -> Resource: ...
    def find(self, kind: ResourceKind, **criteria) -> Iterable[Resource]: ...
    def clear_cache(self) -> None: ...
```

`ResourceKey` is a discriminated union of typed keys (one per
resource kind); `Resource` is the discriminated union of typed
models. Type narrowing happens via the discriminator at the
boundary.

Pros: minimal surface (three methods total); consumers learn one
API; cross-resource references are uniform; future-proof for
adding resource kinds.

Cons: weaker static typing (return type is the union, not the
specific variant); requires consumers to narrow via discriminator
or `isinstance`; less idiomatic Python (the type system rewards
explicit typed methods over enum-dispatched ones).

**Sketch C — Resource model with `load` classmethod**

```python
class Resource(BaseModel, ABC):
    kind: str

class Manual(Resource):
    kind: Literal["manual"] = "manual"
    @classmethod
    def load(cls, key: ManualKey) -> Manual: ...

class VATCatalogue(Resource):
    kind: Literal["vat_catalogue"] = "vat_catalogue"
    @classmethod
    def load(cls, key: int) -> VATCatalogue: ...
```

Pros: most-Pythonic dispatch (`Manual.load(key)`); discoverable;
no separate registry; each resource model owns its loader.

Cons: no central place to clear all caches; cross-resource
queries (`find_all_referencing(...)`) have no natural home; the
existing `ValidatedRegistryAuthority` aggregate doesn't fit this
shape cleanly; tests that want to override the backend must
monkey-patch each model class.

## Pattern recommendation

**Leading candidate: Sketch A (Repository-per-type registry)
with an internal Identity Map cache.**

Rationale: it is the only sketch that preserves both static
typing (each Repository is `Repository[T, K]` with concrete `T`
and `K`) and a central registry surface (one
`ResourceRegistry` instance to import). The migration path is
mechanical: every existing `load_*` function becomes a
Repository method; every existing `@lru_cache` decorator
collapses into the Repository's internal Identity Map; every
existing `_DEFAULT_*_ROOT` constant disappears because the
Repository owns the root resolution via the corpus-registry
locator. The registry instance lives at `aeat.core.resources` as
the single resource-access boundary the architecture rule
mandates.

Specifically:

```python
# aeat/core/resources/__init__.py
@dataclass(slots=True, frozen=True)
class ResourceRegistry:
    modelos: ModeloRepository
    manuals: ManualRepository
    # ... etc

@lru_cache(maxsize=1)
def resources() -> ResourceRegistry:
    """Process-wide resource registry; cached at first call."""
    return ResourceRegistry(...)
```

Consumers call `resources().manuals.get(ManualKey(id=ManualId.IRPF, year=2025))`
instead of `load_manual(manual_id=ManualId.IRPF, year=2025)`.
The migration replaces ~13 imports of `load_*` functions with one
import of `resources`.

**Runner-up #1: Sketch B (single-method discriminated locator).**
Lower migration cost (single import surface) but weaker static
typing. Worth revisiting if the resource taxonomy explodes beyond
20 kinds; today's 13 do not justify the type-erasure trade.

**Runner-up #2: Hybrid (Sketch A + Sketch B at the top).** The
`ResourceRegistry` exposes typed Repository attributes (Sketch A)
AND a `request(key: ResourceKey) -> Resource` shortcut (Sketch B)
for cross-resource resolution. Implementation-wise it adds a
thin wrapper around Sketch A. Worth considering for the ADR if
the cross-resource resolve use case is significant.

**Rejected: Sketch C.** No central cache-clear hook;
cross-resource queries homeless; tests must monkey-patch.

## Open questions for the ADR

The ADR must decide:

1. **Resource taxonomy enumeration**: is the set of resource
   kinds closed (Python `Literal`s in the discriminator) or
   open (entry-point-discovered)? The codebase has 13 known
   kinds. Closed is simpler; open allows future plug-ins. Default:
   closed; reopen the decision when a plugin use case materialises.

2. **Cache key strategy**: typed `ResourceKey` Pydantic model
   (validated, hashable) versus tuple-of-primitives versus
   raw string. Default: typed `ResourceKey` per kind, with
   `model_config = ConfigDict(frozen=True)` so the key is
   hashable for cache use.

3. **Cache backend**: `functools.cache` (unbounded) versus
   `cachetools.LRUCache` (bounded). Default: `functools.cache`
   because the bundled tree is small and immutable; bounded LRU
   adds eviction complexity without benefit. Reopen if memory
   profiles surface pressure.

4. **Association mechanism**: typed `ResourceKey` references vs
   string references. Default for first iteration: keep existing
   string references in the data; the API does not enforce typed
   association until a later ADR.

5. **Lazy vs eager loading**: do Repositories load all their
   resources at first access (eager) or per `get(key)` call (lazy)?
   Default: lazy. Some Repositories already eager-load
   transitively (the modelos registry loads catalogues alongside);
   the eager-vs-lazy choice can be per-Repository.

6. **Error model**: single `ResourceLoadError` base with three
   typed subclasses (`ResourceNotFound`, `ResourceValidationError`,
   `ResourceBackendError`) versus retaining the per-domain
   errors. Default: introduce the three top-level errors as
   superclasses of the existing per-domain errors; downstream
   code can catch either layer.

7. **Settings env-override placement**: today the manuals,
   normatives, and vat-catalogue roots have Settings fields.
   Should the API absorb the env-override into the Repository
   constructor (each Repository reads its root from Settings)
   or keep Settings as an external concern that the registry
   constructor reads? Default: Settings stays external; the
   `resources()` factory reads Settings once and passes resolved
   roots to each Repository.

8. **Singleton-resource convention**: how do Repositories that
   represent a single resource (e.g. `vat_rate_tables`,
   `topics`, `apoderamientos`) expose `get`? Default: typed
   `K = None` plus a convenience `.singleton` property that
   wraps `get(None)`.

## Architectural risks

The migration touches ~13 production modules plus their tests.
Risk inventory:

(a) **Locked taxonomy**: closing the discriminator at design
    time means any future resource kind requires editing the
    union. Mitigation: the codebase already has 13 known kinds
    and no plugin-resource story; an open taxonomy is speculative.

(b) **Indirection overhead**: every loader call goes through
    Repository.get instead of `load_*` directly. Microbenchmark:
    one attribute lookup + one method call per resource get;
    negligible compared to TOML parsing and pydantic validation
    (the actual loaders' dominant cost).

(c) **Migration cost**: ~13 production modules need their loader
    imports rewritten plus ~90 test modules. The diff is
    mechanical and follows the same shape as the corpus-registry
    test migration. Estimated 1-2 days for a focused executor.

(d) **Test-fixture coupling**: tests that today construct
    Repositories or override Settings need to also clear the
    central registry cache between cases. Mitigation: the
    `resources.clear()` method handles this; conftest fixtures
    invoke it.

(e) **Registry-authority duplication**: `ValidatedRegistryAuthority`
    is an aggregate that conceptually fits as
    `resources().modelos` but its `validate_*` methods and
    `snapshot()` cache exceed the Repository surface. The ADR
    must decide whether the authority becomes the modelos
    Repository or remains a wrapper around it. Recommendation:
    keep the authority; the Repository delegates `get` to the
    authority's existing methods and the authority owns its
    validator + snapshot caches.

(f) **Pydantic key models add a small modelling overhead**: each
    of the 13 resource kinds gains a typed key model. Most are
    trivial (`int`, `None`, or a two-field tuple); a handful
    (manuals, modelos) have richer keys. The model effort is
    one-time and the type assurance is durable.

## Recommendation forward

The ADR should ratify Sketch A (Repository-per-type registry
with an Identity Map cache and a top-level `resources()` factory
in `aeat.core.resources`) as the architectural pattern. The 13
loaders fold in mechanically; the existing
`ValidatedRegistryAuthority` becomes the modelos Repository's
backing aggregate; cache management consolidates behind one
`clear()` method; the Settings env-override seam stays external
and is read once at registry construction.

The ADR should leave open the cross-resource association
mechanism (open question 4) and the entry-point plugin extension
(open question 1) for a follow-up; both can land later without
re-deciding Sketch A.

The plan should sequence the migration as: introduce the
Repository base + ResourceRegistry alongside the existing
loaders; migrate Repositories one kind at a time with each
landing behind its own commit; retire the per-module `load_*`
functions and their `@lru_cache` decorators last; close with the
quality gate and a structural test that asserts the registry is
the only resource-access surface in the project.
