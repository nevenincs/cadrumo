---
tags:
  - '#adr'
  - '#wizard-catalogue-startup-ordering'
date: '2026-06-03'
modified: '2026-06-03'
related:
  - "[[2026-06-02-m303-parser-engine-totals-impedance-adr]]"
  - '[[2026-06-04-wizard-catalogue-startup-ordering-research]]'
---


# `wizard-catalogue-startup-ordering` adr: CLI composition root owns wizard registration; tests reuse the production root via shared bootstrap | (**status:** `accepted`)

## Authoring note

Authored via Write tool — same bash-quoting constraint as the prior six ADRs this campaign. Commit-bot validates via `vault check all`.

## Problem statement

`register_wizard_catalogue` populates global process state on import of `aeat.application.wizard._catalogue` (line 859). The CLI root callback at `entrypoints/cli/__init__.py:281` triggers that registration via `_register_wizard_catalogue_for_profile_keys()` — but only on the non-exempt active-profile code path (after the line 277 `has_active_bucket_session()` early-return).

Test paths that route through `cli_runner.invoke(app, ...)` with an active bucket session HIT the early-return BEFORE the registration call AND do not transitively import the wizard package via their own import graph. Result: `"Wizard catalogue has not been registered"` raises mid-test. `test_overview_explain_verb.py::test_explain_721` is the canonical failing case (imports through user_profile + workflow + secure_sql; no wizard touch).

The existing test guard `test_cold_start_wizard_registration.py` documents the exact concern verbatim: "the in-process test suite stays green because some other test in the session imports the catalogue and registers it process-wide". Global-state-leakage IS known and intentional for the cold-start guard's purpose. The new failure mode is the xdist parallel + non-wizard-import path that breaks the session-level leakage invariant.

PM enumerated three options, each violating something:

- **A** — register at `aeat.application.__init__.py`: couples application-layer import-eagerness for every sibling.
- **B** — lazy-import in `core.profile_catalogue` getters: violates `aeat-architecture-boundaries` (core importing application).
- **C** — pytest conftest fixture importing wizard at collection: symptom-fix; per-test boilerplate.

## Decision: Option A with a constrained scope — register in `aeat.application.wizard.__init__.py` only

Move the registration side-effect import to `aeat.application.wizard/__init__.py`. Importing the wizard PACKAGE triggers the catalogue registration. Tests that consume the wizard subsystem already import `aeat.application.wizard` directly. Tests that don't consume the wizard subsystem (`test_explain_721` and its peers) don't trigger registration — but they also don't need it; they hit the guard because the CLI root callback's early-return short-circuits the production registration call.

Two co-landed changes:

1. **`aeat.application.wizard/__init__.py`** gains a top-of-module `from . import _catalogue, _persistence` side-effect import. The package import becomes the registration trigger.

2. **`entrypoints/cli/__init__.py:277-281`** drops the early-return for the active-bucket-session path's wizard registration. Move the `_register_wizard_catalogue_for_profile_keys()` call ABOVE the bucket-session gate. The call becomes unconditional at CLI bootstrap — same shape as the active-profile language resolver per the cold-start guard docstring.

The combination ensures:
- Production CLI cold-start always registers (existing cold-start guard stays green).
- Tests that import the wizard package register via the package init.
- Tests that go through `cli_runner.invoke` register via the CLI bootstrap (now unconditional).
- The `test_explain_721`-style tests that don't touch the wizard at all but DO invoke the CLI hit the unconditional bootstrap registration and pass.

## Why not A-bare (full application/__init__)

PM's framing of Option A was "register at `aeat.application.__init__.py`". That couples EVERY application sibling — calculations, modelo, aggregation, ledger, etc. — to wizard catalogue eagerness. Architectural over-coupling for a wizard-specific need. The constrained scope (`aeat.application.wizard/__init__.py`) keeps eagerness local to the wizard package, which IS the package that owns the catalogue. No cross-sibling coupling.

## Why not B

`aeat-architecture-boundaries` forbids `core` importing `application`. The lazy-import-in-getter pattern would silently violate that rule (the runtime import lives in the getter body, but the discipline is direction-of-travel: core never reaches into application). Reject.

## Why not C

Symptom-fix at the pytest layer. Doesn't address the production failure mode where a cold-start CLI invocation hits the early-return path. The cold-start guard documents this exact concern — fixing only the test surface leaves production exposed. Reject.

## Consequences

- `aeat.application.wizard/__init__.py`: ~3 LOC (one side-effect import).
- `entrypoints/cli/__init__.py`: ~10 LOC move of the registration call above the bucket-session gate.
- Cold-start guard at `test_cold_start_wizard_registration.py` stays green (production CLI still registers at bootstrap).
- `test_explain_721` and ~50 sibling tests stop hitting the registration guard.
- Anti-tautology gate: add a test that imports `aeat.application.wizard` then queries `register_wizard_catalogue` state, asserts registered=True; mutate the side-effect import to a no-op, assert the test fails. Proves the package import IS the registration trigger.

## Migration path

Single atomic commit. The two changes must co-land — moving the CLI registration above the gate without the package init backstop leaves a window where a CLI bootstrap that fails BEFORE reaching the registration line (e.g. import-time exception in the bucket-session gate) leaves the catalogue unregistered. The package init backstop catches that case.

Dispatch to coder. ~15 LOC + 1 anti-tautology test. ~1 commit.

## Out of scope

- Other global-state-leakage axes in the application layer (project-answers registration is analogous; if it surfaces the same failure mode, apply the same pattern but as a separate task).
- The xdist parallel test-isolation discipline more broadly; this ADR fixes the wizard catalogue specifically.
- Refactoring `register_wizard_catalogue` to a lifecycle event rather than an import side-effect (future-hardening direction; out of scope for the current red).
