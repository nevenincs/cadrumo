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

# audits-resolution group-c step-5

## scope

Plan row C5: rewrite three prompt strings that leak engineering
vocabulary into operator-facing language.

## changes

Three locale-key rewrites across `es / en / ca / hu`:

- `wizard.setup.flags.notes.help` and
  `wizard.setup.notes.notes.prompt` (plus the section's `title`):
  "Notas del operador (no consumidas por el motor)" →
  "Notas para tu propio recuerdo (opcional)".
- `cli.config.setup.help`:
  "Ejecutar el asistente de configuración basado en esquema de
  forma interactiva o usando banderas" →
  "Configuración inicial guiada del perfil tributario".
- `wizard.setup.spouse.spouse-disability-grade.prompt` and the
  corresponding `flags.help`:
  "Clave de discapacidad del cónyuge" →
  "Grado de discapacidad del cónyuge (si aplica)".

Locale-specific equivalents land in en / ca / hu too. The honesty
allowlist moved from `_intentional_identical.yml` to
`_intentional_identical.json` so the locale-parity glob
(`locales_dir.glob("*.yml")`) does not pick it up as a phantom
locale.

## verification

`audit_cli_translations()` and `audit_wizard_translations()`
both return `()`.
`pytest src/aeat/locales/test_locale_translation_honesty.py
src/aeat/application/wizard/` all pass on the affected modules.
