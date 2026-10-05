---
tags:
  - '#reference'
  - '#profile-registration-password-policy'
date: '2026-08-22'
modified: '2026-10-03'
body_schema: 'body-v1'
body_hash: 'sha256:04f99e975ca89bd0e08dcfc28cfe62f7ae420ec6e58e61323a4eed7e4b40a34c'
related:
  - "[[2026-08-15-profile-password-custody-per-profile-recovery-mnemonic-adr]]"
---

# `profile-registration-password-policy` reference: `tui custody validation mismatch`

This trace follows profile creation from the Textual registration screen through
the CLI presenter and application registration door into password-wrapped custody.
It also checks the scripted CLI arm, error registry, locale catalogues, and existing
unit and integration coverage.

## Summary

Profile creation has two incompatible password policies.

Therefore passwords of 8 through 14 scalars and passwords above 256 scalars are presented as acceptable and reach custody, where `ProfileCustodyPasswordError` is raised before profile publication.

The raw English password diagnostic and the localised Spanish internal-error guidance are two layers of the same escaped exception, not evidence of corrupt stored data. The inventory sentence reported alongside the failure is not present in this runtime path; the nearest matching text is architectural prose in a separate modelo-work reference, so it is adjacent context rather than a causal storage operation.

The CLI was not tested by the reporter, but source inspection establishes the same uncaught custody exception boundary.

Existing tests prove each half separately but not their parity. TUI coverage omits 8-to-14 and greater-than-256 inputs. The repair should establish one application-visible password policy matching custody before any key derivation or profile staging, translate every user-correctable refusal through `ProfileRegistrationError`, and add boundary tests at 14, 15, 256, and 257 scalars for both TUI and scripted CLI paths.
