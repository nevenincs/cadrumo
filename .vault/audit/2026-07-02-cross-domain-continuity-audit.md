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

Reviewed the W09.P45 operator-surface fixes for S356, S358, S219, and S331.

- S356 adds operator-visible `iva_category` rendering to human `ledger list` output while preserving the existing typed JSON row contract. The audit covered the projection code, the real CLI regression test, the S356 plan row close, and the S356 execution record.
- S358 adds royalty/SGAE guidance to the existing `ledger classify --irpf-category` help text without adding automatic classification heuristics. The audit covered the locale leaves, the real CLI help regression, the S358 plan row close, and the S358 execution record.
- S219 localizes the `NO_PENDING_OBLIGATION` workflow-gate refusal for `modelo work file` through the existing error-rendering boundary. The audit covered the exception mapping, registry key, locale leaves, renderer tests, the S219 plan row close, and the S219 execution record.
- S331 localizes malformed modelo work `KEY=VALUE` guidance and the cross-period not-applicable verify advisory. The audit covered the shared parser, localized finding text, real CLI malformed-binding regression, existing row-parser coverage, locale leaves, the S331 plan row close, and the S331 execution record.

## Findings

### w09-p45-s356 | low | no findings

No findings for the ledger-list IVA-category display fix. Human `ledger list` output now renders the persisted `iva_category` value in a localized column aligned with the row payload, including translated headers. JSON output remains on the existing typed row contract.

### w09-p45-s358 | low | no findings

No findings for the royalty guidance fix. The `--irpf-category` help text now points operators to the category catalogue and explains the Art. 25.4 versus Art. 27 distinction without advertising `capital_mobiliario` as a public ledger category id and without adding a heuristic classifier.

### w09-p45-s219 | low | no findings

No findings for the no-pending-obligation localization fix. `NO_PENDING_OBLIGATION` now resolves its human refusal text through the active output language while preserving the raw `abort_code`, `stage`, workflow result summary for telemetry, and non-`NO_PENDING_OBLIGATION` workflow summaries.

### w09-p45-s331 | low | accepted locale serializer churn

No behavioral findings for the malformed `KEY=VALUE` localization fix. The shared modelo work parser now explains `KEY=VALUE` as key on the left of one equals sign and value on the right, and the cross-period not-applicable verify advisory uses localized operator prose while retaining legal and source references.

The locale CLI rewrote nearby YAML scalars while setting the S331 leaves. This is accepted as CLI-owned serialization churn because locale files must be updated through `aeat.locales`, not hand-edited.

## Recommendations

No follow-up required for S356, S358, S219, or S331.
