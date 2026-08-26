---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:f7b3fe79f9043c591e58fed93dced8fcd1ffefc90b28c9fde51bfa0578b9d291'
step_id: 'S91'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Prove zero production or shared-test imports of the TUI, zero Textual outside its root, and a fully importable canonical package

## Scope

- `src/cadrumo/tests/test_import_hygiene_gate.py`

## Changes

M dev/tests/test_import_hygiene_gate.py

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

The Step row cites src/cadrumo/tests/test_import_hygiene_gate.py; the gate lives at
dev/tests/test_import_hygiene_gate.py, which the architecture rule places outside the src
test lanes deliberately. Code takes precedence, so the assertions landed there.

The whole-tree sweep found three real reaches, all function-local CLI launch seams into the
TUI view hosts. Those are the intended direction and were declared with reasons rather than
rewritten. Textual containment and canonical-package importability needed no exemption.
