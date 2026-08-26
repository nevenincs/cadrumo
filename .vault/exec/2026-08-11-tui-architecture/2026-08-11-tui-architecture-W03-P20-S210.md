---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:2ecf2f72489a9fd293efab5d7cec49ce2d2b702a382a3cb5bb93994e864b2b38'
step_id: 'S210'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Privatize the loader implementation after eliminating every external consumer and public package reach

## Scope

- `src/cadrumo/domain/calculations/registry/loader.py`

## Changes

A src/cadrumo/domain/calculations/registry/_loader_internals.py
M src/cadrumo/domain/calculations/registry/loader.py
M 14 in-package consumers repointed onto the private implementation
M src/cadrumo/conftest.py
M dev/quality/registry_facade_family_census.v1.json

<!-- MECHANICAL LOG. One line per path touched, nothing else:
       `A path` added   `M path` modified   `D path` deleted   `R old -> new` renamed
     Paths are repo-relative, in backticks. No prose, no sentences, no
     narration of intent, outcome, or difficulty - the diff and the plan Step
     already carry those. Example:

       - `M` `src/vaultspec_core/cli/exec_cmd.py`
       - `A` `src/vaultspec_core/cli/tests/test_exec_cmd.py`
       - `D` `src/legacy/shim.py`

     Optional final line, only when a check was run:
       - `verify:` `<command>` -> `pass` | `fail`

     Optional `## Notes` section, ONLY on exception: data loss, skipped work,
     a scaffold left in code, or a persistent failure. Omit it otherwise -
     an absent section is correct; an empty one is a check finding. -->

## Notes

Sixty-three symbols moved; loader.py keeps ten. The ten are not a judgement:
they are the closure of the six externally-required functions under incoming
references. Anything the internals would still reach stays on the contract
side, which is what makes the two modules acyclic.

A hand-picked boundary failed first. The loader has mutual recursion across the
contract line, so choosing the eight that looked right left the internals
calling a contract function. Computing the closure is the difference between a
split that works and one that cycles.

Two silent corruptions came from the extraction script and were caught before
commit. Classifying top-level statements by a single Name target dropped a
tuple assignment entirely, so the split must assert kept plus moved equals the
original count. Taking a block from the `def` line stripped four `@lru_cache`
decorators without any error, so extraction must start at the first decorator
and decorator counts must be diffed old against new.

The registry-tree memo is now reset through a named contract function, which
retires a cross-package private import the fixture had carried since before
this Step. `test_loader_cache_isolation` bound three names to the loader that
the loader only re-exported; each now names the module that defines it.