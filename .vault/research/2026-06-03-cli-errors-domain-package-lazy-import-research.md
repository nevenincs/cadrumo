---
tags:
  - '#research'
  - '#cli-errors-domain-package-lazy-import'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-user-profile-lazy-import-adr]]'
---

# `cli-errors-domain-package-lazy-import` research: `Diagnose the cli/_errors orthogonal registry-leak vector`

Successor research to `2026-06-03-user-profile-lazy-import-adr`. The parent
campaign fixed the `aeat.application.user_profile` package boundary via PEP 562
PEP-562 dispatch (commit `20992e0d4`); the producer-side probe at
`src/aeat/application/user_profile/test_lazy_boundary.py` confirms that
importing the application package now places zero `aeat.domain.calculations.registry*`
modules in `sys.modules`. The CLI-side gate at
`src/aeat/entrypoints/cli/test_lazy_command_tree.py` nonetheless remained red
for all five state-free-surface tests. This research diagnoses the orthogonal
leak vector and characterises the patterns available to close it.

## Findings

### F1. The leak vector is `aeat.domain.user_profile/__init__.py`, not the application boundary

Probe: a fresh-interpreter `import aeat.entrypoints.cli._errors` placed 69
`aeat.domain.calculations.registry*` modules in `sys.modules` — identical to
the 69-module count the CLI-side gate observes end-to-end. The application
boundary is no longer in the chain.

Chain (verified by a meta-path `find_spec` finder that prints the importer
stack on first registry contact):

- `aeat.entrypoints.cli.__init__` line 46 — `from ._errors import decorate_typer_app as _decorate_typer_app`. Module-scope; runs before the typer app object is decorated; cannot move into a lazy block.
- `aeat.entrypoints.cli._errors` line 55 — `from ...domain.user_profile import StoredProfileDriftError`. Module-scope; the symbol is referenced inside `command_error_boundary` to discriminate stored-data drift from input-time validation.
- `aeat.domain.user_profile.__init__` line 22 — `from ._portable_export import UserProfilePortableExport`. Module-scope.
- `aeat.domain.user_profile._portable_export` line 21 — `from ..modelos._calculation_revision import CalculationRevision as _CalculationRevision`. Module-scope.
- `aeat.domain.modelos._calculation_revision` line 52 — `from ..calculations.registry import CasillaObservation`. Module-scope. First contact with the registry package.

### F2. The parent ADR's diagnosis of the vector is partially correct but mis-attributed

The parent ADR's "Findings — execution-time scope expansion" section
attributes the leak to `_registry_contract.py`. The current shape of
`_registry_contract.py` actually defers the registry import via
`TYPE_CHECKING`: its module-level imports are `..calculations._export_field_kind.CasillaFieldKind`
(a five-member StrEnum module that imports only stdlib and pydantic) and
`._schema.ProfileSchemaDefinition`. Importing `_registry_contract` alone
places zero registry modules in `sys.modules`.

The real heavy node in `aeat.domain.user_profile/__init__.py` is the eager
re-export of `UserProfilePortableExport`, which composes four heavy domain
types (`CalculationRevision`, `WorkUnit`, `Transaction`, `ModeloRecord`)
whose imports cascade into the registry. The module docstring of
`_portable_export.py` already names this hazard: *"This module is isolated
from `aeat.domain.user_profile._values` so the four heavy domain types it
composes ... do not enter `sys.modules` at user-profile package init."* —
the isolation succeeded at the `_values.py` level but the `__init__.py`
re-export defeats it for every consumer that touches the package boundary.

### F3. Consumer surface taxonomy: every CLI-side consumer needs only lightweight names

Audit of every `from ...domain.user_profile import ...` site (54 hits across
src/aeat/, of which the test sites are immaterial to the import budget):

- **Error classes** (lightweight, no registry coupling):
  `ProfileNotFoundError`, `ProfileAlreadyExistsError`, `ProfileSchemaValidationError`,
  `ProfilePreflightMissingError`, `ProfileSnapshotHashMismatchError`,
  `ProfileSnapshotNotFoundError`, `StoredProfileDriftError`,
  `UserProfileSchemaLoadError`. All defined in `_errors.py`, which imports
  only stdlib + pydantic + `core.errors.AeatError`.
- **Schema records** (lightweight): `ProfileFieldDefinition`, `ProfileFieldType`,
  `ProfileRemovePolicy`, `ProfileSchemaDefinition`, `ProfileSectionDefinition`,
  `ProfileSnapshotPolicy`. All defined in `_schema.py`, which imports only
  stdlib + pydantic + `core.classification.SensitivityClass` + `_errors`.
- **Value records** (lightweight): `UserProfileFact`, `UserProfileFactValue`,
  `UserProfileRecord`, `UserProfileSnapshot`, `UserProfileStatus`,
  `new_profile_id`, `new_profile_snapshot_id`. All defined in `_values.py`,
  which imports only stdlib + pydantic + `core` primitives.
- **Loader** (lightweight): `load_user_profile_schema` from `_loader.py`.
  Imports only `_errors`, `_schema`, `core._toml`, `core.resources.bundled_path`.
- **Registry-contract surface** (lightweight at module-load via TYPE_CHECKING;
  registry imports occur only at function call time):
  `UserProfileSelectorIndex`, `UserProfileRegistryContractIssue`,
  `UserProfileRegistryContractReport`, `UserProfileRegistryContractSeverity`,
  `build_user_profile_selector_index`, `profile_binding_selectors`,
  `validate_user_profile_registry_contract`.
- **Portable export** (HEAVY): `UserProfilePortableExport`. The sole node
  that pulls registry at module-load time.

The `cli/_errors.py` consumer needs exactly one name (`StoredProfileDriftError`)
from the lightweight error class group. No CLI state-free-surface consumer
needs `UserProfilePortableExport` at module-load time; the portable-export
flow is only reached through explicit `aeat config profile export/import`
verbs that already pay registry costs through their command modules.

### F4. The three candidate patterns and their trade-offs

The parent ADR's Findings section enumerated three follow-up patterns. This
research evaluates each against the project's discipline rules.

**Pattern (a) — Lazy domain-package boundary via PEP 562.** The
`aeat.domain.user_profile/__init__.py` defers `UserProfilePortableExport`
(and conservatively any registry-coupled re-export) to a module-level
`__getattr__` block. Lightweight re-exports (errors / values / schema /
loader) stay eager. The `__all__` list does not change; the public surface
is unchanged.

- *Discipline alignment.* Mirrors the parent ADR's Pattern A exactly: the
  same PEP 562 mechanism, the same "lazy-by-default for heavy / eager for
  lightweight" cut, applied one layer down the import graph. The
  `aeat-architecture-boundaries` rule's relocation-atomicity clause is
  honoured: the move lands in one explicit-path commit.
- *Consumer impact.* Zero. The 54 consumer sites all import lightweight
  names; none receive a code change.
- *Hexagonal direction.* Preserved. The domain package still owns its
  surface; the registry import only fires when a consumer reaches for
  `UserProfilePortableExport`.
- *Codification candidate.* Strengthens the application-boundary rule the
  parent ADR proposed (`application-boundary-lazy-by-default`): the same
  pattern now applies to domain-package boundaries whose re-export surface
  spans the lightweight / registry-coupled cut.

**Pattern (b) — Consumer-side `TYPE_CHECKING` + function-local import.**
`cli/_errors.py` imports `StoredProfileDriftError` only under
`TYPE_CHECKING`; the actual `except` arm in `command_error_boundary` does
a function-local import on first call.

- *Discipline alignment.* Function-local imports inside an `except` arm
  break the source-hygiene principle that consumers consume through the
  package boundary, not past it (rule codified in `4e443841b` and
  re-affirmed in commit `11764506e`). The pattern produces scattered
  local imports across every CLI surface that uses any user_profile
  symbol — there are 13 CLI consumer sites that would each acquire a
  local-import block.
- *Scope.* Single-site cost is small; campaign-wide cost is large. The
  rule has been applied consistently to the project; granting an
  exception only for `cli/_errors.py` would set a precedent that any
  state-free CLI surface can dot into private submodules, weakening the
  package-consumption discipline.
- *Lazy-loading completeness.* Only patches the specific consumer the
  current gate tests against. Any other state-free CLI surface that
  later acquires a user_profile import would re-introduce the same
  regression — the producer side stays structurally wrong.

**Pattern (c) — Lift `StoredProfileDriftError` to `aeat.core.errors`.**
The error class moves up to the framework layer; `cli/_errors.py`
imports it from `core.errors` and never touches the user_profile
domain package.

- *Discipline alignment.* The error is currently a `UserProfileError`
  subclass (the base lives in `aeat.domain.user_profile._errors`).
  Relocating the leaf to `core.errors` either breaks the inheritance
  chain (the base must move too, which cascades to every other
  `UserProfileError` subclass) or introduces a cross-layer parent that
  the core layer should not own. The core layer is meant for primitives
  that every domain depends on; a user-profile-specific drift error is
  not such a primitive.
- *Atomicity.* Per `aeat-architecture-boundaries`, every symbol
  relocation lands in one atomic explicit-path commit. The relocation
  surface here is 22 files (every `StoredProfileDriftError` consumer
  plus the parent class chain). The blast radius is much larger than
  Patterns (a) or (b).
- *Repeat-pattern fragility.* If a second domain error later needs
  lifting under the same pressure, the core layer accumulates
  domain-specific error classes — a layering inversion. The parent ADR
  considered an analogous relocation (Pattern C — "split the package")
  and rejected it on cost and precedent grounds. The same reasoning
  applies here.

### F5. The 13 CLI consumer sites and what they need

The CLI directory imports user_profile symbols from 13 sites (one
top-level `cli/_errors.py` plus 12 function-local imports inside
`cli/_modelo.py`, `cli/_config/__init__.py`). All 12 function-local
imports already defer their cost to first-call time; only `cli/_errors.py`
imports at module-load. Pattern (a) leaves all 13 sites unchanged.

### F6. Producer-side regression contract

The orthogonal-vector diagnosis suggests a producer-side regression
test at `src/aeat/domain/user_profile/test_lazy_boundary.py` mirroring
the application-side probe the parent campaign landed at
`src/aeat/application/user_profile/test_lazy_boundary.py`. The probe
runs in a fresh subprocess (interpreters can be polluted by warm-cache
imports from other test modules in the same session); the assertion
is identical in shape: importing `aeat.domain.user_profile` places
zero `aeat.domain.calculations.registry*` modules in `sys.modules`.

The producer-side probe is necessary because the CLI-side gate only
catches the regression at the `cli/_errors.py` consumer surface. A
future CLI surface acquiring its first user_profile import would
silently regress until the cold-start budget test caught it indirectly.
A domain-package-level probe pins the contract at the layer where it
actually lives.
