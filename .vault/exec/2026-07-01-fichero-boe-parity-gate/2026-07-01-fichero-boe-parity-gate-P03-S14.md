---
tags:
  - '#exec'
  - '#fichero-boe-parity-gate'
date: '2026-07-02'
modified: '2026-07-17'
step_id: 'S14'
related:
  - "[[2026-07-01-fichero-boe-parity-gate-plan]]"
---

# Register locale keys for the parity panic error and the coverage advisory via the locales CLI

## Scope

- `src/aeat/locales/en.yml`

## Description

- The coverage advisory message follows the existing modelo-export notice convention: a constant English message (`_COMPLETENESS_UNVERIFIED_MESSAGE`) on the result plus a notice `code` (`modelo.export.completeness_unverified`) as the translation key.

## Outcome

No locale-CLI keys were added: the entire modelo-export notice family (e.g. `_local_export_evidence_notice`) uses constant messages and the notice `code` as the translation anchor, and its sibling code is not registered in the locale catalogues either. Adding a locale key for only this notice would be inconsistent with the family.

## Notes

Deliberate deviation from the plan Step's "add locale keys" wording, to match the established export-notice convention rather than introduce a lone localized notice. If the export-notice family is later locale-routed, this notice joins it in the same change.
