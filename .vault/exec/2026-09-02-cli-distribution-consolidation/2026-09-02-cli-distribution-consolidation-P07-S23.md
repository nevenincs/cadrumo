---
tags:
  - '#exec'
  - '#cli-distribution-consolidation'
date: '2026-09-02'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:713f6877fef1ff82fff78fde6174b19a23170391cf8aaa3dfadf85aabf80fe12'
step_id: 'S23'
related:
  - "[[2026-09-02-cli-distribution-consolidation-plan]]"
---
# Rewrite the channel descriptor as a flat three-channel inventory

## Scope

- `docs/_data/download_channels.toml`

## Changes

M docs/_data/download_channels.toml

## Notes

The descriptor is now an inventory at schema version two: identity, platform, install
commands, package and repository names, artifact kinds and evidence rows. The tier
vocabulary, the availability states, the product-property block feeding the
cross-product tier rule and the pending-tier register are all gone.
