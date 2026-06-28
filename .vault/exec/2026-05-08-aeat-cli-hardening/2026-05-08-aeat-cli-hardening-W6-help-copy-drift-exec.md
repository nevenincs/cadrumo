---
tags:
  - '#exec'
  - '#aeat-cli-hardening'
date: '2026-05-08'
modified: '2026-05-08'
related:
  - '[[2026-05-08-aeat-cli-hardening-plan]]'
  - '[[2026-05-08-aeat-cli-hardening-review-audit]]'
---



# `aeat-cli-hardening` `W6 Output And Help Contract` `Help Copy Drift`

Closed the first low-risk help drift slice for `A23` and `A27`.

- Modified: `src/aeat/entrypoints/cli/_setup.py`
- Modified: `src/aeat/entrypoints/cli/test_user_cli_surface.py`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/hu.yml`
- Created: `2026-05-08-aeat-cli-hardening-review.md`
- Created: `2026-05-08-aeat-cli-hardening-W6-help-copy-drift.md`

## Description

`aeat setup auth reset` now reads command help, option help, and its explicit
scope error from the locale catalogue instead of inline English strings.

`aeat app invoice import --kind` now documents the actual accepted values:
`issued` and `received`. The Spanish text keeps the operator explanation while
naming the machine values.

This slice intentionally did not add compatibility aliases or change accepted
invoice values. It fixes the misleading help text only.

## Tests

Verification commands:

- `uv run --no-sync pytest src/aeat/entrypoints/cli/test_user_cli_surface.py -k "reset_help or kind_help"`
- `uv run --no-sync aeat setup auth reset --help`
- `uv run --no-sync aeat app invoice import --help`
- `uv run --no-sync python -c "import yaml, pathlib; [yaml.safe_load(pathlib.Path(p).read_text(encoding='utf-8')) for p in ['src/aeat/locales/es.yml','src/aeat/locales/en.yml','src/aeat/locales/ca.yml','src/aeat/locales/hu.yml']]; print('locale yaml ok')"`
- `uv run --no-sync ruff check src/aeat/entrypoints/cli/_setup.py src/aeat/entrypoints/cli/test_user_cli_surface.py`
- `uv run --no-sync ruff format --check src/aeat/entrypoints/cli/_setup.py src/aeat/entrypoints/cli/test_user_cli_surface.py`

The first attempted YAML check used `python -m yaml`, which failed because the
installed YAML package has no `__main__`. The follow-up `yaml.safe_load`
verification passed for all touched locale files.
