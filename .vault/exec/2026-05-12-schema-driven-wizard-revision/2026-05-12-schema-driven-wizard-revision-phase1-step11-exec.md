---
tags:
  - '#exec'
  - '#schema-driven-wizard-revision'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-revision-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# r11 relocate setup-status surface into wizard module

## scope

R11 deletes ``application/setup_status.py`` and folds its semantic
surface into ``application/wizard/_status.py``. The renamed exports:

* ``SetupStatusReport`` → ``WizardStatusReport`` (strict frozen
  pydantic v2 record carrying ``active_profile``, ``profile_ready``,
  ``identity_ready``, ``enrolment_ready``, ``missing_required``,
  ``missing_enrolment``, ``profile_present_keys``,
  ``profile_total_keys``, ``auth_provider``, ``login_ready``,
  ``next_action``)
* ``build_setup_status`` → ``build_wizard_status``

The previous narrower ``WizardStatusReport`` (which was used only by
a never-wired ``aeat config status`` branch) is unified onto this
broader surface.

``load_active_autonomo_profile`` now raises ``WizardStatusError``
(``WizardError → AeatError``-rooted, registered in the application
error registry as ``REFUSED_WIZARD_STATUS``) instead of raw
``ValueError``. Callers (``cli/deadlines/_helpers.py``,
``application/filing/runtime.py``) are updated to catch the typed
error.

A new ``wizard/test_status.py`` adds structural assertions on the
report shape, the wiring from ``WorkflowState``, and the typed
``WizardStatusError`` flow.

## files owned

- ``src/aeat/application/setup_status.py`` (deleted)
- ``src/aeat/application/test_setup_status.py`` (deleted; assertions
  fold into ``wizard/test_status.py``)
- ``src/aeat/application/diagnostics.py`` — import + type rewrite
- ``src/aeat/application/test_diagnostics.py`` — import rewrite,
  pinning test renamed
- ``src/aeat/application/wizard/_status.py`` — broader surface,
  ``WizardStatusError`` + ``next_action`` projection
- ``src/aeat/application/wizard/test_status.py`` — new
- ``src/aeat/entrypoints/cli/deadlines/_helpers.py`` — catches
  ``WizardStatusError``
- ``src/aeat/application/filing/runtime.py`` — catches
  ``WizardStatusError``
- ``src/aeat/core/errors/registry/_application.py`` — registers
  ``REFUSED_WIZARD_STATUS``

## acceptance gates run

- No file at ``src/aeat/application/setup_status.py``
- ``grep -rn 'build_setup_status\|SetupStatusReport' src/aeat/
  --include='*.py'`` returns nothing
- ``pytest src/aeat/application/wizard/test_status.py
  src/aeat/application/test_diagnostics.py`` — green (15 tests)
- ``prek run --files`` over every owned file — green
