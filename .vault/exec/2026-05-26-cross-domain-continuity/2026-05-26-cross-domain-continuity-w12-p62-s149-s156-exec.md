---
tags:
  - "#exec"
  - "#cross-domain-continuity"
step_id: S149
date: 2026-05-27
modified: '2026-05-27'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

# cross-domain-continuity W12.P62.S149-S156 — registry validate-helper dedup (G5 gate)

## Outcome

Consolidated the 7 identical `_missing_refs` module-level function definitions
into a single canonical module `_validate_helpers.py`. All 7 validate-* modules
now import from the canonical path. No shim, no re-export, no compatibility alias.

### Invariant verified

```
git grep "_missing_refs" src/aeat/domain/calculations/registry/ --include="*.py"
```

Result: 1 definition (`_validate_helpers.py:10`) + 7 `from ._validate_helpers import _missing_refs`
lines + 1 unrelated `@staticmethod` in `_validate.py` (class method, not a duplicate).

### `Iterable` import cleanup

`Iterable` was the sole consumer of the `collections.abc.Iterable` import in 6 of
the 7 files. It was removed from those 6 imports. `_validate_constructs.py` retains
`Iterable` because it uses it in other function signatures.

### Pre-existing failure noted

`test_cross_domain_snapshot_registration.py::test_m100_build_on_renta_free_import_path_registers_the_gate`
fails with a circular import (`_applicability.py` → `deadlines._engine` → `registry.__init__`).
This is a pre-existing failure unrelated to this batch. 278/279 registry tests pass.

## Commits

- `46ecfb966` — S149-S156: consolidate _missing_refs into canonical _validate_helpers module

## Files changed

- `src/aeat/domain/calculations/registry/_validate_helpers.py` — created (S149)
- `src/aeat/domain/calculations/registry/_validate_algorithms.py` — import from helpers, Iterable removed (S150)
- `src/aeat/domain/calculations/registry/_validate_constructs.py` — import from helpers, Iterable kept (S151)
- `src/aeat/domain/calculations/registry/_validate_dependency_sections.py` — import from helpers, Iterable removed (S152)
- `src/aeat/domain/calculations/registry/_validate_exports.py` — import from helpers, Iterable removed (S153)
- `src/aeat/domain/calculations/registry/_validate_record_sections.py` — import from helpers, Iterable removed (S154)
- `src/aeat/domain/calculations/registry/_validate_revision_sections.py` — import from helpers, Iterable removed (S155)
- `src/aeat/domain/calculations/registry/_validate_surfaces.py` — import from helpers, Iterable removed (S156)
