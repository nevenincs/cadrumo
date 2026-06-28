---
tags:
  - '#exec'
  - '#cli-workflow-redesign'
date: '2026-05-13'
modified: '2026-05-13'
step_id: 'P06.S02'
related:
  - "[[2026-05-13-cli-workflow-redesign-config-repair-shape-plan]]"
---

# `cli-workflow-redesign` `P06.S02`

Audited `src/aeat/core/errors/_registry.py` for stale `doctor` hint
strings.

- Inspected (no modification needed): `src/aeat/core/errors/_registry.py`

## Description

`_registry.py` is the registry runtime module: it owns `ErrorCode`,
`ErrorEnvelope`, `register`, `bind_error_code`, the rendering helpers,
and the scrubbing helpers. It declares no concrete error-code rows
itself; the per-domain and per-adapter rows live under
`src/aeat/core/errors/registry/_domain.py` and `_adapters.py`. A
full-file grep for `doctor` returned zero hits, so no edit was
required. The actual hint-string updates land in P06.S03.
