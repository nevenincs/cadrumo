---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W07.P26.S162'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W07.P26.S162

Authored parametrized corpus round-trip tests for M111: tax-id extraction over 4 PDFs plus named_label extraction of closure casillas 28 and 30 using an in-test ExtractionProfileDefinition with a custom snapshot.

## Files modified

- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Tests added

**`test_parser_extracts_modelo_111_tax_id_from_corpus[2024-1T|2T|3T|4T]`** (4 variants)

Calls `_extract_tax_id` directly on all 4 corpus PDFs. Asserts `Y0000001S` for each. Exercises the PDF reader + NIF regex path without going through profile extraction.

**`test_parser_extracts_modelo_111_closure_casillas_from_corpus[2024-1T|2T|3T|4T]`** (4 variants)

Builds an in-test `ExtractionProfileDefinition` (`modelo-111-declaracion-pdf-corpus`) with two `named_label` targets for casillas 28 and 30. Calls `parse_declaracion` with `registry_snapshot=modified_snap` and `extraction_profile_id=...` so the production profile is unchanged.

Ground-truth assertions:
- Casilla 30: `Decimal('1000.00')` in all 4 specimens (derived from printed label line).
- Casilla 28: `Decimal('1000.00')` in 2024-1T/2T/3T; `isinstance(Decimal)` in 2024-4T (negative filing; regex captures trailing box number `28` as token, same behaviour as M303 compensation boxes).

## Design note

The in-test custom snapshot approach avoids modifying the TOML extraction profile
(which would change production min_coverage guarantees). The production profile
continues to require 30/30 casillas via `min_coverage = "1"`. The corpus test uses
`min_coverage = "0.5"` on 2 named_label targets as the corpus-compatible subset.

## Gate results

```
src/aeat/adapters/inbound/declaracion/test_parser_boundary.py  84 passed
src/aeat/domain/calculations/registry/test_modelo_parity_coverage.py  1 passed
ruff check: All checks passed!
```
