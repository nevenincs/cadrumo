---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:f5db84089d09da89532cc3ee9b9f809efe5f2b29b1adf64516bfe0e472cd06d3'
step_id: 'S79'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Convert the lazy-facade gate from policing a retreating mechanism to asserting its absence, since removing the last shipped dispatch hook left it scanning only the test package's own permanent facade: its non-vacuity guard asserted merely that SOME lazy facade was found, which stayed true, so a gate written to protect shipped code was passing on a test helper exactly as its own docstring warned would happen. Assert that no shipped module defines a module-level __getattr__, keep the map-versus-TYPE_CHECKING agreement checks for the one permitted facade, and refuse if that facade ever stops being one.

## Scope

- `src/cadrumo/tests/test_lazy_facade_static_bindings.py`

## Changes

- `M` `src/cadrumo/tests/test_lazy_facade_static_bindings.py`
- `verify:` `pytest .../test_lazy_facade_static_bindings.py` 3 passed
- `verify:` teeth proved against the LIVE tree -- appending a module-level
  `__getattr__` to `core/period.py` fails the gate naming `period.py:613`;
  restored and re-verified green
- `verify:` `pytest dev/quality/tests/test_facade_export_lazy_shapes.py
  .../test_inert_namespace_imports_resolve.py` 5 passed, no regression
- `verify:` `ruff check` and `ty check` clean

## Notes

The gate had outlived its subject without failing. It was written to keep a
retreating mechanism honest while shipped package facades gave up their dispatch
maps one at a time, and its own docstring said that when the last map went the
file should be DELETED rather than left passing over an empty population.
Removing the profile-key registry's hook in the previous step took the last
shipped one, and the file kept passing -- because its non-vacuity guard asserted
only that SOME lazy facade was found, and `cadrumo.tests` keeps a deliberate,
permanent facade of its own. A gate protecting shipped code was green on a test
helper.

Deleting it was the documented end state but the wrong move, because the ruling
it enforced is permanent while the mechanism it watched is not: a package
namespace is inert, and PEP 562 resolution types every consumer's view of a name
as `object`. So the file now asserts the ABSENCE, which cannot go vacuous, with a
population floor so a scan that finds almost nothing fails rather than passes.

The two original checks are kept for the one permitted facade, because the drift
they catch is still possible there, and `_permitted_facade` refuses outright if
that facade ever stops dispatching -- the same trap, closed this time by a
failure rather than by a docstring.
