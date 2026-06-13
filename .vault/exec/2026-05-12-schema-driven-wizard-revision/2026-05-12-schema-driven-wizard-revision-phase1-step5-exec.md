---
tags:
  - '#exec'
  - '#schema-driven-wizard-revision'
date: '2026-05-12'
modified: '2026-05-12'
related:
  - "[[2026-05-12-schema-driven-wizard-revision-plan]]"
  - "[[2026-05-12-schema-driven-wizard-adr]]"
---

# r5 delete trivially-ok verifier checks

## scope

R5 removes the two vestigial verifier checks
``_check_residence_ccaa`` and ``_check_iva_regime``. Both returned
``OK`` for every input. The descriptor's ``SELECT`` widget rejects
the same out-of-domain values at prompt time, so duplicating them in
the verifier yielded no signal.

## files owned

- ``src/aeat/application/wizard/_verifier.py``
- ``src/aeat/application/wizard/test_verifier.py``

## acceptance gates run

- ``pytest src/aeat/application/wizard/test_verifier.py`` — green
  (4 tests)
- the verifier still emits findings for tax-id, activity, spouse
  consistency, EU/EEA country consistency, and obligations consistency
- ``grep -rn 'residence_ccaa_ok\|iva_regime_ok'`` returns nothing
  (no locale catalogue depended on the dropped message keys)
