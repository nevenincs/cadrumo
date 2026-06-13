---
tags:
  - '#exec'
  - '#audits-resolution'
date: '2026-05-13'
modified: '2026-05-13'
related:
  - "[[2026-05-13-audits-resolution-plan]]"
  - "[[2026-05-13-wizard-ux-transcripts-audit]]"
---

# audits-resolution group-e step-1

## scope

Plan row E1: re-run the UX transcripts for the regression scenarios
and confirm the previously-broken behaviour now renders cleanly.

## transcripts

The CLI surface relocated `status` from `aeat config status` to
`aeat config profile status` in a concurrent stream; the
B2-introduced empty-profile guard was reverted by that move and
required re-application onto the new location (commit f12fbb38).

### B1: empty-profile status

`aeat config profile status` against a fresh sandbox emits the
translated `Sin perfil configurado. Ejecuta ` aeat config init ` para
empezar.` and exits with code 0. No pydantic traceback.

### D1: quiet-mode NIF rejection

`aeat config init --quiet --tax-id INVALID --activity design`
exits non-zero (code 2). The validator raises
`WizardValidationError` keyed on `wizard.errors.invalid_tax_id`.

### D3: post-setup NIF rejection

`aeat config set tax.id NOT_A_NIF` after a clean setup exits with
code 2 and the translated invalid-NIF message.

### D8d: SELECT validation

`aeat config init --quiet --tax-id 00000000T --activity design
--iva-regime BOGUS` exits with code 2. Typer's click-level enum
validation rejects BOGUS before reaching the wizard surface; the
descriptor's `validate_select` would otherwise emit the translated
`wizard.errors.select_unknown` message (B3 catalogue entry confirms).

### F5: post-reset status

`aeat config init --quiet --tax-id 00000000T --activity design`,
then `aeat config reset --scope PROFILE --yes`, then
`aeat config profile status` emits the translated empty-profile
message and exits 0. No pydantic traceback.

### Quickstart line

`aeat --help` renders `Quickstart: aeat config init --tax-id NIF
--activity ACTIVIDAD` (es locale) — drops the spurious
`--profile NAME` and includes the required `--activity`.

## ca / hu honesty allowlist

`src/aeat/locales/_intentional_identical.json` captures the
wholesale `untranslated_pending` state for ca and hu. The
`test_locale_translation_honesty.py` regression gate passes; the
allowlist short-circuit applies until per-key translations land in a
follow-up slice.
