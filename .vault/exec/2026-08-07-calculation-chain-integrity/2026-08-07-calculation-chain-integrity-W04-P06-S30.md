---
tags:
  - '#exec'
  - '#calculation-chain-integrity'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:e1c0d8fa1293ab7755177a48720af9fde858819a1ba486b547472e78fbda8935'
step_id: 'S30'
related:
  - "[[2026-08-07-calculation-chain-integrity-plan]]"
---
# `calculation-chain-integrity` exec W04.P06.S30

## Outcome

**No correction was needed, because the premise became true.** The ADR is left untouched.

## What the Step objected to

Question one of `2026-08-06-llm-invoice-read-reconciliation-adr` reasons from:

> A closed rate-to-category mapping already exists, and the research records that it is already consumed for a different purpose

The Step's objection is that the singular was wrong: three such mappings existed, only one of which was the invoice-path mapping the ruling means, so an operator reading "a closed mapping" could not tell which one the decision would act on.

## Why it no longer holds

`W06.P08.S28` collapsed those three onto one canonical declaration. Confirmed at HEAD: exactly one file declares a rate-tier to `DOMESTIC_*` mapping (`domain/iva/_classification.py`, five entries), and both former copies — the invoice-path one in `_invoice_classification.py` and the aggregation one in `_iva_ledger.py` — now read it through `domestic_categories_by_rate_kind()`.

So the ADR's singular is now accurate, and the ambiguity the Step names has no referent. The invoice-path mapping and "the closed mapping" are the same object.

## Why the ADR was not edited anyway

Editing a pending ruling to add "and by the way there used to be three of these" would put a resolved historical ambiguity in front of the operator at the moment they are deciding something else. The correction the Step asked for was to stop the premise misleading; making the premise true does that more completely than annotating it.

It also avoids a foreign edit: this ADR belongs to `llm-invoice-read-reconciliation` and is awaiting an operator ruling. Touching a record in that state should clear a real obstacle, and there is no longer one.

## What a reader should take from this

The ordering was lucky rather than planned. Had the ADR been ruled on before `S28` landed, the operator would have decided against an ambiguous premise. That the fix arrived first is worth noting for the next pending ruling that leans on a "single canonical X" claim — the claim is worth verifying at HEAD before the ruling, not after.
