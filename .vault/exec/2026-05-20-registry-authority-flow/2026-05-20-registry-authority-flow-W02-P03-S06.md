---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-05-20'
step_id: 'S06'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W02.P03.S06`

Threaded recursive registry fingerprints into authority cache keys.

- Modified: `_authority.py`
- Created: this execution record

## Description

Changed `ValidatedRegistryAuthority.load` so the cached authority construction depends on the complete registry TOML fingerprint as well as root and source root.

## Tests

Covered by `test_authority_cache_invalidates_when_fragmented_revision_changes`.
