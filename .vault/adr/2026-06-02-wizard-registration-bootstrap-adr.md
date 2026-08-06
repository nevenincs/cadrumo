---
tags:
  - '#adr'
  - '#wizard-registration-bootstrap'
date: '2026-06-02'
modified: '2026-07-17'
body_hash: 'sha256:1e77fa5ad56c918ed5b7789813dca0fb0007b0378ffb2c4ccb22773a59f1b0f0'
related:
  - '[[2026-06-02-wizard-registration-bootstrap-research]]'
  - '[[2026-06-01-domain-boundary-audit-adr]]'
---

# `wizard-registration-bootstrap` adr: `Contribuyente profile-key registration through the composition root` | (**status:** `accepted`)

## Problem Statement

Wizard descriptors in `cadrumo.application.wizard` project profile keys into a
domain-owned registry. The registry belongs to
`cadrumo.domain.contribuyente`, not to a retired generic profile package, and
the domain must never import the application to populate itself. Production
entry points and isolated domain tests also need deterministic ordering: the
push must occur before any consumer reads `PROFILE_KEYS`.

## Decision

Keep one outer-to-inner registration seam:

- `cadrumo.domain.contribuyente._keys` owns `register_profile_keys`, the
  idempotent cache, the fail-closed read guard, and the public `PROFILE_KEYS`
  projection.
- `cadrumo.application.wizard._compiler` purely compiles `WIZARD_FLOWS` into
  `ProfileKey` values and pushes the resulting tuple through the public
  `cadrumo.domain.contribuyente` facade.
- `cadrumo.application.wizard._catalogue` independently registers the wizard
  catalogue through `cadrumo.core.wizard_catalogue`; neither core nor domain
  pulls from application.
- Each production composition root imports the wizard registration modules
  before dispatch. The human CLI centralizes this in
  `_register_wizard_catalogue_for_profile_keys`.
- Domain-local test harnesses may perform the same real registration at
  collection boundaries when they exercise the registry without constructing
  an entry point. They import production registration code and do not duplicate
  the compiler or mutate it through test doubles.

## Constraints

- No domain or core module may import `cadrumo.application.wizard`, directly or
  through a deferred helper.
- Registration is idempotent only for the same compiled tuple. Conflicting
  second registration raises `ProfileKeysRegistrationError`.
- Reading before registration fails closed; it never triggers a lazy
  cross-layer pull.
- The compiler remains a pure projection over supplied `WizardFlow` records.
  Import-time registration is isolated in the explicit registration boundary.
- Startup, cold-process CLI, compiler, and domain registry tests exercise real
  production behavior without mocks, patches, skips, or mirrored logic.

## Implementation

The current implementation is the accepted shape:

- `src/cadrumo/domain/contribuyente/_keys.py` owns the slot and guard;
- `src/cadrumo/application/wizard/_compiler.py` owns compilation and the push;
- `src/cadrumo/application/wizard/_catalogue.py` owns core catalogue
  registration; and
- `src/cadrumo/entrypoints/cli/__init__.py` wires production startup.

`src/cadrumo/application/wizard/tests/`,
`src/cadrumo/domain/contribuyente/tests/`, and the cold-process CLI tests pin
projection correctness, duplicate-registration refusal, and composition-root
ordering.

## Rationale

This keeps dependency direction explicit: application knows the domain port,
the composition root knows both, and the domain knows neither the wizard nor
its startup sequence. The fail-closed read guard exposes missing wiring instead
of concealing it behind an upward import. Naming the current
`domain.contribuyente` owner also removes a stale architectural map that would
send maintainers toward a package that no longer owns this contract.

## Consequences

- Profile-key authority has one owner and one push path.
- Entry points must wire registration before a registry read; omissions fail
  immediately and diagnostically.
- Test collection that bypasses the composition root needs a narrow real-code
  registration boundary, but never a second implementation.
