---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:1086639070eb2f4053984acb2151db1ee5e1a7140614eeef6a2ebb8af41f0962'
step_id: 'S44'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---

# Dispatch negative cases validate bindings execute safe recovery and retry original leaves

## Scope

- `dev/agent_eval/_runner.py`

## Description

- Resolve the S42 identity and validate the observed refusal through S43.
- Resolve bindings and canonical CLI arguments through production authorities and permit only safe execution policy.
- Invoke live canonical recovery, retry the exact original leaf, and observe its resulting JSON verdict.
- Never dispatch explicit no-recovery outcomes or evaluator-authored commands.

## Outcome

Commits `3fed52bea47` and `64cec618df` replace the former report-only runner with safe canonical recovery and exact-leaf retry. A retry may legitimately emit another refusal, so closure requires a valid observed verdict rather than an invented exit-zero contract.

Eight companion tests pass. Terra's owned integration run passes three tests; independent review passed both reached runner paths and identified one external registry-data failure before S44 logic. Ruff and diff checks pass.

## Notes

- The external red is a Modelo 349 registry source reference and is not part of the agent-eval runner contract.
