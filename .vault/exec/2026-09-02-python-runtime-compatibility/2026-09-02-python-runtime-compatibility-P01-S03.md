---
tags:
  - '#exec'
  - '#python-runtime-compatibility'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:f28c673db0b7d143f6430f2c6d2a17bda310064096debeaa8b5243a1bab9fcbc'
step_id: 'S03'
related:
  - "[[2026-09-02-python-runtime-compatibility-plan]]"
---

# Add explicit stable and prerelease runtime records and classifier eligibility

## Scope

- `dev/ci/python-runtime-matrix.json`

## Changes

- `A` `dev/ci/python-runtime-matrix.json`
- `verify:` `uv run --no-sync python -c "import json; from pathlib import Path; p=json.loads(Path('dev/ci/python-runtime-matrix.json').read_text(encoding='utf-8')); assert p['current_stable_minor']=='3.14'; assert [r['minor'] for r in p['stable']]==['3.13','3.14']; assert p['next']['minor']=='3.15'; assert p['next']['phase']=='prerelease'; assert p['next']['classifier_eligible'] is False"` -> `pass`
