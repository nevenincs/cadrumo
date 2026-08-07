---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:7a02ff62706e20237dc5156382b2a062949685a4d17c27bc9969aa93a636bd9e'
step_id: 'S45'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W01.P01.S45

## Outcome

The superseding ADR this Step calls for **already exists**, authored by a peer as `2026-08-07-calculation-chain-integrity-binding-output-casilla-declaration-adr`, status `proposed`.

No second record was opened. Opening one would have produced exactly the duplicate decision record this campaign's sweep phase exists to find.

## What it covers, and what it correctly does not

The Step asks for an ADR "if the registry should declare where an aggregate lands". The existing record scopes that question more precisely than the Step wording does, and the narrowing is right:

> `2026-08-07-calculation-chain-integrity-adr` ruled `W01` on T-05's established pattern... That ruling stands and is shipped — this record does not reopen it. What it does raise is a question `T-05` itself never answers, because the T-05 inventory was scoped to hardcoded casilla MAPS living entirely outside the registry, not to a registry SELECTOR SCHEMA that may be structurally unable to express a fact at all.

So the M130 case is settled by the T-05 remedy and is not re-litigated. The open question is the structural one: whether a `ledger_iva_aggregation`-style binding can ever declare "match these observations, report on a different casilla", and whether being structurally unable to express that is a gap worth closing.

That distinction is what makes `S02` and `S03` refuted as written rather than merely deferred. The ruling ADR settled the M130 case the other way, and this open ADR deliberately does not reopen it.

## Cross-reference

The sweep phase reached the same surface independently, from the other direction. `W06.P08.S25` found the IVA clave-to-category correspondence expressed in three places across two directions, and noted the same inability of the IVA families to express a match-versus-output divergence. Arrived at by meaning-search rather than design review, that is corroboration rather than duplication.

## Note for whoever advances the ADR

Its own file is the one carrying a **staged deletion in the shared index while alive on disk** (9997 bytes, committed at `b79ea00ec4`). A no-pathspec commit would delete the record that closes this Step. Flagged here because the hazard is invisible from the plan.
