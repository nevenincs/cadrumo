---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-27'
body_schema: 'body-v2'
body_hash: 'sha256:420f926a05b77971df053ae741aa6d43d2eb9df5cb14c615cfc01c8b0bfa2a95'
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

## Closure

The independent architecture review is APPROVED. It ran four rounds and its
verdict was verified against the code and the tree at a HEAD past the one under
test, so it held across peer commits rather than only at the tested commit.

Conditions and how each was discharged:

- Gitignored evidence contamination -- the interrupted benchmark run's 795 MB
  source mirror supplied 44 per cent of consumer entries; evidence now
  enumerates tracked paths and the orphaned mirror was deleted.
- Transitive closure excluded from the checked comparison, with its reason.
- Import-as-definition conflation -- imported names are no longer locations.
- Fabricated locator -- a start line below 1 is refused.
- Templated review prose -- the normalizer now erases single-quoted spans, and
  33 rows were re-authored from their definer modules across two fields.
- Loosened path assertion -- replaced by a real `_definition_lines` constraint.
- Re-export follow-on scope -- discharged by decomposition into the 17
  per-definer Steps; both facades now carry zero re-exported `__all__` entries.
- Review status returned to pending, and flipped to approved only on the
  reviewer's verdict, in one commit with the constant the checker matches it
  against.

The two-successive-HEADs precondition was withdrawn by the reviewer: once the
contamination was removed it measured tree activity rather than artefact
quality. Its replacement is green at the reviewed HEAD plus a safe refresh that
both RUNS and preserves every adjudication -- the second clause added after a
peer deletion proved the refresh could be jammed by the drift it exists to
absorb.

Completion criteria beyond the review, verified rather than assumed: 78 unique
follow-on disposition Step ids, every one canonical and present in the plan;
and the final zero-project-binding, zero-re-export registry package gate
`W03.P20.S254`, which is closed.

## Changes

- `M` `dev/quality/registry_facade_family_census.py`
- `M` `dev/quality/registry_facade_family_census.v1.json`
- `verify:` `python -m dev.quality.registry_facade_family_census --refresh-reviewed` -> `pass`
- `verify:` `python -m dev.quality.registry_facade_family_census --check` -> `pass`
- `verify:` `uv run --no-sync pytest dev/tests/test_registry_facade_family_census.py -n0` -> `pass`
