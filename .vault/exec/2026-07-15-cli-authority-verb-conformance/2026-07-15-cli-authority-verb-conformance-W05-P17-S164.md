---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:c91cce55a8e3b62bd62f2024486ad7fdec35c17dd0ac65ec27861c5ea96fbdfb'
step_id: 'S164'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Rewrite profile setup and navigation for exact switch labels and strong logout

## Scope

- `docs/how-to/profile-setup.md`

## Description

- Establish what the profile-navigation verb actually is at HEAD.
- Add the exact-name semantics the login verb enforces but the page never
  stated, and the logout counterpart.

## Outcome

SATISFIED, with the row's own premise corrected.

The row asks for "exact switch labels and strong logout". There is no switch
verb: an exhaustive walk of the materialised command tree - 290 leaves, zero
duplicates - contains no leaf whose path includes `switch` anywhere. It was
superseded by login/logout, and the page already says so, naming
`aeat config login` and warning that it is not `aeat config profile login`.

What was genuinely missing is the semantics the row calls "exact labels". The
live verb accepts a profile UUID or the EXACT label and nothing else, and takes
an optional positional so omitting it uses the already-selected profile. The
page taught none of that. It now does, with the reason attached: a partial
name, different capitalisation or shortened form is refused rather than guessed
at, because guessing which taxpayer was meant is how filings land under the
wrong one. The logout counterpart is stated alongside - it closes the session
and clears the selection, and deletes nothing.

Recording the tree measurement because it settles a question that recurs across
this campaign: five CLOSED Steps in this plan reference a `switch` verb, and it
does not exist at HEAD. Those rows were closed against a surface a peer
campaign later replaced. No operator-facing text still cites it - the shipped
locales carry no `config switch` string and the user docs carry none - so this
is stale plan prose rather than a live dead instruction.

Gates at HEAD `ec62e04591f495a4553abd9da23b0a28766938c8`:

- `uv run --no-sync pytest dev/docs/tests/test_sequence_contract.py
  src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py
  -m "" -n0` collected 362 cases and exited `362 passed in 7.89s`. The
  conformance suite resolves every command these pages cite against the live
  Click tree, so a spelling error here is a hard failure rather than a silent
  dead instruction.

## Notes

The stale references to `switch` in the repository's persona testimonials are
historical run records, not live instructions, and are correctly left alone.
