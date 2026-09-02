---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:7003fc14349f9d70170d2bdf9fa1a64b2f6f6caa630208043fe214b3b9f604db'
step_id: 'S31'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Align manuals companion classifiers with stable runtime evidence

## Scope

- `packaging/cadrumo_data_manuals/pyproject.toml`

## Changes

- `verify:` `uv run --no-sync python -c "import json,tomllib; from pathlib import Path; inv=json.loads(Path('dev/ci/python-runtime-matrix.json').read_text(encoding='utf-8')); eligible={r['minor'] for r in inv['stable'] if r['classifier_eligible']}; data=tomllib.load(open('packaging/cadrumo_data_manuals/pyproject.toml','rb')); claimed={c.rsplit(' :: ',1)[-1] for c in data['project']['classifiers'] if c.startswith('Programming Language :: Python :: ')}; assert data['project']['requires-python'] == '>=3.13'; assert claimed == eligible == {'3.13'}; assert inv['next']['minor'] not in claimed"` -> `pass`
