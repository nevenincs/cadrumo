---
tags:
  - "#exec"
  - "#codebase-solidification"
date: "2026-05-28"
modified: '2026-05-28'
step_id: "S183"
related:
  - "[[2026-05-28-codebase-solidification-plan]]"
  - "[[2026-05-27-centralized-module-drift-audit]]"
---

# codebase-solidification W01.P07.S183 — centralize encoding alias map

## Outcome

Created `src/aeat/domain/calculations/registry/_record_spec.py` exposing
`ENCODING_ALIAS_MAP: Mapping[str, str]` — the canonical nine-entry
fichero-BOE encoding alias normalization dict previously inlined in `_schema.py`.

Removed `_FICHERO_BOE_ENCODING_ALIASES` from `_schema.py` and updated
`_normalise_fichero_boe_encoding` to call `ENCODING_ALIAS_MAP.get(...)`.
Added `from ._record_spec import ENCODING_ALIAS_MAP` import to `_schema.py`.

The `_export_parse.py:207` site is a decode-fallback literal (`body.decode("latin-1")`),
not an alias-normalization reference; it is out of scope for this step
(the step targets the normalization dict, not raw codec fallbacks).

Note: the `_schema.py` commit also carries InputKind enum migration WIP
from a concurrent campaign that was already staged in the index; those
changes pass all tests and are orthogonal to S183.

## Collision signal

`_schema.py` had InputKind enum WIP (staged by another campaign). That
WIP was already in the index; I staged my addition (`ENCODING_ALIAS_MAP`
import) on top. All tests pass with the combined state.

## Commit

`0ed384302`
