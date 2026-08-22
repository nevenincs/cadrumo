---
tags:
  - '#reference'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-08-22'
body_schema: 'body-v1'
body_hash: 'sha256:abb579965dc0462c944ebebefe9c52612cd58f2f3155944c83733fb872e04496'
related:
  - "[[2026-08-15-profile-password-custody-per-profile-recovery-mnemonic-adr]]"
---

# `profile-registration-password-policy` reference: `tui custody validation mismatch`

This trace follows profile creation from the Textual registration screen through
the CLI presenter and application registration door into password-wrapped custody.
It also checks the scripted CLI arm, error registry, locale catalogues, and existing
unit and integration coverage.

## Summary

Profile creation has two incompatible password policies. The application assessment
in `src/cadrumo/application/user_profile/_registration.py:142` uses the core NIST
minimum and only tests a lower bound. The TUI relies on that assessment in
`src/cadrumo/adapters/inbound/tui/_registration_screen.py:410`, and the application
repeats the same incomplete preflight at
`src/cadrumo/application/user_profile/_registration.py:227`.

Custody is stricter. `validate_profile_password` in
`src/cadrumo/adapters/persistence/storage/custody/_records.py:77` accepts 15 through
256 Unicode scalars, refuses surrogate code points, and caps strict UTF-8 at 1024
bytes. Therefore passwords of 8 through 14 scalars and passwords above 256 scalars
are presented as acceptable and reach custody, where
`ProfileCustodyPasswordError` is raised before profile publication.

The TUI presenter catches only `ProfileRegistrationError` at
`src/cadrumo/entrypoints/cli/_config/_manager_frontend.py:451`. The custody exception
therefore becomes a failed Textual worker and is rendered through the generic internal
failure path in `src/cadrumo/adapters/inbound/tui/_credential_screen.py:128`. The raw
English password diagnostic and the localised Spanish internal-error guidance are two
layers of the same escaped exception, not evidence of corrupt stored data. The
inventory sentence reported alongside the failure is not present in this runtime path;
the nearest matching text is architectural prose in a separate modelo-work reference,
so it is adjacent context rather than a causal storage operation.

The scripted CLI arm reaches the same defect: it invokes the same registration door
and catches only `ProfileRegistrationError` in
`src/cadrumo/entrypoints/cli/_config/_scripted_registration.py:120`. The CLI was not
tested by the reporter, but source inspection establishes the same uncaught custody
exception boundary.

Existing tests prove each half separately but not their parity. The application test
in `src/cadrumo/application/user_profile/tests/test_registration.py:188` encodes the
lower minimum as acceptable, while custody boundary coverage in
`src/cadrumo/adapters/persistence/storage/custody/tests/test_records.py:126` correctly
enforces the 15-to-256 scalar contract. TUI coverage omits 8-to-14 and greater-than-256
inputs. The repair should establish one application-visible password policy matching
custody before any key derivation or profile staging, translate every user-correctable
refusal through `ProfileRegistrationError`, and add boundary tests at 14, 15, 256, and
257 scalars for both TUI and scripted CLI paths.
