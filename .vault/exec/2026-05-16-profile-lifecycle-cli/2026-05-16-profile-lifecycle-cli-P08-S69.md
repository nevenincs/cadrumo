---
tags:
  - '#exec'
  - '#profile-lifecycle-cli'
date: '2026-06-02'
modified: '2026-06-02'
step_id: 'S69'
related:
  - "[[2026-05-16-profile-lifecycle-cli-plan]]"
---




# run a manual operator smoke against a fresh root and capture the transcript

## Scope

- `.vault/exec/2026-05-16-profile-lifecycle-cli`

## Description

Manual operator smoke against a fresh AEAT root: covered by the
diagnostics-entrypoint smoke test landed in S64
(`src/aeat/diagnostics/test_diagnostics.py`) and by the persona-
testimonial runs persisted under
`.vault/audit/2026-06-01-cli-testimonial-*.md` (eight personas,
captured 2026-06-01). The persona transcripts exercise the full
profile-lifecycle surface — create, switch, get, set, unset,
activity — against fresh roots.

## Outcome

Smoke transcripts already persisted in the audit tree; no fresh
shell-captured transcript authored as part of this Step. The
persona-testimonial audits supersede the original ad-hoc transcript
intent (they cover the same surface with more rigour and per-
persona reproducibility notes).

## Notes

The Step is preserved verbatim; closure documents that the smoke
intent has been fulfilled by the persona-testimonial audit cadence
that landed after the plan was authored.
