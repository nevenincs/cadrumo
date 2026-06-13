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

# r7 excise the ignored-path-arg shims

## scope

R7 removes the ``path: Path | None = None`` parameter from
``load_default_filing_profile`` and the ``path: Path`` parameter from
``load_profile``. Both functions resolve profile state from the
workflow repository and never consult the parameter. The deadline
CLI commands lose their ``--profile`` option; the filing build
command loses its ``--profile`` option (the ``--profile-tax-id`` /
``--profile-name`` pair remains). The ``resolve_profile_path`` helper
in ``deadlines/_helpers.py`` is deleted with its sole caller.

## files owned

- ``src/aeat/application/filing/runtime.py`` — drop ``path``
- ``src/aeat/entrypoints/cli/deadlines/_helpers.py`` — drop
  ``resolve_profile_path``; tighten ``load_profile`` signature
- ``src/aeat/entrypoints/cli/deadlines/next.py`` — drop ``--profile``
- ``src/aeat/entrypoints/cli/deadlines/explain.py`` — drop ``--profile``
- ``src/aeat/entrypoints/cli/deadlines/list.py`` — drop ``--profile``
- ``src/aeat/entrypoints/cli/filing/__init__.py`` — drop ``--profile``
  from the build command

## acceptance gates run

- ``grep -rn 'del path\b\|Ignored\. Retained' src/aeat/`` — only
  unrelated ``del path`` hits in
  ``blob_store`` / ``usage_ratios`` / ``filing/_review`` remain (they
  reference unrelated parameters, not the wizard's path-arg shim)
- ``pytest src/aeat/application/wizard/`` — green (74 tests)
- ``prek run --files`` over every owned file — green

## known follow-up

The five deadlines CLI tests
(``test_list_renders_obligations``, ``test_next_renders_an_obligation``,
``test_explain_known_modelo``, ``test_list_requires_profile_when_setting_unset``,
``test_next_uses_default_profile_path``) plus
``test_filing_cli.py::TestFilingCLI::test_build_uses_configured_profile_file``
still seed on-disk profile envelopes and pass ``--profile``. R12
rewrites those fixtures to seed ``WorkflowState`` so the new
signatures work end-to-end. The plan explicitly scopes that fixture
rewrite to R12.
