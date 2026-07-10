---
tags:
  - '#exec'
  - '#aeat-user-docs-hardening'
date: '2026-07-04'
modified: '2026-07-08'
step_id: 'S01'
related:
  - "[[2026-06-16-aeat-user-docs-hardening-plan]]"
---

# Harden authenticate-with-aeat.md

## Scope

- `docs/how-to/authenticate-with-aeat.md`

## Description

- Verify-close: read `authenticate-with-aeat.md` against its 2026-06-18-audit findings and confirm resolution at HEAD.
- Confirm finding M22 (over-states provider support): the page now marks each provider `disponible` vs `reservado (no disponible aún)` via `aeat config auth providers` - `certificate`, `clave_movil`, and `clave_permanente` are available (ClavePermanente was subsequently wired), `clave_pin` reserved - rather than presenting all five as usable.
- Confirm the master-key passphrase prerequisite is stated, `--file` is the file-input option (per the cli-pull-and-file standard), and the certificate-expiry/renewal guidance is present.

## Outcome

- Page verified compliant at HEAD; finding M22 resolved (2026-06-19 documentation batch; the available set updated to reflect the wired ClavePermanente provider). Delta: none required.

## Notes

- S-AUTH (auth-unconfigured refusal wording) is addressed on the companion read-live page; the apoderado section is accurate per the audit. CLI conformance gate green.
