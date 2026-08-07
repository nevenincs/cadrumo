---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:124132adf0e41c1799d12c90b50bbf92e809eaa4b86136c3fd1f03d2dc28f9d1'
step_id: 'S44'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W06.P08.S44

## Outcome

Landed in `b76abcb70d`. Recorded here late: the Step was checked without an execution record, which `vault plan status` flagged at closure. The record is written from the commit and the code at HEAD rather than from memory of the session.

## The ambiguity, and why no screen could close it

Three Modelo 349 claves all carry `IvaCategory.INTRA_COMMUNITY_SUPPLY`:

- `E` — an ordinary entrega intracomunitaria
- `M` — a supply following an exempt importation (LIVA art. 27.12)
- `H` — the same, made through a fiscal representative

No predicate over the category, the counterparty, the amount or the dates separates them. The distinguishing fact is what the underlying operation *was*, and that lives with the operator or nowhere.

## Why the requirement sits at creation

The alternative shape — infer a clave at calculate time and screen the ambiguity downstream — fails on timing rather than on logic. At creation the operator is looking at the document and knows which of the three it is. At calculate time nobody is: the invoice is one row among many, weeks later, and the person who could answer has moved on.

So the refusal is placed where the answer exists. `_require_operation_type_where_the_category_cannot_settle_it` raises on an intra-community supply carrying no `operation_type`, and the message names all three claves and says why the category cannot settle it, rather than reporting a missing field.

## The scope discipline that made it acceptable

`_CATEGORY_NEEDING_AN_EXPLICIT_CLAVE` is a single member, not a set. The requirement fires for exactly the one category where the ambiguity is real, and every category that determines its own clave is left alone — an intra-community acquisition, a service supply, a domestic operation all continue to need nothing extra.

That narrowness is what makes a mandatory declaration tolerable. A blanket "state your clave" would tax every operator for a case almost none of them are in.

## Where it was cited afterwards

`W04.P06.S14` used this as evidence about cost rather than as an argument: it shows a mandatory operator declaration is bearable when scoped to the one case the ambiguity is real, which is the shape the open ruling on question one would have to take if it went that way. The ruling remains the operator's, and this Step does not pre-empt it.
