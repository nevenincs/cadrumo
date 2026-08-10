---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:24c0e72195d91770729edac41cbbc716f21cf3359405dab09cc55c24cfb06438'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s30-variable-envelope-code-review-audit]]"
---
# `aeat-export-fragment-generator-authority` audit: `s43 variable envelope recognition`

## Scope

Independent review of `W04.P07.S43` against the accepted generator-authority decision, its active plan row, the parser/schema authority, parser-to-IR boundary, and fixed-width generation refusal.

The review used bounded semantic discovery and exact-symbol confirmation. `src/cadrumo/domain/calculations/registry/_record_design.py` is the sole production envelope recognizer. Development modules consume its typed output; no alternate selector, duplicate parser, legacy export-layout input, or record-name classifier was found.

## Findings

### body-led-exact-composition | resolved-high | A variable body now requires the complete official composition instead of falling back to a fixed record

The parser collects marker candidates generically and enters strict validation whenever the official `Variable` body marker occurs. It requires one body, one 18-byte relative closing suffix, one `Variable` total, contiguous fixed prefix geometry, immediate body offset, and ordered source rows and ordinals. Wrong-length, missing, duplicate, mixed-total, discontinuous, and misordered compositions refuse through the production workbook parser. The parser never derives a record total from the prefix extent.

### isolated-mixed-total | resolved-high | A contradictory fixed-plus-Variable total cannot silently choose a fixed extent

A source row containing both a positive fixed total and `Variable` is independently decisive and refuses even when there is no body or closing marker. Both official `Total` and `Total:` spellings are covered by real temporary-workbook tests.

### source-epoch-coverage | resolved-medium | Real Modelo 200 and every pinned Modelo 303 binary prove the generic envelope contract

The real Modelo 200 design and all five hash-pinned Modelo 303 epochs traverse the production parser. The Modelo 303 test requires six fixed sheets plus one `DP30300` envelope, retains body/closing/total/prefix facts, and confirms the envelope is excluded from fixed records. The parser-to-IR and fixed-generation-refusal tests consume that same typed result rather than reproducing the parsing decision.

### record-name-selector | resolved-medium | The legacy DP200000-specific recognition path is absent

A structural source inspection test fails if either `DP200000` or `DP30300` reappears in `_extract_sheet_rows`. Exact search confirms those identifiers occur only in source-specific real-binary assertions and never in production recognition logic.

## Recommendations

Accept `W04.P07.S43` when the independent code-review verdict is PASS. Preserve parser-owned body-led composition recognition, strict malformed and ambiguous refusal, the five-epoch real-source regression matrix, and the structural no-name-selector assertion. Do not broaden this parser step into export-tree, business-semantics, or registry-layout work.
