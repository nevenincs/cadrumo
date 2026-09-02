---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:c196d68c08eff1070865101cf5b4f5f28adffe5f327851eef7d210cb95f47903'
step_id: 'S42'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Add an inventory-driven local compatibility command

## Scope

- `justfile`

## Changes

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

- `M` `justfile`
- `verify:` `just --dry-run python-compatibility; just --dump | Select-String -Pattern 'python-compatibility:|dev.packaging.release_cohort build|dev.ci.python_runtime_compatibility|for mode in source binary|runtime inventory produced no rows'` -> `pass`
- `verify:` `uv run --no-sync python -c 'import json; from dev.ci.python_runtime_matrix import load_runtime_inventory; inventory=load_runtime_inventory(); rows=inventory.rows; assert [row.identifier for row in rows] == ["cp313","cp314","cp315-next"]; assert [row.phase.value for row in rows] == ["stable","stable","prerelease"]; assert rows[-1].blocking is False; print("inventory-driven rows: pass")'` -> `pass`
