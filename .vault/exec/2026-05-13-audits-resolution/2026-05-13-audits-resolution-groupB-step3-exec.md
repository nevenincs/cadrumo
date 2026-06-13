---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-schema-driven-wizard-ux-audit]]"
---

# audits-resolution group-b step-3

## scope

Plan row B3: add the `wizard.errors.select_unknown` catalogue entry
in every locale.

## change

Each of `src/aeat/locales/{es,en,ca,hu}.yml` gains a new
`wizard.errors:` block carrying translated entries for every
`wizard.errors.<reason>` key the descriptor validators emit:
`blank_integer`, `blank_path`, `blank_secret`, `blank_text`,
`checkbox_required`, `checkbox_unknown`, `checkbox_without_choices`,
`invalid_confirm`, `invalid_integer`, `invalid_tax_id` (introduced
by B1), `select_unknown`, `select_without_choices`.

es and en carry real translations. ca and hu carry the English
strings for now; B6 records the intentional-identical state in the
honesty allowlist.

## verification

A runtime probe builds a SELECT WizardQuestion and feeds it the
token `BOGUS`. The raised `WizardValidationError.translated_message`
renders the Spanish "Valor no reconocido para … Opciones válidas:
['GENERAL']." string. The raw key (still preserved as
`wizard.errors.select_unknown` in the exception message) is no
longer the user-facing surface.

`pytest src/aeat/application/wizard/test_widgets.py` returns 19
passed. The locale parity test
(`test_codebase_to_locale_parity`) was already failing before B3 (the
ASCII-restricted regex scanner misses Unicode keys) and B3 widens
the gap from 142 to 154 extra keys; B4 broadens the regex and
unblocks the gate.
