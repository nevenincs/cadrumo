---
tags:
  - '#exec'
  - '#ledger-invoice-decomposition'
date: '2026-08-06'
modified: '2026-08-06'
body_schema: 'body-v1'
body_hash: 'sha256:ef9e21c19211c39582d36429dd162c9e72333b44807c84de0677342e702fb99d'
step_id: 'S48'
related:
  - "[[2026-08-05-ledger-invoice-decomposition-plan]]"
---
# Thread the operation date into period attribution with a declared rank marker naming which source produced it, surfaced identically on the pull and calculate paths

## Scope

- `src/cadrumo/application/aggregation`

## Description

- Replace the bare-date `invoice_devengo_date` with `resolve_invoice_devengo`, returning a frozen `InvoiceDevengo` carrying the resolved date AND the `InvoiceDevengoRank` marker naming which source produced it.
- Declare `InvoiceDevengoRank` in `core` beside the income-measure grounding marker, with two members: the recorded operation date, and the issue date standing in for it.
- Add `invoice_devengo_in_period` as the single period-attribution predicate for the invoice catalogue, and route the Modelo 303 domestic-IVA screen and the Modelo 369 OSS projection through it instead of each comparing the issue date.
- Carry the resolved devengo date onto the projected observation and candidate, so the record states the date it was selected on.
- Emit one non-blocking advisory, built by one shared builder consumed by both resolvers, naming the invoices whose period placement rested on the proxy.
- Add `--operation-date` to `aeat app ledger invoice catalogue create` and thread it through the creation service, so the advisory's remedy is an action the operator can actually take.

## Outcome

Period attribution now resolves on the LIVA art. 75 devengo date. An operation performed on 28 March and lawfully invoiced on 10 April (RD 1619/2012 art. 11 allows the delay) is declared in Q1, where the cuota devengó, rather than in Q2 where the invoice happens to carry a date. Both quarters are asserted, because a change that simply moved every invoice one quarter earlier would satisfy the Q1 half alone.

The rank is the part that makes the fallback safe to have. A chain that returns a bare date collapses a declared legal fact and a substitute for one into one indistinguishable return, and the substitute agrees with the fact for every operation invoiced inside its own period — diverging exactly at the boundaries where attribution changes. The marker is a closed value set in `core`, so consumers branch on the member rather than re-deriving the distinction from a null.

D10 names a third rank, the bank movement date. It is deliberately NOT a member: an invoice always carries an issue date, so the invoice-side chain terminates at the proxy and can never reach a movement date. That substitution belongs to the ledger-transaction side, whose dates already have their own owners. A member no producer on this axis can emit would be dead capacity wearing the shape of coverage.

A measurement changed the shape of this Step. No CLI surface could set an invoice's operation date, so the advisory would have fired on every invoice forever while instructing the operator to do something no command offered. Mutation-proving tests the guard; it does not test the operator's route to compliance. The verb now accepts the date and a round-trip through the real encrypted repository proves it reaches a declared rank. The art. 75.Dos pago-anticipado role remains unreachable from any surface — it carries preconditions an operator-supplied date cannot assert — and is reported rather than faked.

Both paths share one predicate and one advisory builder, so the calculate surface and any pull surface cannot answer the attribution question differently: there is one implementation and every consumer calls it.

## Verification

Behaviour of the resolution, the rank, the attribution and the advisory bound:

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_invoice_devengo.py -q --no-header -p no:randomly
    9 passed in 7.91s

Attribution and both advisory directions on the real Modelo 303 resolve path, with a real encrypted invoice repository:

    uv run --no-sync pytest src/cadrumo/application/aggregation/tests/test_modelo_source_mesh_ledger.py -q --no-header
    16 passed in 33.36s

Same on the live Modelo 369 OSS path:

    uv run --no-sync pytest src/cadrumo/application/modelo/tests/test_dormant_m369_oss_resolver_live.py -q --no-header
    6 passed in 44.57s

Operator route from the creation service to a declared rank, round-tripped through the real repository:

    uv run --no-sync pytest src/cadrumo/application/invoices/tests/test_creation.py -q --no-header --tb=short -m integration
    15 passed in 11.26s

Regression sweep across the three affected packages:

    uv run --no-sync pytest src/cadrumo/application/invoices src/cadrumo/application/aggregation src/cadrumo/domain/invoices -q --no-header --tb=line -m "unit or integration"
    991 passed, 6 warnings in 274.02s (0:04:34)

Three mutations, each reverted after measuring:

- Attribution reverted to the issue date: 2 failed, 23 passed — the two boundary-case regressions, one on the helper and one on the real Modelo 303 path.
- Every invoice ranked as a declared fact (the advisory goes silent): 5 failed, 20 passed.
- Every invoice ranked as a proxy (the advisory fires on a clean catalogue): 7 failed, 18 passed.

Both directions redden, so the advisory is proved to fire when it should and stay silent when it should not.

## Notes

The pydantic model failed to instantiate at first because its `date` annotation sat under `TYPE_CHECKING`. Lint and import both passed while every construction raised, which is the recurring shape: structural introspection is upstream of behaviour, and neither of the two cheap checks touches it.

The advisory names invoices by their number rather than by the content-addressed id every other diagnostic on that surface carries. The remedy asks the operator to open each record, and the number is what the catalogue listing shows them; a 64-hex digest would also exhaust the bounded message field after two entries and silently elide the rest of the sample, including the notice that the sample was incomplete.

One pre-existing test asserted the Modelo 303 resolve path emitted no diagnostics at all. Its fixture records no operation date, so the advisory is correct there; the assertion was replaced with the specific advisory plus a new paired test whose fixture records the date and asserts silence.

Reported and not fixed here: the creation service does not derive `iva_category` from `operation_type` while the CLI does, so a caller reaching the service directly produces a differently-shaped record than the operator path does.
