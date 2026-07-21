---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-17'
step_id: 'S31'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden troubleshooting.md

## Scope

- `docs/how-to/troubleshooting.md`

## Description

- Verify-close: read `troubleshooting.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding B4 (`ledger participation rebuild` uninvokable - the optional positional swallowed the `rebuild` token): the callback now dispatches the reserved subcommand token, so `aeat app ledger participation rebuild` runs; the page documents it as the participation-index regenerate path.
- Confirm finding M25 (the page quoted a friendly `ledger preflight` "needs a year" message the command never emits): the page now documents that `ledger preflight` takes an AEAT token AND requires `--year` - and instructs the reader to add `--year` even though the calculate-block error omits it - and shows the real `Missing option '--year'` refusal.

## Outcome

- Page verified compliant at HEAD; findings B4 and M25 resolved (B4 app fix + participation-cli surface test; M25 documented honestly). Delta: none required. CLI conformance gate green.

## Notes

- Residual m16 (invalid-PDF parser-internals leak) and the bucket-session inconsistency are APP-side findings, out of documentation-hardening scope; the doc quotes the real messages.
