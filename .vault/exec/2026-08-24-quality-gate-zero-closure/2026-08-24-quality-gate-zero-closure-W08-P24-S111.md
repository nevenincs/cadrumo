---
tags:
  - '#exec'
  - '#quality-gate-zero-closure'
date: '2026-09-07'
modified: '2026-09-07'
body_schema: 'body-v2'
body_hash: 'sha256:db59f4f6d323056bc09f663e025f37717e41376ada9c2db0bf89df19b2e2820a'
step_id: 'S111'
related:
  - "[[2026-08-24-quality-gate-zero-closure-plan]]"
---

# Land the self-echoing-token detector: an assertion keyed on a token the invocation itself supplies, which the refusal quotes back verbatim, cannot separate a retired surface from one that resolved and failed otherwise (Terra xhigh fixes and refactors)

## Scope

- `dev/quality/`

## Changes

- `A` `dev/quality/self_echoing_tokens.py`
- `M` `src/cadrumo/entrypoints/cli/tests/test_app_diagnostics_telemetry.py`
- `verify:` `uv run --no-sync python -c <paired real invocation and real-tree/synthetic detector probes>` -> `pass`
- `verify:` `uv run --no-sync pytest -q -n 0 -m '' src/cadrumo/entrypoints/cli/tests/test_app_diagnostics_telemetry.py::test_telemetry_flush_rejects_an_unknown_tier` -> `pass`
- `verify:` `uv run --no-sync ruff check dev/quality/self_echoing_tokens.py src/cadrumo/entrypoints/cli/tests/test_app_diagnostics_telemetry.py` -> `pass`
