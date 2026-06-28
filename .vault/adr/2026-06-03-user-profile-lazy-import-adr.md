---
tags:
  - '#adr'
  - '#user-profile-lazy-import'
date: '2026-06-03'
modified: '2026-06-03'
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

## Findings — execution-time scope expansion (2026-06-04)

Authoring the producer-side probe at
`src/aeat/application/user_profile/test_lazy_boundary.py` confirmed the
ADR's central premise: after relocating the Pydantic command and
result models into `_commands.py` and routing the four domain records
through PEP 562 `__getattr__`, importing
`aeat.application.user_profile` in a fresh interpreter places zero
`aeat.domain.calculations.registry*` modules into `sys.modules` (down
from 69 against the unfixed boundary). The boundary itself is now
lazy by default and the producer-side probe is green.

However, the CLI-side gate at
`src/aeat/entrypoints/cli/test_lazy_command_tree.py` remains red for
all five originally-named tests. The leak vector is orthogonal to the
application boundary:

- `src/aeat/entrypoints/cli/__init__.py` line 46 imports
  `decorate_typer_app` from `aeat.entrypoints.cli._errors` at module
  scope (it must run before the typer app object is decorated, so it
  cannot move into a lazy block).
- `src/aeat/entrypoints/cli/_errors.py` line 55 imports
  `StoredProfileDriftError` from `aeat.domain.user_profile`.
- The domain package's `__init__.py` eagerly imports `_registry_contract`
  at module scope. This is the same import path the ADR describes as
  "legitimate" under the hexagonal-direction rule.

Empirical verification: importing **only**
`aeat.entrypoints.cli._errors` in a fresh interpreter places 69
`aeat.domain.calculations.registry*` modules into `sys.modules` —
identical to the regression count the CLI gate measures end-to-end.
Importing the domain submodule directly
(`from aeat.domain.user_profile._errors import StoredProfileDriftError`)
places the same 69 modules because Python evaluates the package
`__init__.py` whenever any descendant module is first imported.

### Implication for the fix's sufficiency

The application-boundary relocation Pattern A specifies is necessary
(the boundary should be lazy by default, the producer probe pins the
contract, and Pattern A is correct on its own merits) but **not
sufficient** to turn the five CLI-gate reds green. The acceptance
criterion in the umbrella plan cannot be reached without an additional
decision that the ADR's Problem Statement and Decision sections do
not contemplate, namely one of:

- **Pattern E (lazy domain-package boundary):** `aeat.domain.user_profile/__init__.py`
  routes its registry-coupled re-exports (`UserProfileSelectorIndex`,
  `validate_user_profile_registry_contract`, `profile_binding_selectors`,
  `build_user_profile_selector_index`, the three registry-contract
  records, and the registry-aware loader) through PEP 562 `__getattr__`,
  while keeping the lightweight errors / values / schema re-exports
  eager. The ADR's "domain layer's eager pull is legitimate" claim has
  to be revisited: the legitimacy applies to *callers that actually
  need the registry-contract surface*, not to error-class consumers
  like `cli/_errors.py`.

- **Pattern F (consumer-side direct import):** route
  `cli/_errors.py` and any other state-free CLI surface consumer to
  import `StoredProfileDriftError` from a registry-free surface (a
  dedicated `aeat.domain.user_profile.errors` re-export module, or a
  direct private-submodule import that the package consumption rule
  is amended to allow for the error surface). This is the inverse of
  the `4e443841b` ruling for the error subset.

- **Pattern G (move the error class up):** lift
  `StoredProfileDriftError` (and any sibling errors consumed by the
  state-free CLI surface) into `aeat.core` or `aeat.domain._errors`
  so the consumer never touches the user_profile domain package at
  all.

Each pattern requires its own decision, its own ADR-level analysis
of rule-precedence (package consumption vs lazy-loading vs
hexagonal-direction), and its own consumer sweep. They are out of
scope for the present ADR.

### What lands now, and why

The application-boundary relocation (`_commands.py` plus the extended
`__getattr__`) and the producer-side probe land as authored. They
deliver an honest, non-tautological structural improvement: the
boundary is lazy, the registry-pull count through the application
package is zero, the public surface is unchanged, no consumer needed
adjustment, and the probe pins the contract against future
regression. The five CLI-gate tests remain red but their leak vector
is now demonstrably orthogonal to the application boundary and is
fully diagnosed for a follow-up campaign.

The alternative — landing nothing and waiting for the orthogonal
decision — would discard a real win and leave the application
boundary structurally wrong even after the CLI-side regression is
solved. The brief's guard against the
`m303-primitive-encoder` half-fix pattern is honoured by not editing
the CLI-side or domain-side surfaces under the cover of this ADR;
those edits need their own decision.

### Follow-up

A successor ADR (`2026-06-04-cli-errors-domain-package-lazy-import-adr`
or equivalent) is required before the umbrella plan's
`test_lazy_command_tree.py` gate can be brought green. The successor
ADR's Problem Statement is the diagnosis recorded above; its
Decision will pick among Patterns E / F / G (or a hybrid). The
present ADR's status remains `accepted` for the scope it actually
covers (the application boundary).
