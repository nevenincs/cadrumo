---
tags:
  - '#adr'
  - '#wizard-registration-bootstrap'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-02-wizard-registration-bootstrap-research]]"
  - "[[2026-06-01-domain-boundary-audit-adr]]"
  - "[[2026-06-01-domain-boundary-audit-plan]]"
  - "[[2026-06-01-domain-boundary-audit-audit]]"
---

# `wizard-registration-bootstrap` adr: `Central wizard + profile-key registration bootstrap (DB-17)` | (**status:** `accepted`)

## Problem Statement

The domain profile-key registry (`src/aeat/domain/profile/_keys.py`) compiles its
`PROFILE_KEYS` tuple from the wizard descriptor catalogue, which lives in the
application layer (`src/aeat/application/wizard/_compiler.py`,
`src/aeat/application/wizard/_catalogue.py`). The current implementation reaches the
catalogue through a lazy, in-function import (`_build_profile_keys` imports
`compile_profile_keys` from `application.wizard._compiler`). That is a domain to
application edge — finding **DB-17** of the domain-boundary audit — which the
hexagonal-direction mandate forbids.

The audit step `W06.P18.S64` proposed simply deleting the lazy pull and relying on the
existing push path (`register_profile_keys`, called by the wizard compiler's
import-time side effect). An empirical attempt (recorded in the related research and
audit documents) proved this is unsafe as a standalone change: the package
`src/aeat/domain/profile/__init__.py` re-exports `PROFILE_KEYS` through a module
`__getattr__`, so `domain/profile/test_keys.py` touches the registry at import time,
before any wizard module is imported. With the lazy fallback removed, the
not-registered guard fires during collection. The same import-order fragility afflicts
the wizard-catalogue registration in `src/aeat/core/profile_catalogue.py` (a "wizard
catalogue has not been registered" error surfaces in modelo CLI paths run in
isolation). Registration today is triggered only by ad-hoc imports of specific wizard
submodules — evidenced by the many test modules that carry an explicit
`# side-effect: registers wizard catalogue` import — with no central guarantee that
registration precedes the first domain access.

## Considerations

- **Push vs pull.** The hexagonal-correct direction is a push: the application layer
  seeds the domain registry; the domain never imports the application. The push API
  (`register_profile_keys`, `register_wizard_catalogue`) already exists. What is missing
  is a guaranteed trigger.
- **Composition-root wiring.** The entrypoints layer is the composition root and may
  legally import both application and domain. A startup hook there can guarantee the
  push for every production CLI/MCP path.
- **Test-session bootstrap.** Pytest collects domain test modules without exercising a
  composition root, so a session-scoped trigger (a root conftest import, mirroring the
  existing `src/aeat/domain/deadlines/conftest.py` side-effect import) is required for
  the test lane.
- **Eager package-init registration.** Making `application/wizard/__init__.py` import
  `_catalogue` and `_compiler` at package load turns any import of `application.wizard`
  (or any of its submodules) into a full registration, collapsing the scattered
  side-effect imports into one deterministic point.
- **Not-registered guard.** Once the push is guaranteed, the lazy pull is replaced by a
  fail-fast guard that raises when the registry is read before registration — turning a
  silent ordering dependency into an explicit, catchable error.

## Constraints

- The domain layer must never import the application layer; the bootstrap therefore
  cannot live in `domain/`. The domain may only expose the registration slot it already
  has.
- Eager imports inside `application/wizard/__init__.py` must avoid re-entrant
  partial-initialisation cycles: `_compiler` imports `domain.profile._keys` (for the
  push target) and `_catalogue`; neither may import the `application.wizard` package in a
  way that re-enters its half-initialised `__init__`.
- The change is only verifiable by a full-suite run, not a narrow subset: the CLI
  json-schema-conformance gate and the wizard-dependent modelo tests are
  collection-scope and registration-order fragile (the missing-schema count varies with
  the collected file set), so narrow runs produce false reds. Full-suite (CI) green is
  the authoritative gate.
- Parent stability: this decision depends only on the already-stable push API and the
  existing wizard catalogue; no frontier or immature dependency is involved.

## Implementation

The bootstrap lands as one atomic change with three layers, then removes the pull:

1. **Eager registration at the wizard package boundary.** `application/wizard/__init__.py`
   imports the catalogue and compiler submodules so that importing the wizard package
   performs both registrations (the wizard catalogue into core, the compiled profile
   keys into the domain registry) exactly once, idempotently.
2. **Composition-root trigger.** The CLI (and any other entrypoint composition root)
   imports the wizard package during application construction, guaranteeing the push
   before any command handler reaches a domain profile-key access.
3. **Test-session trigger.** A root-level pytest conftest performs the same side-effect
   import once per session, mirroring the established `domain/deadlines/conftest.py`
   pattern, so domain test modules that touch `PROFILE_KEYS` at collection time find the
   registry seeded.

Only after those three are in place is the lazy `_build_profile_keys` pull deleted and
`_profile_keys` switched to a not-registered guard (the `S64` change). The generalised
`ProfileKeysRegistrationError` (a message-accepting constructor, default preserved)
carries the not-registered case without a new registered error class, avoiding the
registry plus four-locale cascade a brand-new error would incur. The full test suite
must be green — in particular no collection-time guard firing anywhere — before the
change is accepted.

## Rationale

The decision is grounded in a reproduced failure, not speculation: the standalone
pull-removal breaks `domain/profile/test_keys.py` at collection because the domain
package eagerly re-exports `PROFILE_KEYS`. A deterministic, central push is the only way
to remove the domain to application edge without reintroducing the scattered
side-effect-import fragility. Locating the trigger at the wizard package boundary plus
the composition root keeps the domain pull-free (satisfying the hexagonal mandate of the
parent domain-boundary ADR) while making registration an explicit, witnessed startup
step rather than an implicit consequence of whichever module happened to be imported
first.

## Consequences

- **Gains.** The DB-17 domain to application edge is eliminated. Registration becomes
  deterministic and witnessable. The dozens of `# side-effect: registers` imports
  scattered across test modules become unnecessary and can be retired over time. The
  not-registered guard converts a silent ordering bug into a fail-fast, catchable error.
- **Difficulties.** Eager `__init__` imports must be ordered to avoid re-entrant
  partial-init; every composition root must wire the trigger, and a missed entry path
  surfaces as a hard guard error (fail-fast — acceptable, and better than today's
  silent lazy fallback). The change requires a full-suite verification pass and cannot be
  landed against a churning shared worktree without `application/wizard/__init__.py`,
  the CLI entrypoint, and `domain/profile/_keys.py` all being simultaneously quiescent.
- **Pathways opened.** The same composition-root bootstrap pattern generalises to other
  domain registries that today rely on import side effects, and is a precondition for the
  `S64` hexagonal closure.

## Codification candidates

- **Rule slug:** `domain-registries-seeded-by-composition-root`.
  **Rule:** A domain-layer registry that derives its contents from an outer layer MUST be
  seeded by a push from the composition root (entrypoints) or an eager application
  package-init registration, never by a lazy in-function import from the domain into the
  application layer; reading the registry before it is seeded MUST raise a fail-fast
  not-registered error rather than triggering a cross-layer pull.
