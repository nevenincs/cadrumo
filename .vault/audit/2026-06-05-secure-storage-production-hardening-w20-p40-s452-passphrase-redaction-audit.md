---
tags:
  - '#audit'
  - '#secure-storage-production-hardening'
date: '2026-06-05'
modified: '2026-06-05'
related:
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `secure-storage-production-hardening` `W20.P40.S452` passphrase and redaction audit

## S452-001 | PASS | Passphrase bootstrap is settings-backed

The passphrase resolver reads `aeat_secret_passphrase` from centralized settings and
the fail-closed unset-path test now uses `override_settings(aeat_secret_passphrase=None)`
to reach the real prompt boundary. The deleted legacy failclosed test no longer uses
monkeypatching or a fake callback to simulate prompt behavior.

## S452-002 | PASS | Custody harness no longer uses secret env handoff

The custody lifecycle harness now accepts the test passphrase as a subprocess
argument, converts it into `Settings` in the child process, and keeps `extra_env` for
non-secret active-profile precedence only. `AEAT_TEST_SECRET_PASSPHRASE` no longer
appears in the custody integration test surface.

## S452-003 | PASS | Central redaction covers multi-word passphrase assignments

The central logging scrubber now redacts quoted and unquoted assignment-shaped
passphrases across whitespace. Focused coverage proves `passphrase=correct horse
battery staple status=locked` removes every secret word while preserving the adjacent
`status=locked` context.

## S452-004 | PASS | Residual environment use is explicitly justified

The only residual environment reference in the reviewed custody lifecycle surface is
the subprocess harness environment sanitizer. It removes inherited `AEAT_` and
`PYTEST_` values before rebuilding the child process settings, and separate
`AEAT_ACTIVE_PROFILE` cases exercise non-secret profile precedence. This does not
carry passphrase material.

Disposition: close `W20.P40.S452`. Remaining W20 work stays open for guard narrowing,
broader convention/provenance follow-up, central CLI redaction enrollment proof, and
the profile-switch compatibility decision.
