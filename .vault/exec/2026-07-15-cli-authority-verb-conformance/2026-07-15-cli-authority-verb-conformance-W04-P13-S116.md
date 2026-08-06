---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:4fc5f4a385ef39c974fb0ae17fcf31607da81cb7b42d2b9f1a704143160f7136'
step_id: 'S116'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Remove certificate backend selection and key set, remove certificate secrets only by name through secure storage, and expose no compatibility alias or migration surface

## Scope

- `src/cadrumo/entrypoints/cli/_config/_certificate.py`

## Description

The certificate `secret set`/`remove` verbs had to lose any backend-selection option and
address a named certificate source's secret only through real secure storage, with no
compatibility alias, keyring selector, migration prerequisite, or fallback surface.

## Outcome

`src/cadrumo/entrypoints/cli/_config/_certificate.py` declares `certificate_secret_set`
(lines 396-475) and `certificate_secret_remove` (lines 485-534) with parameters limited to
`--name`, `--secrets-stdin`, and `--output-language`/`--language` — no `--backend` option
is declared on either command, and neither reads a passphrase from `argv` (the secret
arrives only via `_CertificateSecretSetSecrets`, a strict `extra="forbid"` model, or a
no-echo prompt). A file-wide `rg` for `backend|keyring|migrat|fallback` in
`_certificate.py` returns zero hits, confirming no selector, migration prerequisite, or
fallback participates in the module at all. `set_operator_certificate_source_secret` /
`remove_operator_certificate_source_secret` are called with only `name` and the resolved
`SecretStr`, addressing the selected profile's secure storage exclusively.

## Notes

Verified by direct read of `_certificate.py` in full plus a targeted `rg` sweep for
`--backend`/keyring/migrat/fallback tokens across
`src/cadrumo/entrypoints/cli` (zero production hits). Cited the coordinator's gate run
(all certificate tests passed in both lanes per the coordinator's summary) rather than
re-executing.
