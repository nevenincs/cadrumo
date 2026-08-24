---
tags:
  - '#exec'
  - '#deadline-window-revision-authority'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:e94e03d07858d43303dd1de8910939f2988406ee0791c3d9dc265e7fa2711edc'
step_id: 'S09'
related:
  - "[[2026-08-24-deadline-window-revision-authority-plan]]"
---

# Prove deadline validation under cold construction and fingerprint-backed warm-load verdict paths with planted mutations

## Scope

- `src/cadrumo/domain/calculations/registry/tests/`

## Description

- Locate the canonical warm-load verdict path and its governing decisions with
  Vaultspec RAG, then confirm exact symbols with targeted search.
- Audit existing fingerprint and validation authorities before editing; reuse
  `loader_code_fingerprint` in both existing cache keys and create no cache,
  validator, resolver, or coordinate declaration.
- Reject digest-valid stale pickles whose restored Pydantic graph lacks fields
  from the current schema, deleting and recompiling instead of hydrating them.
- Bind writable and shipped validation verdicts to the same canonical registry
  code fingerprint so validator changes cannot inherit an older green verdict.
- Prove cold deadline invariants and warm stale-cache refusal with planted
  catalogue, qualifier, ownership, uniqueness, and identity defects.

## Outcome

Completed. The compiled cache now invalidates its former frame generation and
recursively refuses restored Pydantic objects missing any current model field.
This closes the observed stale `RegistryCatalogues` failure and the equivalent
nested pre-qualifier deadline-row path without a compatibility migration.

The existing writable and shipped verdict-key constructors now fold the existing
memoized `loader_code_fingerprint`. A green verdict can certify only the registry
tree, evidence, package, and validation/compiler/schema code that produced it.
Focused supported-year, compiled-cache, verdict-cache, ownership, uniqueness,
and qualifier tests passed; Ruff passed on every changed Python file.

## Notes

- Vaultspec RAG and exact search found one production registry-code fingerprint,
  one compiled cache, one verdict cache, and one authority consultation path;
  no redeclaration was introduced.
- The reproduced pre-fix supported-year run failed three tests because a warm
  pickle lacked `supported_filing_years`. After repair, the focused catalogue,
  compiled-cache, and verdict set passed 28 tests; the cold ownership,
  uniqueness, and qualifier mutation set passed 26 tests.
- Independent review reported no blocking finding. Its sole low coverage note,
  direct shipped-verdict code-fingerprint sensitivity, was added before closure.
