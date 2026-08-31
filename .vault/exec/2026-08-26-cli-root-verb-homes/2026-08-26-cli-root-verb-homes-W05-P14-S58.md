---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:8f4b7a6c9dabea2c60732cf1d4ff623a55d0c69c60f8ff427ef9480b4f02288d'
step_id: 'S58'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Re-run the same-subject scan over every leaf and give the ledger lifecycle verbs help that says which state they move a row into and which one deletes

## Scope

- `src/cadrumo/locales/`

## Changes

- `M` `src/cadrumo/locales/en/cli.yml`
- `M` `src/cadrumo/locales/es/cli.yml`
- `M` `src/cadrumo/locales/ca/cli.yml`
- `M` `src/cadrumo/locales/hu/cli.yml`
- `verify:` `python -m dev.locales scaffold --check` -> `ok in all four`
- `verify:` `pytest four campaign gates` -> `22 passed`

## Notes

The scan S57 asked for was run properly this time: group EVERY leaf by subject,
group those by positional signature, and flag any subject where two leaves share
one. Twenty-one subjects do. Most are ordinary CRUD -- `view`, `update`,
`remove` on one id is not a conflation -- but `app ledger` carries fifteen leaves
on `transaction_id`, and five of them could each be read as "make this row stop
counting": `archive`, `stash`, `exclude`, `remove`, `restore`.

They are all principled, on three separate axes. `archive` and `stash` are
lifecycle states, `exclude` is a review status (excluded from filing), `remove`
deletes, `restore` returns to active from either non-active state. The
distinction between the two lifecycle states is written out in full in
`TransactionLifecycleState`: ARCHIVED is "removed from default attention without
deleting", STASHED is "parked pending classification or review", and both are
reversible. The code even enforces the ordering -- `archived -> stashed` is
refused, because stash is the undecided state and archive is the decided one.

None of that reached the operator. `archive` said "Archive one ledger
transaction", `stash` said "Stash one ledger transaction" -- help that restates
the verb and answers nothing. The most serious case was `remove`, whose "Remove
one ledger transaction from the active profile" reads almost identically to
archive's documented "remove the row from default attention", while `remove` is
the only one of the five that actually deletes.

All four now state the state they move the row into, name `restore` as the way
back, and `remove` says plainly that it deletes and points at `archive` for the
non-deleting alternative.

A second finding from the same reading is raised separately as S59, and one
smaller inconsistency is recorded here rather than changed: `config profile`
spells its subject `profile_name` on `create`/`edit` and `name` on
`delete`/`validate`/`view`, two names for one thing inside one family.
