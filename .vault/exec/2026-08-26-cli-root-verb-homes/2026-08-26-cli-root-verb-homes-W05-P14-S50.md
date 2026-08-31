---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:b888a62917160431751362e1e59b8d59ed7bfe13e0fba65a1cd56e471ffe50c0'
step_id: 'S50'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Examine the assurance and enumeration verb families and record the criterion each satisfies

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `python -c "...COMMAND_GRAPH same-subject clash scan..."` -> `verify/validate/check clean; list/history clash on four subjects, one of which is a real finding (S51)`

## Notes

No code changed. Two families examined, each reduced to a criterion a later
reader can re-run rather than re-argue.

**`verify` (7) / `validate` (3) / `check` (6) is principled by construction.**
The reading that separates them is the kind of authority each appeals to:
`verify` checks against an external or cryptographic authority (a signature, the
registry corpus, AEAT filing expectations, workbook parity); `validate` checks
against a declared schema or constraint (profile facts, an M145 record, ratios);
`check` checks whether a resource is healthy and usable (storage, a certificate,
config, a ledger before calculation, an audit bundle's digests).

That reading is soft on its own, so it was replaced by a hard test: **does any
subject carry two of the three?** None does. Sixteen leaves, sixteen subjects,
no subject offering a choice between them. An operator therefore never has to
decide which of the three applies to the thing in front of them, which is the
only place a synonym split can actually cost anything.

**`list` (33) versus `history` (7): collection versus one subject's event
chain.** The hard test here is the subject argument. Zero of the 33 `list`
leaves take a subject argument -- the criterion holds without exception on that
side. On the `history` side, three take a required subject id (`app ledger
history` a transaction, `app modelo work history` a work unit, `config profile
history` a profile, the last optional and defaulting to the active one), and
three more address an implicit singleton scoped by coordinates (`app live
iva-wallet history` by year, `app modelo history` by modelo/year/period, `app
live notifications document history`).

The seventh, `app modelo reconcile history`, does not fit either side and is
raised separately as S51.

`runs` was checked in passing: `app modelo work` carries `list`, `history` and
`runs`, and they return three different entity types -- work units, lifecycle
events, and persisted workflow runs. Not a three-way split of one question.
