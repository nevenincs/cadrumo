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

# audits-resolution group-c step-2

## scope

Plan row C2: emit a translated two-line success message after
`--quiet` setup so the operator sees confirmation plus a next-step
pointer.

## changes

`src/aeat/entrypoints/cli/_config.py`: the wizard-command wrapper
inspects `kwargs.get("quiet")` after the inner callable returns and
emits two locale-rendered lines: `cli.config.setup.success.saved`
(carries the profile name) and
`cli.config.setup.success.next_step` (points at
`aeat app overview`).

Locale catalogues `es / en / ca / hu` gain
`cli.config.setup.success.{saved, next_step}`. es and en carry real
translations; ca and hu reuse the English text (allowlist captures
the intentional-identical state).

## verification

`aeat config init --quiet --tax-id 00000000T --activity design`
against an isolated sandbox emits:

    Perfil 'default' guardado.
    Próximo paso: ejecuta `aeat app overview` para revisar tu próxima obligación.

Exit code 0.
