---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8ded9e4f72cf5cbfdec06833cfe68f46f816c761c9e4ece3a13b14b6f4918dd7'
step_id: 'S32'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Align official-data companion classifiers with stable runtime evidence

## Scope

- `packaging/cadrumo_data_official/pyproject.toml`

## Changes

- `verify:` `uv run --no-sync python -c "import json,tomllib; from pathlib import Path; inv=json.loads(Path('dev/ci/python-runtime-matrix.json').read_text(encoding='utf-8')); data=tomllib.loads(Path('packaging/cadrumo_data_official/pyproject.toml').read_text(encoding='utf-8')); claimed={c.rsplit(' :: ',1)[-1] for c in data['project']['classifiers'] if c.startswith('Programming Language :: Python :: ')}; eligible={r['minor'] for r in inv['stable'] if r['classifier_eligible']}; assert claimed == eligible == {'3.13'}; assert inv['next']['minor'] not in claimed"` -> `pass`
