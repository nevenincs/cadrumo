---
tags: ['#exec', '#live-pull-verification-sweep']
date: '2026-06-12'
modified: '2026-06-12'
related:
  - '[[2026-06-12-live-pull-verification-sweep-plan]]'
---

# `live-pull-verification-sweep` `W01.P02` summary

W01.P02 established the pull-only safety contract through central access-gate proof, remote-operation policy proof, static mutation guards, and operator-facing IVA evidence wording cleanup.

- Modified: `src/aeat/entrypoints/cli/_app_live.py`
- Modified: `src/aeat/entrypoints/cli/_app_live_payloads.py`
- Modified: `src/aeat/entrypoints/cli/tests/test_live_read_subgroups.py`
- Modified: `src/aeat/entrypoints/cli/tests/test_registry_cli.py`
- Modified: `src/aeat/locales/ca.yml`
- Modified: `src/aeat/locales/en.yml`
- Modified: `src/aeat/locales/es.yml`
- Modified: `src/aeat/locales/hu.yml`
- Modified: `docs/how-to/check-aeat-notifications.md`
- Created: `.vault/exec/2026-06-12-live-pull-verification-sweep/2026-06-12-live-pull-verification-sweep-W01-P02-S04.md`
- Created: `.vault/exec/2026-06-12-live-pull-verification-sweep/2026-06-12-live-pull-verification-sweep-W01-P02-S05.md`
- Created: `.vault/exec/2026-06-12-live-pull-verification-sweep/2026-06-12-live-pull-verification-sweep-W01-P02-S06.md`
- Created: `.vault/exec/2026-06-12-live-pull-verification-sweep/2026-06-12-live-pull-verification-sweep-W01-P02-S07.md`

## Description

The phase proves the current live-read access path routes through the central live-read gate, live writes refuse through the permanent central write gate, registry remote-operation policies fail closed for write-shaped actions, and static CLI/outbound guards reject write-shaped live surfaces. The final row removes operator-facing `remote-state` vocabulary from the combined IVA wallet command and replaces it with `pull-evidence`, while leaving backend implementation names intact for the existing read-only acquisition service.

Verification included focused access-gate, remote-operation, command-tree, Sede no-write, Renta Web safety, JSON schema, documented-command conformance, locale parity, and ruff checks. The phase did not initiate an authenticated AEAT pull; live credential and matching-profile requirements remain open in later rows.
