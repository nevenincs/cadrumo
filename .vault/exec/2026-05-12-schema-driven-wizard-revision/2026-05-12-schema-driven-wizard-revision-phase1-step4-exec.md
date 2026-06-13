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

# r4 replace monkeypatch.setattr purity test with structural assertion

## scope

R4 removes ``monkeypatch.setattr(Path, "read_text", _explode)`` from
``test_compile_is_pure_no_env_or_file_io`` and replaces it with two
structural assertions:

* ``test_wizard_flows_carry_only_frozen_literals`` walks every value
  in the real ``WIZARD_FLOWS`` catalogue and asserts each is a frozen
  pydantic record, a ``Translatable`` marker, or one of the permitted
  immutable primitives (``str``/``bool``/``int``/``NoneType``/
  ``WizardWidget``/``type``/``tuple``).
* ``test_compile_is_pure_on_the_real_catalogue`` runs the projection
  against the real catalogue and asserts the resulting keys match the
  set of declared ``profile_key`` values.

The structural shape catches every plausible side-effect carrier
(callable defaults, mutable containers, module references) at the
descriptor level, where the side effect would actually originate.

## files owned

- ``src/aeat/application/wizard/test_compile.py``

## acceptance gates run

- ``grep -n 'monkeypatch\|MonkeyPatch\|setattr' src/aeat/application/wizard/test_compile.py``
  returns nothing
- ``pytest src/aeat/application/wizard/test_compile.py`` — green
  (10 tests, +1 vs previous baseline because the purity gate is now
  split into the structural + projection pair)

## notes

The `os` and `pathlib.Path` imports are no longer needed after the
``monkeypatch`` patch was removed.
