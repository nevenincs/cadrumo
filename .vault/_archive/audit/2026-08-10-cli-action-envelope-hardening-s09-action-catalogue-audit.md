---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:04fc909194f15038a5525080cd8ccd79b1128a126976c0929e6e4c24c3d220af'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S09 action catalogue review`

## Scope

Reviewed `src/cadrumo/application/operator_actions/_catalogue.py` and its direct
contract tests against the accepted application-owned verdict and
schema-resolved action-chain decision. The review covered catalogue ownership,
all seven initial action identities and command keys, argument-source metadata,
determinism, immutability, duplicate and unknown handling, external-system
omission, and the application-to-entrypoint import boundary.

An independent live probe joined every target command key to both
`command_schema_refs()` and `build_verb_input_schemas(...)`. All seven command
keys resolve to registered result schemas. Every declared argument exists in
the corresponding live input schema; all declared arguments are currently
optional there, and no live required parameter is omitted. The profile-create,
profile-edit, and login bindings use verdict context; pointer repair separates
the selected profile from operator-supplied safety flags; workflow addressing
uses exact condition-evidence identities and matching fact keys. The status
action correctly declares no supplied arguments. No external-database action is
declared.

## Findings

No findings. The declarations contain no applicability predicate, filesystem
path, localized prose, command-line string, resolution status, or runtime value.
Their models are strict and frozen, nested records are immutable, entry and
argument order is canonical, duplicate action IDs and argument names fail
validation, and unknown lookup fails closed. Production application code does
not import an entrypoint module; the catalogue remains private to its package at
this step, while its model dependencies come only from application and core.

Focused verification passed: six catalogue tests, Ruff, and basedpyright. The
live schema probe independently exercised all seven registrations rather than
mirroring catalogue literals. The live join is intentionally not added to this
application unit suite: the accepted plan assigns runtime schema resolution and
insufficient-binding rejection to `W02.P04.S14` at the operator-surface
boundary.

## Recommendations

Proceed to `W02.P03.S10`, retaining the catalogue as declarative application
data. In `W02.P04.S14`, prove the live result/input-schema join and binding
sufficiency at the operator-surface boundary without importing entrypoint
schema builders into this application module or its unit tests.
