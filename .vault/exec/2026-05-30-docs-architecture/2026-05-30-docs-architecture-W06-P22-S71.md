---
tags:
  - '#exec'
  - '#docs-architecture'
date: '2026-06-01'
modified: '2026-06-01'
step_id: 'S71'
related:
  - "[[2026-05-30-docs-architecture-plan]]"
---




# build-time CLI reference migration and json-contract autodoc regression fix

## Scope

- `docs/conf.py`
- `.gitignore`
- `src/aeat/entrypoints/cli/test_doc_reference_conformance.py`
- `src/aeat/entrypoints/cli/_schemas.py`

## Description

- Pin the English output language at the top of `docs/conf.py` before any project import so `tr()` help resolves to English for the whole build.
- Render the CLI reference from the materialised command tree via the existing flat renderer in a `builder-inited` hook, writing into `docs/cli/`.
- Gitignore `docs/cli/`; retire the committed `app.rst` / `config.rst` pages and the byte-for-byte drift test.
- Reframe the conformance test to render the reference in a fresh English-pinned subprocess into a temporary directory and assert it covers the accepted roots and the schema registry, with no committed-page reads.
- Remove the seven import-time `__module__ = __name__` reassignments in `_schemas.py`.

## Outcome

- The offline-hermetic nitpicky build (`AEAT_DOCS_OFFLINE=1`, `sphinx -n -W`) is green: zero warnings, zero errors. The CLI reference renders fresh from the live command tree on every build and cannot drift, since the output directory is never committed.
- The full json-contract surface is documented again: three classes, one exception, three functions, the type alias, and the data attribute.
- The affected unit tests pass: the json-envelope roundtrip, the JSON-schema conformance, the doc-reference conformance, and the common-output suites.

## Notes

- The migration surfaced a latent regression rather than introducing one. `_schemas.py` re-imported the strict JSON-contract primitives from their canonical core home and then rewrote each one's `__module__` to the CLI module at import time. Before this migration the documentation build never imported the CLI, so the mutation was invisible. Once the `builder-inited` hook materialised the command tree, autodoc saw `OutputSchema`, `OutputRootSchema`, `OutputSchemaError`, `SchemaEnvelope`, `emit_json_document`, `emit_json_success`, and `register_schema` as foreign imported members of their defining module and silently dropped all seven, leaving the module docstring's cross-references unresolvable (seven nitpicky failures).
- Root-caused by isolating the drop to the command-tree materialisation call and confirming the `__module__` flip with a before-and-after probe; a minimal reproduction rendered the same module correctly until the materialisation ran. A tree-wide sweep found no other `__module__` reassignment, so the fix is complete and isolated.
- The reassignment served no consumer; removing it keeps the primitives' canonical home intact and leaves `_schemas.py` as a plain re-export surface.
