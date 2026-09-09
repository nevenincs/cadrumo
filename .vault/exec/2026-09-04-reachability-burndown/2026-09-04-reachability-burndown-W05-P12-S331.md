---
tags:
  - '#exec'
  - '#reachability-burndown'
date: '2026-09-09'
modified: '2026-09-09'
body_schema: 'body-v2'
body_hash: 'sha256:86b540625dbaad4b6d7dd2c3752edc6bae5e77491c3b8b08db05ff83dedcba36'
step_id: 'S331'
related:
  - "[[2026-09-04-reachability-burndown-plan]]"
---

<!-- Machine-owned: the filename, the frontmatter, the title heading and the
     Scope list are all filled by `vaultspec-core vault add exec` from the
     originating Step row; never hand-edit them. Add no frontmatter fields.
     Wiki-links belong in `related:` only, never in the body. -->

# Delete the LLM loopback protocol-vocabulary singularity scanner and embedded servers

## Scope

- `development loopback singularity gate`
- `real LLM client behavior`
- `exact reachability`
- `cadence reference`
- `and Step Record`

## Changes

- `D` `dev/tests/test_loopback_llm_singularity.py`
- `M` `.vault/reference/2026-09-04-reachability-burndown-reference.md`
- `verify:` `uv run --no-sync pytest -q src/cadrumo/llm/tests/test_client.py src/cadrumo/llm/tests/test_transport_retry_policy.py src/cadrumo/application/tests/test_provisioning.py` -> `pass`
- `verify:` `uv run --no-sync python -m dev.audit.unreachable_code --confidence exact` -> `fail`

## Notes

Exact remeasurement reports the campaign's remaining live signal: 36 unreachable modules and 278 unused symbols.
