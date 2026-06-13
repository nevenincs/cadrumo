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

# r12 excise legacy autonomo helpers; fix wizard-introduced regressions

## scope

R12 rewrites ``domain/deadlines/_profiles.autonomo_profile_from_mapping``
on top of ``project_answers(SETUP_FLOW, …)`` and deletes the
``_bool_value``, ``_iva_regime_value``, ``_text_value``,
``_TRUE_TOKENS``, ``_FALSE_TOKENS``, and dotted-alias-fallback chain.
The helper coerces mixed-typed mappings to canonical-token strings,
normalises ``iva.regime`` to uppercase, and pads ``tax.id`` /
``activity`` defaults so an empty profile still projects (the
deadline engine's diagnostic schedule path depends on that).

Three wizard-introduced regressions are closed by re-rooting their
fixtures against ``WorkflowState``:

* ``cli/deadlines/test_cli.py`` — ``test_list_renders_obligations``,
  ``test_next_renders_an_obligation``, ``test_explain_known_modelo``
  now seed an active profile through
  ``workflow_state_repository().update(set_active_profile + set_profile_values)``
  and drop the ``--profile`` flag. The two pre-existing tests that
  exercised ``--profile`` / ``AEAT_DEFAULT_PROFILE_PATH`` are
  removed because R7 deleted the surfaces they tested.
* ``cli/filing/test_filing_cli.py::test_build_uses_configured_profile_file``
  → renamed ``test_build_uses_active_workflow_profile`` and rewritten
  to seed the active profile instead of writing an on-disk envelope.

``test_models.py``'s ``autonomo_profile_from_mapping`` cases use
canonical-token strings (``"true"``/``"false"``) and the canonical
underscored profile keys; the unknown-boolean-token test is dropped
because the wizard's pydantic-projected bool only accepts
``"true"``/``"false"`` (semantically distinct from the legacy
``_bool_value``).

## files owned

- ``src/aeat/domain/deadlines/_profiles.py``
- ``src/aeat/domain/deadlines/test_models.py``
- ``src/aeat/entrypoints/cli/deadlines/test_cli.py``
- ``src/aeat/entrypoints/cli/filing/test_filing_cli.py``

## acceptance gates run

- ``grep -n '_bool_value\|_iva_regime_value\|_TRUE_TOKENS\|_FALSE_TOKENS'
  src/aeat/domain/deadlines/_profiles.py`` returns nothing
- ``pytest src/aeat/domain/deadlines/ src/aeat/entrypoints/cli/deadlines/
  src/aeat/entrypoints/cli/filing/test_filing_cli.py::TestFilingCLI::test_build_uses_active_workflow_profile
  src/aeat/application/wizard/`` — green (127 wizard/deadlines tests
  + 1 filing CLI test)
- ``load_active_autonomo_profile`` raises ``WizardStatusError`` (a
  ``WizardError`` subclass registered as ``REFUSED_WIZARD_STATUS``);
  ``ProfileError`` is raised by the deadlines CLI helper after the
  wizard error is caught.
- ``prek run --files`` over every owned file — green

## notes

The off-limits ``entrypoints/cli/_common._profile_to_autonomo``
caller keeps its existing call site; the rewritten helper preserves
the same external signature so no further plumbing is required
here.
