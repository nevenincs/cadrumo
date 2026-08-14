---
tags:
  - '#exec'
  - '#test-harness-sanity'
date: '2026-08-14'
modified: '2026-08-14'
body_schema: 'body-v1'
body_hash: 'sha256:7a08d1e35786d34cae0376251fd11b55abb595fb68ba4b1b14237b26a2b26777'
step_id: 'S49'
related:
  - "[[2026-08-14-test-harness-sanity-plan]]"
---

# Generate the complete fixture ownership manifest with no unclassified records

## Scope

- `dev/quality/fixture_ownership.toml`

## Description

- Generate one deterministic ownership row for every current fixture declaration.
- Preserve owner identity, lifecycle constraints, body identity, and conservative semantic worklist groups.
- Route every repeated effective-name or repeated-body fixture to later semantic adjudication.

## Outcome

The ownership manifest accounts for all 709 current fixtures with no unclassified records. It retains 227 fixtures that are unique by both effective name and normalized body and routes 482 fixtures to semantic adjudication across 75 repeated-name families and 73 repeated-body families.

## Notes

The initial manifest used an exact name, body, and constraint match as its disposition boundary. Independent review rejected that narrow rule because it hid divergent same-name and same-body fixtures. Manifest v2 uses the conservative union rule; narrower static substitution groups remain evidence only. TOML parsing, 709 unique ordered IDs, group counts and anchors, row-digest integrity, diff integrity, and final structural review passed. The final census generation took 32.6 seconds.
