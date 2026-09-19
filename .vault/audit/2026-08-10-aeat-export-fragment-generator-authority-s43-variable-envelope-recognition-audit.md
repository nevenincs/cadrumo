---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:0333c1fa0598e84019f147c516c30a7bdb3ec76989a70b751c4440208febdac1'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s30-variable-envelope-code-review-audit]]"
---
# `aeat-export-fragment-generator-authority` audit: `s43 variable envelope recognition`

## Scope

Verdict: **PASS.** The independent final re-review found no open critical, high, medium, or low findings after body-led recognition and isolated mixed-total refusal were proven against the registered corpus.

Independent review of `W04.P07.S43` against the accepted generator-authority decision, its active plan row, the parser/schema authority, parser-to-IR boundary, and fixed-width generation refusal.

The review used bounded semantic discovery and exact-symbol confirmation. `src/cadrumo/domain/calculations/registry/_record_design.py` is the sole production envelope recognizer. Development modules consume its typed output; no alternate selector, duplicate parser, legacy export-layout input, or record-name classifier was found.

## Findings

### raw-partial-marker-fallback | resolved-high | Final recognition is body-led and preserves legitimate partial-marker sources

The initial review found that a malformed or incomplete composition could fall back to a fixed record. An interim remediation treated every raw body, relative closer, or Variable-total marker as decisive. Subsequent real-source review disproved that broader rule: four Modelo 131, two Modelo 232, and four Modelo 390 designs legitimately contain closer or Variable-total facts without a Variable body. The union trigger incorrectly rejected those ten registered sources.

The accepted final remediation uses the Variable body marker as the composition trigger. Any body marker activates strict complete-envelope validation. A row that mixes a positive fixed total with `Variable` is independently decisive and refuses even without a body or closer. Relative closer and Variable-total facts without a body remain ordinary parser facts because the official corpus proves they are not unique envelope markers. The ten M131, M232, and M390 binaries remain parseable in the full registered-source gate rather than being allowlisted out.

### body-led-exact-composition | resolved-high | A recognized envelope requires the complete exact official composition and geometry

Once a Variable body is present, the parser requires one typed body, one supported relative closing, one explicit `Variable` total, contiguous fixed-prefix geometry, immediate body offset, and ordered source rows and ordinals. Wrong-length, missing, duplicate, mixed-total, discontinuous, and misordered compositions raise `RegistryValidationError`. The parser never derives a record total from prefix extent.

### mixed-total-fixed-fallback | resolved-high | Mixed fixed and Variable totals refuse without relying on another marker

Both `Total` and `Total:` punctuation variants are covered by isolated real workbook cases containing a positive fixed extent and `Variable` in the same total row. Each refuses before any fixed-record fallback, even when body and closer markers are absent.

### source-epoch-coverage | resolved-medium | Real Modelo 200 and every pinned Modelo 303 binary prove the generic envelope contract

The real Modelo 200 design and all five hash-pinned Modelo 303 epochs traverse the production parser. The Modelo 303 proof requires six fixed sheets plus one `DP30300` envelope, retains body, closing, total, and prefix facts through the typed intermediate representation, and confirms the envelope is excluded from fixed records. The parser-to-IR and fixed-generation-refusal tests consume that typed result rather than reproducing the parsing decision.

### record-name-selector | resolved-medium | Recognition has no record-name selector

A structural source inspection test fails if `DP200000` or `DP30300` appears in `_extract_sheet_rows`. Exact search confirms those identifiers occur only in source-specific real-binary assertions and never in production recognition logic.

## Recommendations

`W04.P07.S43` is accepted. Preserve parser-owned body-led recognition, isolated mixed-total refusal, strict validation after recognition, parseability of the ten registered partial-marker sources, the five-epoch Modelo 303 matrix, and the structural no-name-selector assertion. Do not restore the rejected union trigger for standalone closers or Variable-total facts. Do not broaden this parser step into export-tree, business-semantics, or registry-layout work.
