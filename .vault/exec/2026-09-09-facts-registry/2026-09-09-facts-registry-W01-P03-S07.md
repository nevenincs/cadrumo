---
tags:
  - '#exec'
  - '#facts-registry'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:34c1642de72fc9289a5928f0ace56bb67b8af6583b4d798e5b5ae7ea0d671abb'
step_id: 'S07'
related:
  - "[[2026-09-09-facts-registry-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Classify every statutory declaration and production consumer

## Scope

- `src/cadrumo/core/external_constants.py`

## Changes

- `A` `dev/registry/analysis/facts_external_constants_retirement.toml`
- `A` `dev/registry/tests/test_facts_external_constants_retirement.py`
- `A` `.vault/exec/2026-09-09-facts-registry/2026-09-09-facts-registry-W01-P03-S07.md`
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
