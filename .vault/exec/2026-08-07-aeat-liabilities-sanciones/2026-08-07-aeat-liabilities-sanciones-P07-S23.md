---
tags:
  - '#exec'
  - '#aeat-liabilities-sanciones'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:e32e69f690b598f4fc686ceb46b0753c0231b8abb9322266a39c18a47091b325'
step_id: 'S23'
related:
  - "[[2026-08-07-aeat-liabilities-sanciones-plan]]"
---
# Author real es, en, ca and hu values for the new deudas CLI help and label keys via python -m dev.locales set, then scaffold and scaffold --check clean. Lands as ONE unit with P04.S10 through S12 because the codebase-to-locale parity gate is tree-wide and immediate, so no ordering exists in which the CLI rows are green before these values exist in all four catalogues. The original en.yml and hu.yml peer-WIP blocker is discharged

## Scope

- `src/cadrumo/locales`

## Description

- Establish that this row was NOT complete, against a prior reading that it
  was. All five keys carried the locales scaffold's self-referencing
  placeholder, value byte-identical to the dotted key, in all four catalogues.
- Author real values for all five keys in all four catalogues through the
  locales CLI, never by editing a catalogue file.
- Refuse any cross-locale collision before writing, since a value equal to
  another locale's value for the same key is counted untranslated by the
  honesty ratchet.
- Stage the result through the apply-cached drive, because the catalogues
  acquired a peer's Catalan content while the writes were running.

## Outcome

All twenty values are authored and no key carries a placeholder. Spanish is the
source; Catalan translates the domain noun as the shipped Catalan catalogue
already does for its sibling family; Hungarian follows its sibling block's
shape. No two locales share a value for any key.

The prior reading that this row was complete came from
`python -m dev.locales scaffold --check` reporting the catalogues ok. That
command measures PARITY, which held: all five keys existed in all four files.
It does not measure whether a value is real, and all twenty were the
placeholder. The gate that measures that is the translation-honesty ratchet,
and it was red naming these keys.

So the tree was carrying the exact state this row exists to prevent: five `tr`
keys live in source with no real value behind them in any language, and the
one command consulted reported ok.

## Verification

Before, per key and catalogue:

    cli.app.live.deudas.app_help  en=SELF-REFERENCING-PLACEHOLDER es=SELF-REFERENCING-PLACEHOLDER ca=SELF-REFERENCING-PLACEHOLDER hu=SELF-REFERENCING-PLACEHOLDER
    (and the same for latest_help, list_help, snapshot_id_help, view_help)
    failures: 25 across 5 keys x 4 catalogues

After:

    cli.app.live.deudas.app_help en=ok(31c) es=ok(40c) ca=ok(41c) hu=ok(43c)
    cli.app.live.deudas.latest_help en=ok(36c) es=ok(42c) ca=ok(39c) hu=ok(49c)
    cli.app.live.deudas.list_help en=ok(27c) es=ok(39c) ca=ok(37c) hu=ok(41c)
    cli.app.live.deudas.snapshot_id_help en=ok(35c) es=ok(38c) ca=ok(36c) hu=ok(47c)
    cli.app.live.deudas.view_help en=ok(65c) es=ok(65c) ca=ok(59c) hu=ok(75c)
    failures: 0 across 5 keys x 4 catalogues

The honesty ratchet's en-identical populations fell from 17 to 10 for Catalan,
17 to 10 for Hungarian, and 18 to 11 for Spanish. Those deltas are larger than
the five keys this row owns, so they are NOT claimed as this row's effect alone
— peers were writing the same catalogues concurrently. What IS this row's
measured effect is that no deudas key appears anywhere in the gate's output
afterwards, where five did before.

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_live_deudas_verbs.py -m integration -n0 -q
    8 passed in 6.97s

## Notes

One of the twenty writes failed on a Windows sharing violation during the
locales CLI's atomic replace of the Spanish catalogue, leaving that one key at
its placeholder while the run reported nineteen successes. It was caught by
re-running the per-key verification rather than by trusting the write log, and
retried. A write log is a record of calls attempted, not of state reached.

The catalogues were clean when checked immediately before the writes and
carried roughly 276 lines of a peer's Catalan ledger-counterparty content
afterwards, against 28 of this row's. Committing the files as they stood would
have taken that peer's in-flight work. The staged change was therefore built
from HEAD bytes with only the twenty placeholder lines replaced, verified
own-only by asserting every removal is a deudas placeholder line and every
addition sits on a deudas key line, staged with `git apply --cached`, and
committed from the index rather than by pathspec, which would have taken the
working tree back. The commit is exactly five changed lines in each of four
files.
