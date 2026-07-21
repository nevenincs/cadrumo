---
tags:
  - '#exec'
  - '#cadrumo-product-rename'
date: '2026-07-12'
modified: '2026-07-12'
step_id: 'S37'
related:
  - "[[2026-07-12-cadrumo-product-rename-plan]]"
---

# Update the slim-wheel clean-install probe to Cadrumo names

## Scope

- `dev/packaging/smoke_core.py`

## Description

- Retarget source paths, wheel glob, archive prefixes, imports, install target, executable, version assertion, and optional-extra remedy to Cadrumo.
- Preserve `registry/aeat` leaves as authority-owned taxonomy evidence.
- Isolate installed-wheel subprocess settings from unrelated host product state.
- Run the real wheel build and fresh virtual-environment installation probe.

## Outcome

The slim-wheel probe now expects `cadrumo`, `cadrumo-*.whl`, `cadrumo/_data`,
`cadrumo[anthropic]`, Cadrumo imports, and the installed `cadrumo` script, with no
former distribution, import, member, or executable expectation. Ruff, formatting,
residue, plan, and diff checks pass.

## Notes

The first real run exposed an installed import inheriting former-product host
state; the second exposed the same leak in the default CLI check. Both child
processes now receive isolated Cadrumo storage and database settings. The final
run built and installed the real wheel and advanced through installed data and
runtime-surface checks into CLI profile/config work, but the outer 124-second
command budget expired before the smoke manifest was written. This timeout is
recorded as incomplete end-to-end acceptance evidence rather than a passing run.
