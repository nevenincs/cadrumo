---
tags:
  - '#exec'
  - '#tui-architecture'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:a431c5554766a314138b491fa3953dbb790e428de3273295e6c062b3f8bf6dc7'
step_id: 'S254'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# Prove the registry package fixed point: zero project package bindings, zero re-exports, and zero unresolved family rows

## Scope

- `src/cadrumo/domain/calculations/registry/__init__.py`

## Changes

M src/cadrumo/domain/calculations/registry/tests/test_keep_public_family.py
M dev/quality/registry_facade_family_census.v1.json

## Notes

The registry package reaches its fixed point. All seventy-eight census rows now
reach their adjudicated terminal state, and the gate's exemption table is empty,
so the assertion runs against every row with nothing carved out.

Getting there corrected four adjudications that the evidence contradicted. Two
delete rows were wrong in opposite directions: the handoff-path family was not
dead and folded into its canonical owner, while the construct reader genuinely
was and went. The loader and snapshot rows were adjudicated for privatisation of
the whole module when only the implementation can go private, because their
construction entry points are contracts that test and tooling callers outside
the package depend on.

One row's reviewed owner was simply wrong: it named the loader as the definer of
a symbol the loader only re-exported. The split exposed it, and it now names the
module that defines it.

Proved the gate bites with the table empty: planting a borrowed export on a
keep-public module reds the terminal-state assertion by row id.
