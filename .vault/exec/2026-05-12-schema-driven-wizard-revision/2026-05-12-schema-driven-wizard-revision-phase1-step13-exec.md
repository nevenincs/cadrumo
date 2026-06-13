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

# r13 relocate namespace constants and delete application/setup/

## scope

R13 deletes ``src/aeat/application/setup/`` (the stub subpackage
that held three storage-namespace constants and an ``__init__.py``)
and moves the constants to
``src/aeat/application/profile/_storage_namespaces.py``:

* ``_PROFILE_NAMESPACE = "aeat.application.setup.profile"``
* ``_PROFILE_VERSION = 1``
* ``_PROFILE_HKDF_CONTEXT = b"aeat.application.setup.profile.v1"``
* ``_profile_object_key(target: Path) -> str``

The string and byte-string literals stay verbatim — persisted rows
reference ``aeat.application.setup.profile`` and decrypt under
``b"aeat.application.setup.profile.v1"``, so changing those breaks
existing operator data. Only the Python module path moves.

The archive registry's built-in adapter loop now imports
``_PROFILE_NAMESPACE`` from the new home. The storage rotation plan
imports ``_PROFILE_HKDF_CONTEXT`` from the new home (lazy import
inside ``default_rotation_plan`` to avoid the
adapter→application→adapter circular dependency at module load
time).

## files owned

- ``src/aeat/application/setup/`` (fully deleted)
- ``src/aeat/application/profile/_storage_namespaces.py`` (new
  canonical home for the constants)
- ``src/aeat/application/archive/_registry.py`` — import + use
  ``_PROFILE_NAMESPACE``
- ``src/aeat/adapters/persistence/storage/_rotation.py`` — import +
  use ``_PROFILE_HKDF_CONTEXT``

## acceptance gates run

- No directory at ``src/aeat/application/setup/``
- ``grep -rn 'application\.setup\b' src/aeat/ --include='*.py'``
  returns only the test-archive string literals and the new module's
  docstring (every remaining hit IS the stable namespace identifier,
  not a Python module reference)
- ``pytest src/aeat/application/archive/test_archive.py`` — green
  (14 tests; crypto round-trip preserved because the namespace and
  HKDF context bytes are unchanged)
- ``prek run --files`` over every owned file — green
