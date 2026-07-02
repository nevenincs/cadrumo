---
tags:
  - '#audit'
  - '#cross-domain-continuity'
date: '2026-07-02'
modified: '2026-07-02'
related:
  - "[[2026-05-26-cross-domain-continuity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cross-domain-continuity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cross-domain-continuity` audit: `W09.P45 operator-surface review`

## Scope

Reviewed the W09.P45 operator-surface fixes for S356 and S358.

- S356 adds operator-visible `iva_category` rendering to human `ledger list` output while preserving the existing typed JSON row contract. The audit covered the projection code, the real CLI regression test, the S356 plan row close, and the S356 execution record.
- S358 adds royalty/SGAE guidance to the existing `ledger classify --irpf-category` help text without adding automatic classification heuristics. The audit covered the locale leaves, the real CLI help regression, the S358 plan row close, and the S358 execution record.

## Findings

### w09-p45-s356 | low | no findings

No findings for the ledger-list IVA-category display fix. Human `ledger list` output now renders the persisted `iva_category` value in a localized column aligned with the row payload, including translated headers. JSON output remains on the existing typed row contract.

### w09-p45-s358 | low | no findings

No findings for the royalty guidance fix. The `--irpf-category` help text now points operators to the category catalogue and explains the Art. 25.4 versus Art. 27 distinction without advertising `capital_mobiliario` as a public ledger category id and without adding a heuristic classifier.

## Recommendations

No follow-up required for S356 or S358.
