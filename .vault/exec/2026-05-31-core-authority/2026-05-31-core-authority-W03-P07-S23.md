---
tags:
  - '#exec'
  - '#core-authority'
step_id: S23
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
---

# core-authority W03.P07.S23 — DELETE-004/005/006 ripgrep gate: BLOCKED

## Blocking Condition

The plan's own execution gate "after ripgrep confirms zero callers" was not
satisfied. All three constants in `core/external_constants.py` have active
callers:

- `LATIN_1_ENCODING`: imported as `_LATIN_1_ENCODING` in
  `domain/calculations/registry/_export_parse.py` line 15, used at line 210.
- `PROVENANCE_SOURCE_MANUAL_CLI`: imported in `application/user_profile/__init__.py`
  (line 26, used at lines 105, 116) and `application/user_profile/_testing.py`
  (line 17, used at line 47); also `domain/user_profile/_values.py` line 17,
  used at line 135.
- `PDF_MIME_TYPE`: imported as `_PDF_MIME_TYPE` in
  `adapters/outbound/aeat/sede/_declarations.py` (line 50) and
  `adapters/outbound/aeat/sede/_walker.py` (line 32).

## Resolution

Step left unchecked. No code changes made. These are actively-used
centralisation constants, not dead constants. The tracker's "zero consumer"
claim was incorrect. Deferred to a future campaign.
