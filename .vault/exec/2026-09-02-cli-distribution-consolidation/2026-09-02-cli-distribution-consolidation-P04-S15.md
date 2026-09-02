---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:8858edcd02bd783623c71c1f89a741527740ba2222d01a76ff809a01a281c774'
step_id: 'S15'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Unlist the superseded plugin from the marketplace descriptor

## Scope

- `packaging/marketplace`

## Changes

D packaging/marketplace/.claude-plugin/marketplace.json
D packaging/marketplace/.claude-plugin/supersedes.json
D packaging/marketplace/README.md
D packaging/marketplace/.gitignore

## Notes

The local descriptor is gone with the host-extension channel it served, so nothing in
this repository advertises the plugin any more. The live listing is a separate
repository and remains published: it still serves the pre-rename plugin under the
former product name. Withdrawing it is an outward action on that repository, not a
change here, and it is not covered by this Step.
