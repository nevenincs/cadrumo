---
tags:
  - '#research'
  - '#wizard-registration-bootstrap'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - "[[2026-06-01-domain-boundary-audit-audit]]"
---

# `wizard-registration-bootstrap` research: `Wizard + profile-key registration order: empirical findings`

Empirical investigation of how the domain profile-key registry and the core wizard
catalogue are populated, undertaken to determine whether the DB-17 lazy
domain-to-application pull in `src/aeat/domain/profile/_keys.py` could be removed
(audit step `W06.P18.S64`). The work was an attempt-and-revert on the
`chore/eliminate-shims` branch; the detailed reproduction log lives in the related
domain-boundary audit document. These findings ground the sibling decision record.

## Findings

- **The lazy pull is the only universal trigger.** `_build_profile_keys` in
  `domain/profile/_keys.py` imports `compile_profile_keys` from
  `application.wizard._compiler`; that import is also what first executes the
  compiler module's import-time `register_profile_keys` push. The explicit push path
  exists (`register_profile_keys`, `register_wizard_catalogue`) but is triggered only by
  importing specific wizard submodules (`_compiler`, `_status`, `_catalogue`). There is
  no central bootstrap. The application `wizard` package `__init__` is docstring-only,
  so importing the package does not register anything.

- **Many test modules carry manual side-effect imports.** A recurring
  `# side-effect: registers wizard catalogue` import appears across CLI and domain test
  modules (and `domain/deadlines/conftest.py`), which is direct evidence that callers
  must hand-trigger registration today — there is no guarantee it has happened.

- **Removing the pull breaks collection (reproduced).** With `_build_profile_keys`
  deleted and `_profile_keys` switched to a not-registered guard, isolated smoke tests
  passed both ways (guard fires when unregistered; importing the wizard compiler pushes
  57 keys and access succeeds). But the first real suite run failed at COLLECTION:
  `domain/profile/__init__.py` re-exports `PROFILE_KEYS` via a module `__getattr__`, and
  `domain/profile/test_keys.py` reads it at import time before any wizard import, firing
  the guard during collection. This proves the lazy fallback is load-bearing for every
  profile-key access path that does not first import the wizard layer.

- **The wizard catalogue registration is fragile in the same way.** Modelo CLI paths run
  in isolation surface "wizard catalogue has not been registered" from
  `core/profile_catalogue.py` for the identical reason (the catalogue is registered only
  when `application/wizard/_catalogue.py` is imported).

- **The conformance gate is collection-scope sensitive.** The CLI
  `test_every_cli_leaf_has_a_registered_schema` reports a different missing-schema count
  depending on which test files are collected (observed 150 then 109), because
  `@register_schema` decorators only fire when their payload modules are imported. Only a
  full-suite run is authoritative for that gate; narrow subsets produce false reds.

- **No new error class is required for the guard.** `ProfileKeysRegistrationError` can be
  generalised to accept a message (default preserved for the existing
  already-registered case), covering the not-registered case without a new registered
  error and its registry-plus-four-locale cascade.

- **Conclusion.** A standalone pull-removal is unsafe. The DB-17 closure requires a
  guaranteed central registration bootstrap first: eager registration at the wizard
  package boundary, a composition-root trigger for production, and a session-scoped
  conftest trigger for tests. The decision is formalised in the sibling ADR.
