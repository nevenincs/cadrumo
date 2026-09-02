---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:e0ff0726b8d5d5b67c539189a4a4ef1e375467da9a4160f77afc3befbd1e379d'
step_id: 'S06'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Replace the stale Python ceiling assertion with the open-floor policy

## Scope

- `dev/audit/security.py`

## Changes

- `M` `dev/audit/security.py`
- `verify:` `uv run --no-sync ruff check dev/audit/security.py; uv run --no-sync python -c "from pathlib import Path; text=Path('dev/audit/security.py').read_text(encoding='utf-8'); assert 'requires Python' in text and 'no upper bound' in text; assert '>=3.13,<3.14' not in text; assert '>=3.13,<3.15' not in text"` -> `pass`

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
