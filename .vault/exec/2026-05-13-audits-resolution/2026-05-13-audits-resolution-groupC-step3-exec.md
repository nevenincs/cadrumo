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

# audits-resolution group-c step-3

## scope

Plan row C3: append a translated single-line next-step hint to
`aeat config status` when an active profile is present.

## change

`src/aeat/entrypoints/cli/_config.py`: `config_status` echoes
`tr("cli.config.status.next_step")` after the TSV block when the
profile has tax.id and activity (the empty-profile branch from B2
short-circuits before reaching this echo).

Locale catalogues `es / en / ca / hu` gain
`cli.config.status.next_step`. es / en carry real translations; ca
and hu reuse the English text (allowlist captures the state).

## verification

`aeat config status` against a configured sandbox emits the existing
TSV block followed by `Próximo paso: ` aeat app overview ` `.
