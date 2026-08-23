---
tags:
  - '#exec'
  - '#secure-storage-performance-hardening'
date: '2026-08-23'
modified: '2026-08-23'
body_schema: 'body-v1'
body_hash: 'sha256:3f8f611e4f5e308a6a70e83615942545ee555d3c908d1b244ba5377088790c13'
step_id: 'S12'
related:
  - "[[2026-08-22-secure-storage-performance-hardening-plan]]"
---

# Extend lazy import failure coverage across nested groups and leaves for required and optional dependencies

## Scope

- `src/cadrumo/entrypoints/cli/tests/`

## Description

- Exercise the S09 lazy-node kernel through real temporary Python packages in
  fresh subprocesses instead of replacing import or command-resolution code.
- Cover exact declared optional misses, unclassified required misses,
  same-namespace internal misses, transitive misses, ordinary `ImportError`,
  `SyntaxError`, and module-initialization failures at both nested groups and
  nested leaves.
- Prove root and parent help and completion remain metadata-only, selected
  dispatch imports no sibling, required failures retry without caching and
  preserve their original causes, and optional unavailable nodes cache one
  materialized command.
- Exercise the installed required-dependency refusal and the exact optional
  unavailable surface in every supported locale through real CLI dispatch.
- Plant an external classifier mutation and confirm the exact-optional gate
  fails before restoring the untouched tracked tree.
- Resolve every independent review finding and rerun the scoped quality and
  behavior gates.

## Outcome

Nested lazy import failure semantics are now certified at both node kinds. An
exact missing declared dependency is the only path that materializes the
localized unavailable feature. Missing first-party, same-namespace internal,
or transitive modules retain their real `ModuleNotFoundError` as the cause of
the typed required refusal. Other import, syntax, and initialization defects
escape unchanged. None is converted into an unknown command, and failure does
not import a sibling.

Parent and root help and completion enumerate registration metadata without
loading the selected child. Required failures are deliberately retried and
retain a fresh original cause; the successfully constructed optional
unavailable command is cached by identity. The production required refusal
keeps the shared JSON envelope in Spanish, English, Catalan, and Hungarian,
while the production optional fallback is classified, decorated, helped, and
dispatched through `LazySubcommand` in all four locales.

The final focused lane passed 48 tests across the S09 loader and S12 failure
surfaces, including 29 new S12 integration cases. Scoped Ruff formatting and
lint and scoped `ty` analysis passed. The externally injected classifier
mutation made the exact-optional dispatch gate fail with an assertion, proving
the detector is not tautological. Independent review's initial HIGH and MEDIUM
findings were remediated and re-reviewed with no open blocking finding.

## Notes

The first probe run produced eight failures because callbackless Typer fixtures
collapsed into commands instead of the intended nested groups. The fixtures
were corrected to use the real group topology; no production-kernel change was
needed. This distinction is recorded because those reds were test-construction
defects, not evidence of a runtime regression.

A concurrent shared-worktree writer included the initial S12 test and helper
change in commit `e731378590` beside unrelated session-sealing work, and the
initial review audit landed in `816f4f3c64`. The final review fixes, execution
record, and plan transition were staged by exact path; no unrelated registry,
custody, or audit work was absorbed or reverted. S13 was not started.
