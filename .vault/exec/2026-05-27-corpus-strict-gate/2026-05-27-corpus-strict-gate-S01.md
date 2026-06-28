---
tags:
  - "#exec"
  - "#corpus-strict-gate"
step_id: "S01"
date: 2026-05-27
modified: '2026-05-27'
commit: "91b0633fc"
task: "190"
related:
  - "[[2026-05-19-profile-lifecycle-disaster-plan]]"
---

# corpus-strict-gate S01 — gate required_text checks behind corpus_strict flag

## What was done

Added a `corpus_strict: bool = True` parameter to `verify_legal_reference` and
`verify_legal_catalogue` in `_legal.py`.  When `False`, the `required_text`
corpus check is entirely skipped; key/id alignment and known-bad citation checks
still run.

`RegistryValidator.__init__` gains a matching `catalogue_corpus_strict: bool = True`
parameter stored as `self._catalogue_corpus_strict` and forwarded to
`verify_legal_catalogue` inside `_validate_catalogues`.

`_load_authority` now constructs the production authority's validator with
`catalogue_corpus_strict=False`, so `bindings list`, `work calculate`, and every
snapshot-consuming verb are decoupled from pending corpus annotations.

`verify_registry_tree` (the maintainer audit path) compensates by calling
`_verify_legal_catalogue(authority.catalogues.legal, source_root=source_root, corpus_strict=True)`
explicitly after `authority.validate_registry()`.

The `_CatalogueCacheKey` type gained a `bool` slot for `catalogue_corpus_strict`
to prevent a strict and a non-strict validator sharing the same catalogue objects
from cross-contaminating the module-level `_CATALOGUE_FAILURE_CACHE`.

## Files changed

- `src/aeat/domain/calculations/registry/_legal.py` — `corpus_strict` param on `verify_legal_reference` + `verify_legal_catalogue`
- `src/aeat/domain/calculations/registry/_validate.py` — `catalogue_corpus_strict` param + cache key fix
- `src/aeat/domain/calculations/registry/_authority.py` — production authority uses `catalogue_corpus_strict=False`
- `src/aeat/application/registry/__init__.py` — `verify_registry_tree` runs strict check explicitly
- `src/aeat/domain/calculations/registry/test_catalogue_verification.py` — two regression tests

## Test results

All 33 tests in `test_catalogue_verification.py` and all 49 tests in
`test_referential_integrity.py` pass (exit code 0).

## Cache bug surfaced and fixed

Discovered that the module-level `_CATALOGUE_FAILURE_CACHE` was keyed on
`(id(legal), id(sources), source_root_key)` without including the strictness
flag.  A strict validator's result was returned verbatim to a subsequent
non-strict validator sharing the same catalogue objects.  Fixed by adding
`catalogue_corpus_strict` as the fourth element of the cache key.
