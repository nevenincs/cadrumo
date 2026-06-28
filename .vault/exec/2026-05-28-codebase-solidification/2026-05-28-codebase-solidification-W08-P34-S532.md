---
tags:
  - '#exec'
  - '#codebase-solidification'
date: '2026-05-31'
modified: '2026-05-31'
step_id: 'S532'
related:
  - '[[2026-05-28-codebase-solidification-plan]]'
---

# `codebase-solidification` `W08.P34.S532`

ENROLL: `LATIN_1_ENCODING` constant from `aeat.core.external_constants` in all BOE export-format test files, replacing 20+ bare `"iso-8859-1"` string literals.

- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_fichero_boe_roundtrip.py` (14 occurrences)
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_currency_edge_cases.py` (6 occurrences)
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_envelope.py` (6 occurrences)
- Modified: `src/aeat/adapters/outbound/aeat/export/_formats/test_record_spec.py` (1 encoding arg; regex match pattern left as `r"iso-8859-1|latin"`)

## Description

`LATIN_1_ENCODING = "latin-1"` (Python codec alias for ISO 8859-1). Each test file received a `from aeat.core.external_constants import LATIN_1_ENCODING` import; every `encoding="iso-8859-1"` and `.encode("iso-8859-1")` call was replaced with the constant. The `match=r"iso-8859-1|latin"` regex in `test_record_spec.py` was intentionally preserved because it tests both codec alias forms in error messages.

Grep-post-condition: `grep -rn '"iso-8859-1"' src/aeat/adapters/outbound/aeat/export/_formats/` returned 0 lines.

## Tests

S540 inventory test `test_no_bare_iso8859_1_in_export_test_package` (in `src/aeat/test_w08_p34_latin1_inventory.py`) confirms zero bare `"iso-8859-1"` literals in the export test package. Passed.
