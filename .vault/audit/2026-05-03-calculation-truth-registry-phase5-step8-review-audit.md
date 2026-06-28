---
tags:
  - '#audit'
  - '#calculation-truth-registry'
date: '2026-05-03'
modified: '2026-05-03'
related:
  - '[[2026-05-03-calculation-truth-registry-rebuild-plan]]'
  - '[[2026-05-03-calculation-truth-registry-phase5-step8-exec]]'
---

# `calculation-truth-registry` Code Review

CALC-STEP8-001 | MEDIUM | Orphaned modelo-specific fixture truth remained in runtime package

Initial review found `_test_fixtures.py` still present under the runtime
`_formats` package. The file was no longer imported after generated-module test
deletion, but it still carried Modelo 130/303 header and casilla fixture data in
`src`, which violated the slice intent of retaining only shared primitives.

Resolution:

- Deleted `_test_fixtures.py`.
- Tightened the deletion gate so non-test runtime files under `_formats` must
  exactly equal `__init__.py`, `_deserialise.py`, `_ingest.py`, `_record_spec.py`,
  and `_serialise.py`.

CALC-STEP8-002 | LOW | Primitive docs still described concrete per-modelo Python modules

Initial review found `_record_spec.py` and `_serialise.py` still describing
committed concrete modelo modules as the source of export specs.

Resolution:

- Rewrote docstrings to describe registry-backed specs and loaders.

Follow-up review result:

- No findings.
- Reviewer confirmed the prior Medium and Low findings were resolved.

Residual risk:

- Primitive serializer/deserializer coverage remains, but registry-backed
  export-layout completeness is still future work.
