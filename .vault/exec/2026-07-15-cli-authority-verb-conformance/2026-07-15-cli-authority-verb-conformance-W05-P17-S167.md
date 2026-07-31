---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:aaa218d62dae6c4db77f36e72fe8ab41bcb0302d6fa32afc2dc03977f1e5a69d'
step_id: 'S167'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Align the how-to index with logout, passphrase, recovery, and reset lifecycle terminology

## Scope

- `docs/how-to/index.md`

## Description

- Sweep the how-to index for retired lifecycle vocabulary.
- Replace the two cards still describing verbs the cutover removed.

## Outcome

SATISFIED, and it found two live stale citations rather than none.

The data-access card told operators to "change or recover your passphrase,
lock, or reset". LOCK is retired - the cutover removed it and made strong
logout the sole local-session close - so the index advertised a verb that no
longer exists, on the one card an operator reads when looking for how to
protect their data. It now says log out.

The profile card offered "Create, inspect, switch, export, import, rename, or
delete". SWITCH is likewise gone, superseded by login. The card now names the
real mechanism and points at logging in to the profile you want active, which
is what the profile guide teaches.

Both were invisible to an obvious search. A sweep for the removed command
strings `config lock` and `config switch` returns nothing across the whole
documentation tree, because the index writes the bare verb inside running
prose. The pattern has to fit the shape the data actually uses, and here that
meant searching for the bare word and then excluding the legitimate homonyms -
file locks, acquisition locks, idle-lock windows and `.lock` files, all real
and all correct.

Gates at HEAD `ec62e04591f495a4553abd9da23b0a28766938c8`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed in 7.89s`. The
  conformance suite resolves every command these pages cite against the live
  Click tree, so a spelling error here is a hard failure rather than a silent
  dead instruction.

## Notes

The residual `lock` occurrences elsewhere in the documentation were each
checked and are unrelated concepts, not the retired verb.
