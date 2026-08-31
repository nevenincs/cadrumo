---
tags:
  - '#exec'
  - '#cli-root-verb-homes'
date: '2026-08-26'
modified: '2026-08-26'
body_schema: 'body-v2'
body_hash: 'sha256:4c850646dadba3d4f0b2061c0e3c82474275aa45542b2bd27c7976a0f038631e'
step_id: 'S55'
related:
  - "[[2026-08-26-cli-root-verb-homes-plan]]"
---

# Examine the session, selection and reporting verb groups; record the criterion clearing each and the one borderline case worth naming

## Scope

- `src/cadrumo/entrypoints/cli/`

## Changes

- `verify:` `python -c "...COMMAND_GRAPH policy and family census..."` -> `no new conflation`

## Notes

No code changed.

**`login` / `logout` (3 each) are keyed on the counterparty, like the transport
verbs.** `config login` unlocks the local profile (`bootstrap-root`), `config
auth login` authenticates to the AEAT sede, `config google login` runs Google
OAuth. Three counterparties, three pairs, every login matched by its logout. The
symmetry is complete, which is what the campaign asked of the transport axis.

**`start` / `resume` / `status` on `config reset` is a lifecycle triple on one
subject**, not three names for one act. `app modelo work resume` shares only the
word; its subject is an interrupted work session.

**`select` (2) and `wizard` (2) are each used consistently.** `select` chooses
among candidates (a work unit, a certificate); `wizard` runs interactive
multi-step creation (an invoice, a work unit).

**Both `report` leaves are principled, for different reasons, and neither family
carries a `status` to choose against.** `config auth diagnostics report`
declares `write_route=profile-bound` -- it CREATES an encrypted diagnostic
record, so it is a creating verb naming the record it creates, sitting beside
`list` and `view` which read. `config provision report` is a computation verb:
it measures hardware, derives per-role model selection and admission. Neither is
the stored-state summary that the nine `status` leaves return.

**One borderline case, named rather than resolved.** `app ledger invoice`
carries both `add` (scripted) and `wizard` (interactive) for creating the same
record, and `wizard` names the mechanism rather than the record -- which is what
the contract's third verb category asks a creating verb not to do. It is not a
conflation, because the two are different interaction modes rather than two
names for one act, and the tree applies `wizard` consistently in both places
it appears. It is recorded here so a later reader knows it was seen and not
missed, and that `config profile create` is itself interactive, so the tree is
not uniform about whether an interactive creator takes the record's name or the
mechanism's.
