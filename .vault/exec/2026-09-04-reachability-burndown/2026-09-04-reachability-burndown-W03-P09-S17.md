---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-04'
body_schema: 'body-v2'
body_hash: 'sha256:61e1e5897909a1675340bb3bd6e14de3e319396fa5637d34dc450e0bde0cbec0'
step_id: 'S17'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Merge the duplicated TypeAdapter declarations at their owning registry boundary

## Scope

- `src/cadrumo/domain/calculations/registry`

## Changes

- `A` `src/cadrumo/core/url_validation.py`
- `A` `src/cadrumo/core/tests/test_url_adapter_is_canonical.py`
- `M` six modules repointed onto the canonical adapter
- `verify:` `uv run --no-sync lint-imports` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/categories src/cadrumo/adapters/inbound/justificante` -> `pass`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/core/tests/test_url_adapter_is_canonical.py` -> `pass`

## Notes

Six modules each built their own `TypeAdapter(AnyHttpUrl)` under FOUR different names:
`_ANY_HTTP_URL_ADAPTER`, `_HTTP_URL_ADAPTER`, `_URL_ADAPTER` and
`_SITE_HEALTH_URL_ADAPTER`. The adapter is stateless and identical wherever it is built,
so each copy was a duplicate. They are now `ANY_HTTP_URL_ADAPTER` in `core/url_validation`,
which every layer may import.

The names mattered more than the copies. `_URL_ADAPTER` is ALSO the name
`domain/portals/_entries/common` gives to a `TypeAdapter(HttpUrl)` -- a different
validator. Merging on the name rather than on the validated type would have swapped one
check for another at a call site that never asked for it, so the portals adapter was
deliberately left alone and the canonical module is named for the type it validates.

Because this adds a `core` import to domain and adapter modules, the layered architecture
was verified rather than assumed: `lint-imports` reports 11 contracts kept, 0 broken.

## Notes on a corrected rationale

The first version of this module's docstring and its gate asserted that `HttpUrl`
constrains the scheme while `AnyHttpUrl` does not. That is FALSE in this pydantic version:
measured directly, both reject `ftp://`. What actually separates them is a maximum URL
length that `HttpUrl` enforces and `AnyHttpUrl` does not, so a 2090-character URL passes
one and fails the other.

The gate now asserts that measured difference. Had the original claim shipped, the module
would have carried a false rationale for a real decision, and the gate would have been
asserting a property that does not distinguish the two types -- passing while proving
nothing. The first attempt used a `core_schema` equality comparison, which failed for
reasons unrelated to the distinction and was replaced with the behavioural assertion.

Teeth proven by reintroducing a local `_URL_ADAPTER`: the gate exits 1 naming the module,
and exits 0 once restored.
