---
tags:
  - '#exec'
  - '#semantic-dedup-epic'
date: '2026-06-13'
modified: '2026-06-13'
step_id: 'S18'
related:
  - "[[2026-06-13-semantic-dedup-epic-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace semantic-dedup-epic with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S18 and 2026-06-13-semantic-dedup-epic-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Promote canonical normalize_decimal_separators and redirect the eight inline European-decimal separator sites and ## Scope

- `src/aeat/core/decimal/_coerce.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Promote canonical normalize_decimal_separators and redirect the eight inline European-decimal separator sites

## Scope

- `src/aeat/core/decimal/_coerce.py`

## Description

- Add canonical `normalize_decimal_separators(text, *, strip_thousands)` to
  `core/decimal/_coerce.py` and export it from `core.decimal`.
- Redirect the eight inline separator sites — `sede/_iva_compensation_wallet_parsing.py`
  (full Spanish), `sede/_censo.py` (×2 comma-only), `registry/_export_parse.py`
  (×2 comma-only), `registry/_renta_web_open_oracle.py` (full Spanish, conditional),
  `inbound/pdf/_label_regex.py` (×2: full-Spanish and comma-only branches) — to the
  helper, preserving each site's own validation, symbol-stripping, locale-detection
  and error handling.

## Outcome

The repeated comma/dot separator idiom is single-sourced; the pdf
comma-as-thousands-strip branch (not the kernel) is left as-is. Helper
unit-verified (`"1.234,56"`->`"1234.56"`); 1080 parsing tests pass; ruff and
collect-only clean. Landed as commit `95cdf474e`.

## Notes

Reclassified from the earlier ruled-out/marginal disposition after the directive
to land every behavior-preserving consolidation. F1 (tax-id) and F2 (fichero
`_formats`) remain genuinely not-actionable without a behavior change.
