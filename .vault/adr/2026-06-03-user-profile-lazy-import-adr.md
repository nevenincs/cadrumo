---
tags:
  - '#adr'
  - '#user-profile-lazy-import'
date: '2026-06-03'
related:
  - '[[2026-06-03-user-profile-lazy-import-research]]'
  - '[[2026-06-03-bare-invocation-bucket-session-gate-adr]]'
---

# `user-profile-lazy-import` adr: `Lazy import via PEP 562 dispatch for the user_profile package boundary` | (**status:** `accepted`)

## Problem Statement

The CLI's lazy-loading discipline gate at `src/aeat/entrypoints/cli/test_lazy_command_tree.py` now reds five tests: `test_version_cold_start_completes_under_budget`, `test_importing_cli_package_does_not_import_registry`, and three parameterised instances of `test_state_free_surface_does_not_import_registry`. A runtime probe shows that importing `aeat.application.user_profile` transitively loads 69 `aeat.domain.calculations.registry` submodules — every state-free CLI surface (`aeat`, `aeat --help`, `aeat --version`) now pays the full registry cost.

The root cause is structural rather than incidental. `aeat.application.user_profile/__init__.py` declares Pydantic command and result models at module scope whose field types come from `aeat.domain.user_profile` (`UserProfileFact`, `UserProfileFactValue`, `UserProfileRecord`, `UserProfileStatus`). The domain package eagerly pulls the registry through its `_registry_contract` module to validate user-profile selectors against the registry binding set. Pydantic v2 resolves field types at class-creation time, so the top-level domain import in the application boundary cannot simply be `__getattr__`-deferred.

The regression appeared when commit `11764506e refactor(cli): migrate user_profile imports to top-level re-exports` migrated 8 dot-into-private-submodule imports across `_common.py`, `_modelo.py`, and `_overview.py` to consume through the package boundary that `bec06bb46 refactor(user-profile): promote orchestration surface to package top-level` had promoted. The boundary-tightening was correct under the package-consumption rule codified in `4e443841b`. The collision happened because the boundary itself was not lazy.

## Considerations

The discipline ratchet at `test_lazy_command_tree.py` is documented as load-bearing for the cold-start UX: a fresh `aeat --version` budget of 2.0 s would silently regress to 3+ s without it. The companion ADR `2026-06-03-bare-invocation-bucket-session-gate` documents the same axis from a different angle (the bare-invocation surface is stateless and must not require persistent storage). Both ADRs frame the state-free CLI surfaces as a distinct architectural class with stricter import constraints than subcommand-bound surfaces.

The rule `aeat-architecture-boundaries` mandates hexagonal direction: the domain layer's eager pull of registry through `_registry_contract` is legitimate (domain imports nothing from adapters; the registry is itself a domain primitive). The registry's import cost is real but architecturally correct. The fix must therefore live in the *application boundary*, not in the domain layer.

The rule codified in `4e443841b` (consume through the package boundary, not past it) and the lazy-loading ratchet are both correct. The fix must satisfy both simultaneously — neither can yield.

## Constraints

Pydantic v2 resolves field types at class-creation time. Any solution that keeps the command and result models in `__init__.py` body cannot lazy-resolve their field types. A solution that lazy-resolves the field types must therefore move the models out of `__init__.py` body.

The `aeat.application.user_profile` `__init__.py` already implements module-level `__getattr__` (PEP 562) for the service classes and orchestration verbs at lines 304-394. The pattern is present and proven; the gap is its scope, not its presence.

The file is currently being edited by peer agents (visible in git status). The fix must land as one atomic explicit-path commit per `aeat-architecture-boundaries` symbol-relocation discipline.

## Decision: Pattern A — relocate command and result models into `_commands.py`, extend `__getattr__` to cover them and the four domain records

Move the Pydantic command and result classes currently declared in the body of `aeat.application.user_profile/__init__.py` (the `RegisterProfileCommand`, `EditProfileFieldCommand`, `EditProfileSectionCommand`, `RemoveProfileCommand`, `DuplicateProfileCommand`, `RenameProfileCommand`, `ProfileLifecycleResult`, `ProfileListing`, `ProfileListResult`, `ProfileValidationIssue`, `ProfileValidationReport`, `ProfilePreflightRequirement`, `ProfilePreflightReport`, `ProfileSnapshotRequest`, `ProfileSnapshot`, `ProfileStaleCheckReport`, `ProfileImportResult` set) into a sibling private module `_commands.py` that imports the domain records normally.

Extend the existing module-level `__getattr__` block to resolve the relocated command and result classes on demand, and to resolve the four domain records (`UserProfileFact`, `UserProfileFactValue`, `UserProfileRecord`, `UserProfileStatus`) on demand for any consumer that imports them through the application package boundary. Remove the top-level `from ...domain.user_profile import (...)` import from `__init__.py`.

After the relocation, `aeat.application.user_profile/__init__.py` contains: the module docstring, the existing `_register_language_resolver()` call (which is itself already cheap), the `__getattr__` block (extended), and the `__all__` list. No top-level imports remain that pull domain records, registry, or service modules.

The package consumes lazy-by-default: every consumer that touches a name through `aeat.application.user_profile.<name>` triggers the on-demand import for that name and only that name. The boundary stays canonical; the cost moves to first-use.

## Why not the alternatives

**Pattern B (`TYPE_CHECKING` guard plus runtime resolver)** is functionally identical to Pattern A — it still requires relocating the Pydantic models out of `__init__.py` body because field types must be concrete at class-creation time. Pattern B adds a `TYPE_CHECKING` annotation surface without removing the relocation cost, so it is strictly more verbose with no benefit.

**Pattern C (split the package into a contracts package and a services package)** introduces a topology dictated by import cost rather than by domain cohesion. Every consumer migrated by `11764506e` and the prior boundary-tightening commits would have to choose between the new packages. The split also sets a precedent that the codebase has not previously needed; the lazy-loading rule has been satisfied by PEP 562 dispatch at every other boundary. Reject on cost and precedent grounds.

**Pattern D (revert `11764506e` and accept dot-into-private imports)** re-introduces 8 forbidden cross-package dot-ins and weakens a discipline ratchet codified one commit earlier. Reject on rule-precedence grounds.

## Implementation

The implementation is a single atomic relocation:

- Create `src/aeat/application/user_profile/_commands.py` carrying the Pydantic command and result classes. The new module imports `UserProfileFact`, `UserProfileFactValue`, `UserProfileRecord`, `UserProfileStatus` from `aeat.domain.user_profile` and `ProfileId`, `BaseSeverity`, `PROVENANCE_SOURCE_MANUAL_CLI`, `STRICT_FROZEN_CONFIG` from the core layer. The hash-constraint kwargs constant `_PROFILE_SNAPSHOT_HASH_KWARGS` moves with the models that use it.
- Strip the top-level domain import and the Pydantic model declarations from `src/aeat/application/user_profile/__init__.py`. Keep the module docstring, the `_register_language_resolver()` call, the `__getattr__` block, and the `__all__` list.
- Extend the `__getattr__` block to resolve the relocated command and result classes (one new branch per class group) and to resolve the four domain records (one new branch that imports them from `aeat.domain.user_profile` on demand).
- The `__all__` list does not change; the public surface is unchanged.
- No consumer code changes.

## Regression gate

The existing `src/aeat/entrypoints/cli/test_lazy_command_tree.py` test module is the enforcement gate. The fix is green when all five currently red tests pass and `test_dispatching_a_subcommand_loads_its_module` continues to pass (proving subcommand dispatch still wires through `__getattr__` correctly).

A new dedicated regression test lands alongside the relocation: an in-process or subprocess probe that asserts `import aeat.application.user_profile` does not place any `aeat.domain.calculations.registry*` module in `sys.modules`. This catches the same regression class at the producer boundary, not only at the CLI consumer surface — a future eager-import on `aeat.application.user_profile` would red here before it reds the cli-level gate.

## Rationale

The decision preserves both binding rules: the package-consumption discipline (consume through the boundary, not past it) and the lazy-loading ratchet (state-free CLI surfaces import no registry). The PEP 562 pattern is already in use at the same site for service classes and orchestration verbs; the relocation extends the pattern's scope rather than introducing a new mechanism. The fix carries no skip, xfail, mock, or stub — it makes the gate green honestly per `aeat-quality-gates`.

The relocation respects `aeat-architecture-boundaries` symbol-relocation atomicity: one symbol-group move, one commit, every consumer update (none needed here because the public surface is unchanged), and the `__getattr__` extension all land together.

## Consequences

- The application boundary becomes lazy by default. First reference to any name from `aeat.application.user_profile.*` triggers the on-demand import for that name. The cost shifts from import-time to first-use.
- The state-free CLI surfaces stay registry-free without skip or test rewrite. The cold-start budget at `aeat --version` returns to the pre-regression profile.
- The PEP 562 pattern is now established as the canonical lazy-loading shape for application-layer package boundaries that aggregate domain-record-carrying Pydantic models. Future application boundaries that bind to registry-coupled domain records can follow the same shape.
- The implementation cost is one new sibling module plus a small `__getattr__` extension. No consumer code changes. The relocation lands in one commit.
- Pitfall to track: a future consumer that uses `from aeat.application.user_profile import ProfileSnapshot` (a Pydantic model) will trigger the model's domain imports at first reference, not at module import. The cost is unchanged, only deferred. Consumers that need the model at module-import time pay the cost there.

## Codification candidates

- **Rule slug:** `application-boundary-lazy-by-default`.
  **Rule:** Application-layer package `__init__.py` files that aggregate registry-coupled or otherwise heavy surfaces MUST use module-level `__getattr__` (PEP 562) to resolve every re-exported name on demand. Top-level imports in the `__init__.py` body are reserved for genuinely lightweight primitives that every consumer pays for unconditionally; anything that pulls registry, services, repositories, or domain records goes through the `__getattr__` block.

  **Why:** the state-free CLI surface budget enforced by `test_lazy_command_tree.py` is operator-visible; any application boundary that eagerly imports registry-coupled material drags the cost across every consumer that crosses the boundary. The PEP 562 pattern lets the boundary stay canonical (one consumption point) while keeping the cost deferred.

  **How to apply:** when authoring or modifying an `aeat.application.*` package `__init__.py`, check whether the file would import a domain package that itself imports the registry. If yes, the imports go through `__getattr__`. Pydantic command and result models whose field types come from such a domain package live in a sibling private module (`_commands.py` is the established name) and are themselves re-exported via `__getattr__`.
