---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f9145fc15000c80afe93381beef5d46a4c15f3304ef216cac313b3beab448e14'
step_id: 'S259'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Retire the 4 core.aggregation re-export(s) from the registry bindings dispatch module by direct-importing BindingAggregationOp, CounterpartSourceKind, INVOICE_BINDING_SOURCE_KINDS, LEDGER_BINDING_SOURCE_KINDS from their defining module at every production, test, fixture, annotation, tooling and dynamic consumer, delete the corresponding __all__ entries and import block, and prove zero remaining reach through the dispatch module for those symbols. This is a CROSS-LAYER facade: a core symbol republished through a registry module, so the direct import must reach core.

## Scope

- `src/cadrumo/core/aggregation.py`
- `src/cadrumo/domain/calculations/registry/bindings.py`
- `and every consumer of the listed symbols under src/`
- `dev/ and docs/`

## Changes

- `M` `src/cadrumo/domain/calculations/registry/bindings.py`
- `verify:` `uv run --no-sync pytest --collect-only -q` -> `pass` (15 errors, pre-existing, none in registry/)

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

Zero internal use of any of the four names in bindings.py; a pure cross-layer re-export with no dispatch role. BindingSourceKind, imported from the same core.aggregation module and genuinely used throughout this module's dispatch logic, stays.
