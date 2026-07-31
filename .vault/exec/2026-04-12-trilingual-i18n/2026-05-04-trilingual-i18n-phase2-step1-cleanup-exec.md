---
tags:
  - "#exec"
  - "#trilingual-i18n"
date: 2026-05-04
modified: '2026-07-17'
body_hash: 'sha256:281e7148e5ea201fdbcf96150ceebff61ed73b8e0437190477db9f269e82747b'
related:
  - "[[2026-04-12-trilingual-i18n-plan]]"
---

# cleanup-remaining-field-call-sites

Finish the i18n migration by updating all remaining call sites for the renamed fields.

- Modified: `src/aeat/domain/vat/_verify.py`
- Modified: `src/aeat/domain/vat/_lookup.py`
- Modified: `src/aeat/domain/vat/test_rules.py`
- Modified: `src/aeat/domain/transactions/_llm.py`
- Modified: `src/aeat/domain/categories/test_proportionality.py`
- Modified: `src/aeat/domain/calculations/registry/test_catalogue_verification.py`
- Modified: `src/aeat/domain/categories/test_profile.py`
- Modified: `src/aeat/domain/portals/test_metadata.py`
- Modified: `src/aeat/domain/portals/_cli.py`

## Description

Updated the following field call sites to their new i18n-compatible names:
- `VatCitation.quoted_text_es` -> `quoted_text`
- `ProportionalityRule.notes_es` -> `notes`
- `StatutoryCapVariant.label_es` -> `label`
- `CategoryCitation.quote_es` -> `quote`
- `KnownBadCitation.role_substring_es` -> `role_substring`
- `PortalMetadata.purpose_es` -> `purpose` (audit find)

## Tests

Ran unit tests for affected modules.
Verified no occurrences of old field names remain in `src/`.
