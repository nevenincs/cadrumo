---
tags:
  - '#exec'
  - '#cli-action-envelope-hardening'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:33345e7c445229d55ded5867e17ed835370b5febc843c892f95188113f918f3e'
step_id: 'S95'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-plan]]"
---
# Teach operators the actionable-versus-no-recovery refusal algorithm

## Scope

- `src/cadrumo-harness/src/cadrumo_harness/_data/agent/rules/cadrumo-operator-envelope-reading.md`
- `src/cadrumo-harness/src/cadrumo_harness/tests`
- `src/cadrumo/core/tests`
- `src/cadrumo/application/operator_actions/tests`

## Description

- Branch exclusively on whether the nested resolved action is present.
- Honor conditionality, resolved bindings, and exact missing arguments before invoking the canonical CLI path.
- Require an explicit no-recovery outcome when no action exists and forbid inferred commands.
- Pin the shipped rule to the live envelope fields and closed enum values.

## Outcome

Commit `e24e6b22ce` teaches the complete executable/no-recovery algorithm and adds mutation-sensitive conformance against the real schema and enums. It covers terminal, safety, and operator-decision outcomes without defining alternate production authority.

VaultSpec RAG and independent review found no schema or action-authority redeclaration. Harness conformance passes seven tests; core and operator-actions verification passes 57 tests. Ruff and diff checks pass.

## Notes

- Operators may never infer a command from error code, message, context, evidence, or condition identity.
