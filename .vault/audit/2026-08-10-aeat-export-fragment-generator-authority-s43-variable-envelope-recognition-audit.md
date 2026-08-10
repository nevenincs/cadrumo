---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:a00fd55656323598e055e8b910ea9aa7611b50fe9233dcb9f8d05d04017ec85b'
related:
  - "[[2026-08-10-aeat-export-fragment-generator-authority-adr]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-plan]]"
  - "[[2026-08-10-aeat-export-fragment-generator-authority-s30-variable-envelope-code-review-audit]]"
---
# `aeat-export-fragment-generator-authority` audit: `s43 variable envelope recognition`

## Scope

Verdict: **PASS.** The independent re-review found no open critical, high, or medium findings after raw-marker remediation.

Independent review of `W04.P07.S43` against the accepted generator-authority decision, its active plan row, the parser/schema authority, parser-to-IR boundary, and fixed-width generation refusal.

The review used bounded semantic discovery and exact-symbol confirmation. `src/cadrumo/domain/calculations/registry/_record_design.py` is the sole production envelope recognizer. Development modules consume its typed output; no alternate selector, duplicate parser, legacy export-layout input, or record-name classifier was found.

## Findings

### raw-partial-marker-fallback | resolved-high | Every raw variable-envelope marker now enters strict refusal instead of silently becoming a fixed record

The initial review found that a standalone `Variable` total or relative `***` closer, and a malformed body or closer lacking parsed coordinates, could be dropped before typed marker construction. The parser now tracks raw body, relative-closing, and Variable-total declarations before numeric conversion. Every partial or malformed constellation enters the refusal path, so it cannot become a fixed record or derive a total from its prefix.

Ten real registered source binaries exercise the new failure boundary: four Modelo 131, two Modelo 232, and four Modelo 390 designs. The normal parseability gate excludes only that declared refusal set, while a paired parameterized real-source gate requires each exact failure. This preserves deliberate current-source rejection rather than hiding those marker rows behind a green broad parseability result.

### body-led-exact-composition | resolved-high | A complete envelope requires the exact official composition and geometry

The parser requires one body, one 18-byte relative closing suffix, one `Variable` total, contiguous fixed prefix geometry, immediate body offset, and ordered source rows and ordinals before constructing the typed envelope. Wrong-length, missing, duplicate, mixed-total, discontinuous, and misordered compositions raise `RegistryValidationError`. The parser never derives a record total from prefix extent.

### source-epoch-coverage | resolved-medium | Real Modelo 200 and every pinned Modelo 303 binary prove the generic envelope contract

The real Modelo 200 design and all five hash-pinned Modelo 303 epochs traverse the production parser. The Modelo 303 test requires six fixed sheets plus one `DP30300` envelope, retains body/closing/total/prefix facts, and confirms the envelope is excluded from fixed records. The parser-to-IR and fixed-generation-refusal tests consume that typed result rather than reproducing the parsing decision.

### record-name-selector | resolved-medium | The legacy DP200000-specific recognition path is absent

A structural source inspection test fails if either `DP200000` or `DP30300` reappears in `_extract_sheet_rows`. Exact search confirms those identifiers occur only in source-specific real-binary assertions and never in production recognition logic.

## Recommendations

`W04.P07.S43` is accepted. Preserve parser-owned recognition, strict malformed and partial refusal, the ten-source real partial-envelope matrix, the five-epoch Modelo 303 matrix, and the structural no-name-selector assertion. Do not broaden this parser step into export-tree, business-semantics, or registry-layout work.
