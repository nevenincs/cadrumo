---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P05.S01'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P05.S01`

Removed the obsolete `cli.config.doctor.*` block (9 keys) from the
English locale catalogue. The replacement `cli.config.repair.*` block
already landed in P03 and is the only namespace consumed by the
Typer surface in `src/aeat/entrypoints/cli/_config/__init__.py`. The
`quick_start_doctor` translation key in the root-landing section is
deliberately left in place — its lookup site in
`src/aeat/entrypoints/cli/_root_landing.py` still reads
`cli.root.landing.quick_start_doctor`. P06 owns that rename; the
string value already advertises `aeat config repair` so the rendered
output is correct today.

- Modified: `src/aeat/locales/en.yml`

## Tests

`uv run python -c "import yaml; yaml.safe_load(open('src/aeat/locales/en.yml', encoding='utf-8'))"`
parses cleanly. Full repo test suite is unrelated-broken upstream
(missing `ErrorCode` registration for `AmendmentOverrideCasillaError`
introduced in an unrelated in-flight modelo change).
