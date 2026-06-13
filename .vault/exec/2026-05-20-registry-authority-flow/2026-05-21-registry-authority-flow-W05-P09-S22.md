---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S22'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
  - '[[2026-05-20-registry-authority-flow-adr]]'
  - '[[2026-05-20-registry-authority-flow-research]]'
---

# `registry-authority-flow` `W05.P09.S22`

Ran package-wide registry pytest with chunked diagnostics.

- Modified: `.vault/exec/2026-05-20-registry-authority-flow/2026-05-21-registry-authority-flow-W05-P09-S22.md`
- Modified: `src/aeat/locales/es.yml`

## Description

Collected the registry package test surface and executed it in bounded
alphabetic and hotspot chunks so package-wide failures could be separated
from timeout behavior. Collection found 1,799 tests under
`src/aeat/domain/calculations/registry`.

The first broad `test_[abc]` run timed out, so the gate was split further.
The broad `test_m` and `test_[n-r]` runs also exceeded the configured command
windows, but the underlying files passed when broken into smaller groups. This
confirms the residual issue for later W05.P09 steps is runtime cost and repeated
registry loading, not a deterministic correctness failure in the package-wide
registry suite.

During the registry gate, `test_config_repair_report_includes_registry_integrity_check`
surfaced an invalid YAML scalar in the Spanish locale catalogue. The locale
catalogue is owned by adjacent CLI/i18n work, but the syntax error blocked this
planned registry diagnostics step through the application diagnostics import
path. The blocker was repaired as a minimal YAML syntax correction and then
validated with the required locale CLI.

## Tests

2026-05-21 follow-up: `uv run pytest src/aeat/domain/calculations/registry
--collect-only -q` collected 1,801 tests in 1.16s after the residual
performance fixes. `uv run ruff check src/aeat/domain/calculations/registry
src/aeat/application/calculations/test_iva_compensation_history.py` passed.

The sorted registry package chunks passed in the follow-up run:

- files 0..24: 345 passed in 286.34s.
- files 25..49: 487 passed in 179.52s.
- files 50..59: 33 passed in 150.71s.
- files 60..64: 63 passed in 48.14s.
- files 65..74: 181 passed in 48.96s.
- files 75..84: 132 passed in 136.06s.
- files 85..89: 168 passed in 362.83s.
- files 90..94: 39 passed in 85.72s.
- files 95..97: 161 passed in 91.65s after caching Renta escala lookups.
- files 98..99: 28 passed in 0.91s.
- files 100..111: 163 passed in 121.64s after removing the IVA
  compensation hand-summed assertion pattern flagged by the tautology gate.

The chunked package gate is therefore correctness-green, while total runtime
remains explicitly suspicious and is tracked by `W05.P12.S29`.

`uv run pytest --collect-only -q src/aeat/domain/calculations/registry` passed
with 1,799 collected tests.

The registry package passed through these split chunks:

- `test_a` files: 40 passed in 23.69s.
- `test_b` files: 3 passed in 40.78s.
- first `test_c` subgroup: 84 passed in 198.08s.
- `test_committed_registry.py`: 41 passed in 24.96s.
- remaining `test_c` subgroup: 140 passed in 169.80s.
- `test_[d-l]` files: 407 passed in 111.05s.
- first Modelo subgroup through `test_modelo_145_source_catalogue.py`: 132 passed in 119.01s.
- Modelo 180-202 subgroup: 32 passed in 124.98s.
- `test_modelo_232_registry.py`: 34 passed in 22.50s after the coarse chunk timed out.
- Modelo 303-322 subgroup: 44 passed in 39.05s.
- Modelo 347-390 subgroup: 133 passed in 41.12s.
- Modelo 720/840, chain, and parity subgroup: 45 passed in 68.89s.
- NIF/parity/period/public-boundary subgroup: 96 passed in 4.61s.
- queries/read-parameter subgroup: 11 passed in 65.89s.
- `test_record_design.py`: 41 passed in 105.99s.
- referential-integrity, scenarios, and schema subgroup: 115 passed in 215.87s after the locale syntax repair.
- relation and remote-state subgroup: 39 passed in 101.82s.
- Renta chain subgroup: 12 passed in 70.33s.
- Renta autonomic savings scale: 66 passed in 49.88s.
- Renta state savings scale: 48 passed in 28.29s.
- Renta state general scale: 47 passed in 30.99s.
- Renta oracle, replay, required-role, cross-reference, and runtime-graph subgroup: 54 passed in 18.08s.
- `test_[s-y]` files: 137 passed in 119.42s.

`uv run python -m aeat.locales audit` passed for `ca.yml`, `en.yml`,
`es.yml`, and `hu.yml`.

`uv run python -m aeat.locales scaffold --check` passed for `ca.yml`,
`en.yml`, `es.yml`, and `hu.yml`.
