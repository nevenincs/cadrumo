---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:a713e175d3dbd94546555aecbdb0af4631011477e7824b7f2a49d2008f2f6e29'
step_id: 'S30'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Add classifiers only for stable runtimes proven by the matrix

## Scope

- `pyproject.toml`

## Changes

- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_classifier_parity.py -o addopts='' -n 0; uv run --no-sync python -c "import json,tomllib; from pathlib import Path; inv=json.loads(Path('dev/ci/python-runtime-matrix.json').read_text(encoding='utf-8')); data=tomllib.load(open('pyproject.toml','rb')); claimed={c.rsplit(' :: ',1)[-1] for c in data['project']['classifiers'] if c.startswith('Programming Language :: Python :: ')}; eligible={r['minor'] for r in inv['stable'] if r['classifier_eligible']}; assert claimed == eligible == {'3.13'}; assert inv['next']['minor'] not in claimed"` -> `pass`
