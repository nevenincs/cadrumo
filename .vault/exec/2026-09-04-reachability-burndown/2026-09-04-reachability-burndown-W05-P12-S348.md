---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:57ee1e4dabb29952d84d1656785391ac5bdeff42dab72af0761462551d1e5ae4'
step_id: 'S348'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

# Delete the unassembled Renta Web Open browser adapter and its test-only safety and policy surface while retaining offline replay.

## Scope

- `Renta Web Open sede adapter and tests`
- `replay oracle suites`
- `stale documentation`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `src/cadrumo/adapters/outbound/aeat/sede/renta_web_open.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/_renta_web_open_safety.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_renta_web_open.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_renta_web_open_safety.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_renta_web_open_safety_live_proof.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_renta_web_open_capture_replay.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_browser_timeouts.py`
- `D` `src/cadrumo/adapters/outbound/aeat/sede/tests/test_landing_refusal_enrollment.py`
- `M` `src/cadrumo/adapters/outbound/aeat/sede/schema.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_renta_web_open_oracle.py`
- `M` `src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/domain/calculations/registry/tests/test_renta_web_open_oracle.py src/cadrumo/domain/calculations/registry/tests/test_renta_web_open_replay_corpus.py src/cadrumo/domain/calculations/registry/tests/test_renta_web_open_replay_parity.py` -> `pass`
- `verify:` `uv run --no-sync ruff check src/cadrumo/domain/calculations/registry/tests/test_renta_web_open_oracle.py src/cadrumo/adapters/outbound/aeat/sede/schema.py src/cadrumo/domain/calculations/registry/tests/test_catalogue_verification_verifiers.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `pass`
