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

# audits-resolution group-b step-6

## scope

Plan row B6: add an honesty assertion for ca / hu locale values that
mirror the English text.

## changes

`src/aeat/locales/_intentional_identical.yml` (new): allowlist
mapping ``{locale: {key: reason}}``. The current state uses one
``untranslated_pending`` bucket per locale that captures the whole
"ca / hu still ships English values" state explicitly; later
translation passes replace that bucket with per-key reasons (or
remove entries entirely as real translations land).

`src/aeat/locales/test_locale_translation_honesty.py` (new):
`test_ca_hu_values_differ_from_en_unless_allowlisted` walks every
flat ``ca`` / ``hu`` value, compares to the corresponding `en` value,
and asserts the deviation is either real translation OR explicitly
allowlisted. The current wholesale "untranslated_pending" bucket
short-circuits to a pass; once any future slice removes that bucket
the test starts flagging per-key offenders.

## verification

`pytest src/aeat/locales/test_locale_translation_honesty.py -q`:
2 passed.

The honesty pin formalises the audit's "ca and hu fall back to
English without an honest marker" finding: the test now captures
that state in source rather than letting it propagate silently.
