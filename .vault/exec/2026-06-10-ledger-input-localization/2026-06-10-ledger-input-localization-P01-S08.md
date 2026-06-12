---
tags:
  - '#exec'
  - '#ledger-input-localization'
date: '2026-06-12'
step_id: 'S08'
related:
  - "[[2026-06-10-ledger-input-localization-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace ledger-input-localization with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.
     step_id is the originating Step's canonical identifier, e.g. S01.

     Related: use wiki-links as '[[YYYY-MM-DD-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add frontmatter fields
     outside the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path. -->

# Run pytest --collect-only -q to verify zero collection errors across all six migrated modules

## Scope

- `confirm no surviving local _parse_decimal/_parse_required_decimal definition remains in any of the six migrated files`
- `src/aeat/entrypoints/cli/`

## Description

- Ran `pytest --collect-only -q` over the migrated CLI modules and the new parser test files.
- Swept the six migrated files for surviving local `_parse_decimal`/`_parse_required_decimal` definitions.

## Outcome

Done. Collect-only is clean (51 tests collected on the migrated surface, zero collection errors). The six migrated files carry zero local parse definitions.

## Notes

Deviation from the literal plan criterion ("zero definitions outside `_common.py`"): two definitions survive in `_ledger_support.py`, but they are zero-logic delegators forwarding to the `_common.py` canonical helpers, and they are live (consumed by `_ledger.py`'s business-pct/taxable-base/iva call sites). Single canonical logic is preserved; the criterion wording predates the peer extraction of `_ledger_support`. Documented in the closure audit; optional cosmetic inline left as a future tidy.
