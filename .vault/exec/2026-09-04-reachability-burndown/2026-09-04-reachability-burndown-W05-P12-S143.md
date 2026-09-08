---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-04'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:aaf329fad14f2ac831c73f765f6bbc33d34bd2ecf69076034fe8a43f9e358c9a'
step_id: 'S143'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Pay every dangling shipped docstring reference, delete the reference-count baseline and four-way ratchet metastate, and make the structural scanner itself a zero-target gate whose CLI refuses planted and live dangling targets

## Scope

- `shipped docstring prose`
- `development reference scanner and tests`
- `quality aggregation and CI recipe`

## Changes

- `M` `src/cadrumo/adapters/persistence/storage/envelope/secure_bound_repository.py`
- `M` `src/cadrumo/core/decimal/coercion.py`
- `M` `src/cadrumo/core/decimal/formatting.py`
- `M` `src/cadrumo/entrypoints/tui/components/theme.py`
- `M` `dev/quality/docstring_reference_targets.py`
- `M` `dev/quality/tests/test_docstring_reference_targets.py`
- `M` `dev/quality/suite.py`
- `M` `justfile`
- `M` `.github/workflows/ci.yml`
- `D` `dev/quality/docstring_reference_ratchet.py`
- `D` `dev/quality/docstring_reference_ratchet.toml`
- `D` `dev/quality/tests/test_docstring_reference_ratchet.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run pytest -q -n 0 --confcutdir=dev/quality/tests -m unit dev/quality/tests/test_docstring_reference_targets.py` -> `pass (14 passed)`
- `verify:` focused `uv run ruff check` over the scanner, tests, and four repaired production modules -> `pass`
- `verify:` exact removed ratchet API, baseline, recipe, and dangling-target scan -> `pass (zero matches)`
- `verify:` `uv run python -m dev.quality.docstring_reference_targets` -> `pass (zero dangling targets across zero modules)`
- `verify:` aggregate gate table projection -> `pass (check-docstring-references)`
