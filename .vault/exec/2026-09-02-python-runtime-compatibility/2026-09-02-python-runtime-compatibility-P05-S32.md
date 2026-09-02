---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:5a125866d8695d27191c691982d8d27828b9b6d6b144f1cc82ec39cfa19550ea'
step_id: 'S32'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Align official-data companion classifiers with stable runtime evidence

## Scope

- `packaging/cadrumo_data_official/pyproject.toml`

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

- `verify:` `uv run --no-sync python -c "import json,tomllib; from pathlib import Path; inv=json.loads(Path('dev/ci/python-runtime-matrix.json').read_text(encoding='utf-8')); data=tomllib.loads(Path('packaging/cadrumo_data_official/pyproject.toml').read_text(encoding='utf-8')); claimed={c.rsplit(' :: ',1)[-1] for c in data['project']['classifiers'] if c.startswith('Programming Language :: Python :: ')}; eligible={r['minor'] for r in inv['stable'] if r['classifier_eligible']}; assert claimed == eligible == {'3.13'}; assert inv['next']['minor'] not in claimed"` -> `pass`
