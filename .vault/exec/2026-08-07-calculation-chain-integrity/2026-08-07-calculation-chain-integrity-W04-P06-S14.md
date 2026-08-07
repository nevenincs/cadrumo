---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:50162d1ad2efad6941fd0320fc7567363a1862aaba34d2e90ffcb926b7164a39'
step_id: 'S14'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W04.P06.S14

## Outcome

Satisfied, and satisfied by NOT doing something: no competing record was opened. The `classify_iva` disposition attaches to question one of the existing ADR.

## Verified

`.vault/adr/` carries no record on `classify_iva`, the domestic-vs-not discriminator, or the rate-to-category derivation. `2026-08-06-llm-invoice-read-reconciliation-adr` question one — "the domestic-vs-not discriminator" — is the only place that decision lives, and it remains the right home:

> `iva_category` is load-bearing on the income path, and no CLI surface can set a domestic one, so every domestic invoice from every path is currently ungrounded.

## The disposition attaching to it

This campaign's work bears on question one in one concrete way, and it strengthens rather than changes the ruling: the mapping the question reasons from is now genuinely singular (`W04.P06.S30`), so whichever reading the operator picks acts on one object rather than one of three.

The question's three readings are untouched and remain the operator's:

- derive domesticity from `counterparty_country`, which defaults to `ES` and would silently claim domesticity for an unstated counterparty;
- require an explicit operator declaration, honest but a mandatory field on every invoice-creating surface;
- keep the category absent and treat the degradation as correct until an operator states it.

## Note on the second reading, from adjacent work

`W06.P08.S44` landed the same *shape* of answer for a narrower case: an entrega intracomunitaria must now state its Modelo 349 clave, because the category cannot separate E from M and H and only the operator holds the fact.

That is evidence about cost rather than an argument for reading two. It shows a mandatory declaration is tolerable when scoped to the one case where the ambiguity is real — S44 explicitly refused to demand the field for categories that determine their own clave. Whether question one's case is similarly narrow is the operator's call, not this record's; the reason S44 stayed narrow is offered because it is the part that made the requirement acceptable.

## Why `S15` stays open

`W04.P06.S15` is conditional on this ruling making the classifier wireable. The ruling has not been made, so the condition is unmet and the R13 clave fix is not attempted.
