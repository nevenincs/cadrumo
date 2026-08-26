---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:23fda6cd88cb1d7a04403b7699ed615f6e1cb6c79cbbda91393e7d874cc184e7'
step_id: 'S57'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Distinguish `ledger history` from `ledger track`, two verbs on one subject whose help described the same thing and one of which misdescribed its own output

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

The sharpest same-subject collision found in the hunting phase, and the earlier
enumeration scan missed it because that scan only compared `list`, `history`,
`runs`, `queue` and `backlog`. `track` was never in the candidate set.

Both verbs sit under `app ledger`, both take `transaction_id` positionally, and
both described themselves as emitting that transaction's events:
`history` as "the chronological bucket-event chain", `track` as "the event
lineage". Nothing told an operator which to reach for.

They are not duplicates. `history` reads the bucket-event chain -- what happened
TO the row. `track` returns `participated_in`, built from the
`TransactionRevisionParticipationIndex`, which is the rebuildable inverse index
from ledger rows to finalized revisions -- where the row WENT, into which modelo
revisions and filings.

So `track`'s help was not merely ambiguous, it was wrong: it promised events, and
the verb returns participations. Both strings now state what their verb uniquely
covers and name the sibling, following S37 and S47.

The split itself is worth keeping. Backward lifecycle and forward participation
are the two halves of a ledger row's audit trail, and the participation index
exists precisely so the forward half can be answered.
