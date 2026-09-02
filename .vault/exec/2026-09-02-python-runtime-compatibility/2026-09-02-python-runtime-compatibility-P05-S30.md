---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:66c9e5c0b1b1a4ac8e0b0bdc35a99487150e062961c8bf41b47f1bc6acd78413'
step_id: 'S30'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Add classifiers only for stable runtimes proven by the matrix

## Scope

- `pyproject.toml`
- `uv.lock`

## Changes

- `M` `pyproject.toml`
- `M` `uv.lock`
- `verify:` `uv run --no-sync pytest -q dev/packaging/tests/test_classifier_parity.py -o addopts='' -n 0; uv run --no-sync python -c "import json,tomllib; from pathlib import Path; inv=json.loads(Path('dev/ci/python-runtime-matrix.json').read_text(encoding='utf-8')); data=tomllib.load(open('pyproject.toml','rb')); claimed={c.rsplit(' :: ',1)[-1] for c in data['project']['classifiers'] if c.startswith('Programming Language :: Python :: ')}; eligible={r['minor'] for r in inv['stable'] if r['classifier_eligible']}; assert claimed == eligible == {'3.13'}; assert inv['next']['minor'] not in claimed"` -> `pass`
- `verify:` `uv lock --check; uv run --no-sync python -c "import tomllib; from pathlib import Path; data=tomllib.load(Path('pyproject.toml').open('rb')); runtime=data['project']['dependencies']; dev=[item for item in data['dependency-groups']['dev'] if isinstance(item,str)]; assert not any(item.startswith('rtoml') for item in runtime); assert any(item.startswith('rtoml') for item in dev)"` -> `pass`
