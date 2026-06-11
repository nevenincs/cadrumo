---
tags:
  - '#exec'
  - '#live-censo-calendar-reconciliation'
date: '2026-06-11'
step_id: 'S09'
related:
  - '[[2026-06-05-live-censo-calendar-reconciliation-plan]]'
---

# `live-censo-calendar-reconciliation` `W04.P04.S09` exec - unlock candidates refused

## Scope

Step `W04.P04.S09` - Unlock profile-bound live storage with a non-interactive secret-store passphrase or keychain session; `env/.env`.

## Description

- Retried the profile-bound CLI with the operator-provided candidate passphrase supplied only as a transient process environment value.
- The candidate was rejected before key derivation because it is shorter than the configured NIST SP 800-63B minimum passphrase length.
- Discovered the project has a separate `aeat_dev_test_database_password` setting used by isolated test storage and tried it as a transient `AEAT_SECRET_PASSPHRASE` without printing the value.
- The dev-test storage passphrase did not unlock the active profile store; the CLI returned the generic master-key provider failure.
- Inspected `env/.env` by key and value length only. It contains live Cl@ve identity/configuration keys but no `AEAT_SECRET_PASSPHRASE` or dev database password override.

## Outcome

- `uv run aeat --format json config --help` with the operator-provided candidate refused with the passphrase-too-short policy.
- `uv run aeat --format json app live --help` with the operator-provided candidate refused with the passphrase-too-short policy.
- `uv run aeat --format json config --help` with the dev-test database passphrase failed to obtain the active master key.
- `uv run aeat --format json app live --help` with the dev-test database passphrase failed to obtain the active master key.
- `uv run aeat --format json config status` with the dev-test database passphrase failed to obtain the active master key.

## Notes

- This step remains unchecked: no tested passphrase or keychain session unlocked the active encrypted profile store.
- The dev-test database password is for isolated test storage and is not evidence that the live profile store can be unlocked.
- W04.P04.S10 and W04.P04.S11 remain blocked until the active profile-store master key is available.
