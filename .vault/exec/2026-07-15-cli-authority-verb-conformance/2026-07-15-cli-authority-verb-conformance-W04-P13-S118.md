---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:2d5b319c4ad6c86973b652df28584e1bb93c9c92b676bcb3f10849e13a4d92af'
step_id: 'S118'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Prove certificate secret set and remove against real secure storage, including command failure after the secret mutation but before event commit followed by an idempotent retry with one correctly classified event, and reject backend selection, keyring spellings, migration, fallback, and duplicate mutation paths

## Scope

- `src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py`

## Description

`certificate secret set`/`remove` needed real-secure-storage proof, including the
failure-after-mutation-but-before-event-commit case followed by an idempotent retry that
lands exactly one correctly classified lifecycle event, plus rejection of backend
selection, keyring spellings, migration, fallback, and duplicate-mutation paths.

## Outcome

`src/cadrumo/entrypoints/cli/_config/tests/test_certificate.py` (marked
`pytest.mark.serial` because it activates the process-global master-key-provider
singleton, line 43) proves this against real encrypted secure-object storage and a real
SQLite trigger that blocks the event-history commit:
`_blocking_certificate_secret_event_commit` (lines 76-95) installs a `BEFORE UPDATE`
trigger on `secure_objects` for the event-history namespace. Three tests exercise set,
rotate, and remove: `test_certificate_secret_set_cli_resumes_failed_event_commit_as_set_once`
(478-585) fails the first `set`, confirms the secret was written but zero
`AUTH_CERTIFICATE_SOURCE_SECRET_SET` events exist, then confirms a differing-value retry
also fails (no phantom mutation) and the matching-value retry resumes to exactly one event;
`test_certificate_secret_rotate_cli_resumes_failed_event_commit_as_rotation_once`
(588-677) proves the analogous rotate case yields exactly one `ROTATED` event and one prior
`SET` event; `test_certificate_secret_remove_cli_resumes_failed_event_commit_truthfully_once`
(680-750) proves remove resumes to exactly one `REMOVED` event and a truthful repeat-remove
reports `removed\tFalse`. `test_certificate_secret_cli_exposes_no_backend_or_legacy_grammar`
(753-811) proves `--backend keyring` is rejected on both `set` and `remove` ("No such
option: --backend") and that `keyring`/`migrate`/`fallback`/`probe`/`clear`/`put`/`delete`
are all "No such command" under `certificate secret`. Companion tests
(`test_certificate_secret_set_rejects_argv_passphrase`,
`test_certificate_secret_set_without_terminal_or_stdin_refuses_cleanly`,
`test_certificate_secret_set_help_names_only_secure_channels`, lines 817-859) prove no
argv secret channel and a help surface naming only `--secrets-stdin`.

## Notes

File matches the step's declared scope exactly. Per the coordinator's brief, all
certificate tests passed in both the parallel lane (154 passed/1 failed, unrelated S112)
and the serial `-n0` lane (27 passed/1 failed, same unrelated failure), explicitly
including the three event-commit resume tests; this record cites that run rather than
re-executing the `os_keychain`-adjacent serial suite myself.
