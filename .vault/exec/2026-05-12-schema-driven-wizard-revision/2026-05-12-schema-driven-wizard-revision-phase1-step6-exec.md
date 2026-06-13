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

# r6 deduplicate _normalise_key

## scope

R6 collapses every profile-key normaliser to one definition. The
canonical home is ``src/aeat/domain/profile/_normalise.py`` per the
plan's "domain/profile/_normalise.py (or inline on ProfileKey)"
option; ``ProfileKey.from_key`` and ``workflow._utils._normalise_key``
both import that function. The two parallel copies in
``application/workflow/_utils.py`` and ``application/review/_models.py``
are removed and replaced by re-exports / import-statements. The
unrelated logging-key normaliser in ``core/logging.py`` (which
camelCase-splits log keys; semantically distinct from profile-key
normalisation) is renamed to ``_normalise_log_key`` so the
``def _normalise_key`` grep gate returns exactly one hit.

## files owned

- ``src/aeat/application/workflow/_utils.py`` — re-export
- ``src/aeat/application/review/_models.py`` — drop local copy,
  import from workflow utils
- ``src/aeat/domain/profile/_keys.py`` — ``from_key`` calls the
  canonical function instead of inlining the rule
- ``src/aeat/domain/profile/_normalise.py`` — new canonical home
- ``src/aeat/core/logging.py`` — rename ``_normalise_key`` to
  ``_normalise_log_key`` (semantically distinct)

## acceptance gates run

- ``grep -rn 'def _normalise_key' src/aeat/`` returns exactly one hit
  (``src/aeat/domain/profile/_normalise.py:20``)
- ``pytest src/aeat/application/wizard/ src/aeat/application/profile/
  src/aeat/domain/profile/test_keys.py src/aeat/entrypoints/cli/test_config_setter.py``
  — green
- ``prek run --files`` over every owned file — green

## notes

The pre-existing circular-import failure in the review subpackage
test discovery is unchanged by R6 and not caused by this Step. The
``test_profile_errors_have_registered_codes`` failure in
``src/aeat/domain/profile/test_errors.py`` is unrelated to R6 (it
asserts an error-code prefix change unrelated to the normaliser
move).
