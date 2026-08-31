---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:d6410d9f43da46269be2f8d8b042f6d0f20d5258b8f1b4a9b86733db0034792b'
step_id: 'S61'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Correct `config repair quarantine`, whose help told the operator active quarantine was disabled while `--yes` moves encrypted rows out of the live table

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `python -m dev.locales scaffold --check` -> `ok in all four`
- `verify:` `pytest dev/locales/tests/test_locale_translation_honesty.py` -> `6 passed`
- `verify:` `pytest four campaign gates` -> `22 passed`

## Notes

The most consequential help defect found in this campaign, and it was reached by
chasing a verb whose name and description disagreed.

The help read: "Preview undecryptable rows; active quarantine is disabled by
preserve-first repair policy". That is false. The handler refuses only when
neither `--dry-run` nor `--yes` is given; with `--yes` it falls through the
dry-run branch and calls `quarantine_unreadable_secure_objects`, which copies
each undecryptable row's metadata and still-encrypted payload into a
`secure_objects_quarantine` archive table and then DELETES the row from the live
`secure_objects` table.

So an operator reading `--help` on a data-safety command was told it could only
look, when in fact one flag makes it move their encrypted rows out of the active
store. The "preserve-first" policy the help invoked is real but describes
something else entirely: the ciphertext is preserved in the archive rather than
deleted, so a later recovered master key can still reach it. Preserve-first
means nothing is destroyed; it does not mean nothing moves.

The help now says what the command does, names the flag that arms it, and points
at `--dry-run` for the behaviour the old text wrongly claimed was the only one
available.

No code changed. The verb, its guard and its policy are all correct as written;
only the description was wrong. It was found by reading every remaining
singleton verb for agreement between its name, its help and its handler, after
the same-subject scan had been exhausted.
