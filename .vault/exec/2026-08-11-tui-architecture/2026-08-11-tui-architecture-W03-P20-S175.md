---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:e07b4b14cfae87beb7709c976e570e21303edd4dbae471e62b0ebe00133717fb'
step_id: 'S175'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Retrospectively adjudicate before S173 or any affected registry-family implementation the exactly 78 private-to-public module candidates mechanically renamed by c94133f29516b12e3529f3d154c31592562f6198 by running semantic Vaultspec-RAG owner discovery followed by a deterministic exact AST and text consumer census, generate and commit a schema-versioned fixed matrix containing exactly 78 unique rows plus a deterministic generator with check mode, require each row to record the c94133f old and new module paths, every exported symbol and categorized production, test, fixture, documentation, tooling, annotation, registration, dynamic-target, package-attribute, and transitive consumer, semantic owner and evidence, exactly one keep-public proof, hard-move/direct-import completion, privatize/external-elimination, or delete disposition, and exactly one unique canonical follow-on Step ID, fail every extra, missing, duplicate, unresolved, unrelated-grouped, omitted, mechanically inferred, or many-to-one row or Step mapping, obtain independent architecture review, and amend W03.P20 through the canonical plan CLI with one bounded disposition Step per matrix row plus one final zero-project-binding, zero-re-export, and zero-unresolved-row registry package gate before S175 can close, without implementing any disposition inside this census Step or hiding work in internal commits

## Scope

- `.vault/audit/2026-08-26-tui-architecture-registry-facade-family-census-audit.md`
- `dev/quality/registry_facade_family_census.py`
- `dev/quality/registry_facade_family_census.v1.json`
- `dev/tests/test_registry_facade_family_census.py`
- `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `c94133f29516b12e3529f3d154c31592562f6198 and its parent`
- `src/cadrumo/domain/calculations/registry/__init__.py`
- `and the exact 78 mechanically renamed module candidates plus every categorized consumer under src/`
- `dev/`
- `and docs/`

## Changes

- `M` `dev/quality/registry_facade_family_census.py`
- `M` `dev/quality/registry_facade_family_census.v1.json`
- `M` `dev/tests/test_registry_facade_family_census.py`
- `M` `.vault/plan/2026-08-11-tui-architecture-plan.md`
- `verify:` `uv run --no-sync pytest dev/tests/test_registry_facade_family_census.py -n0` -> `pass`

## Notes

The independent architecture review recorded in the census audit is derived
from the current worktree, not from an immutable Git object; the audit's
dirty-worktree-immunity wording is corrected in the same change.
