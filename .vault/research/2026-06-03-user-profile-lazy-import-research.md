---
tags:
  - '#research'
  - '#user-profile-lazy-import'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - '[[2026-06-03-bare-invocation-bucket-session-gate-adr]]'
---

# `user-profile-lazy-import` research: `user_profile re-export pulls registry transitively`

## Context

Task #165 surfaced five red tests in `src/aeat/entrypoints/cli/test_lazy_command_tree.py`: `test_version_cold_start_completes_under_budget`, `test_importing_cli_package_does_not_import_registry`, and three parameterised instances of `test_state_free_surface_does_not_import_registry`. The test module is the structural enforcement gate for the lazy-loading discipline that was put in place to keep `aeat --version`, `aeat --help`, and the bare invocation surface registry-free.

A runtime import probe confirmed the regression vector: importing `aeat.application.user_profile` pulls 69 submodules under `aeat.domain.calculations.registry` transitively. The CLI bootstrap touches `aeat.application.user_profile` symbols at module-import time for shared utilities consumed by both state-free and state-bound surfaces, so any state-free CLI surface that crosses that package boundary now drags the registry along.

## Re-exported symbols in `aeat.application.user_profile/__init__.py`

The package `__init__.py` exposes two classes of surface:

### Eagerly imported at module top (the regression vector)

- `pydantic.BaseModel`, `Field` — framework primitives, no registry exposure.
- `aeat.core.errors.BaseSeverity` (aliased `_BaseSeverity`) — lightweight.
- `aeat.core.external_constants.PROVENANCE_SOURCE_MANUAL_CLI` — lightweight.
- `aeat.core.identity.ProfileId` — lightweight typed-id alias.
- `aeat.core._models.STRICT_FROZEN_CONFIG` — lightweight.
- `aeat.domain.user_profile` `(UserProfileFact, UserProfileFactValue, UserProfileRecord, UserProfileStatus)` — **this is the chain that pulls registry**. The domain package's `__init__.py` imports `_registry_contract` (lines 23-31) which in turn imports the registry to validate user-profile selectors against the registry binding set. The 69-submodule pull originates here.
- `._language_resolver.register_language_resolver` — local, lightweight, registers an i18n hook.

### Lazily resolved via PEP 562 `__getattr__`

The package already implements module-level `__getattr__` at lines 304-394 for: `ProfileLifecycleService`, the `Censo*` family (errors and sync), the `_projections` helpers (`facts_to_values`, `projection_for_taxpayer`, `record_to_values`, `snapshot_to_values`), `ProfilePreflightService`, `ProfileValidationService`, the bundle round-trip family (`SUPPORTED_BUNDLE_SCHEMA_VERSIONS`, `UnsupportedBundleSchemaVersionError`, `deserialize_profile_bundle`, `serialize_profile_bundle`), the orchestration family (`ProfileAlreadyRegisteredError`, `build_lifecycle_service`, `delete_profile_with_lifecycle_span`, `fact_value`, `logout_active_profile`, `profile_create_storage_span`, `profile_storage_session`, `read_active_profile`, `register_active_profile`, `remove_active_profile`, `remove_profile_bucket_directory`, `rename_profile`, `select_profile`, `select_profile_with_lifecycle_span`, `set_active_field`, `set_active_fields`), the `_repository` namespace family, and `ProfileRepository`.

The lazy block proves the discipline already exists at this site for service classes and orchestration verbs. The gap is the **domain-record import** at lines 29-34 — a top-level import that bypasses the lazy block because the records are used by the command/result Pydantic models declared in the same `__init__.py` body.

## Regression origin

Commit `11764506e refactor(cli): migrate user_profile imports to top-level re-exports` (Wed Jun 3 2026) migrated 8 dot-into-private-submodule imports across 4 CLI files (`_common.py`, `_modelo.py`, `_overview.py`) to consume through the `aeat.application.user_profile` package boundary promoted in `bec06bb46 refactor(user-profile): promote orchestration surface to package top-level`. Pre-`bec06bb46`, callers reached past the package boundary directly into private submodules (`_projections`, `_orchestration`, etc.), bypassing whatever the package `__init__.py` body imported.

`11764506e` is structurally correct under the boundary-discipline rule (codified in `4e443841b`): consumers should consume through the package boundary, not past it. The defect is on the producer side. The package boundary itself eagerly pulls `aeat.domain.user_profile` to declare its command/result Pydantic models, and `aeat.domain.user_profile` eagerly pulls the registry through its `_registry_contract` module. Once every consumer goes through the boundary, every consumer pays the registry cost.

Two concurrent forces created the regression:

1. **The boundary-tightening rule** (codified in `4e443841b`) is correct and durable: it removes 58+ cross-package re-exports and forces consumption through the canonical package boundary.
2. **The lazy-loading rule** (enforced by `test_lazy_command_tree.py`) is also correct and durable: state-free CLI surfaces must not import the registry.

The two collided at the `aeat.application.user_profile` boundary because the boundary's `__init__.py` body is not itself lazy — it eagerly imports `aeat.domain.user_profile` to declare module-level Pydantic models that consume `UserProfileFact` etc. as field types.

## Why the domain layer pulls the registry

`aeat.domain.user_profile/__init__.py` imports `_registry_contract` at module-load time. That module exists because the user-profile schema is registry-coupled: profile selectors are validated against the registry's binding set so a profile cannot declare a selector the registry has no binding for. The contract validation is a property of the schema; the schema lives in the domain package; therefore the domain package eagerly resolves the registry.

This is a legitimate domain-layer dependency under the hexagonal direction (domain imports nothing from adapters; the registry is a domain primitive). The cost only becomes a regression when a *state-free CLI surface* unavoidably crosses the application-layer boundary that re-exports domain records.

## Lazy-import patterns surveyed

Four patterns can resolve the conflict:

### Pattern A: PEP 562 `__getattr__` extension covering the domain records

Extend the existing `__getattr__` block at lines 304-394 to also resolve the four domain records (`UserProfileFact`, `UserProfileFactValue`, `UserProfileRecord`, `UserProfileStatus`) on demand. Remove the corresponding top-level import.

Problem: the Pydantic command/result models declared in the `__init__.py` body (`RegisterProfileCommand`, `EditProfileFieldCommand`, `EditProfileSectionCommand`, `ProfileLifecycleResult`, `ProfileSnapshot`, `ProfileImportResult`, etc.) use `UserProfileFact`, `UserProfileFactValue`, `UserProfileRecord`, `UserProfileStatus` as field types. Pydantic v2 resolves field types at class-creation time (module-import time), not lazily, so the domain records must be importable when the model classes are constructed. Lazy-resolving them at the package level does not help the in-module model classes.

Resolution path for Pattern A: relocate the command/result Pydantic models out of `__init__.py` into a sibling `_commands.py` / `_results.py` module that imports the domain records normally. The package `__init__.py` then carries no top-level domain imports at all; both the command/result types and the service/orchestration verbs resolve through `__getattr__`. Module-level `__getattr__` is the standard Python 3.7+ tool (PEP 562) for this exact shape.

### Pattern B: `TYPE_CHECKING` guard + runtime resolver

Move the domain-record imports under a `TYPE_CHECKING` guard and use a runtime resolver (a `def __getattr__` at module level) to lazy-load them. The Pydantic field-type problem persists in the same shape as Pattern A — Pydantic v2 needs concrete types at class-creation time, so the command/result models still cannot live in `__init__.py` if their field types are lazy. Pattern B is effectively a more verbose Pattern A with the same relocation requirement and no additional benefit.

### Pattern C: split the package

Split `aeat.application.user_profile` into two packages: a lightweight `aeat.application.user_profile_contracts` (commands, results, validation reports — the Pydantic envelope surface) that imports the domain records normally, and an `aeat.application.user_profile_services` (lifecycle, snapshot, preflight, censo, orchestration, repository) that lives behind the lazy boundary.

The split has a high churn cost: every consumer migrated by `11764506e` and the prior boundary-tightening commits would have to choose between the two new packages. The split also fragments what is conceptually one feature surface ("the user-profile contract") into a topology dictated by import cost. The lazy-loading rule has not previously demanded a package split anywhere else in the codebase, so this would be a precedent.

### Pattern D: revert `11764506e` and accept dot-into-private imports for the four migrated files

Revert the boundary-tightening on `_common.py`, `_modelo.py`, `_overview.py` and let the lazy-loading discipline win. This re-introduces 8 dot-into-private-submodule imports the rule (codified `4e443841b`) explicitly forbids, and weakens the boundary-discipline ratchet across the codebase. Recommend against on rule-precedence grounds.

## Applicable AEAT rules

- `aeat-architecture-boundaries`: documents the CLI root surface as `config` + `app` and mandates hexagonal direction. The bare-invocation surface and the state-free CLI surfaces (`--help`, `--version`) are pre-subcommand introspection, parallel to the `bare-invocation-bucket-session-gate` ADR (2026-06-03). The architecture-boundaries rule does not directly mandate lazy loading but the lazy-loading test is the operator-visible enforcement of the cold-start UX it implies.
- `aeat-quality-gates`: forbids defeating the gate with skip / xfail / mock. The fix must make the lazy_command_tree gate green honestly.
- `aeat-source-hygiene`: the regression-origin commit is process-traceable; the fix should not encode process labels in code.

## Recommendation

**Pattern A with the command/result relocation.** Move the Pydantic command and result classes out of the `aeat.application.user_profile/__init__.py` body into a private sibling module (`_commands.py` is the natural name); the package `__init__.py` carries only the existing `__getattr__` block (extended to cover the relocated command/result classes and the four domain records) plus the unchanged orchestration registration call.

This:

- preserves the package-boundary consumption discipline (no consumer goes back to dot-into-private imports);
- preserves the lazy-loading ratchet (`test_lazy_command_tree.py` stays the enforcement gate, no skip);
- preserves the bec06bb46 promotion intent (the boundary still exposes everything consumers expect by name);
- requires zero changes to any consumer of `aeat.application.user_profile.*`;
- follows the standard PEP 562 pattern already in active use in the same file.

The relocation is a one-shot move that ships with a regression test (the existing `test_lazy_command_tree.py` gate, plus an additional probe that asserts `import aeat.application.user_profile` does not pull `aeat.domain.calculations.registry`).
