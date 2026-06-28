---
tags: ["#exec", "#declaracion-extraction-architecture"]
date: '2026-05-26'
modified: '2026-05-26'
step_id: 'W07.P26.S163'
related:
  - '[[2026-05-21-declaracion-extraction-architecture-plan]]'
---

# declaracion-extraction-architecture W07.P26.S163

Authored parametrized corpus round-trip tests for M130: tax-id extraction over all 15 PDFs (2021-2T through 2024-4T) plus structural gap documentation tests asserting `numeric_casilla` profile raises `DeclaracionParseError` with `coverage=0` for every corpus specimen.

## Files modified

- `src/aeat/adapters/inbound/declaracion/test_parser_boundary.py`

## Tests added

**`test_parser_extracts_modelo_130_tax_id_from_corpus[*]`** (15 variants)

Calls `_extract_tax_id` directly on all 15 M130 corpus PDFs. Asserts `Y0000001S` for each. Exercises PDF reader + NIF regex for the full 2021-2024 corpus range.

**`test_parser_modelo_130_corpus_numeric_casilla_profile_gap[*]`** (15 variants)

Calls `parse_declaracion` with `modelo_override="130"` and asserts `DeclaracionParseError` is raised with:
- `coverage=0` in the message (all 19 targets missing)
- `missing=` substring confirming the coverage-gap failure path

**Why M130 corpus PDFs cannot be parsed:**

The M130 AEAT printed form places box numbers at the END of label lines (e.g. `...Ingresos computables ... 01`) and prints monetary values as a detached block at the bottom of page 2. The `numeric_casilla` strategy requires box number at LINE START. The `named_label` strategy also fails because values are not adjacent to any label. No extraction is possible from M130 corpus PDFs with the current parser strategy set.

The gap test is a positive structural assertion — it will alert maintainers if:
- The profile's `failure_semantics` changes to allow silent partial success
- `min_coverage` is lowered without intentional review
- A future corpus PDF specimen has a different layout that accidentally triggers extraction

## Gate results

```
src/aeat/adapters/inbound/declaracion/test_parser_boundary.py  84 passed (includes 15+15 new M130 variants)
ruff check: All checks passed!
```
