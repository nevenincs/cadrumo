---
tags:
  - '#exec'
  - '#tui-interface'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:5501fba06265a91e25dadd67090f318c3df070fae05d0c055e6305200a428810'
step_id: 'S14'
related:
  - "[[2026-08-11-tui-interface-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Render explicit automatic-source capabilities scope authentication needs and operation launch actions

## Scope

- `src/cadrumo/entrypoints/tui/profile/overview.py`

## Changes

- `A` `src/cadrumo/application/user_profile/acquisition_sources.py`
- `M` `src/cadrumo/entrypoints/tui/profile/overview.py`
- `verify:` `uv run --no-sync pytest src/cadrumo/entrypoints/tui/profile/ -q -m "unit or integration"` -> `pass` (21 passed)

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

"Capabilities scope and authentication needs" has no backing public contract today (no operation declares requires-auth/scope, and the existing CapabilityDecision resolver covers unrelated service opt-ins, not acquisition sources). Rendered only the explicit source identity and launch action; reported rather than fabricating a local policy.
