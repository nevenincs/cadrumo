---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-20'
modified: '2026-07-17'
body_hash: 'sha256:19f18ff01836e6cecc6a5309a4aba7cf0014313157c67c3891f13b98c63e8161'
step_id: 'S08'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W02.P03.S08`

Aligned filing runtime caching with authority fingerprints.

- Modified: `_authority.py`
- Created: this execution record

## Description

The filing runtime provider already computes registry fingerprints before constructing providers; fixing the authority cache made that existing cache key effective instead of returning stale path-cached authority objects.

## Tests

`uv run pytest src/aeat/application/filing/test_runtime.py src/aeat/application/filing/test_filing.py -q` passed.
