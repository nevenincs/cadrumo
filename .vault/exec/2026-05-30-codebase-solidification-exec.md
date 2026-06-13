---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-30'
modified: '2026-05-30'
step_id: 'S315'
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
---

# `codebase-solidification` `W03.P14.S315-S320`

Introduce `aeat.core.profile_catalogue` registry slot and migrate all
upward-import violations for `SETUP_FLOW` / `WIZARD_FLOWS` out of
`aeat.domain.deadlines._profiles` and `aeat.domain.profile._keys`.

- Created: `src/aeat/core/profile_catalogue.py`
- Created: `src/aeat/core/test_profile_catalogue.py`
- Modified: `src/aeat/application/wizard/_catalogue.py`
- Modified: `src/aeat/domain/deadlines/_profiles.py`
- Modified: `src/aeat/domain/profile/_keys.py`
- Modified: `src/aeat/entrypoints/cli/_config/__init__.py`

## Description

Decision: registry-slot pattern (option b / Protocol) rather than moving
descriptor data to core. `WizardFlow` and `SetupAnswers` depend on
application-layer models (`_models.py`, `_setup_answers.py`); moving the
full catalogue to core would invert the layering further. Instead,
`register_wizard_catalogue()` is called at the end of `_catalogue.py`'s
module body — importing `_catalogue` anywhere (including via `_commands.py`
which the CLI already imports) fills the slot as a side effect, so
`get_setup_flow()` / `get_wizard_flows()` always return the real objects.

- S315: new `aeat.core.profile_catalogue` with registry slot, accessor
  functions, `WizardCatalogueNotRegisteredError`, and `WizardFlowProtocol`.
- S316: `_catalogue.py` calls `register_wizard_catalogue(SETUP_FLOW, WIZARD_FLOWS)`
  after constants are built; imports `register_wizard_catalogue` from core.
- S317: `_profiles.py` top-level `from aeat.core.profile_catalogue import get_setup_flow`;
  deferred application imports (`project_answers`, `SetupAnswers`) remain
  deferred inside the function body; `SETUP_FLOW` import removed from the
  deferred block.
- S318: `_keys.py` replaces deferred `from ...application.wizard._catalogue import WIZARD_FLOWS`
  with `get_wizard_flows()` call; top-level `get_wizard_flows` import from core.
- S319: `cli/_config/__init__.py` replaces top-level `_SETUP_FLOW` import
  from `_catalogue` with `_get_setup_flow` from core; both module-level
  wizard command builds and the deferred `config_status` usage updated.
- S320: 7 real-behaviour unit tests: identity round-trip (is-check), flow id,
  flows containment, source-grep for absent bypass pattern in both domain
  modules, protocol exports callable.

## Tests

7 tests in `src/aeat/core/test_profile_catalogue.py` — all pass.
Targeted suite (wizard, deadlines, profile, cli/_config, excluding pre-existing
failures): 612 passed, 2 pre-existing live-auth failures unrelated to this work.
Commit: `f2166683e`.
