---
tags:
  - '#exec'
  - '#profile-password-custody'
date: '2026-08-24'
modified: '2026-08-24'
body_schema: 'body-v1'
body_hash: 'sha256:f9d0ee42c9b3895d21494f16be0eb956e30024fbd0a3ea4c04915c34f0b1fa6d'
step_id: 'S229'
related:
  - "[[2026-08-13-profile-password-custody-plan]]"
---

# Resynchronize the Spanish, Catalan, and Hungarian Sphinx gettext catalogues from stable English sources and retire the generated-page environment-overrides orphans

## Scope

- `docs/locales/es/LC_MESSAGES/ and docs/locales/ca/LC_MESSAGES/ and docs/locales/hu/LC_MESSAGES/`

## Description

- Confirm the authored English documentation tree carries no local source edits.
- Run the canonical `dev.docs.i18n` extraction and three-language update once.
- Retire the three generator-owned environment-overrides catalogue orphans.
- Preserve existing translations and leave editorial completion to S230-S232.
- Run real orphan, fresh-extraction drift, diff-hygiene, and formal review gates.

## Outcome

Spanish, Catalan, and Hungarian catalogues now match the current authored user
page msgid sets. The mechanical update touched the same three source catalogues
per language, preserved every unchanged msgstr byte-for-byte, carried changed
messages forward as fuzzy, and left new profile strings blank. No generated POT
output or environment-overrides orphan is committed. Formal review passed with
no findings.

## Notes

The extraction completed with pre-existing documentation warnings from
unrelated sequence-golden drift and excluded generated/CLI references. They did
not prevent template generation or catalogue synchronization. Translation
completion is intentionally deferred to S230, S231, and S232.
