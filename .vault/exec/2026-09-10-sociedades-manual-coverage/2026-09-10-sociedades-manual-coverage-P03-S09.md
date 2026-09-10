---
tags:
  - '#exec'
  - '#sociedades-manual-coverage'
date: '2026-09-10'
modified: '2026-09-10'
body_schema: 'body-v2'
body_hash: 'sha256:b59993c47dac984825e02f227bf462b715b98949e58653e6c40d9e1328d8ff1a'
step_id: 'S09'
related:
  - "[[2026-09-10-sociedades-manual-coverage-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Regenerate the CLI reference and Pagefind inputs from the live localized command graph

## Scope

- `dev/docs`

## Changes

- `M` `docs/cli/app/registry.rst`
- `M` `docs/_static/cli-tree.json`
- `M` `dev/docs/tests/test_cli_tree.py`
- `verify:` `uv run pytest dev/docs/tests/test_cli_reference_pages_are_not_stubs.py dev/docs/tests/test_cli_anchor_parity.py` -> `pass`
- `verify:` `uv run pytest dev/docs/tests/test_cli_tree.py -k "sociedades_manual_list or projection_covers_every_collected_path or write_cli_tree_emits_default_static_path" dev/docs/tests/test_sequence_build_gate.py` -> `pass`

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
