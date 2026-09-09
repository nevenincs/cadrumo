---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:f0187e51f054008bf03e7f44d726da7ed0403c817a962e418d26149ef6e4f7c4'
step_id: 'S09'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Record exact global legal-parameter adapter callers and closure conditions

## Scope

- `src/cadrumo/domain/calculations/registry/loader.py`

## Changes

- `M` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `M` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P03-S09.md`
- `M` `.vault/plan/2026-09-09-facts-registry-plan.md`
- `verify:` `.venv/Scripts/python.exe -m pytest -n 0 dev/registry/tests/test_facts_external_constants_retirement.py -q` -> `pass`

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
