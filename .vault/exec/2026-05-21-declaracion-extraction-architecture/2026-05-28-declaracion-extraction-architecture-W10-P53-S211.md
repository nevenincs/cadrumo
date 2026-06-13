---
tags:
  - "#exec"
  - "#declaracion-extraction-architecture"
date: "2026-05-28"
modified: '2026-05-28'
step_id: "W10.P53.S211"
related:
  - "[[2026-05-21-declaracion-extraction-architecture-plan]]"
  - "[[2026-05-28-declaracion-extraction-architecture-W10-P49-S206]]"
---

# declaracion-extraction-architecture W10.P53.S211 -- M036 NOT-CHAIN-READY resolution

## Unit 1 findings

**Current period_selector**: `period_selector = { year_from = 2025, periods = ["alta", "modificacion", "baja"] }`

M036 is a censal (ad-hoc) modelo. Its revision declares census event periods, not calendar time-codes. The `select_revision` function checks both `includes_year(filing_year)` AND `period.lower() in {p.lower() for p in revision.period_selector.periods}`. For fixture `2025-0A.pdf` with `filing_year=2025, period="0A"`: year passes, but `"0a"` is not in `{"alta", "modificacion", "baja"}` -- empty candidates -- RegistrySnapshotError.

**Fixture year/period**: `2025-0A.pdf` -- year 2025, period `0A` (calendar time-code, incorrect for censal modelo)

**PDF content**: The fixture is an Alta censal. Parsing with `modelo_override="036", año_override=2025, period_override="alta"` extracts `decl.event-kind = "Alta"` successfully.

## Fix path chosen: option (b) -- corrected fixture period

No registry revision change needed. The M036 revision's period_selector is correct. The fixture filename embedded a calendar time-code (`0A`) that is semantically wrong for an ad-hoc censal modelo. Fix: rename fixture to `2025-alta.pdf` (matching the actual PDF content) and write the chain test using `period_override="alta"`.

Option (a) (extend period_selector) would be wrong: adding `"0A"` to a censal modelo's periods would corrupt the registry's semantic model. Option (c) (new revision) is not warranted: M036 did not change structure in 2025 -- only one revision exists.

## Changes

- `src/aeat/tests/fixtures/justificantes/036/2025-0A.pdf` -- renamed to `2025-alta.pdf` (git rename, 100% similarity)
- `src/aeat/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/extraction_profiles/0001-declaracion-pdf.toml` -- updated comment reference from `2025-0A.pdf` to `2025-alta.pdf`
- `src/aeat/adapters/inbound/declaracion/test_verification_chain.py` -- added `test_verification_chain_m036_parser_extracts_event_kind_casilla`; updated module docstring table (M036 row added), follow-up note, and summary (NOT-CHAIN-READY 1->0, EXTRACTION-ONLY 7->8)

## Verification chain result

`uv run --no-sync pytest src/aeat/adapters/inbound/declaracion/test_verification_chain.py -v -k "m036" --tb=short`:

```
PASSED test_verification_chain_m036_parser_extracts_event_kind_casilla [100%]
1 passed, 61 deselected in 20.07s
```

M036: NOT-CHAIN-READY -> EXTRACTION-ONLY

## Honest verdict

- Root cause was fixture naming, not registry schema. The revision period_selector is semantically correct.
- The test asserts `decl.event-kind == "Alta"` (str). No numeric formula exists for M036 casillas -- EXTRACTION-ONLY is the correct final verdict, not VERIFIED. M036 is a census event form, not a calculation form.
- ty check passes; ruff reports only pre-existing errors (not in new code range).
- `vault plan step check` closed W10.P53.S211.

## Commit

`7ab224117` -- fix(m036): resolve NOT-CHAIN-READY -- rename fixture to 2025-alta.pdf, add chain test
