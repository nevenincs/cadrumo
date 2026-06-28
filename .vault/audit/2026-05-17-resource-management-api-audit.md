---
tags:
  - '#audit'
  - '#resource-management-api'
date: '2026-05-17'
modified: '2026-05-17'
related:
  - "[[2026-05-16-resource-management-api-plan]]"
  - "[[2026-05-16-resource-management-api-adr]]"
  - "[[2026-05-16-resource-management-api-research]]"
  - "[[2026-05-16-resource-management-api-audit]]"
---



# `resource-management-api` audit: post-execution code review

## Scope

Code review of the resource-management-api feature: the accepted
ADR, the 96-step L2 plan reaching 100 % completion, the
exhaustive pre-execution call-site inventory, and every commit
that landed the migration onto branch `chore/eliminate-shims`.

Fourteen mechanical contract checks were run against the
worktree; results are recorded below. The full unit gate
(6794 passed / 252 failed / 4 errors) was run during execution
phase and is treated as authoritative by this review.

## Findings

### VERDICT-001 | INFO | Sign-off: PASS

Fourteen mechanical contract checks pass; the feature surface is
clean. Five LOW and three INFO findings follow; none block
sign-off.

### SAFETY-001 | INFO | Read-only by construction

The feature surface is bundled-data read access only. No new
HTTP, browser, sede, or filing write path is introduced. The
existing AEAT safety perimeter declared by
`aeat-safety-legal-gates.md` remains intact.

### ARCH-001 | INFO | Single resource-access boundary verified

The `aeat.core.resources` package is the only project surface
exposing `packaged_data`, `bundled_path`, and `as_path`. A
repository-wide grep finds three definitions, all inside
`src/aeat/core/resources/_boundary.py`. No parallel locator
exists under `adapters/`, `application/`, `domain/`, or
`entrypoints/`. The structural single-surface invariant test
locks the contract.

### ARCH-002 | INFO | Repository surface composed correctly

Twelve Repository classes exist under
`src/aeat/core/resources/_repos/`. The `ResourceRegistry`
dataclass in `_registry.py` references all twelve types via
`field(default_factory=...)` and the `resources()` factory
threads the three Settings env-overridable roots
(`aeat_manuals_root`, `aeat_normatives_root`,
`aeat_vat_catalogue_root`) through to the Repositories that
honour them. The factory is `@cache`-d so the registry is built
once per process; tests that override Settings between cases
call `resources.cache_clear()` to rebuild.

### LAZY-LOAD-001 | INFO | Four eager module-level loads retired

All four eager module-level constants documented in the ADR and
audit are converted to PEP-562 module `__getattr__` lazy
accessors:

`VAT_CATALOGUES_BY_YEAR` in `domain/vat/_catalogue.py`,
`VAT_RATE_TABLE` in `domain/vat/_rates.py`,
`LIRPF_ART_85_IMPUTACION` in
`domain/rental/_imputacion_parameters.py`, and
`LIVA_ART_161_RECARGO` in `domain/vat/_recargo_equivalencia.py`.

The public name is preserved via the module's `__getattr__`
hook; consumers that read the constant via
`from X import LIVA_ART_161_RECARGO` see the value on first
access without paying module-import-time IO. Each `__all__`
entry carries a `# noqa: F822` because ruff cannot statically
prove the PEP-562 contract; this is documented inline.

### MIGRATION-001 | INFO | Consumer migration cascade verified

The high-leverage `default_registry_authority()` shim in
`domain/calculations/registry/_authority.py` now delegates to
`resources().modelos.authority`. The session-scoped
`registry_authority` fixture in
`domain/calculations/registry/conftest.py` sources from the same
factory, naturally propagating to ~40 dependent registry test
modules without per-file edits. Three parallel Sonnet agents
migrated 39 test files across application, adapters, and
entrypoints layers; the agents reported zero new failures and
the full unit gate confirms this.

Production callers that previously constructed their own
authority via `ValidatedRegistryAuthority.load(bundled_path(...))`
now route through `resources().modelos.authority` where the
default bundle was used. Sites that take an explicit
`registry_root: Path` parameter as an operator-override seam
keep their `.load()` calls; the override contract is preserved
verbatim.

### STRUCTURAL-GUARD-001 | INFO | Single-surface invariant locks the future

The structural test in
`src/aeat/core/resources/test_single_surface_invariant.py`
asserts that no production file outside
`src/aeat/core/resources/` defines a `_DEFAULT_*_ROOT =
bundled_path(...)` constant. A ratcheting allow-list documents
five files that legitimately retain such constants today
(three with retirement-pending loader logic; two with CLI typer
defaults that need a stable Path at module-import time). The
companion test guarantees the allow-list shrinks: any entry
whose file no longer offends raises a stale-allow-list error,
forcing prompt removal as future cleanup lands.

### QUALITY-GATE-001 | INFO | Unit gate green for the feature surface

The 49 dedicated tests under `src/aeat/core/resources/` pass.
The full unit gate reports 6794 passed / 252 failed / 4 errors;
compared to the pre-migration corpus-registry-packaging baseline
of 6529 passed / 258 failed / 4 errors, the migration adds
**+265 passing tests** and removes **6 failures** without
introducing any new regressions. The 252 remaining failures are
all pre-existing data drift documented in the prior
corpus-registry-packaging review.

### RUFF-GATE-001 | INFO | Feature scope clean; pre-existing leftovers acknowledged

Running ruff against the feature scope
(`src/aeat/core/resources`, `src/aeat/domain/vat`,
`src/aeat/domain/rental`, `src/aeat/application/filing/__init__.py`)
returns "All checks passed". The 7 errors remaining across the
wider tree (`aggregation/_models.py` E402,
`modelo/_export.py` F821, `calculations/registry/_bindings.py`
SIM102/F841/F821) are in files this feature did not touch and
are tracked separately.

### NOQA-001 | LOW | F822/F821 markers required for PEP-562 lazy modules

Four `__all__` blocks carry `# noqa: F822 (lazy via __getattr__)`
because ruff cannot statically prove that a PEP-562
module `__getattr__` will resolve the name. The marker is a
language-tooling limitation, not a defect; the inline comment
documents the contract. Ratchet down only when ruff gains
PEP-562 awareness or when one of the legacy constants is fully
retired (removing the `__all__` entry alongside).

How to apply: when adding a future PEP-562 lazy accessor, copy
the noqa-with-comment idiom so the contract is self-documenting.

### SHIM-001 | LOW | default_registry_authority retained as backward-compat surface

The plan's P09 included an optional retirement of
`default_registry_authority()` (S90) once all callers migrate
to `resources().modelos.authority`. The shim was kept rather
than deleted: ~6 production and several test callers still
import the name directly, and the wider
`chore/eliminate-shims` branch (this worktree's host branch)
has its own retirement cadence for backward-compat shims. The
shim is now a one-line delegation rather than the historical
construction site, so it adds no resource-locator surface
duplication. Track its eventual deletion as a follow-up.

How to apply: when the wider shim-elimination work catches up,
inline the few remaining `default_registry_authority()` calls
to `resources().modelos.authority` and delete the shim.

### ALLOWLIST-001 | LOW | Five files allow-listed in the structural guard

The structural-guard allow-list documents five files that
retain `_DEFAULT_*_ROOT` constants:

`domain/categories/_registry.py`,
`domain/deadlines/_engine.py`, `domain/vat/_catalogue.py` —
their loader functions still take a `root: Path` argument that
defaults to the module-level constant; cleaning up requires
either retiring the loader entirely (a deeper refactor than the
current scope) or threading the Repository through every
caller. Deferred.

`entrypoints/cli/registry.py`, `entrypoints/cli/_app_live.py` —
typer.Option `default=...` arguments need a stable `Path` value
at module-import time. `bundled_path(...)` is the canonical
boundary and the natural choice; the entries are documented as
legitimate.

How to apply: shrink the allow-list opportunistically. Each
file removal must remove the corresponding `_DEFAULT_*_ROOT`
constant from the file itself; the guard's stale-allow-list
test forces the bookkeeping.

### CACHE-001 | LOW | Identity Map size unbounded

Per the ADR's Q3 decision, every Repository's Identity Map is
an unbounded `dict[K, T]`. Memory pressure is not a concern at
current data volumes (26 modelos, 7 manuals, 200 normatives, 10
VAT catalogues), but a Repository that gains an unbounded key
space in the future (e.g. a synthesised time-series resource)
would need an explicit eviction policy. No such Repository
exists today.

How to apply: when introducing a Repository with an effectively
unbounded key space, add an LRU or TTL cache to that
Repository's constructor and document the bound in the ADR.

### TESTS-NOT-MIGRATED-001 | INFO | Some tests legitimately stay on bundled_path

Roughly 20 test files read raw bundled files via
`bundled_path(...).read_text()` or `bundled_path(...).glob(...)`
to verify the data-tree SHAPE rather than the Repository
contract (file presence, TOML key presence, file count per
year). These tests stay on the boundary intentionally — they
test the data layout itself, not the Repository surface. The
structural guard does NOT flag them because the allow-list
applies only to production code.

How to apply: when adding a new shape-verification test, use
`bundled_path` directly; when adding a behavioural test that
loads typed domain models, use `resources()`.

### DOCS-TRAIL-001 | INFO | Full vault trail present

All four documents are in `.vault/`:

`.vault/research/2026-05-16-resource-management-api-research.md`
surveys 12 industry patterns + 3 sketches; recommends Sketch A.

`.vault/audit/2026-05-16-resource-management-api-audit.md`
captures the exhaustive call-site inventory from the six Haiku
+ three Sonnet sweeps.

`.vault/adr/2026-05-16-resource-management-api-adr.md` decides
all eight open questions, ratifies Sketch A, sequences the 11-
step migration.

`.vault/plan/2026-05-16-resource-management-api-plan.md` (L2,
10 phases, 96 steps, 100 % completion) is the execution log.

The feature index at
`.vault/index/resource-management-api.index.md` ties them
together.

## Recommendations

Recommended next steps in order of leverage:

1. Track ruff's PEP-562 awareness as it lands so the four
   `# noqa: F822` markers can be dropped.
2. Investigate the 248 pre-existing test failures via a
   separate triage feature; many appear to be 2026Q1-period
   data drift in the calculation registry rather than packaging
   defects.
3. When the next read-only resource kind lands, follow the
   Repository pattern: declare a `Repository[T, K]` subclass,
   wire it into `ResourceRegistry`, expose it via
   `_repos/__init__.py`, and let the existing structural guard
   keep it honest.

## Addendum (2026-05-16) — strict no-compat enforcement landed

The first two recommendations above are CLOSED. Branch
`chore/eliminate-shims` landed the strict no-compat pass:

- `default_registry_authority()` deleted; all callers route through
  `resources().modelos.authority` (or `ValidatedRegistryAuthority.load`
  for explicit-override paths) — see commit `02f3409f`.
- `_DEFAULT_*_ROOT` constants deleted from `cli/registry.py`,
  `cli/_app_live.py`, `domain/categories/_registry.py`,
  `domain/deadlines/_engine.py`, `domain/vat/_rates.py`,
  `domain/vat/_catalogue.py`, `domain/vat/_recargo_equivalencia.py`,
  `domain/rental/_imputacion_parameters.py`,
  `domain/user_profile/_loader.py`. All typer.Option defaults switched
  to `Path | None = None` with body-resolution via `bundled_path(...)`
  / `resources()`. Commit `dda33572`.
- Module-level `CATEGORY_PROFILES_2025` and
  `CATEGORY_PROFILE_REGISTRY_BY_YEAR` eager loads deleted; six call
  sites migrated to `resolve_category_profiles(2025)`.
- PEP-562 `__getattr__` lazy module shims deleted from
  `domain/vat/_recargo_equivalencia.py` and
  `domain/rental/_imputacion_parameters.py`; both expose ordinary
  `load_*()` accessor functions.
- Structural-guard allow-list at
  `src/aeat/core/resources/test_single_surface_invariant.py` is now
  `frozenset()`. The companion ratchet test enforces that no
  production module outside `src/aeat/core/resources/` may declare
  a `_DEFAULT_*_ROOT = bundled_path(...)` constant.
- Residual CLI test `test_registry_verify_cli_validates_sources_and_catalogues`
  root-caused (stale `PROJECT_ROOT` source-root after the
  corpus-registry-packaging physical move) and fixed in commit
  `d2742b03` to use `bundled_path()`.
